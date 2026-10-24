"""Trusted, read-only SQLite artifact checker. Exit codes: 0 pass, 1 fail, 2 infrastructure."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def check(root, application_path, checkpoint_path):
    checks=[]
    def add(name,passed,detail):
        checks.append({"name":name,"passed":bool(passed),"detail":detail})
    if not application_path.is_file() or not checkpoint_path.is_file():
        return {"status":"failed","checks":[{"name":"required_files","passed":False,"detail":"Application and checkpoint databases are required."}]}
    people={row['employee_id']:row for row in read_jsonl(root/'Day4_Datasets/01_HR/people.jsonl')}
    policies=read_jsonl(root/'Day4_Datasets/01_HR/department_context.jsonl')
    db=sqlite3.connect(application_path.resolve().as_uri()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    try:
        def exact_unique_key(table,column):
            info=list(db.execute('PRAGMA table_info('+table+')'))
            primary=[row['name'] for row in sorted(info,key=lambda row:row['pk']) if row['pk']]
            if primary==[column]:return True
            for index in db.execute('PRAGMA index_list('+table+')'):
                if index['unique'] and not index['partial']:
                    index_name=index['name'].replace('"','""')
                    columns=[row['name'] for row in db.execute('PRAGMA index_info("'+index_name+'")')]
                    if columns==[column]:return True
            return False
        add("connection",db.execute("SELECT 1").fetchone()[0]==1,"Real read-only SQLite connection.")
        add("integrity",db.execute("PRAGMA integrity_check").fetchone()[0]=='ok',"SQLite integrity check.")
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected={'memories','profiles','approvals','writes','audit','jobs'}
        add("tables",expected<=tables,"Six application tables are required.")
        if not expected<=tables:
            return {"status":"failed","checks":checks}
        fks=list(db.execute("PRAGMA foreign_key_list(writes)"))
        add("approval_foreign_key",any(row['table']=='approvals' and row['from']=='approval_id' and row['to']=='approval_id' for row in fks),"writes.approval_id must reference approvals.approval_id.")
        add("foreign_key_integrity",not list(db.execute("PRAGMA foreign_key_check")),"No orphan foreign keys.")
        profiles=[dict(row) for row in db.execute("SELECT * FROM profiles")]
        def valid_scope(row):
            person=people.get(row['employee_id'])
            return person is not None and person['tenant']==row['tenant']
        add("profile_scope",bool(profiles) and all(valid_scope(row) and type(row['version']) is int and row['version']>0 for row in profiles),"Profiles must belong to real synthetic employees in the same tenant.")
        grounded=True
        for row in profiles:
            value=json.loads(row['payload']);person=people.get(row['employee_id'])
            required={'employee_id','department','claims','limitations','decision'}
            if (not isinstance(value,dict) or set(value)!=required
                or type(value.get('employee_id')) is not str or type(value.get('department')) is not str
                or not isinstance(value.get('limitations'),list) or not all(type(item) is str for item in value['limitations'])):
                grounded=False
                continue
            if person is None:
                grounded=False;continue
            policy=next(p for p in policies if p['tenant']==person['tenant'] and p['department']==person['department'])
            evidence={e['evidence_id']:e for e in person['evidence'] if e['verified']}
            if value.get('employee_id')!=row['employee_id'] or value.get('department')!=person['department'] or value.get('decision')!='skills_inventory_only':
                grounded=False
            claims=value.get('claims',[])
            if not isinstance(claims,list):
                grounded=False;continue
            seen=set()
            for claim in claims:
                if not isinstance(claim,dict) or set(claim)!={'skill','evidence_id','quote'} or not all(type(item) is str and item for item in claim.values()):
                    grounded=False
                    continue
                source=evidence.get(claim.get('evidence_id'))
                if not source or claim.get('skill')!=source['skill'] or claim.get('quote')!=source['text'] or claim.get('skill') not in policy['required_skills'] or claim.get('evidence_id') in seen:
                    grounded=False
                seen.add(claim.get('evidence_id'))
        add("grounding",bool(profiles) and grounded,"Claims are rechecked independently against source evidence.")
        approvals={row['approval_id']:dict(row) for row in db.execute("SELECT * FROM approvals")}
        add("approval_rows",bool(approvals) and all(valid_scope(row) and row['approved'] in (0,1) and isinstance(row['reviewer'],str) and row['reviewer'].strip() and isinstance(row['base_version'],int) and row['base_version']>=0 and len(row['payload_hash'])==64 for row in approvals.values()),"Approval records require a reviewer, scope, version and payload hash.")
        writes=[dict(row) for row in db.execute("SELECT * FROM writes")]
        profile_map={(row['tenant'],row['employee_id']):row for row in profiles}
        linked=True
        for row in writes:
            approval=approvals.get(row['approval_id']);profile=profile_map.get((row['tenant'],row['employee_id']))
            if approval is None or profile is None:
                linked=False;continue
            body_hash=hashlib.sha256(canonical(json.loads(profile['payload'])).encode()).hexdigest()
            linked &= bool(approval['approved']==1 and approval['tenant']==row['tenant'] and approval['employee_id']==row['employee_id'] and approval['payload_hash']==row['payload_hash'] and approval['base_version']==row['version']-1 and profile['version']>=row['version'])
            if profile['version']==row['version']:
                linked &= row['payload_hash']==body_hash
        add("write_approval_binding",bool(writes) and linked,"Every committed write is bound to an approved body, employee, tenant and base version.")
        write_keys=[row['idempotency_key'] for row in writes]
        valid_write_keys=all(type(key) is str and key.strip() and len(key)<=200 for key in write_keys)
        add("idempotency_constraint",exact_unique_key('writes','idempotency_key') and valid_write_keys and len(write_keys)==len(set(write_keys)),"A nonempty idempotency key must be unique on its own, not merely part of a composite key.")
        audit=[dict(row) for row in db.execute("SELECT * FROM audit")]
        expected_audit=sorted((row['tenant'],row['employee_id'],row['version']) for row in writes)
        actual_audit=sorted((row['tenant'],row['employee_id'],row['version']) for row in audit if row['action']=='profile_committed')
        add("audit_matches_writes",bool(writes) and expected_audit==actual_audit,"Exactly one commit audit per committed version.")
        memories=[dict(row) for row in db.execute("SELECT * FROM memories")]
        memory_ok=bool(memories)
        for row in memories:
            person=people.get(row['employee_id']);source=None if person is None else next((e for e in person['evidence'] if e['evidence_id']==row['evidence_id'] and e['verified']),None)
            memory_ok &= bool(valid_scope(row) and source is not None and source['text']==row['text'] and type(row['expires_day']) is int and row['expires_day']>=0)
        add("memory_provenance",memory_ok,"At least one verified, scoped memory with a valid expiry.")
        jobs=[dict(row) for row in db.execute("SELECT * FROM jobs")]
        job_keys=[row['event_key'] for row in jobs]
        valid_jobs=all(type(row['event_key']) is str and row['event_key'].strip() and len(row['event_key'])<=200 and row['status'] in {'received','completed','failed'} for row in jobs)
        add("durable_jobs",bool(jobs) and valid_jobs and exact_unique_key('jobs','event_key') and len(job_keys)==len(set(job_keys)),"Durable event keys must be nonempty and have a real single-column uniqueness constraint.")
    finally:
        db.close()
    checkpoint=sqlite3.connect(checkpoint_path.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        tables={row[0] for row in checkpoint.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        durable=False
        if 'checkpoints' in tables:
            columns={row[1] for row in checkpoint.execute("PRAGMA table_info(checkpoints)")}
            if {'thread_id','checkpoint_id','checkpoint','metadata'}<=columns:
                durable=checkpoint.execute("SELECT COUNT(*) FROM checkpoints WHERE length(checkpoint)>0").fetchone()[0]>0
        add("persistent_checkpoint",durable,"Nonempty LangGraph checkpoints are stored in a separate SQLite database.")
    finally:
        checkpoint.close()
    return {"status":"passed" if all(row['passed'] for row in checks) else "failed","checks":checks,
            "proof":"grader must execute its own trusted copy; student report alone is not proof"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--application-db',type=Path,required=True)
    parser.add_argument('--checkpoint-db',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        report=check(args.root,args.application_db,args.checkpoint_db)
    except (sqlite3.DatabaseError,ValueError,KeyError,TypeError) as error:
        report={"status":"failed","checks":[],"error_type":type(error).__name__}
    except (OSError,ImportError) as error:
        report={"status":"infrastructure_error","checks":[],"error_type":type(error).__name__}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({"status":report['status'],"checks":len(report['checks'])}))
    return {'passed':0,'failed':1,'infrastructure_error':2}[report['status']]

if __name__=='__main__':
    sys.exit(main())

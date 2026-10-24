"""Trusted read-only structural checker. Never execute submitted code."""
from pathlib import Path
import argparse
import json
import math
import sqlite3
import sys
import numpy as np

REVISION='9217f5db79a29953eb74d5343926648285ec7e67'
MODEL_HASHES={'qwen2.5-0.5b-instruct-q4_k_m.gguf':'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db',
 'qwen2.5-0.5b-instruct-q8_0.gguf':'ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e'}
REQUIRED_ARTIFACTS={'selection.json','runtime_config.json','test_predictions.jsonl','selected_adapter.npz','adapter_selection.json','adapter_test_predictions.npy','quantization_selection.json','quant_test_predictions.npy','local_agent.sqlite','agent_trace.json','security_tests.json'}
def strict_json(text):
    def pairs(items):
        obj={}
        for key,value in items:
            if key in obj:raise ValueError('Duplicate JSON key.')
            obj[key]=value
        return obj
    def finite_float(text):
        value=float(text)
        if not math.isfinite(value):raise ValueError('Nonfinite JSON number.')
        return value
    return json.loads(text,object_pairs_hook=pairs,parse_float=finite_float,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('Nonfinite JSON.')))

def run(submission,datasets):
    root=Path(submission).resolve();data=Path(datasets).resolve();checks=[]
    def check(name,fn):
        try:
            value=fn()
            checks.append({'name':name,'passed':value is True,'detail':'ok' if value is True else str(value)[:300]})
        except Exception as exc:checks.append({'name':name,'passed':False,'detail':type(exc).__name__+': '+str(exc)[:240]})
    def path(name):
        p=(root/name).resolve()
        if p.parent!=root or p.is_symlink():raise ValueError('Artifact path outside submission root.')
        if p.stat().st_size>20*2**20:raise ValueError('Oversized grading artifact.')
        return p
    def read(name):return strict_json(path(name).read_text(encoding='utf-8'))
    def jl(p):return [strict_json(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    selection=read('selection.json');config=read('runtime_config.json');preds=jl(path('test_predictions.jsonl'))
    cases=jl(data/'local_eval_test.jsonl');ids=[r['case_id'] for r in cases];pid=[r['case_id'] for r in preds]
    check('selection_is_dev_only',lambda:selection['selection_split']=='dev' and selection['test_used_for_selection'] is False)
    check('pinned_model_revision',lambda:selection['model_revision']==REVISION and selection['selected_quant'] in ['q4_k_m','q8_0'])
    check('pinned_model_hashes',lambda:selection['hashes']==MODEL_HASHES)
    check('runtime_configuration',lambda:config['engine']=='llama.cpp' and config['context']==2048 and config['threads']==4 and config['network']=='loopback')
    check('complete_unique_prediction_ids',lambda:len(pid)==len(set(pid))==len(ids) and set(pid)==set(ids))
    def prediction_contract():
        languages={r['case_id']:r['language'] for r in cases}
        for row in preds:
            value=row['predicted_days']
            if value is not None and (type(value) is not int or not 0<=value<=366):return False
            if row['quant']!=selection['selected_quant'] or row['split']!='test' or any(k in row for k in ['expected_days','correct']):return False
            if not isinstance(row['raw'],str) or len(row['raw'])>10000:return False
            if row['language']!=languages.get(row['case_id']) or row['finish_reason'] not in ('stop','length'):return False
            if type(row['elapsed_s']) not in (int,float) or not math.isfinite(row['elapsed_s']) or row['elapsed_s']<=0:return False
            if type(row['prompt_tokens']) is not int or row['prompt_tokens']<=0 or type(row['completion_tokens']) is not int or row['completion_tokens']<0:return False
            try:
                raw=strict_json(row['raw']);valid=isinstance(raw,dict) and set(raw)=={'days'} and type(raw['days']) is int and 0<=raw['days']<=366
            except (ValueError,TypeError):valid=False
            if row['schema_valid'] is not valid or (raw['days'] if valid else None)!=value:return False
        return True
    check('prediction_values_match_raw',prediction_contract)
    adapter=np.load(path('selected_adapter.npz'),allow_pickle=False)
    a=np.asarray(adapter['a']);b=np.asarray(adapter['b']);scale=float(adapter['scale'])
    adapter_selection=read('adapter_selection.json');rank=adapter_selection['rank']
    check('adapter_schema_and_freeze',lambda:type(rank) is int and rank in [1,2,4] and a.shape==(16,rank) and b.shape==(rank,8) and np.isfinite(a).all().item() and np.isfinite(b).all().item() and math.isfinite(scale) and scale==2/rank and adapter_selection['base_frozen'] is True and adapter_selection['selection_split']=='dev')
    adapter_data=np.load(data/'adapter_lab.npz',allow_pickle=False)
    expected=adapter_data['test_x']@(adapter_data['base_weight']+scale*a@b)
    supplied=np.load(path('adapter_test_predictions.npy'),allow_pickle=False)
    check('adapter_predictions_recomputed',lambda:supplied.shape==(128,8) and bool(np.isfinite(supplied).all()) and bool(np.allclose(supplied,expected,atol=1e-5,rtol=1e-5)))
    quant_selection=read('quantization_selection.json')
    check('quantization_selection_contract',lambda:quant_selection['bits']==4 and quant_selection['group_size']==16 and quant_selection['percentile'] in [100,99,95] and quant_selection['selection_split']=='dev' and quant_selection['toy_not_gguf'] is True)
    qpred=np.load(path('quant_test_predictions.npy'),allow_pickle=False)
    check('quantization_prediction_shape',lambda:qpred.shape==(96,96) and bool(np.isfinite(qpred).all()))
    # Recompute the toy quantizer independently, without importing student modules.
    qdata=np.load(data/'quantization_lab.npz',allow_pickle=False);w=qdata['weights'];blocks=w.reshape(96,3,16)
    bounds=np.percentile(abs(blocks),quant_selection['percentile'],axis=2,keepdims=True)
    scales=np.where(bounds>0,bounds/7,1).astype('float32')
    reconstructed=(np.clip(np.rint(blocks/scales),-7,7)*scales).reshape(96,48)
    check('quantization_predictions_recomputed',lambda:bool(np.allclose(qpred,qdata['test']@reconstructed.T,atol=1e-5,rtol=1e-5)))
    db_path=path('local_agent.sqlite')
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True,timeout=3) as db:
        db.execute('PRAGMA query_only=ON')
        check('sqlite_integrity',lambda:db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        columns=db.execute('PRAGMA table_info(runs)').fetchall()
        required={'run_id':'TEXT','quant':'TEXT','days':'INTEGER','policy_id':'TEXT','approved':'INTEGER'}
        check('sqlite_required_columns',lambda:{r[1]:r[2].upper() for r in columns}==required and all(r[3]==1 for r in columns))
        def unique_key():
            for index in db.execute('PRAGMA index_list(runs)').fetchall():
                if index[2]==1 and index[4]==0 and [r[2] for r in db.execute('PRAGMA index_info('+json.dumps(index[1])+')')]==['run_id']:return True
            return False
        check('run_id_single_column_unique',unique_key)
        def constraint_probes():
            if db.execute("SELECT count(*) FROM sqlite_schema WHERE type='trigger'").fetchone()[0]:return False
            with sqlite3.connect(':memory:') as probe:
                db.backup(probe)
                probe.execute('PRAGMA trusted_schema=OFF')
                values=[('',22,0),(' ',22,0),(None,22,0),('__probe-low',-1,0),('__probe-high',367,0),('__probe-approve',22,1)]
                for run_id,days,approved in values:
                    probe.execute('SAVEPOINT constraint_test')
                    rejected=False
                    try:probe.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run_id,selection['selected_quant'],days,'P-LEAVE',approved))
                    except sqlite3.IntegrityError:rejected=True
                    finally:probe.execute('ROLLBACK TO constraint_test');probe.execute('RELEASE constraint_test')
                    if not rejected:return False
            return True
        check('sqlite_constraints_enforced_in_memory',constraint_probes)
        stored=db.execute('SELECT run_id,quant,days,policy_id,approved FROM runs').fetchall()
        check('no_invalid_or_duplicate_rows',lambda:len(stored)==len({r[0] for r in stored}) and all(isinstance(r[0],str) and bool(r[0].strip()) and r[1]==selection['selected_quant'] and type(r[2]) is int and r[2]==22 and r[3]=='P-LEAVE' and r[4]==0 for r in stored))
    trace=read('agent_trace.json');manifest=read('handoff_manifest.json')
    check('bounded_trace',lambda:isinstance(trace,list) and len(trace)==3 and [r['step'] for r in trace]==[1,2,3] and trace[0]['kind']=='model_plan' and trace[-1]['kind']=='model_extract')
    def action_contract():
        accepted=trace[0]['accepted']
        if type(accepted) is not bool:return False
        if accepted:return trace[0]['plan']=={'action':'get_policy','policy_id':'P-LEAVE'} and trace[1]['kind']=='readonly_tool' and trace[1]['policy_id']=='P-LEAVE'
        return trace[1]['kind']=='stop' and trace[-1]['days'] is None and trace[-1]['grounded'] is False
    check('trace_action_contract',action_contract)
    check('grounding_and_persistence_consistent',lambda:type(manifest['grounded']) is bool and manifest['grounded']==trace[-1]['grounded'] and ((manifest['grounded'] and len(stored)==1 and manifest['days']==22 and trace[-1]['days']==22 and trace[1]['kind']=='readonly_tool' and trace[1]['policy_id']=='P-LEAVE') or (not manifest['grounded'] and len(stored)==0)))
    def handoff_integrity():
        import hashlib
        if manifest['assignment']!='day5' or manifest['selected_quant']!=selection['selected_quant'] or manifest['days']!=trace[-1]['days']:return False
        entries=manifest['files'];names=[r['path'] for r in entries]
        if len(names)!=len(set(names)) or set(names)!=REQUIRED_ARTIFACTS:return False
        for entry in entries:
            with path(entry['path']).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if entry['sha256']!=actual:return False
        return True
    check('handoff_manifest_integrity',handoff_integrity)
    security=read('security_tests.json')
    check('security_evidence_contract',lambda:security['cross_tenant_injection_blocked'] is True and security['unknown_tool_and_extra_args_rejected'] is True and security['model_injection_immunity_claim'] is False)
    return {'passed':all(r['passed'] for r in checks),'checks':checks,'limitations':['No submitted code is executed.','This checker validates artifact consistency, not proof of actual inference.','Instructor reruns in an isolated environment and scores reasoning separately.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--datasets',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:report=run(a.submission,a.datasets)
    except Exception as exc:report={'passed':False,'checks':[{'name':'input_contract','passed':False,'detail':type(exc).__name__+': '+str(exc)[:300]}]}
    Path(a.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"Checks passed: {sum(c['passed'] for c in report['checks'])}/{len(report['checks'])}")
    sys.exit(0 if report['passed'] else 1)

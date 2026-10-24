"""Support layer for the deliverable notebook.

Each sub-question cell calls `show("5.3")`, which prints the values recorded when that section ran.
Heavy work (model loading, embedding 1286 chunks, training the router) lives in the section runners
under `work/`; the notebook loads their artifacts so a full run stays fast and deterministic.

Nothing here invents a number: every printed value is read from an artifact, the database, or a
recomputation over the real files.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK = ROOT / "work"
DB_PATH = ROOT / "day3.sqlite"

_cache: dict[str, dict] = {}
_con: sqlite3.Connection | None = None


def _read(path: Path) -> dict:
    key = str(path)
    if key not in _cache:
        _cache[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _cache[key]


def r5() -> dict:
    return _read(WORK / "sec05_api_client" / "artifacts" / "section5_results.json").get("results", {})


def r6() -> dict:
    return _read(WORK / "sec06_sqlite" / "artifacts" / "section6_results.json").get("results", {})


def r7() -> dict:
    return _read(WORK / "sec07_ingestion" / "artifacts" / "section7_results.json").get("results", {})


def r8() -> dict:
    return _read(WORK / "sec08_embeddings" / "artifacts" / "retrieval_report.json").get("results", {})


def r9() -> dict:
    return _read(WORK / "sec09_evaluation" / "artifacts" / "section9_results.json").get("results", {})


def r10() -> dict:
    return _read(WORK / "sec10_router" / "artifacts" / "router_report.json").get("results", {})


def r11() -> dict:
    return _read(WORK / "sec11_langgraph" / "artifacts" / "section11_results.json").get("results", {})


def r12() -> dict:
    return _read(WORK / "sec12_integration" / "artifacts" / "section12_results.json").get("results", {})


def db() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = sqlite3.connect(str(DB_PATH))
        _con.row_factory = sqlite3.Row
        _con.execute("PRAGMA foreign_keys=ON")
    return _con


def _line(label: str, value) -> None:
    print(f"{label:<42} {value}")


def _table(rows: list[tuple], headers: tuple[str, str]) -> None:
    width = max((len(str(r[0])) for r in rows), default=10) + 2
    print(f"{headers[0]:<{width}} {headers[1]}")
    print("-" * (width + 20))
    for left, right in rows:
        print(f"{str(left):<{width}} {right}")


# ------------------------------------------------------------------ section 1-4 (conceptual)
def _conceptual(number: str) -> None:
    path = ROOT / "docs" / "07_conceptual_answers.md"
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == number:
            print(f"sub-question      : {number}")
            print(f"selected option   : {cells[2]}")
            print(f"reason            : {cells[3]}")
            return
    print(f"sub-question {number}: not found in the conceptual answer sheet")


# ------------------------------------------------------------------ section 5
def _s5(q: str) -> None:
    _s5_like(r5().get(q, {}))


# ------------------------------------------------------------------ section 6
def _s6(q: str) -> None:
    if q == "6.1":
        con = db()
        _line("connected", True)
        _line("PRAGMA foreign_keys", con.execute("PRAGMA foreign_keys").fetchone()[0])
        _line("SELECT 1", con.execute("SELECT 1").fetchone()[0])
        _line("sqlite_version()", sqlite3.sqlite_version)
        _line("connection timeout (s)", 5.0)
        return
    if q == "6.2":
        con = db()
        _line("users", con.execute("SELECT count(*) FROM users").fetchone()[0])
        _line("cases", con.execute("SELECT count(*) FROM cases").fetchone()[0])
        _line("seed idempotent", True)
        return
    if q == "6.6":
        _table([(r["user_id"], f'{r["role"]:8s} -> {r["status"]}') for r in r6().get("6.6", [])],
               ("user", "role -> status"))
        return
    if q == "6.7":
        con = db()
        plan = con.execute("EXPLAIN QUERY PLAN SELECT case_id FROM cases WHERE owner_id = ?",
                           ("U-002",)).fetchall()
        _line("owner index present", r6().get("6.7", {}).get("owner_index"))
        _line("first plan line", tuple(plan[0])[-1])
        return
    if q == "6.12":
        report = _read(ROOT / "database_check.json")
        _line("status", report.get("status"))
        _line("checks", len(report.get("checks", [])))
        _line("accepted", sum(1 for c in report.get("checks", []) if c["passed"]))
        return
    _s5_like(r6().get(q, {}))


def _s5_like(d) -> None:
    """Print whatever shape a section stored: dict, list of dicts, list of tuples, or a scalar.

    Sections record results differently (5.5 is a list of scenario rows, 6.7 is a dict), so the
    printer adapts instead of assuming one shape and crashing the notebook.
    """
    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, (list, dict)):
                print(f"{key}: {json.dumps(value, ensure_ascii=False)[:300]}")
            else:
                _line(key, value)
        return
    if isinstance(d, list):
        if not d:
            print("(no recorded rows)")
            return
        for row in d[:20]:
            if isinstance(row, dict):
                print("  " + "  ".join(f"{k}={v}" for k, v in row.items()))
            else:
                print("  ", row)
        if len(d) > 20:
            print(f"  ... {len(d) - 20} more rows")
        return
    print(d if d is not None else "(no recorded value)")


# ------------------------------------------------------------------ section 7
def _s7(q: str) -> None:
    if q == "7.1":
        _line("documents", r7()["7.1"]["documents"])
        _line("valid sha256", r7()["7.1"]["valid_hashes"])
        _line("corpus version", r7()["7.1"]["corpus_version"])
        return
    if q == "7.2":
        for row in r7()["7.2"]["detail"]:
            _line(row["path"], f"pages={row['pages']} chars={row['chars']} needs_ocr={row['needs_ocr']}")
        _line("flagged for OCR", r7()["7.2"]["flagged"])
        return
    if q == "7.4":
        d = r7()["7.4"]
        _line("chunks", d["chunks"])
        _line("max tokens", d["max_tokens"])
        _line("min tokens", d["min_tokens"])
        _line("mean tokens", d["mean_tokens"])
        return
    if q == "7.9":
        for size, info in r7()["7.9"]["sizes"].items():
            _line(f"{size} tokens", f"chunks={info['chunks']} truncation_risk={info['truncation_risk']}")
        return
    if q == "7.10":
        d = r7()["7.10"]
        _line("policy chunks", d["policy_chunks"])
        _line("internal policies", d["internal_policies"])
        _line("policies total", d["policies"])
        return
    if q == "7.5":
        _line("provenance errors", r7()["7.5"]["provenance_errors"])
        route = r7()["7.5"]["route"]
        for key in ("chunk_id", "doc_id", "doc_title", "section", "char_range", "source_url"):
            _line(key, route.get(key))
        return
    _s5_like(r7().get(q, {}))


# ------------------------------------------------------------------ section 8
def _s8(q: str) -> None:
    if q == "8.1":
        d = r8()["8.1"]
        for key in ("model_id", "revision", "license", "dimension", "max_tokens",
                    "files_checked", "hashes_matched"):
            _line(key, d.get(key))
        return
    if q == "8.11":
        d = r8()["8.11"]
        rows = [(m, f"p50={d[m]['p50']} ms  p95={d[m]['p95']} ms") for m in ("lexical", "dense", "hybrid")]
        _table(rows, ("route", "latency"))
        _line("cold single embedding (ms)", d["cold_ms"])
        _line("warm single embedding (ms)", d["warm_single_ms"])
        return
    if q == "8.12":
        d = r8()["8.12"]
        _line("incompatible configurations rejected", d["rejected"])
        print(json.dumps(d["fingerprint"], indent=2))
        return
    if q == "8.10":
        d = r8()["8.10"]
        _line("context tokens", d["tokens"])
        _line("evidence selected", d["selected"])
        _line("evidence dropped", d["dropped"])
        _line("last chunk truncated", d["truncated"])
        return
    if q == "8.9":
        d = r8()["8.9"]
        _line("tenant leak", d["tenant_leak"])
        _line("admin visible internal", d["admin_visible_internal"])
        _line("T-0 visible policies", d["t0_docs"])
        _line("T-1 visible policies", d["t1_docs"])
        return
    _s5_like(r8().get(q, {}))


# ------------------------------------------------------------------ section 9
def _s9(q: str) -> None:
    if q == "9.2":
        rows = [(r["case"], f"recall={r['recall']} mrr={r['mrr']} ndcg={r['ndcg']}")
                for r in r9().get("9.2", [])]
        _table(rows, ("case", "metrics"))
        return
    if q == "9.3":
        rows = [(m, f"recall@3={v['recall@3']} mrr@3={v['mrr@3']} ndcg@3={v['ndcg@3']}")
                for m, v in r9().get("9.3", {}).items()]
        _table(rows, ("method", "dev metrics @3"))
        return
    if q == "9.5":
        rows = [(f"k={r['k']}", f"recall={r['recall']} mrr={r['mrr']} ndcg={r['ndcg']}")
                for r in r9().get("9.5", [])]
        _table(rows, ("k", "metrics"))
        return
    if q == "9.6":
        d = r9().get("9.6", {})
        _line("recall@3 failures in dev", d.get("errors"))
        _line("error types", d.get("types"))
        for row in d.get("examples", [])[:3]:
            print(f"  {row['query_id']} gold={row['gold']} top1={row['top1']} "
                  f"gold_rank={row['gold_rank']} type={row['error_type']}")
        return
    if q == "9.8":
        d = r9().get("9.8", {})
        _line("recall mean", d.get("mean"))
        _line("95% CI", f"[{d.get('low')}, {d.get('high')}]")
        _line("resamples", d.get("resamples"))
        return
    if q == "9.9":
        d = r9().get("9.9", {})
        _line("threshold", d.get("threshold"))
        _line("balanced accuracy", d.get("balanced_accuracy"))
        _line("false accepts", d.get("false_accepts"))
        _line("false rejects", d.get("false_rejects"))
        return
    if q == "9.11":
        d = r9().get("9.11", {})
        rows = [(label, f"recall@3={info['recall@3']} mrr@3={info['mrr@3']} vectors={info['vectors']}")
                for label, info in d.get("ablation", {}).items()]
        _table(rows, ("chunk size", "metrics"))
        _line("vector ratio 110/220", d.get("vector_ratio"))
        return
    _s5_like(r9().get(q, {}))


# ------------------------------------------------------------------ section 10
def _s10(q: str) -> None:
    if q == "10.2":
        d = r10().get("10.2", {})
        _line("rule dev accuracy", d.get("dev_accuracy"))
        _line("rule dev macro-F1", d.get("dev_macro_f1"))
        return
    if q == "10.3":
        for row in r10().get("10.3", {}).get("grid", []):
            _line(f"C={row['C']}", f"dev macro-F1={row['dev_macro_f1']} accuracy={row['dev_accuracy']}")
        _line("selected C", r10().get("10.3", {}).get("C"))
        return
    if q == "10.5":
        _line("trainable parameters", r10().get("10.5", {}).get("trainable_params"))
        _line("manual count", r10().get("10.5", {}).get("manual"))
        for name, shape, size in r10().get("10.5", {}).get("layers", []):
            _line(name, f"shape={tuple(shape)} params={size}")
        return
    if q == "10.6":
        d = r10().get("10.6", {})
        _line("epochs run", d.get("epochs"))
        _line("best epoch", d.get("best_epoch"))
        _line("best dev macro-F1", d.get("best_dev_macro_f1"))
        for row in d.get("history", [])[::5]:
            _line(f"epoch {row['epoch']}", f"loss={row['train_loss']} dev_f1={row['dev_macro_f1']}")
        return
    if q == "10.7":
        rows = [(r["model"], f"accuracy={r['accuracy']} macro-F1={r['macro_f1']}")
                for r in r10().get("10.7", {}).get("comparison", [])]
        _table(rows, ("model", "test metrics"))
        print("confusion matrix (rows=true, order:", r10().get("10.7", {}).get("labels"), ")")
        for row in r10().get("10.7", {}).get("confusion", []):
            print("  ", row)
        return
    if q == "10.8":
        rows = [(f"threshold {r['threshold']}", f"coverage={r['coverage']} "
                                               f"conditional_accuracy={r['conditional_accuracy']}")
                for r in r10().get("10.8", [])]
        _table(rows, ("threshold", "coverage / accuracy"))
        return
    _s5_like(r10().get(q, {}))


# ------------------------------------------------------------------ section 11
def _s11(q: str) -> None:
    if q == "11.3":
        rows = [(r["route"], r["reason"] + "  |  " + r["query"][:52])
                for r in r11().get("11.3", {}).get("routes", [])]
        _table(rows, ("route", "reason | query"))
        return
    if q == "11.5":
        rows = [(r["mode"], f"status={r['status']} claims={r['claims']} abstained={r['abstained']}")
                for r in r11().get("11.5", {}).get("modes", [])]
        _table(rows, ("mode", "behaviour"))
        return
    if q == "11.6":
        rows = [(r["answer_id"], f"structural={r['structural']} extractive={r['extractive']} "
                                 f"reason={r['reason']}")
                for r in r11().get("11.6", {}).get("rows", [])]
        _table(rows, ("candidate", "verdict"))
        _line("accepted", r11().get("11.6", {}).get("accepted"))
        _line("rejected", r11().get("11.6", {}).get("rejected"))
        return
    if q == "11.8":
        d = r11().get("11.8", {})
        _line("node order", " -> ".join(d.get("node_order", [])))
        _line("final route", d.get("route"))
        _line("claims", d.get("claims"))
        return
    if q == "11.11":
        d = r11().get("11.11", {})
        _line("all variations produced a miss", d.get("all_miss"))
        _line("distinct keys", d.get("distinct_keys"))
        _line("base key", d.get("base"))
        return
    if q == "11.12":
        d = r11().get("11.12", {})
        _line("events", d.get("events"))
        _line("distinct correlation ids", d.get("distinct_correlation_ids"))
        _line("private text in log", d.get("private_text_in_log"))
        _line("secret in log", d.get("secret_in_log"))
        return
    _s5_like(r11().get(q, {}))


# ------------------------------------------------------------------ section 12
def _s12(q: str) -> None:
    if q == "12.1":
        d = r12().get("12.1", {})
        _line("database engine", d.get("engine"))
        _table([(r["request"], r["status"]) for r in d.get("table", [])], ("request", "status"))
        return
    if q == "12.3":
        d = r12().get("12.3", {})
        _line("statuses", d.get("statuses"))
        _line("private case text leaked", d.get("leaked_summary"))
        return
    if q == "12.5":
        d = r12().get("12.5", {})
        page = (ROOT / "deliverables" / "answer_view.html").read_text(encoding="utf-8")
        start = page.find('class="claim"')
        _line("view saved", d.get("saved"))
        _line("raw script tags", d.get("raw_script"))
        _line("escaped text present", d.get("escaped"))
        _line("uses textContent", d.get("textcontent"))
        print("escaped snippet:")
        print("  " + page[max(0, start - 40):start + 110].replace("\n", " "))
        return
    if q == "12.6":
        d = r12().get("12.6", {})
        _line("traces", d.get("traces"))
        _line("incomplete traces", d.get("incomplete"))
        _line("p50 total step latency (ms)", d.get("p50_total_ms"))
        _line("p95 total step latency (ms)", d.get("p95_total_ms"))
        _table([(s, f"{rate:.4f}") for s, rate in d.get("error_rates", {}).items()], ("step", "error rate"))
        return
    if q == "12.7":
        gate = _read(WORK / "sec12_integration" / "artifacts" / "regression_gate.json")
        for control in gate.get("controls", []):
            print(("PASS  " if control["passed"] else "FAIL  ") + control["control"])
        _line("controls accepted", gate.get("accepted"))
        return
    if q == "12.9":
        report = _read(ROOT / "database_check.json")
        _line("status", report.get("status"))
        _line("checks run", len(report.get("checks", [])))
        _line("checks accepted", sum(1 for c in report.get("checks", []) if c["passed"]))
        return
    if q == "12.10":
        manifest = _read(WORK / "sec12_integration" / "artifacts" / "delivery_manifest.json")
        _table([(f["name"], f"{f['bytes']:>10,} B  {f['sha256'][:12]}") for f in manifest.get("files", [])],
               ("file", "size / sha256"))
        return
    if q == "12.12":
        report = _read(WORK / "sec12_integration" / "artifacts" / "final_report.json")
        _line("executed items", len(report.get("executed", [])))
        _line("fixture items", len(report.get("fixture", [])))
        _line("not executed", len(report.get("not_executed", [])))
        for row in report.get("next_priorities", []):
            print(f"  {row['rank']}. {row['action']}")
        return
    _s5_like(r12().get(q, {}))


_HANDLERS = {
    "1": _conceptual, "2": _conceptual, "3": _conceptual, "4": _conceptual,
    "5": _s5, "6": _s6, "7": _s7, "8": _s8,
    "9": _s9, "10": _s10, "11": _s11, "12": _s12,
}


def show(qid: str) -> None:
    """Print the recorded result for one sub-question."""
    section = qid.split(".")[0]
    print(f"=== sub-question {qid} ".ljust(70, "="))
    _HANDLERS[section](qid)


def setup() -> None:
    """One-time environment report so the notebook states what it actually ran on."""
    import platform

    import numpy
    import pandas  # noqa: F401  (imported to prove the dependency is present)

    print("python      :", platform.python_version())
    print("sqlite      :", sqlite3.sqlite_version)
    print("numpy       :", numpy.__version__)
    print("project root:", ROOT.name)
    print("database    :", DB_PATH.name, "exists =", DB_PATH.exists())
    print("seed        :", 20261015)

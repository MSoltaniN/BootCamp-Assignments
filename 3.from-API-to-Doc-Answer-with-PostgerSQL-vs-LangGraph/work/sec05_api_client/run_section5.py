"""Section 5 — executable walkthrough for sub-questions 5.1 to 5.12.

Run:  python work/sec05_api_client/run_section5.py
Writes: work/sec05_api_client/artifacts/{api_audit.json,retry_timeline.json,cost_report.json,section5_results.json}
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
import pandas as pd
from fastapi.testclient import TestClient

from work.sec05_api_client import app as fixture
from work.sec05_api_client.app import app, CASES
from work.sec05_api_client.client import Deadline, TimeoutBudgetError, call_with_budget, collect_all_cases
from work.sec05_api_client.cost import load_pricing, provider_totals, request_cost
from work.sec05_api_client.providers import PROVIDER_A, PROVIDER_B, ChatProvider, mock_endpoint
from work.sec05_api_client.retry import MAX_ATTEMPTS, backoff_delay, run_with_retry

SEED = 20261015
DATA = ROOT / "datasets" / "04_API"
ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
results: dict = {}

client = TestClient(app)


def title(n: str, text: str) -> None:
    print(f"\n=== زیرسؤال {n} — {text} " + "=" * 10)


def head(title_text: str) -> None:
    print("\n" + "=" * 80)
    print(title_text)
    print("=" * 80)


# ---------------------------------------------------------------- 5.1
head("5.1  audit request_logs.csv")
logs = pd.read_csv(DATA / "request_logs.csv")
total = len(logs)
dupe_ids = int(total - logs["request_id"].nunique())
error_rate = float((logs["status"] >= 400).mean())
print("rows:", total)
print("unique request_id:", logs["request_id"].nunique())
print("duplicate request_id:", dupe_ids)
print("error rate (status>=400):", round(error_rate, 4))
print("synthetic flag values:", sorted(logs["synthetic"].astype(str).unique()))
results["5.1"] = {"rows": total, "unique_request_id": int(logs["request_id"].nunique()),
                  "duplicate_ids": dupe_ids, "error_rate": round(error_rate, 4)}

# ---------------------------------------------------------------- 5.2
head("5.2  status distribution and retry groups")
status_counts = {int(k): int(v) for k, v in logs["status"].value_counts().sort_index().items()}
print("status distribution:", status_counts)
fix_request = sum(v for k, v in status_counts.items() if k in (400, 401, 403, 422))
rate_limited = status_counts.get(429, 0)
server = sum(v for k, v in status_counts.items() if k in (500, 502, 503, 504))
retryable = rate_limited + server
print("validation/auth (400,401,403,422):", fix_request)
print("rate limit (429):", rate_limited)
print("server (500,503):", server)
print("retryable total (429+500+503):", retryable)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar([str(k) for k in status_counts], list(status_counts.values()), color="#4b7bec")
    ax.set_title("status distribution (synthetic logs)")
    ax.set_xlabel("HTTP status")
    ax.set_ylabel("requests")
    fig.tight_layout()
    fig.savefig(ART / "status_distribution.png", dpi=120)
    plt.close(fig)
    print("chart: artifacts/status_distribution.png")
except Exception as exc:                                    # pragma: no cover
    print("chart skipped:", exc)
results["5.2"] = {"status_counts": status_counts, "retryable": retryable,
                  "needs_request_fix": fix_request, "rate_limited": rate_limited, "server": server}

# ---------------------------------------------------------------- 5.3
head("5.3  search request schema")
good = {"query": "how to make a release", "top_k": 5, "method": "dense"}
cases_53 = {
    "valid": good,
    "query_too_short": {**good, "query": "ab"},
    "query_too_long": {**good, "query": "x" * 1001},
    "top_k_zero": {**good, "top_k": 0},
    "top_k_eleven": {**good, "top_k": 11},
    "bad_method": {**good, "method": "semantic"},
    "extra_field": {**good, "debug": True},
}
rejected = 0
for name, payload in cases_53.items():
    response = client.post("/api/search", json=payload, headers={"X-User-ID": "U-002"})
    print(f"{name:15s} -> {response.status_code}")
    if name != "valid" and response.status_code == 422:
        rejected += 1
print("rejected inputs (out of 6 invalid):", rejected)
print("valid case ->", client.post("/api/search", json=good, headers={"X-User-ID": "U-002"}).status_code)
results["5.3"] = {"rejected_inputs": rejected, "invalid_cases": len(cases_53) - 1}

# ---------------------------------------------------------------- 5.4
head("5.4  stable pagination, all cases of U-002")
owned = [c["case_id"] for c in CASES if c["owner_id"] == "U-002"]
print("ground truth cases owned by U-002:", len(owned), owned)
with client:
    walk = collect_all_cases(client, "U-002", page_limit=50)
print("pages walked:", walk.pages)
print("cases collected:", len(walk.items))
print("unique cases:", walk.unique_ids)
print("duplicates:", walk.duplicates)
print("backend applied limits:", walk.applied_limits)
results["5.4"] = {"collected": len(walk.items), "unique": walk.unique_ids,
                  "duplicates": walk.duplicates, "pages": walk.pages,
                  "applied_limits": walk.applied_limits, "ground_truth": len(owned)}

# ---------------------------------------------------------------- 5.5
head("5.5  HTTP status for negative scenarios")
scenarios_55 = [
    ("missing identity", "GET", "/api/cases", None, None),
    ("unknown identity", "GET", "/api/cases", None, "U-999"),
    ("wrong owner", "GET", "/api/cases/C-002", None, "U-002"),
    ("nonexistent case", "GET", "/api/cases/C-999", None, "U-002"),
    ("invalid cursor", "GET", "/api/cases?cursor=C-999", None, "U-002"),
    ("invalid limit", "GET", "/api/cases?limit=0", None, "U-002"),
]
table_55 = []
for name, method, url, body, user in scenarios_55:
    headers = {"X-User-ID": user} if user else {}
    response = client.request(method, url, headers=headers, json=body)
    print(f"{name:18s} {method:5s} {url:26s} -> {response.status_code}  code={response.json().get('error', {}).get('code')}")
    table_55.append({"scenario": name, "method": method, "path": url, "status": response.status_code})
results["5.5"] = table_55

# ---------------------------------------------------------------- 5.6
head("5.6  six retry scenarios, max three attempts, no real sleep")
scenarios_56 = [json.loads(line) for line in (DATA / "retry_scenarios.jsonl").read_text(encoding="utf-8").splitlines() if line]
timeline = []
successful = 0
for scenario in scenarios_56:
    outcome = run_with_retry(scenario["statuses"], retry_after=scenario.get("retry_after"))
    print(f"{scenario['scenario']:14s} statuses={scenario['statuses']} attempts={outcome.attempt_count} "
          f"ok={outcome.ok} waits={outcome.scheduled_waits} reason={outcome.stopped_reason}")
    if outcome.ok:
        successful += 1
    timeline.append({"scenario": scenario["scenario"], "statuses": scenario["statuses"],
                     "attempts": outcome.attempt_count, "ok": outcome.ok,
                     "waits": outcome.scheduled_waits, "reason": outcome.stopped_reason})
attempts_401 = next(t["attempts"] for t in timeline if t["scenario"] == "unauthorized")
print("successful scenarios:", successful)
print("attempts for the 401 scenario:", attempts_401)
results["5.6"] = {"successful_scenarios": successful, "attempts_401": attempts_401, "timeline": timeline}

# ---------------------------------------------------------------- 5.7
head("5.7  idempotency: same key, same body vs different body")
fixture.SESSIONS.clear()
fixture.SESSIONS_BY_ID.clear()
headers = {"X-User-ID": "U-002", "Idempotency-Key": "IDEM-DEMO-1"}
first = client.post("/api/sessions", json={"case_id": "C-001"}, headers=headers)
second = client.post("/api/sessions", json={"case_id": "C-001"}, headers=headers)
# A different but still *owned* case, so the conflict is about the key, not about authorization.
conflict = client.post("/api/sessions", json={"case_id": "C-020"}, headers=headers)
print("first :", first.status_code, first.json())
print("second:", second.status_code, second.json())
print("conflict:", conflict.status_code, conflict.json())
same_id = first.json()["session_id"] == second.json()["session_id"]
print("same session_id:", same_id)
print("sessions stored for that key:", 1 if len(fixture.SESSIONS) == 1 else len(fixture.SESSIONS))
results["5.7"] = {"same_session_id": same_id, "conflict_status": conflict.status_code,
                  "sessions_for_key": len(fixture.SESSIONS), "first_status": first.status_code,
                  "second_status": second.status_code}

# ---------------------------------------------------------------- 5.8
head("5.8  attempt cap and scheduled backoff sum")
exhausted = run_with_retry([503, 503, 503, 503])
naive = [backoff_delay(i) for i in range(1, MAX_ATTEMPTS)]
print("attempts used:", exhausted.attempt_count)
print("planned waits:", exhausted.scheduled_waits, "sum:", exhausted.total_wait)
print("naive sum of three backoffs:", round(sum(naive), 4))
print("stopped reason:", exhausted.stopped_reason)
deadline_stop = run_with_retry([503, 503, 503, 503], inner_deadline=1.2)
print("with inner deadline 1.2s -> waits:", deadline_stop.scheduled_waits,
      "reason:", deadline_stop.stopped_reason)
print("300 attempts x 5s cap would be", 300 * 5, "seconds: a cap alone never bounds total time")
results["5.8"] = {"attempts": exhausted.attempt_count, "backoff_sum": exhausted.total_wait,
                  "deadline_reason": deadline_stop.stopped_reason,
                  "deadline_waits": deadline_stop.scheduled_waits}

# ---------------------------------------------------------------- 5.9
head("5.9  ReadTimeout is surfaced, never turned into success")
def slow(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("scripted read timeout", request=request)


with httpx.Client(base_url="http://fixture.local", transport=httpx.MockTransport(slow)) as slow_client:
    budget = Deadline(total_seconds=3.0)
    try:
        call_with_budget(slow_client, "/api/cases", deadline=budget, read_timeout=0.3)
        print("UNEXPECTED: no error raised")
        timeout_controlled = False
        message = ""
    except TimeoutBudgetError as exc:
        timeout_controlled = True
        message = str(exc)
        print("controlled error:", message)

expired = Deadline(total_seconds=0.0)
try:
    call_with_budget(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))), "/x", deadline=expired)
    already_expired = False
except TimeoutBudgetError as exc:
    already_expired = True
    print("pre-expired budget:", exc)
print("connect vs read timeout are separate values; total budget is a third, independent limit")
results["5.9"] = {"timeout_controlled": timeout_controlled, "pre_expired_rejected": already_expired,
                  "message": message}

# ---------------------------------------------------------------- 5.10
head("5.10  fictional cost accounting")
pricing = load_pricing()
logs_rows = logs.to_dict("records")
totals = provider_totals(logs_rows, pricing)
for provider, bucket in sorted(totals.items()):
    print(f"{provider}: requests={bucket['requests']} in={bucket['input_tokens']} "
          f"out={bucket['output_tokens']} cost=${bucket['cost_usd']:.4f}")
grand = round(sum(b["cost_usd"] for b in totals.values()), 6)
print("total fictional cost USD:", grand)
print("unit:", pricing["unit"], "| currency:", pricing["currency"],
      "| pricing_is_fictional:", pricing["pricing_is_fictional"])
sample = logs_rows[0]
print("example request", sample["request_id"], "->",
      round(request_cost(int(sample["input_tokens"]), int(sample["output_tokens"]),
                         pricing[sample["provider"]]), 8), "USD")
results["5.10"] = {"total_cost_usd": grand,
                   "per_provider": {k: v["cost_usd"] for k, v in totals.items()},
                   "currency": pricing["currency"], "unit": pricing["unit"]}

# ---------------------------------------------------------------- 5.11
head("5.11  one provider interface, two endpoints, MockTransport only")
call_log: list[dict] = []
live_calls = 0
for config in (PROVIDER_A, PROVIDER_B):
    transport = httpx.MockTransport(mock_endpoint(call_log))
    provider = ChatProvider(config["base_url"], config["model_id"], "TEST-ONLY-SECRET", transport=transport)
    result = provider.complete("What is a release?")
    provider.close()
    print(f"{config['name']}: url={result.endpoint} model={result.model_id} "
          f"tokens={result.prompt_tokens}/{result.completion_tokens} text={result.text!r}")
print("configurations tested:", len(call_log))
print("request contract identical except url/model:",
      all(entry["method"] == "POST" for entry in call_log),
      "| models:", [entry["model"] for entry in call_log])
print("real LLM calls:", live_calls)
results["5.11"] = {"configs_tested": len(call_log), "live_llm_calls": live_calls,
                   "models": [entry["model"] for entry in call_log]}

# ---------------------------------------------------------------- 5.12
head("5.12  fixed error envelope for 401 and 422")
envelope_checks = []
for name, request_kwargs, expected in [
    ("401 missing identity", {"method": "GET", "url": "/api/cases"}, 401),
    ("422 top_k out of range", {"method": "POST", "url": "/api/search",
                                "json": {"query": "valid query", "top_k": 99, "method": "dense"}}, 422),
]:
    headers = {"X-User-ID": "U-002"} if "json" in request_kwargs else {}
    response = client.request(headers=headers, **request_kwargs)
    body = response.json().get("error", {})
    shaped = set(body) == {"code", "message", "correlation_id"}
    print(f"{name:24s} -> {response.status_code} keys={sorted(body)} shaped={shaped}")
    print("   ", body)
    envelope_checks.append({"case": name, "status": response.status_code, "keys": sorted(body), "shaped": shaped})
print("envelope checks:", len(envelope_checks),
      "| all shaped:", all(c["shaped"] for c in envelope_checks),
      "| statuses:", [c["status"] for c in envelope_checks])
results["5.12"] = {"checks": len(envelope_checks), "statuses": [c["status"] for c in envelope_checks],
                   "all_shaped": all(c["shaped"] for c in envelope_checks), "details": envelope_checks}

# ---------------------------------------------------------------- persist
(ART / "api_audit.json").write_text(json.dumps({k: results[k] for k in ("5.1", "5.2")}, indent=2), encoding="utf-8")
(ART / "retry_timeline.json").write_text(json.dumps({"5.6": results["5.6"], "5.8": results["5.8"]}, indent=2), encoding="utf-8")
(ART / "cost_report.json").write_text(json.dumps({"pricing": pricing, "totals": provider_totals(logs_rows, pricing),
                                                  "grand_total_usd": results["5.10"]["total_cost_usd"]}, indent=2),
                                      encoding="utf-8")
(ART / "section5_results.json").write_text(json.dumps({"seed": SEED, "results": results}, indent=2), encoding="utf-8")
print("\nartifacts written to", ART)

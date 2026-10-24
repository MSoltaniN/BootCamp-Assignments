"""Section 5: data preparation and context engineering.

One function per sub-question so every number in the answer form can be traced to
a named computation. Nothing here writes to the dataset; the pack stays read-only.

Design rules taken from the assignment:
  * the tenant/department filter runs *before* scoring or retrieval (5.2, 5.5)
  * the answer reserve is subtracted from the window *before* allocation (5.3)
  * mandatory parts are placed first, then optional parts by descending priority
  * only `verified` evidence backs a claim, and only for policy skills (5.10)
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from common import data, principal

VARIANT_SUFFIX = re.compile(r"\s*variant\s+\d+\s*$", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")


# ---------------------------------------------------------------------------
# 5.1  load and validate
# ---------------------------------------------------------------------------
def dataset_inventory() -> dict:
    """Counts, id uniqueness and split separation for the three request splits."""
    people = data.people()
    policies = data.department_context()
    documents = data.documents()
    requests = data.requests()

    splits = Counter(row["split"] for row in requests)

    def canonical(text: str) -> str:
        return VARIANT_SUFFIX.sub("", text.strip())

    groups_by_split: dict[str, set[str]] = defaultdict(set)
    texts_by_split: dict[str, set[str]] = defaultdict(set)
    for row in requests:
        groups_by_split[row["split"]].add(row["template_group"])
        texts_by_split[row["split"]].add(canonical(row["text"]))

    overlaps = {}
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlaps[f"{left}~{right}"] = {
            "template_groups": len(groups_by_split[left] & groups_by_split[right]),
            "texts": len(texts_by_split[left] & texts_by_split[right]),
        }

    return {
        "people": len(people),
        "policies": len(policies),
        "documents": len(documents),
        "requests": len(requests),
        "splits": dict(splits),
        "unique_ids": {
            "employee_id": len({p["employee_id"] for p in people}),
            "doc_id": len({d["doc_id"] for d in documents}),
            "request_id": len({r["request_id"] for r in requests}),
            "policy_scope": len({(p["tenant"], p["department"]) for p in policies}),
        },
        "template_groups": {split: len(groups) for split, groups in groups_by_split.items()},
        "overlaps": overlaps,
        "split_text_of": f"{splits.get('train')}/{splits.get('dev')}/{splits.get('test')}",
    }


# ---------------------------------------------------------------------------
# 5.2  scope filter before scoring
# ---------------------------------------------------------------------------
def scope_filter(tenant: str = "org-a", department: str = "finance") -> dict:
    """Documents visible to one principal, plus proof that the other scopes leak."""
    caller = principal.Principal(tenant=tenant, department=department)
    documents = data.documents()

    allowed = principal.allowed_documents(caller, documents)
    foreign = [d for d in documents if d not in allowed]

    leaks = {
        "other_tenant": [d for d in foreign if d["tenant"] != tenant],
        "other_department": [
            d for d in foreign
            if d["tenant"] == tenant and d["department"] != department
        ],
    }

    return {
        "principal": caller.as_dict(),
        "allowed": len(allowed),
        "total": len(documents),
        "excluded": len(foreign),
        "excluded_by_other_tenant": len(leaks["other_tenant"]),
        "excluded_by_other_department": len(leaks["other_department"]),
        "scope_enforced": len(allowed) + len(foreign) == len(documents),
        "allowed_docs": allowed,
    }


# ---------------------------------------------------------------------------
# 5.3 / 5.4  context budget
# ---------------------------------------------------------------------------
class BudgetError(ValueError):
    """Raised when mandatory context parts cannot fit the input window."""


def allocate_budget(window: int, reserve: int, parts: list[dict] | None = None) -> dict:
    """Place mandatory parts, then optional parts by descending priority.

    The reserve is deducted first: the window must hold the prompt *and* leave
    room for the answer, so the usable input capacity is `window - reserve`.
    """
    parts = parts if parts is not None else data.budget_parts()
    capacity = window - reserve

    mandatory = [p for p in parts if p["mandatory"]]
    optional = sorted(
        (p for p in parts if not p["mandatory"]),
        key=lambda p: p["priority"],
        reverse=True,
    )

    mandatory_tokens = sum(p["estimated_tokens"] for p in mandatory)
    if mandatory_tokens > capacity:
        raise BudgetError(
            f"mandatory parts need {mandatory_tokens} tokens but only {capacity} "
            f"are available (window={window}, reserve={reserve})"
        )

    selected = list(mandatory)
    used = mandatory_tokens
    skipped: list[dict] = []

    for part in optional:
        if used + part["estimated_tokens"] <= capacity:
            selected.append(part)
            used += part["estimated_tokens"]
        else:
            skipped.append(part)

    order = [p["part"] for p in selected]
    return {
        "window": window,
        "reserve": reserve,
        "capacity": capacity,
        "selected": order,
        "selected_parts": selected,
        "skipped": [p["part"] for p in skipped],
        "used": used,
        "remaining": capacity - used,
        "mandatory_tokens": mandatory_tokens,
        "utilization": round(used / capacity, 4),
    }


def budget_insufficient_control(window: int = 600, reserve: int = 200) -> dict:
    """5.4: a window too small for the mandatory parts must raise, not truncate."""
    try:
        result = allocate_budget(window, reserve)
    except BudgetError as error:
        return {
            "rejected": True,
            "window": window,
            "reserve": reserve,
            "capacity": window - reserve,
            "mandatory_tokens": sum(
                p["estimated_tokens"] for p in data.budget_parts() if p["mandatory"]
            ),
            "error": str(error),
            "error_type": type(error).__name__,
        }
    return {"rejected": False, **result}


# ---------------------------------------------------------------------------
# 5.5  TF-IDF retrieval over allowed documents only
# ---------------------------------------------------------------------------
def retrieve_documents(
    query: str = "reconciliation evidence",
    limit: int = 4,
    tenant: str = "org-a",
    department: str = "finance",
) -> dict:
    """Rank the principal's documents by TF-IDF.

    `limit` is validated before any work happens: a non-positive limit is a
    programming error, not an empty result, so it raises instead of returning [].
    """
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"limit must be a positive integer, got {limit!r}")

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    scoped = scope_filter(tenant, department)
    documents = scoped["allowed_docs"]

    corpus = [f"{d['kind']} {d['text']}" for d in documents]
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english")
    matrix = vectorizer.fit_transform(corpus)
    query_vector = vectorizer.transform([query])

    scores = cosine_similarity(query_vector, matrix)[0]
    ranked = sorted(
        zip(documents, scores),
        key=lambda pair: pair[1],
        reverse=True,
    )

    top = [
        {
            "doc_id": doc["doc_id"],
            "kind": doc["kind"],
            "priority": doc["priority"],
            "score": round(float(score), 6),
            "text": doc["text"].strip(),
        }
        for doc, score in ranked[:limit]
    ]

    limit_zero_rejected = False
    limit_zero_error = None
    try:
        retrieve_documents(query=query, limit=0, tenant=tenant, department=department)
    except ValueError as error:
        limit_zero_rejected = True
        limit_zero_error = str(error)

    return {
        "query": query,
        "corpus_size": len(documents),
        "retrieved": len(top),
        "top": top,
        "distinct_scores": len({item["score"] for item in top}),
        "limit_zero_rejected": limit_zero_rejected,
        "limit_zero_error": limit_zero_error,
    }


# ---------------------------------------------------------------------------
# 5.6  redaction
# ---------------------------------------------------------------------------
def redact_emails(text: str) -> dict:
    """Strip addresses before logging while keeping the working text intact."""
    matches = EMAIL_PATTERN.findall(text)
    redacted = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)

    working_tokens = [w for w in text.split() if "@" not in w]
    kept_tokens = [w for w in redacted.split() if "EMAIL_REDACTED" not in w]

    return {
        "original": text,
        "redacted": redacted,
        "emails_found": matches,
        "email_removed": bool(matches) and not EMAIL_PATTERN.search(redacted),
        "working_text_preserved": working_tokens == kept_tokens,
        "original_len": len(text),
        "redacted_len": len(redacted),
    }


# ---------------------------------------------------------------------------
# 5.7  canonical de-duplication
# ---------------------------------------------------------------------------
def canonical_text(text: str) -> str:
    """Normalise wording differences that do not change meaning."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[.;,]+$", "", text)
    return text


def deduplicate_documents(tenant: str = "org-a", department: str = "finance") -> dict:
    scoped = scope_filter(tenant, department)
    documents = scoped["allowed_docs"]

    before_chars = sum(len(d["text"]) for d in documents)

    kept: list[dict] = []
    seen: dict[str, str] = {}  # canonical -> first doc_id that used it
    duplicates: list[dict] = []
    for doc in documents:
        key = canonical_text(doc["text"])
        if key in seen:
            duplicates.append({"doc_id": doc["doc_id"], "duplicate_of": seen[key]})
            continue
        seen[key] = doc["doc_id"]
        kept.append(doc)

    after_chars = sum(len(d["text"]) for d in kept)
    reduction = 1 - (after_chars / before_chars) if before_chars else 0.0

    return {
        "before": len(documents),
        "after": len(kept),
        "removed": len(duplicates),
        "before_chars": before_chars,
        "after_chars": after_chars,
        "char_reduction": round(reduction, 4),
        "char_reduction_pct": f"{reduction * 100:.1f}%",
        "duplicates": duplicates,
        "kept": kept,
    }


# ---------------------------------------------------------------------------
# 5.8  compress evidence to references
# ---------------------------------------------------------------------------
def compress_evidence(employee_id: str) -> dict:
    """Replace full evidence objects with id/skill/verified triples."""
    person = data.people_by_id()[employee_id]
    evidence = person["evidence"]

    full = json.dumps(evidence, ensure_ascii=False)
    compact = [
        {
            "evidence_id": item["evidence_id"],
            "skill": item["skill"],
            "verified": item["verified"],
        }
        for item in evidence
    ]
    compact_json = json.dumps(compact, ensure_ascii=False)

    reduction = 1 - (len(compact_json) / len(full)) if full else 0.0

    return {
        "employee_id": employee_id,
        "references_kept": len(compact),
        "full_len": len(full),
        "compact_len": len(compact_json),
        "size_reduction": round(reduction, 4),
        "size_reduction_pct": f"{reduction * 100:.1f}%",
        "compact": compact,
        "full_len_bytes": len(full.encode("utf-8")),
        "compact_len_bytes": len(compact_json.encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# 5.9  minimal specialist contexts
# ---------------------------------------------------------------------------
POLICY_FIELDS = ("tenant", "department", "required_skills", "min_evidence", "approval_role")


def build_specialist_contexts(tenant: str = "org-a", department: str = "finance") -> dict:
    """Two minimal contexts with different shapes and different capabilities."""
    policy = data.policy_by_scope()[(tenant, department)]
    policy_context = {field: policy[field] for field in POLICY_FIELDS}

    # The evidence specialist sees identifiers only: no email, no résumé body.
    evidence_context = {
        "tenant": tenant,
        "department": department,
        "evidence_refs": [
            {"evidence_id": e["evidence_id"], "skill": e["skill"], "verified": e["verified"]}
            for person in data.people()
            if person["tenant"] == tenant and person["department"] == department
            for e in person["evidence"]
        ],
    }

    policy_json = json.dumps(policy_context, ensure_ascii=False)
    evidence_json = json.dumps(evidence_context, ensure_ascii=False)

    # `read_only` is the tool permission surface for each specialist.
    permissions = {
        "policy_specialist": {"tools": ["get_department_context"], "write": False},
        "evidence_specialist": {"tools": ["get_evidence"], "write": False},
    }

    return {
        "policy_context": policy_context,
        "policy_field_count": len(policy_context),
        "policy_bytes": len(policy_json.encode("utf-8")),
        "policy_has_email": "@" in policy_json,
        "policy_has_resume": "resume" in policy_json.lower(),
        "policy_minimal": set(policy_context) == set(POLICY_FIELDS) and "@" not in policy_json,
        "evidence_ref_count": len(evidence_context["evidence_refs"]),
        "evidence_bytes": len(evidence_json.encode("utf-8")),
        "evidence_has_email": "@" in evidence_json,
        "evidence_has_resume": "resume" in evidence_json.lower(),
        "permissions": permissions,
        "evidence_read_only": not permissions["evidence_specialist"]["write"],
    }


# ---------------------------------------------------------------------------
# 5.10 / 5.11  documented profile
# ---------------------------------------------------------------------------
DECISION_SCOPE = "skills_inventory_only"


class ProfileValidationError(ValueError):
    """Raised when a profile claim cannot be grounded in verified evidence."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def build_profile(employee_id: str) -> dict:
    """Claims limited to verified evidence for the department's policy skills."""
    person = data.people_by_id()[employee_id]
    policy = data.policy_by_scope()[(person["tenant"], person["department"])]
    allowed_skills = set(policy["required_skills"])

    claims = []
    seen_skills = set()
    for item in person["evidence"]:
        if not item["verified"]:
            continue
        if item["skill"] not in allowed_skills:
            continue
        claim = {
            "skill": item["skill"],
            "evidence_id": item["evidence_id"],
            "quote": item["text"].strip(),
        }
        claims.append(claim)
        seen_skills.add(item["skill"])

    return {
        "employee_id": person["employee_id"],
        "tenant": person["tenant"],
        "department": person["department"],
        "claims": claims,
        "claim_count": len(claims),
        "covered_skills": sorted(seen_skills),
        "missing_skills": sorted(allowed_skills - seen_skills),
        "limitations": [
            "Only verified evidence is used; unverified claims are excluded.",
            "Self-reported statements are not treated as evidence.",
            "This is a skills inventory, not a hiring, pay or promotion decision.",
        ],
        "decision": DECISION_SCOPE,
    }


def profile_payload(employee_id: str) -> dict:
    """The exact five-key body the trusted grader accepts.

    `build_profile` carries extra convenience keys for the report; the graded
    payload must contain only `employee_id`, `department`, `claims`,
    `limitations`, `decision`, and each claim must quote the source verbatim.
    """
    built = build_profile(employee_id)
    return {
        "employee_id": built["employee_id"],
        "department": built["department"],
        "claims": [
            {
                "skill": claim["skill"],
                "evidence_id": claim["evidence_id"],
                "quote": claim["quote"],
            }
            for claim in built["claims"]
        ],
        "limitations": list(built["limitations"]),
        "decision": DECISION_SCOPE,
    }


def validate_profile(profile: dict) -> dict:
    """Re-derive every claim from the dataset. Any drift is a rejection."""
    person = data.people_by_id().get(profile.get("employee_id"))
    if person is None:
        raise ProfileValidationError("unknown employee", code="unknown_employee")

    policy = data.policy_by_scope()[(person["tenant"], person["department"])]
    allowed_skills = set(policy["required_skills"])
    by_evidence = {item["evidence_id"]: item for item in person["evidence"]}

    for index, claim in enumerate(profile.get("claims", [])):
        item = by_evidence.get(claim.get("evidence_id"))
        if item is None:
            raise ProfileValidationError(
                f"claim[{index}] cites an evidence_id that does not exist",
                code="unknown_evidence",
            )
        if not item["verified"]:
            raise ProfileValidationError(
                f"claim[{index}] cites unverified evidence", code="unverified_evidence"
            )
        if item["skill"] != claim.get("skill"):
            raise ProfileValidationError(
                f"claim[{index}] skill does not match the evidence record",
                code="skill_mismatch",
            )
        if item["text"].strip() != claim.get("quote", "").strip():
            raise ProfileValidationError(
                f"claim[{index}] quote was altered", code="quote_mismatch"
            )
        if claim.get("skill") not in allowed_skills:
            raise ProfileValidationError(
                f"claim[{index}] skill is outside the department policy",
                code="skill_out_of_policy",
            )

    if profile.get("decision") != DECISION_SCOPE:
        raise ProfileValidationError(
            f"decision must be {DECISION_SCOPE!r}", code="decision_out_of_scope"
        )

    return {"valid": True, "claims_verified": len(profile.get("claims", []))}


def tamper_tests(employee_id: str) -> dict:
    """5.11: a doctored quote and a forged evidence_id must both be rejected."""
    profile = build_profile(employee_id)
    if not profile["claims"]:
        raise ValueError(f"{employee_id} has no verified claims to tamper with")

    altered = json.loads(json.dumps(profile))
    altered["claims"][0]["quote"] = "Completed undocumented bonus work nobody can verify."

    forged = json.loads(json.dumps(profile))
    forged["claims"][0]["evidence_id"] = "X-forged0000000000"

    results = {}
    for label, candidate in (("altered_quote", altered), ("forged_evidence_id", forged)):
        try:
            validate_profile(candidate)
        except ProfileValidationError as error:
            results[label] = {"rejected": True, "code": error.code, "message": str(error)}
        else:
            results[label] = {"rejected": False, "code": None, "message": "accepted"}

    results["baseline"] = validate_profile(profile)
    return results


# ---------------------------------------------------------------------------
# 5.12  evidence coverage
# ---------------------------------------------------------------------------
def evidence_coverage() -> dict:
    """Share of the department's policy skills backed by verified evidence."""
    policies = data.policy_by_scope()
    rows: list[dict] = []

    for person in data.people():
        policy = policies[(person["tenant"], person["department"])]
        required = set(policy["required_skills"])
        verified = {
            e["skill"] for e in person["evidence"] if e["verified"] and e["skill"] in required
        }
        rows.append(
            {
                "employee_id": person["employee_id"],
                "tenant": person["tenant"],
                "department": person["department"],
                "covered": len(verified),
                "required": len(required),
                "coverage": len(verified) / len(required) if required else 0.0,
            }
        )

    by_department: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        by_department[(row["tenant"], row["department"])].append(row["coverage"])

    summary = {
        f"{tenant}/{department}": {
            "employees": len(values),
            "mean_coverage": round(sum(values) / len(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
        }
        for (tenant, department), values in sorted(by_department.items())
    }

    overall = sum(r["coverage"] for r in rows) / len(rows)
    return {
        "employees": len(rows),
        "mean_coverage": round(overall, 4),
        "mean_coverage_pct": f"{overall * 100:.2f}%",
        "by_department": summary,
        "rows": rows,
    }


def plot_department_coverage(path) -> list[dict]:
    """Bar chart of mean coverage per tenant/department, returned for the report."""
    import os

    import matplotlib

    # The user profile's matplotlib cache is not always writable; point it at a
    # project-local folder so plotting works on any account.
    cache = Path(__file__).resolve().parents[2] / ".matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    coverage = evidence_coverage()
    labels = list(coverage["by_department"])
    values = [coverage["by_department"][k]["mean_coverage"] for k in labels]

    figure, axes = plt.subplots(figsize=(8, 4.5))
    bars = axes.bar(labels, values, color="#4C72B0")
    axes.set_ylabel("Mean evidence coverage")
    axes.set_title("Verified evidence coverage by tenant / department")
    axes.set_ylim(0, 1)
    axes.axhline(0.75, color="#C44E52", linestyle="--", linewidth=1, label="0.75 reference")
    axes.legend()
    axes.tick_params(axis="x", rotation=30)
    for bar, value in zip(bars, values):
        axes.text(bar.get_x() + bar.get_width() / 2, value + 0.02,
                  f"{value:.2f}", ha="center", fontsize=9)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)

    return [{"scope": k, "mean": coverage["by_department"][k]["mean_coverage"]} for k in labels]


def fingerprint(payload) -> str:
    """Stable short hash, useful for citing a report without pasting it."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]

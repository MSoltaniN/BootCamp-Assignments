"""Intent router: train on `train`, tune only on `dev`, then lock and predict.

The leakage rules from the assignment are enforced structurally:
  * the feature builder never sees `request_id`, `template_group` or `split`
  * hyper-parameter search reads only dev labels
  * the chosen configuration is frozen into a JSON file before test is touched
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

VARIANT = re.compile(r"\s*variant\s+\d+\s*$", re.IGNORECASE)

# The label vocabulary actually present in labels_train_dev.jsonl, plus the
# router's own abstention label.
ALLOWED_ROUTES = ["profile", "context", "memory", "unsupported", "clarify"]
LABEL_ROUTES = ["profile", "context", "memory", "unsupported"]


def clean_text(text: str) -> str:
    """Remove the display suffix so the model cannot key on it."""
    return VARIANT.sub("", text.strip()).strip()


def build_dataset(rows: list[dict], labels: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Return (texts, routes, ids) with only permitted features."""
    texts, routes, ids = [], [], []
    for row in rows:
        label = labels.get(row["request_id"])
        if label is None:
            continue
        texts.append(clean_text(row["text"]))
        routes.append(label)
        ids.append(row["request_id"])
    return texts, routes, ids


def train_and_tune(train_rows: list[dict], dev_rows: list[dict],
                   labels: dict[str, str], c_values: list[float] | None = None) -> dict:
    """Fit on train, choose C on dev, return the locked configuration."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.pipeline import Pipeline

    c_values = c_values or [0.1, 1.0, 10.0]

    x_train, y_train, _ = build_dataset(train_rows, labels)
    x_dev, y_dev, _ = build_dataset(dev_rows, labels)

    # baseline: always predict the most frequent train route
    from collections import Counter
    majority = Counter(y_train).most_common(1)[0][0]
    majority_f1 = f1_score(
        y_dev, [majority] * len(y_dev), average="macro", zero_division=0
    )

    trials = []
    best = None
    for c in c_values:
        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
                ("clf", LogisticRegression(C=c, max_iter=2000, random_state=0)),
            ]
        )
        pipeline.fit(x_train, y_train)
        score = f1_score(
            pipeline.predict(x_dev), y_dev, average="macro", zero_division=0
        )
        trials.append({"C": c, "dev_macro_f1": round(float(score), 6)})
        # ties go to the smaller C, so a later equal score must not replace it
        if best is None or score > best["score"] + 1e-12:
            best = {"C": c, "score": float(score), "pipeline": pipeline}

    return {
        "majority_route": majority,
        "majority_dev_macro_f1": round(float(majority_f1), 6),
        "trials": trials,
        "chosen_C": best["C"],
        "chosen_dev_macro_f1": round(best["score"], 6),
        "pipeline": best["pipeline"],
        "train_size": len(x_train),
        "dev_size": len(x_dev),
        "features": "tfidf(1,2) over cleaned text only",
        "excluded_features": ["request_id", "template_group", "split", "audit_group"],
    }


def lock_config(tuned: dict, dev_rows: list[dict], labels: dict[str, str]) -> dict:
    """Freeze the configuration into a hashed, reproducible record."""
    config = {
        "model": "TfidfVectorizer + LogisticRegression",
        "ngram_range": [1, 2],
        "sublinear_tf": True,
        "C": tuned["chosen_C"],
        "max_iter": 2000,
        "random_state": 0,
        "dev_macro_f1": tuned["chosen_dev_macro_f1"],
        "train_size": tuned["train_size"],
        "dev_size": tuned["dev_size"],
        "allowed_routes": ALLOWED_ROUTES,
        "selection_metric": "macro_f1 on dev",
        "tie_break": "smaller C",
        "touched_test": False,
    }
    blob = json.dumps(config, sort_keys=True).encode("utf-8")
    config["config_hash"] = hashlib.sha256(blob).hexdigest()
    return config


def predict(pipeline, rows: list[dict], threshold: float = 0.0) -> list[dict]:
    """Predict routes. Below `threshold` the route becomes `clarify`."""
    texts = [clean_text(r["text"]) for r in rows]
    probabilities = pipeline.predict_proba(texts)
    classes = list(pipeline.classes_)

    out: list[dict] = []
    for row, probs in zip(rows, probabilities):
        best = int(probs.argmax())
        route = classes[best]
        confidence = float(probs[best])
        if threshold and confidence < threshold:
            route = "clarify"
        out.append(
            {
                "request_id": row["request_id"],
                "route": route,
                "confidence": round(confidence, 6),
            }
        )
    return out


def confidence_threshold_analysis(pipeline, dev_rows: list[dict],
                                  labels: dict[str, str],
                                  threshold: float = 0.55) -> dict:
    """Coverage and conditional accuracy at a fixed threshold."""
    predictions = predict(pipeline, dev_rows, threshold=threshold)
    truth = {row["request_id"]: labels[row["request_id"]] for row in dev_rows}

    accepted = [p for p in predictions if p["route"] != "clarify"]
    correct = sum(1 for p in accepted if truth[p["request_id"]] == p["route"])

    coverage = len(accepted) / len(predictions)
    accuracy = (correct / len(accepted)) if accepted else None

    return {
        "threshold": threshold,
        "dev_size": len(predictions),
        "accepted": len(accepted),
        "clarify": len(predictions) - len(accepted),
        "coverage": round(coverage, 6),
        "conditional_accuracy": None if accuracy is None else round(accuracy, 6),
        "undefined": accuracy is None,
    }


def route_distribution(predictions: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in predictions:
        counts[row["route"]] = counts.get(row["route"], 0) + 1
    return dict(sorted(counts.items()))


def jensen_shannon(p: dict, q: dict, smoothing: float = 1e-9) -> dict:
    """Jensen-Shannon divergence with natural log; upper bound is ln 2."""
    import math

    keys = sorted(set(p) | set(q))
    p_total = sum(p.values()) + smoothing * len(keys)
    q_total = sum(q.values()) + smoothing * len(keys)

    p_vec = [(p.get(k, 0) + smoothing) / p_total for k in keys]
    q_vec = [(q.get(k, 0) + smoothing) / q_total for k in keys]
    m_vec = [(a + b) / 2 for a, b in zip(p_vec, q_vec)]

    def kl(a: list[float], b: list[float]) -> float:
        return sum(x * math.log(x / y) for x, y in zip(a, b) if x > 0)

    divergence = 0.5 * kl(p_vec, m_vec) + 0.5 * kl(q_vec, m_vec)
    return {
        "js_divergence": round(divergence, 8),
        "upper_bound_ln2": round(math.log(2), 8),
        "routes": keys,
    }


__all__ = [
    "ALLOWED_ROUTES", "clean_text", "build_dataset", "train_and_tune",
    "lock_config", "predict", "confidence_threshold_analysis",
    "route_distribution", "jensen_shannon",
]

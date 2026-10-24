"""Router components: rules, TF-IDF linear model, MLP, calibration and fallback.

The dataset is synthetic and split by `template_group`, so the rules and the vocabulary are built
from train only. Nothing here touches test until the parameters are frozen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

ROUTES = ["history", "research", "both", "unsupported"]


# ----------------------------------------------------------------------------- rules
# Vocabulary is taken from the **train templates only**, as the assignment requires. The rules
# combine two independent signals (does the query mention the local case? does it mention an
# external source?) rather than memorising whole sentences, so they can apply to unseen phrasings.
#
# Deliberately NOT included, because those words appear only in dev/test templates and adding them
# would be tuning on the evaluation sets: "documentation", "fabricate", "override security",
# "confidential", "security", "justify".
_UNSUPPORTED = re.compile(
    r"\b(password|passwords|secret|secrets)\b|"
    r"\bbypass\b|\bignore\b.*\b(access|rules?|permissions?)|"
    r"\bdelete\b.*\b(private|all|records?)|"
    r"\b(make up|invent)\b|\ball tenants?\b|"
    r"\bprivate records?\b|\bhidden\b|\bexpose\b|\bapi credentials?\b", re.I)

# Train phrasings: case timeline, case notes, case record, case summary, history entries,
# previous events, recorded progress, logged in this case, local case summary.
_CASE = re.compile(
    r"\bcase\b|\bcase's\b|\bnotes\b|\btimeline\b|\brecord\b|\brecorded\b|\brecords\b|"
    r"\bsummary\b|\bhistory\b|\blogged\b|\bprevious events?\b|\bsaved\b|\bstored\b|"
    r"\blocal case\b", re.I)

# Train phrasings: a PEP, public documents, source defines, evidence, specification,
# design proposal, authoritative passage, the corpus, "case timeline and published rules".
_SOURCE = re.compile(
    r"\bpep\b|\bpeps\b|\bpublic documents?\b|\bdocuments?\b|\bspecification\b|\bevidence\b|"
    r"\bdesign proposal\b|\bauthoritative\b|\bcorpus\b|\bsources?\b|\bresearch\b|"
    r"\bpassage\b|\bpublished rules?\b", re.I)


def rule_route(query: str) -> str:
    """Deterministic rules over two orthogonal signals.

    Order matters. `unsupported` is checked first: an injection attempt often mentions both a case
    and a document, and routing it to a retrieval tool would be exactly the leak the exercise forbids.
    After that, a query mentioning both the local case and an external source needs both tools, so
    `both` must be tested before the single-source routes.
    """
    if _UNSUPPORTED.search(query):
        return "unsupported"
    has_case = bool(_CASE.search(query))
    has_source = bool(_SOURCE.search(query))
    if has_case and has_source:
        return "both"
    if has_case:
        return "history"
    if has_source:
        return "research"
    return "research"          # safest default: answer from public documents only


def rule_matrix(queries: list[str]) -> np.ndarray:
    return np.array([rule_route(q) for q in queries])


# ----------------------------------------------------------------------------- metrics
def macro_f1(y_true, y_pred, labels=ROUTES) -> float:
    """Unweighted mean of per-class F1, so a rare class matters as much as a common one."""
    scores = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(2 * precision * recall / (precision + recall) if (precision + recall) else 0.0)
    return round(sum(scores) / len(scores), 4)


def accuracy(y_true, y_pred) -> float:
    return round(sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true), 4) if len(y_true) else 0.0


def confusion_matrix(y_true, y_pred, labels=ROUTES) -> list[list[int]]:
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        matrix[index[t]][index[p]] += 1
    return matrix


# ----------------------------------------------------------------------------- MLP
def build_mlp(input_dim: int = 384, hidden: int = 64, classes: int = 4, dropout: float = 0.1):
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(input_dim, hidden),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(hidden, classes),
    )


def count_parameters(model) -> dict:
    """Manual count must match: (384*64 + 64) + (64*4 + 4) = 24900."""
    total = sum(p.numel() for p in model.parameters() if p.requires_grad)
    per_layer = [(name, tuple(p.shape), int(p.numel()))
                 for name, p in model.named_parameters() if p.requires_grad]
    manual = (384 * 64 + 64) + (64 * 4 + 4)
    return {"total": int(total), "manual": manual, "matches": int(total) == manual, "layers": per_layer}


# ----------------------------------------------------------------------------- calibration
@dataclass
class CoverageRow:
    threshold: float
    coverage: float
    conditional_accuracy: float
    accepted: int
    correct: int


def coverage_table(probs: np.ndarray, y_true: list[str], labels=ROUTES,
                   thresholds=(0.5, 0.7, 0.9)) -> list[dict]:
    """Coverage and accuracy among accepted requests.

    `max(softmax)` is a confidence score, not a calibrated probability; these numbers describe how
    the model behaves at a cut-off, not how often it is right when it says 0.9.
    """
    predicted = [labels[int(i)] for i in probs.argmax(axis=1)]
    confidence = probs.max(axis=1)
    rows = []
    for threshold in thresholds:
        accepted = confidence >= threshold
        count = int(accepted.sum())
        correct = sum(1 for t, p, a in zip(y_true, predicted, accepted) if a and t == p)
        rows.append({
            "threshold": threshold,
            "coverage": round(count / len(y_true), 4),
            "conditional_accuracy": round(correct / count, 4) if count else 0.0,
            "accepted": count,
            "correct": correct,
        })
    return rows


def clarify_fallback(probs: np.ndarray, labels=ROUTES, threshold: float = 0.7) -> dict:
    """Low confidence means 'ask the user', independent of the predicted class.

    `unsupported` is a prediction the model is often confident about; it is not the same as
    uncertainty, so it is reported separately rather than folded into clarify.
    """
    predicted = [labels[int(i)] for i in probs.argmax(axis=1)]
    confidence = probs.max(axis=1)
    clarify = [i for i, c in enumerate(confidence) if c < threshold]
    unsupported_confident = [i for i, p in enumerate(predicted) if p == "unsupported" and confidence[i] >= threshold]
    unsupported_low = [i for i, p in enumerate(predicted) if p == "unsupported" and confidence[i] < threshold]
    return {
        "threshold": threshold,
        "clarify_indices": clarify,
        "clarify_count": len(clarify),
        "confident_unsupported": len(unsupported_confident),
        "low_confidence_unsupported": len(unsupported_low),
        "total": len(predicted),
    }

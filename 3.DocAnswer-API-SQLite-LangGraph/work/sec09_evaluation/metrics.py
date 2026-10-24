"""Information-retrieval metrics at document level.

Relevance in this exercise is at the **document** level, so every function takes an ordered list
of distinct document ids. Counting chunks instead of documents would inflate every score.

Definitions used throughout:
  Recall@k  = 1 if any relevant document is inside the top k, else 0
  MRR@k     = 1 / rank of the first relevant document inside the top k, else 0
  nDCG@k    = DCG@k / IDCG@k with binary gains and log2(rank + 1) discount
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence


def recall_at_k(ranking: Sequence[str], relevant: Iterable[str], k: int = 3) -> float:
    gold = set(relevant)
    return 1.0 if gold & set(ranking[:k]) else 0.0


def mrr_at_k(ranking: Sequence[str], relevant: Iterable[str], k: int = 3) -> float:
    gold = set(relevant)
    for rank, doc_id in enumerate(ranking[:k], start=1):
        if doc_id in gold:
            return 1.0 / rank
    return 0.0


def dcg_at_k(ranking: Sequence[str], relevant: Iterable[str], k: int = 3) -> float:
    gold = set(relevant)
    return sum(1.0 / math.log2(rank + 1) for rank, doc_id in enumerate(ranking[:k], start=1) if doc_id in gold)


def ndcg_at_k(ranking: Sequence[str], relevant: Iterable[str], k: int = 3) -> float:
    gold = set(relevant)
    if not gold:
        return 0.0
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg_at_k(ranking, gold, k) / idcg if idcg else 0.0


def mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def evaluate(rankings: dict[str, list[str]], qrels: dict[str, dict], *, k: int = 3) -> dict:
    """Aggregate the three metrics over answerable queries only.

    Unanswerable queries have no gold document, so including them would mean dividing by zero or
    silently counting them as failures. They are scored separately by the abstention threshold.
    """
    recall, mrr, ndcg, per_query = [], [], [], {}
    for query_id, entry in qrels.items():
        if not entry.get("answerable"):
            continue
        gold = entry.get("relevant_doc_ids") or []
        if not gold:
            continue
        ranking = rankings.get(query_id, [])
        r = recall_at_k(ranking, gold, k)
        m = mrr_at_k(ranking, gold, k)
        n = ndcg_at_k(ranking, gold, k)
        recall.append(r)
        mrr.append(m)
        ndcg.append(n)
        per_query[query_id] = {"recall": r, "mrr": round(m, 4), "ndcg": round(n, 4)}

    return {
        "k": k,
        "queries": len(recall),
        f"recall@{k}": mean(recall),
        f"mrr@{k}": mean(mrr),
        f"ndcg@{k}": mean(ndcg),
        "per_query": per_query,
    }


def bootstrap_ci(values: Sequence[float], *, n_resamples: int = 2000, seed: int = 20261015,
                 level: float = 0.95) -> dict:
    """Percentile bootstrap over queries.

    The interval measures uncertainty from having only a handful of queries. It does not account
    for the fact that several dev queries paraphrase the same underlying question, so it is
    optimistic about how well the score generalises to genuinely new questions.
    """
    if not values:
        return {"low": None, "high": None, "n": 0}
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(n_resamples):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(draw) / n)
    samples.sort()
    alpha = (1.0 - level) / 2.0
    low = samples[int(alpha * n_resamples)]
    high = samples[int((1.0 - alpha) * n_resamples) - 1]
    return {"low": round(low, 4), "high": round(high, 4), "n": n,
            "resamples": n_resamples, "seed": seed, "mean": round(sum(values) / n, 4)}


def balanced_accuracy(y_true: Sequence[bool], y_pred: Sequence[bool]) -> float:
    """Mean of sensitivity and specificity, so a lazy all-positive model cannot win."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    sensitivity = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return 0.5 * (sensitivity + specificity)


def choose_threshold(scores: Sequence[float], labels: Sequence[bool]) -> dict:
    """Pick the max-cosine threshold that maximises balanced accuracy on dev.

    Ties are broken toward the **larger** threshold, as the assignment requires: among equally
    accurate cut-offs, the more conservative one abstains more and invents less.
    """
    candidates = sorted({0.0, 1.0, *[round(s, 6) for s in scores]})
    best = None
    for threshold in candidates:
        predicted = [score >= threshold for score in scores]
        score_ba = balanced_accuracy(labels, predicted)
        if best is None or score_ba > best["balanced_accuracy"] + 1e-12 or (
            abs(score_ba - best["balanced_accuracy"]) <= 1e-12 and threshold > best["threshold"]
        ):
            best = {"threshold": threshold, "balanced_accuracy": round(score_ba, 4)}
    predicted = [score >= best["threshold"] for score in scores]
    best.update({
        "accepted": sum(predicted),
        "rejected": len(predicted) - sum(predicted),
        "true_positives": sum(1 for t, p in zip(labels, predicted) if t and p),
        "false_accepts": sum(1 for t, p in zip(labels, predicted) if not t and p),
        "false_rejects": sum(1 for t, p in zip(labels, predicted) if t and not p),
        "true_negatives": sum(1 for t, p in zip(labels, predicted) if not t and not p),
    })
    return best

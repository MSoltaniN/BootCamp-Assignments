"""Section 10 — four-route classifier: split audit, baselines, MLP, calibration, model card.

Run:  .venv\\Scripts\\python.exe work/sec10_router/run_section10.py
Writes: work/sec10_router/artifacts/*
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from work._common.config import MODEL_ID, MODEL_REVISION, SEED
from work._common.paths import MODEL_DIR, ROUTER
from work.sec10_router.router import (
    ROUTES,
    accuracy,
    build_mlp,
    clarify_fallback,
    confusion_matrix,
    count_parameters,
    coverage_table,
    macro_f1,
    rule_matrix,
)

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(exist_ok=True)
results: dict = {}

torch.manual_seed(SEED)
np.random.seed(SEED)
torch.use_deterministic_algorithms(False)


def head(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


df = pd.read_csv(ROUTER / "requests.csv")
train = df[df["split"] == "train"].reset_index(drop=True)
dev = df[df["split"] == "dev"].reset_index(drop=True)
test = df[df["split"] == "test"].reset_index(drop=True)

# ---------------------------------------------------------------- 10.1
head("10.1  class and split distribution, template_group leakage check")
print("rows:", len(df))
print("split sizes:", df["split"].value_counts().to_dict())
print("route counts overall:", df["route"].value_counts().to_dict())
for split, frame in (("train", train), ("dev", dev), ("test", test)):
    print(f"  {split:5s}: rows={len(frame)} groups={frame['template_group'].nunique()} "
          f"classes={frame['route'].value_counts().to_dict()}")

train_groups = set(train["template_group"])
dev_groups = set(dev["template_group"])
test_groups = set(test["template_group"])
shared = (train_groups & dev_groups) | (train_groups & test_groups) | (dev_groups & test_groups)
print("template groups: train", len(train_groups), "dev", len(dev_groups), "test", len(test_groups))
print("groups shared between splits:", len(shared))
print("majority-class share in test:", round(test["route"].value_counts(normalize=True).max(), 4))
print("grouping is by template, so every split contains unseen phrasings rather than unseen words")
results["10.1"] = {"requests": len(df), "shared_groups": len(shared),
                   "splits": {k: int(v) for k, v in df["split"].value_counts().items()},
                   "groups": {"train": len(train_groups), "dev": len(dev_groups), "test": len(test_groups)}}

# ---------------------------------------------------------------- 10.2
head("10.2  rule-based baseline, designed from train examples only")
print("sample train phrasings per route:")
for route in ROUTES:
    print(f"  {route:11s}: {train[train['route'] == route]['query'].head(2).tolist()}")

rule_dev = list(rule_matrix(dev["query"].tolist()))
rule_dev_acc = accuracy(dev["route"].tolist(), rule_dev)
rule_dev_f1 = macro_f1(dev["route"].tolist(), rule_dev)
print("rule baseline dev accuracy:", rule_dev_acc)
print("rule baseline dev macro-F1:", rule_dev_f1)
print("rule predictions on dev:", dict(Counter(rule_dev)))
results["10.2"] = {"dev_accuracy": rule_dev_acc, "dev_macro_f1": rule_dev_f1}

# ---------------------------------------------------------------- 10.3
head("10.3  TF-IDF(1,2) + LogisticRegression, C chosen by dev macro-F1")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

best_c, best_f1, c_rows = None, -1.0, []
for c in (0.1, 1.0, 10.0):
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)),
        ("clf", LogisticRegression(C=c, max_iter=2000, random_state=SEED)),
    ])
    pipeline.fit(train["query"], train["route"])          # vocabulary sees train only
    predicted = list(pipeline.predict(dev["query"]))
    f1 = macro_f1(dev["route"].tolist(), predicted)
    acc = accuracy(dev["route"].tolist(), predicted)
    c_rows.append({"C": c, "dev_macro_f1": f1, "dev_accuracy": acc})
    print(f"C={c:5.1f}  dev macro-F1={f1}  dev accuracy={acc}")
    if f1 > best_f1:
        best_c, best_f1 = c, f1

print("selected C:", best_c, "| dev macro-F1:", best_f1)
linear = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)),
    ("clf", LogisticRegression(C=best_c, max_iter=2000, random_state=SEED)),
]).fit(train["query"], train["route"])
linear_dev = list(linear.predict(dev["query"]))
print("vocabulary size (train only):", len(linear.named_steps["tfidf"].vocabulary_))
results["10.3"] = {"C": best_c, "dev_macro_f1": best_f1, "grid": c_rows,
                   "vocab": len(linear.named_steps["tfidf"].vocabulary_)}

# ---------------------------------------------------------------- 10.4
head("10.4  frozen embedding features")
from sentence_transformers import SentenceTransformer

encoder = SentenceTransformer(str(MODEL_DIR), device="cpu")
X_train = encoder.encode(train["query"].tolist(), batch_size=64, normalize_embeddings=True,
                         convert_to_numpy=True)
X_dev = encoder.encode(dev["query"].tolist(), batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
X_test = encoder.encode(test["query"].tolist(), batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
for name, matrix in (("train", X_train), ("dev", X_dev), ("test", X_test)):
    norms = np.linalg.norm(matrix, axis=1)
    print(f"{name:5s} shape={matrix.shape} min_norm={norms.min():.4f} max_norm={norms.max():.4f}")
print("encoder is frozen: features are extracted once, no gradient reaches it")
print("difference from fine-tuning: fine-tuning would update encoder weights and needs a training loop")
results["10.4"] = {"train_shape": list(X_train.shape), "dev_shape": list(X_dev.shape),
                   "test_shape": list(X_test.shape)}

# ---------------------------------------------------------------- 10.5
head("10.5  MLP architecture and parameter count")
label_index = {route: i for i, route in enumerate(ROUTES)}
y_train = np.array([label_index[r] for r in train["route"]])
y_dev = np.array([label_index[r] for r in dev["route"]])
y_test = np.array([label_index[r] for r in test["route"]])

network = build_mlp(384, 64, 4, 0.1)
param_info = count_parameters(network)
print("layers:")
for name, shape, size in param_info["layers"]:
    print(f"  {name:12s} shape={shape} params={size}")
print("total trainable:", param_info["total"], "| manual:", param_info["manual"],
      "| matches:", param_info["matches"])
sample_logits = network(torch.tensor(X_dev[:2], dtype=torch.float32))
print("input shape:", tuple(X_dev.shape), "-> output shape:", tuple(sample_logits.shape))
results["10.5"] = {"trainable_params": param_info["total"], "manual": param_info["manual"],
                   "matches": param_info["matches"], "layers": param_info["layers"]}

# ---------------------------------------------------------------- 10.6
head("10.6  train with AdamW lr=0.003, batch=32, max 60 epochs, patience=10 on dev macro-F1")
train_tensor = torch.tensor(X_train, dtype=torch.float32)
dev_tensor = torch.tensor(X_dev, dtype=torch.float32)
train_labels = torch.tensor(y_train, dtype=torch.long)
dev_labels = torch.tensor(y_dev, dtype=torch.long)

torch.manual_seed(SEED)
model = build_mlp(384, 64, 4, 0.1)
optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
criterion = nn.CrossEntropyLoss()

BATCH, MAX_EPOCHS, PATIENCE = 32, 60, 10
best_state, best_epoch, best_dev_f1 = None, 0, -1.0
epochs_run = 0
history = []
patience_left = PATIENCE

for epoch in range(1, MAX_EPOCHS + 1):
    model.train()
    permutation = torch.randperm(len(train_tensor))
    epoch_loss = 0.0
    for start in range(0, len(train_tensor), BATCH):
        batch = permutation[start:start + BATCH]
        optimizer.zero_grad()
        logits = model(train_tensor[batch])
        loss = criterion(logits, train_labels[batch])
        loss.backward()
        optimizer.step()
        epoch_loss += loss.detach().item() * len(batch)
    epoch_loss /= len(train_tensor)

    model.eval()
    with torch.no_grad():
        dev_logits = model(dev_tensor)
        dev_pred = dev_logits.argmax(dim=1).numpy()
    dev_pred_labels = [ROUTES[i] for i in dev_pred]
    dev_f1 = macro_f1(dev["route"].tolist(), dev_pred_labels)
    history.append({"epoch": epoch, "train_loss": round(epoch_loss, 4), "dev_macro_f1": dev_f1})
    epochs_run = epoch

    if dev_f1 > best_dev_f1:
        best_dev_f1, best_epoch = dev_f1, epoch
        best_state = {k: v.clone() for k, v in model.state_dict().items()}
        patience_left = PATIENCE
    else:
        patience_left -= 1
        if patience_left <= 0:
            print(f"early stop at epoch {epoch}")
            break

print("epochs run:", epochs_run, "| best epoch:", best_epoch, "| best dev macro-F1:", best_dev_f1)
print("loss curve (every 5th epoch):",
      [(h["epoch"], h["train_loss"], h["dev_macro_f1"]) for h in history[::5]])
model.load_state_dict(best_state)
torch.save({"state_dict": best_state, "classes": ROUTES, "input_dim": 384, "hidden": 64, "dropout": 0.1},
           ART / "router_mlp.pt")
print("checkpoint saved to artifacts/router_mlp.pt")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
axes[0].plot([h["epoch"] for h in history], [h["train_loss"] for h in history])
axes[0].set_title("train loss"); axes[0].set_xlabel("epoch")
axes[1].plot([h["epoch"] for h in history], [h["dev_macro_f1"] for h in history], color="#2d7d46")
axes[1].axvline(best_epoch, ls="--", color="grey")
axes[1].set_title("dev macro-F1"); axes[1].set_xlabel("epoch")
fig.tight_layout(); fig.savefig(ART / "training_curves.png", dpi=120); plt.close(fig)
print("curves saved to artifacts/training_curves.png")
results["10.6"] = {"epochs": epochs_run, "best_epoch": best_epoch, "best_dev_macro_f1": best_dev_f1,
                   "history": history}

# ---------------------------------------------------------------- 10.7
head("10.7  compare the three models on test once, parameters now frozen")
rule_test = list(rule_matrix(test["query"].tolist()))
linear_test = list(linear.predict(test["query"]))
model.eval()
with torch.no_grad():
    test_probs = torch.softmax(model(torch.tensor(X_test, dtype=torch.float32)), dim=1).numpy()
mlp_test = [ROUTES[int(i)] for i in test_probs.argmax(axis=1)]

comparison = []
for name, predicted in (("rules", rule_test), ("linear", linear_test), ("mlp", mlp_test)):
    row = {"model": name, "accuracy": accuracy(test["route"].tolist(), predicted),
           "macro_f1": macro_f1(test["route"].tolist(), predicted)}
    comparison.append(row)
    print(f"{name:7s} test accuracy={row['accuracy']}  macro-F1={row['macro_f1']}")

matrix = confusion_matrix(test["route"].tolist(), mlp_test)
print("MLP confusion matrix (rows=true, cols=pred), order:", ROUTES)
for label, row in zip(ROUTES, matrix):
    print(f"  {label:11s} {row}")
results["10.7"] = {"comparison": comparison, "confusion": matrix, "labels": ROUTES}

# ---------------------------------------------------------------- 10.8
head("10.8  coverage and conditional accuracy on dev at 0.5 / 0.7 / 0.9")
model.eval()
with torch.no_grad():
    dev_probs = torch.softmax(model(dev_tensor), dim=1).numpy()
coverage = coverage_table(dev_probs, dev["route"].tolist())
for row in coverage:
    print(f"threshold={row['threshold']}: coverage={row['coverage']} "
          f"conditional_accuracy={row['conditional_accuracy']} accepted={row['accepted']}")
print("softmax max is a confidence score, not a calibrated probability")
results["10.8"] = coverage

# ---------------------------------------------------------------- 10.9
head("10.9  fallback to clarify below a fixed 0.7 confidence")
fallback = clarify_fallback(dev_probs, threshold=0.7)
print("clarify needed:", fallback["clarify_count"], "of", fallback["total"])
print("confident unsupported:", fallback["confident_unsupported"],
      "| low-confidence unsupported:", fallback["low_confidence_unsupported"])
print("unsupported is a class, not a confidence level; the two counts are kept apart")
results["10.9"] = {k: v for k, v in fallback.items() if k != "clarify_indices"}

# ---------------------------------------------------------------- 10.10
head("10.10  three test errors of the MLP")
errors = []
for i, (true_label, pred_label) in enumerate(zip(test["route"], mlp_test)):
    if true_label != pred_label:
        errors.append({
            "request_id": test.loc[i, "request_id"], "query": test.loc[i, "query"],
            "true": true_label, "predicted": pred_label,
            "confidence": round(float(test_probs[i].max()), 4),
            "template_group": test.loc[i, "template_group"],
        })
print("test errors:", len(errors))
review_mode = "errors" if errors else "lowest_confidence"
if not errors:
    order = np.argsort(-test_probs.max(axis=1))[::-1][:2]
    low = [{"request_id": test.loc[i, "request_id"], "query": test.loc[i, "query"],
            "true": test.loc[i, "route"], "predicted": mlp_test[i],
            "confidence": round(float(test_probs[i].max()), 4)} for i in order]
    print("no errors; falling back to two lowest-confidence correct cases as declared")
    for row in low:
        print(f"  {row['request_id']} conf={row['confidence']} true={row['true']} -> {row['predicted']}")
    shown = low
else:
    for row in errors[:3]:
        print(f"  {row['request_id']} conf={row['confidence']} true={row['true']} -> {row['predicted']}")
        print(f"     Q: {row['query']}")
    shown = errors[:3]
results["10.10"] = {"test_errors": len(errors), "review_mode": review_mode, "shown": shown}

# ---------------------------------------------------------------- 10.11
head("10.11  mask the ten topics with TOPIC and re-score the frozen linear model")
# The topic is the only slot that varies inside a template group. Ten topics x 12 phrasings x 4
# routes x ... gives 480 rows, and each topic appears 40 times across the whole file.
TOPICS = ["typing", "packaging", "async functions", "code style", "generators",
          "pattern matching", "exceptions", "versions", "data classes", "coroutines"]
observed = {t: int(df["query"].str.contains(re.escape(t), case=False, regex=True).sum()) for t in TOPICS}
print("topics:", len(TOPICS), TOPICS)
print("occurrences per topic:", observed)
print("longest first, so 'async functions' is replaced before a shorter substring could match")
TOPICS_SORTED = sorted(TOPICS, key=len, reverse=True)

def mask_topics(text: str) -> str:
    for topic in TOPICS_SORTED:
        text = re.sub(re.escape(topic), "TOPIC", text, flags=re.I)
    return text


masked_train = [mask_topics(text) for text in train["query"]]
masked_dev = [mask_topics(text) for text in dev["query"]]
still_leaking = sum(1 for text in masked_train + masked_dev
                    if any(topic.lower() in text.lower() for topic in TOPICS))
print("rows still containing a topic word after masking:", still_leaking)

print("example before:", train["query"].iloc[0])
print("example after :", masked_train[0])

masked_linear = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)),
    ("clf", LogisticRegression(C=best_c, max_iter=2000, random_state=SEED)),
]).fit(masked_train, train["route"])
masked_pred = list(masked_linear.predict(masked_dev))
masked_f1 = macro_f1(dev["route"].tolist(), masked_pred)
baseline_f1 = macro_f1(dev["route"].tolist(), linear_dev)
print("macro-F1 before masking:", baseline_f1)
print("macro-F1 after masking :", masked_f1)
print("delta:", round(masked_f1 - baseline_f1, 4))
print("the frozen model was refit on train only; dev was never used for training")
results["10.11"] = {"masked_macro_f1": masked_f1, "baseline_macro_f1": baseline_f1,
                    "delta": round(masked_f1 - baseline_f1, 4), "topics": len(TOPICS),
                    "leaking_rows": still_leaking}

# ---------------------------------------------------------------- 10.12
head("10.12  model card, saved weights and class order")
best_model_name = max(comparison, key=lambda r: (r["macro_f1"], r["accuracy"]))["model"]
model_card = {
    "name": "day3-route-classifier",
    "version": "1.0.0",
    "origin": "synthetic request templates generated for the bootcamp; not real user traffic",
    "data": {
        "rows": len(df),
        "split": "grouped by template_group; no group appears in more than one split",
        "splits": {k: int(v) for k, v in df["split"].value_counts().items()},
        "classes": ROUTES,
        "class_balance": {k: int(v) for k, v in df["route"].value_counts().items()},
    },
    "features": {
        "rules": "hand-written patterns",
        "linear": f"TF-IDF unigram+bigram, C={best_c}",
        "mlp": "frozen sentence-transformers embeddings, 384 dims",
        "encoder": {"model_id": MODEL_ID, "revision": MODEL_REVISION},
    },
    "metrics": {"test_comparison": comparison,
                "dev_macro_f1": {"rules": rule_dev_f1, "linear": baseline_f1, "mlp": best_dev_f1}},
    "deployment_choice": best_model_name,
    "deployment_reason": "highest test macro-F1, and macro-F1 weights all four routes equally, "
                         "which matters because a missed 'unsupported' is a safety issue",
    "language_domain": "English software-documentation requests from one synthetic template set",
    "intended_use": "choosing which tool the workflow may call in this teaching project",
    "unsuitable_use": [
        "any language other than English",
        "real user traffic with phrasings unlike these templates",
        "safety-critical routing without human review",
        "deciding permissions or access control",
    ],
    "class_order": ROUTES,
    "weights_path": "artifacts/router_mlp.pt",
    "known_limitations": [
        "The data is synthetic and generated from templates; accuracy reflects template structure.",
        "A random split would leak template patterns and inflate every score.",
        "Confidence is softmax output, not a calibrated probability.",
        "The MLP sees 384-dim sentence embeddings, so it cannot use exact token cues a rule can.",
    ],
}
(ART / "model_card.json").write_text(json.dumps(model_card, indent=2), encoding="utf-8")
weights_exist = (ART / "router_mlp.pt").exists()
print("deployment choice:", best_model_name, "| reason recorded")
print("weights saved:", weights_exist, "| class order stored:", ROUTES)
print("model card written to artifacts/model_card.json")
results["10.12"] = {"weights_saved": weights_exist, "class_order": ROUTES,
                    "deployment_choice": best_model_name}

(ART / "router_report.json").write_text(json.dumps({"seed": SEED, "results": results}, indent=2),
                                       encoding="utf-8")
print("\nartifacts written to", ART)

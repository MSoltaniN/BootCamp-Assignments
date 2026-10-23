import os, sys, json, time
PKGS = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
sys.path.insert(0, PKGS)
import pandas as pd, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, accuracy_score, classification_report

ROOT = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning"
DATA = os.path.join(ROOT, "persian-news-6")
tr = pd.read_csv(os.path.join(DATA, "train.csv"))
va = pd.read_csv(os.path.join(DATA, "val.csv"))
te = pd.read_csv(os.path.join(DATA, "test.csv"))

results = []
best = None
t0 = time.time()
for ngram in [(1, 1), (1, 2)]:
    for C in [1.0, 3.0, 10.0]:
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=ngram, min_df=2, sublinear_tf=True,
                                      max_features=200000)),
            ("clf", LogisticRegression(C=C, max_iter=2000, n_jobs=16)),
        ])
        pipe.fit(tr["text"], tr["label"])
        pred = pipe.predict(va["text"])
        f1 = f1_score(va["label"], pred, average="macro")
        acc = accuracy_score(va["label"], pred)
        results.append({"ngram": str(ngram), "C": C, "macro_f1": round(f1, 4),
                        "acc": round(acc, 4)})
        print(f"ngram={ngram} C={C:5.1f}  val acc={acc:.4f}  val macroF1={f1:.4f}", flush=True)
        if best is None or f1 > best[0]:
            best = (f1, acc, ngram, C, pipe, pred)

f1, acc, ngram, C, pipe, pred = best
print(f"\nBEST baseline: ngram={ngram} C={C} acc={acc:.4f} f1={f1:.4f} ({time.time()-t0:.1f}s)")
print(classification_report(va["label"], pred, digits=4))

test_pred = pipe.predict(te["text"])
json.dump({"grid": results,
           "best": {"ngram": str(ngram), "C": C, "val_acc": acc, "val_macro_f1": f1},
           "test_distribution": pd.Series(test_pred).value_counts().to_dict()},
          open(os.path.join(ROOT, "run", "baseline.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\nSAVED baseline.json")

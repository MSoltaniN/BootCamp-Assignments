import os, sys, json, time
import numpy as np

PKGS = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
sys.path.insert(0, PKGS)

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import transformers, tokenizers, torch
print("transformers", transformers.__version__)
print("tokenizers  ", tokenizers.__version__)
print("torch       ", torch.__version__)

MODEL_DIR = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\model\bert-fa-zwnj-base"
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
print("tokenizer class:", type(tok).__name__, "| is_fast:", getattr(tok, "is_fast", None))

S1 = "مدل\u200cهای زبانی بزرگ، متن\u200cهای فارسی را بهتر از گذشته می\u200cفهمند."
enc = tok(S1)
ids = enc["input_ids"]
print("\n=== Q1.1 ===")
print("sentence:", S1)
print("n tokens:", len(ids))
print("tokens:", tok.convert_ids_to_tokens(ids))

W = "دانش\u200cآموزان"
print("\n=== Q1.2 ===")
w_ids = tok(W)["input_ids"]
print("word:", W, "n:", len(w_ids))
print("tokens:", tok.convert_ids_to_tokens(w_ids))

print("\n=== Q1.3  ZWNJ behaviour ===")
for w in ["مدل\u200cهای", "مدلهای", "مدل های"]:
    ii = tok(w)["input_ids"]
    print(repr(w), "->", tok.convert_ids_to_tokens(ii))

# --- token length distribution over train.csv
import pandas as pd
DATA = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\persian-news-6"
tr = pd.read_csv(os.path.join(DATA, "train.csv"))
va = pd.read_csv(os.path.join(DATA, "val.csv"))
te = pd.read_csv(os.path.join(DATA, "test.csv"))

t0 = time.time()
lens = np.array([len(x) for x in tok(tr["text"].tolist(), add_special_tokens=True,
                                     truncation=False, padding=False)["input_ids"]])
print(f"\ntokenized train in {time.time()-t0:.1f}s")
print("\n=== Q1.4  max token length (with specials) ===")
print("max:", lens.max(), "| mean:", round(lens.mean(), 1), "| median:", int(np.median(lens)))
for q in [50, 90, 95, 99, 99.5, 100]:
    print(f"  p{q}: {int(np.percentile(lens, q))}")
print("count > 128:", int((lens > 128).sum()), f"({(lens>128).mean()*100:.1f}%)")
print("count > 160:", int((lens > 160).sum()), f"({(lens>160).mean()*100:.1f}%)")
print("count > 192:", int((lens > 192).sum()), f"({(lens>192).mean()*100:.1f}%)")
print("count > 256:", int((lens > 256).sum()), f"({(lens>256).mean()*100:.1f}%)")
print("count > 384:", int((lens > 384).sum()), f"({(lens>384).mean()*100:.1f}%)")
print("count > 512:", int((lens > 512).sum()), f"({(lens>512).mean()*100:.1f}%)")

val_lens = np.array([len(x) for x in tok(va["text"].tolist(), add_special_tokens=True,
                                          truncation=False, padding=False)["input_ids"]])
test_lens = np.array([len(x) for x in tok(te["text"].tolist(), add_special_tokens=True,
                                           truncation=False, padding=False)["input_ids"]])
print("val max:", val_lens.max(), "| test max:", test_lens.max())

# fraction of tokens kept at various max_length
print("\ntoken coverage by max_length:")
for ml in [64, 96, 128, 160, 192, 256]:
    kept = np.minimum(lens, ml).sum() / lens.sum()
    trunc = (lens > ml).mean() * 100
    print(f"  max_len={ml:3d}: {trunc:5.2f}% of texts truncated, {kept*100:5.2f}% of all tokens kept")

import pickle
with open(r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\_lens.pkl", "wb") as f:
    pickle.dump({"train": lens, "val": val_lens, "test": test_lens}, f)

json.dump({
    "transformers": transformers.__version__,
    "tokenizers": tokenizers.__version__,
    "torch": torch.__version__,
    "s1_tokens": tok.convert_ids_to_tokens(ids),
    "s1_len": len(ids),
    "danesh_tokens": tok.convert_ids_to_tokens(w_ids),
    "max_train_len": int(lens.max()),
    "len_mean": float(lens.mean()),
    "len_median": float(np.median(lens)),
    "p90": int(np.percentile(lens, 90)),
    "p95": int(np.percentile(lens, 95)),
    "p99": int(np.percentile(lens, 99)),
    "n_over_128": int((lens > 128).sum()),
    "n_over_160": int((lens > 160).sum()),
    "n_over_192": int((lens > 192).sum()),
    "n_over_256": int((lens > 256).sum()),
    "n_over_384": int((lens > 384).sum()),
    "n_over_512": int((lens > 512).sum()),
    "n_train": int(len(lens)),
}, open(r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\_tok_stats.json", "w", encoding="utf-8"),
    ensure_ascii=False, indent=2)
print("\nSAVED")

"""Q4.3: freeze the BERT backbone, train only the classifier head. Compare acc/time."""
import os, sys, time, json, random
PKGS = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
sys.path.insert(0, PKGS)
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch, numpy as np, pandas as pd
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import f1_score, accuracy_score

ROOT = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning"
MODEL_DIR = os.path.join(ROOT, "model", "bert-fa-zwnj-base")
DATA = os.path.join(ROOT, "persian-news-6")
RUN = os.path.join(ROOT, "run")

MAX_LEN, BATCH, LR, WD = 128, 16, 1e-3, 0.0
torch.set_num_threads(16)
random.seed(42); np.random.seed(42); torch.manual_seed(42)

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
tr = pd.read_csv(os.path.join(DATA, "train.csv")); va = pd.read_csv(os.path.join(DATA, "val.csv"))
labels = sorted(tr["label"].unique().tolist())
l2i = {l: i for i, l in enumerate(labels)}; i2l = {i: l for l, i in l2i.items()}

class DS(Dataset):
    def __init__(self, t, y): self.t, self.y = t, y
    def __len__(self): return len(self.t)
    def __getitem__(self, i): return {"text": self.t[i], "label": self.y[i]}

def collate(b):
    enc = tok([x["text"] for x in b], padding="longest", truncation=True,
              max_length=MAX_LEN, return_tensors="pt")
    enc["labels"] = torch.tensor([x["label"] for x in b], dtype=torch.long)
    return enc

tr_dl = DataLoader(DS(tr["text"].tolist(), [l2i[l] for l in tr["label"]]),
                   batch_size=BATCH, shuffle=True, collate_fn=collate)
va_dl = DataLoader(DS(va["text"].tolist(), [l2i[l] for l in va["label"]]),
                   batch_size=64, shuffle=False, collate_fn=collate)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, num_labels=6).train()
for p in model.bert.parameters():
    p.requires_grad = False
for p in model.classifier.parameters():
    p.requires_grad = True
n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"trainable after freeze: {n_train:,}", flush=True)

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR, weight_decay=WD)

t0 = time.time()
step = 0
for batch in tr_dl:
    out = model(**batch)
    out.loss.backward()
    torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
    opt.step(); opt.zero_grad(); step += 1
    if step % 60 == 0:
        print(f"  step {step}/{len(tr_dl)} elapsed={time.time()-t0:.0f}s", flush=True)
epoch_time = time.time() - t0

model.eval()
preds, trues = [], []
with torch.no_grad():
    for batch in va_dl:
        preds.extend(model(**batch).logits.argmax(-1).tolist())
        trues.extend(batch["labels"].tolist())
acc = accuracy_score(trues, preds); f1 = f1_score(trues, preds, average="macro")
print(f"FROZEN 1 epoch: acc={acc:.4f} macroF1={f1:.4f} time={epoch_time:.0f}s", flush=True)

json.dump({"acc": acc, "macro_f1": f1, "epoch_time_s": epoch_time, "lr": LR,
           "trainable_params": n_train, "epochs": 1,
           "steps_per_epoch": len(tr_dl)},
          open(os.path.join(RUN, "frozen_bert.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("SAVED frozen_bert.json", flush=True)

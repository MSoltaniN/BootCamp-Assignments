"""Q4.3 (extended): frozen BERT backbone, 3 epochs, per-epoch val metrics."""
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

MAX_LEN, BATCH, LR, EPOCHS = 128, 16, 1e-3, 3
torch.set_num_threads(16)
random.seed(42); np.random.seed(42); torch.manual_seed(42)

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
tr = pd.read_csv(os.path.join(DATA, "train.csv")); va = pd.read_csv(os.path.join(DATA, "val.csv"))
labels = sorted(tr["label"].unique().tolist())
l2i = {l: i for i, l in enumerate(labels)}

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
trainable = [p for p in model.parameters() if p.requires_grad]
print("trainable params:", sum(p.numel() for p in trainable), flush=True)
opt = torch.optim.AdamW(trainable, lr=LR)

hist = []
t0 = time.time()
for ep in range(1, EPOCHS + 1):
    model.train()
    run, n = 0.0, 0
    for batch in tr_dl:
        out = model(**batch)
        out.loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        opt.step(); opt.zero_grad()
        run += out.loss.item() * batch["labels"].shape[0]; n += batch["labels"].shape[0]

    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for batch in va_dl:
            preds.extend(model(**batch).logits.argmax(-1).tolist())
            trues.extend(batch["labels"].tolist())
    acc = accuracy_score(trues, preds); f1 = f1_score(trues, preds, average="macro")
    rec = {"epoch": ep, "train_loss": run / n, "val_acc": acc, "val_macro_f1": f1,
           "elapsed_s": time.time() - t0}
    hist.append(rec)
    print(f"EPOCH {ep}: train_loss={run/n:.4f} val_acc={acc:.4f} val_f1={f1:.4f} "
          f"total_elapsed={rec['elapsed_s']:.0f}s", flush=True)

json.dump({"epochs": hist, "lr": LR, "batch": BATCH, "epochs_run": EPOCHS,
           "trainable_params": sum(p.numel() for p in trainable)},
          open(os.path.join(RUN, "frozen_bert_3ep.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("SAVED", flush=True)

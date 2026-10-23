"""Fine-tune ParsBERT on persian-news-6; log everything needed for the assignment."""
import os, sys, time, json, random
PKGS = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
sys.path.insert(0, PKGS)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch, numpy as np, pandas as pd
from torch.utils.data import Dataset, DataLoader
from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                          get_linear_schedule_with_warmup)
from sklearn.metrics import f1_score, accuracy_score, classification_report, confusion_matrix

ROOT = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning"
MODEL_DIR = os.path.join(ROOT, "model", "bert-fa-zwnj-base")
DATA = os.path.join(ROOT, "persian-news-6")
OUT = os.path.join(ROOT, "run")
os.makedirs(OUT, exist_ok=True)

SEED = 42
MAX_LEN = 128
BATCH = 16
EPOCHS = 3
LR = 3e-5
WD = 0.01
WARMUP_RATIO = 0.1
THREADS = 16

torch.set_num_threads(THREADS)
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

print(f"threads={THREADS} batch={BATCH} epochs={EPOCHS} lr={LR} max_len={MAX_LEN}", flush=True)

tok = AutoTokenizer.from_pretrained(MODEL_DIR)
tr = pd.read_csv(os.path.join(DATA, "train.csv"))
va = pd.read_csv(os.path.join(DATA, "val.csv"))
te = pd.read_csv(os.path.join(DATA, "test.csv"))

labels = sorted(tr["label"].unique().tolist())
label2id = {l: i for i, l in enumerate(labels)}
id2label = {i: l for l, i in label2id.items()}
print("labels:", labels, flush=True)

class NewsDS(Dataset):
    def __init__(self, texts, labels=None):
        self.texts = texts
        self.labels = labels

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        item = {"text": self.texts[i]}
        if self.labels is not None:
            item["label"] = self.labels[i]
        return item

def collate(batch):
    texts = [b["text"] for b in batch]
    enc = tok(texts, padding="longest", truncation=True, max_length=MAX_LEN, return_tensors="pt")
    if "label" in batch[0]:
        enc["labels"] = torch.tensor([b["label"] for b in batch], dtype=torch.long)
    return enc

tr_ds = NewsDS(tr["text"].tolist(), [label2id[l] for l in tr["label"]])
va_ds = NewsDS(va["text"].tolist(), [label2id[l] for l in va["label"]])
te_ds = NewsDS(te["text"].tolist())

g = torch.Generator(); g.manual_seed(SEED)
tr_dl = DataLoader(tr_ds, batch_size=BATCH, shuffle=True, collate_fn=collate, generator=g)
va_dl = DataLoader(va_ds, batch_size=64, shuffle=False, collate_fn=collate)
te_dl = DataLoader(te_ds, batch_size=64, shuffle=False, collate_fn=collate)

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_DIR, num_labels=len(labels), id2label=id2label, label2id=label2id)
model.train()

n_all = sum(p.numel() for p in model.parameters())
n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
n_cls = sum(p.numel() for p in model.classifier.parameters())
print(f"PARAMS total={n_all:,} trainable={n_train:,} classifier={n_cls:,} backbone={n_all-n_cls:,}", flush=True)

steps_per_epoch = len(tr_dl)
total_steps = steps_per_epoch * EPOCHS
warmup_steps = int(WARMUP_RATIO * total_steps)
print(f"steps/epoch={steps_per_epoch} total={total_steps} warmup={warmup_steps}", flush=True)

no_decay = ["bias", "LayerNorm.weight"]
opt_groups = [
    {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
     "weight_decay": WD},
    {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
     "weight_decay": 0.0},
]
opt = torch.optim.AdamW(opt_groups, lr=LR, betas=(0.9, 0.999), eps=1e-8)
sched = get_linear_schedule_with_warmup(opt, warmup_steps, total_steps)

@torch.no_grad()
def evaluate(dl, with_labels=True):
    model.eval()
    tot, n = 0.0, 0
    preds, trues, probs = [], [], []
    for batch in dl:
        out = model(**batch)
        if with_labels:
            bs = batch["labels"].shape[0]
            tot += out.loss.item() * bs; n += bs
            preds.extend(out.logits.argmax(-1).tolist())
            trues.extend(batch["labels"].tolist())
        probs.append(torch.softmax(out.logits, dim=-1))
    model.train()
    res = {"loss": tot / max(n, 1) if with_labels else None, "probs": torch.cat(probs)}
    if with_labels:
        res["preds"] = preds; res["trues"] = trues
        res["acc"] = accuracy_score(trues, preds)
        res["macro_f1"] = f1_score(trues, preds, average="macro")
    return res

# ---- Q2.3: validation loss BEFORE any training step
t0 = time.time()
pre = evaluate(va_dl)
print(f"PRE-TRAIN val loss = {pre['loss']:.4f}  acc={pre['acc']:.4f} f1={pre['macro_f1']:.4f} ({time.time()-t0:.0f}s)", flush=True)
print(f"ln(6) = {np.log(6):.4f}", flush=True)

history = {"pre_train_val_loss": pre["loss"], "steps": [], "epochs": []}
global_step = 0
t_start = time.time()

for ep in range(1, EPOCHS + 1):
    model.train()
    run_loss, run_n = 0.0, 0
    t_ep = time.time()
    for batch in tr_dl:
        out = model(**batch)
        out.loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad()
        global_step += 1
        run_loss += out.loss.item() * batch["labels"].shape[0]
        run_n += batch["labels"].shape[0]
        history["steps"].append({"step": global_step, "epoch": ep,
                                 "loss": out.loss.item(), "lr": sched.get_last_lr()[0],
                                 "t": time.time() - t_start})
        if global_step % 40 == 0:
            print(f"  ep{ep} step {global_step}/{total_steps} loss={run_loss/run_n:.4f} "
                  f"lr={sched.get_last_lr()[0]:.2e} elapsed={time.time()-t_start:.0f}s", flush=True)

    train_loss = run_loss / run_n
    ev = evaluate(va_dl)
    rec = {"epoch": ep, "train_loss": train_loss, "val_loss": ev["loss"],
           "val_acc": ev["acc"], "val_macro_f1": ev["macro_f1"],
           "time_s": time.time() - t_ep, "lr_end": sched.get_last_lr()[0]}
    history["epochs"].append(rec)
    print(f"EPOCH {ep}: train_loss={train_loss:.4f} val_loss={ev['loss']:.4f} "
          f"val_acc={ev['acc']:.4f} val_f1={ev['macro_f1']:.4f} ({rec['time_s']:.0f}s)", flush=True)

# ---- final evaluation on val
final = evaluate(va_dl)
cm = confusion_matrix(final["trues"], final["preds"])
print("\nclassification report (val):", flush=True)
print(classification_report(final["trues"], final["preds"], target_names=labels, digits=4), flush=True)
print("confusion matrix:\n", cm, flush=True)

# ---- test predictions
test_probs = evaluate(te_dl, with_labels=False)["probs"]
test_pred = test_probs.argmax(-1).tolist()
pred_df = pd.DataFrame({"id": te["id"], "label": [id2label[i] for i in test_pred]})
pred_df.to_csv(os.path.join(OUT, "predictions.csv"), index=False, encoding="utf-8")
print("\ntest prediction distribution:\n", pred_df["label"].value_counts(), flush=True)

# ---- probe sentences (Q4.1)
probes = {
    "الف": "باشگاه استقلال برای جبران زیان مالی، بخشی از سهام خود را در بورس عرضه می‌کند.",
    "ب": "وزیر بهداشت در سفر به ژنو با مدیرکل سازمان جهانی بهداشت دربارهٔ واکسن کرونا گفتگو کرد.",
    "ج": "مجلس طرح حمایت از شرکت‌های دانش‌بنیان در حوزهٔ هوش مصنوعی را تصویب کرد.",
}
probe_out = {}
model.eval()
with torch.no_grad():
    for k, txt in probes.items():
        enc = tok(txt, return_tensors="pt", truncation=True, max_length=MAX_LEN)
        logits = model(**enc).logits[0]
        p = torch.softmax(logits, -1)
        order = torch.argsort(p, descending=True)
        probe_out[k] = {"text": txt,
                        "pred": id2label[order[0].item()],
                        "probs": {id2label[i.item()]: round(float(p[i]), 4) for i in order}}
        print(f"probe {k}: {probe_out[k]['pred']} -> {probe_out[k]['probs']}", flush=True)

# ---- misclassified val samples (Q4.2)
mis = []
for i in range(len(va)):
    if final["preds"][i] != final["trues"][i]:
        pr = final["probs"][i]
        mis.append({"idx": i, "text": va["text"].iloc[i],
                    "true": id2label[final["trues"][i]],
                    "pred": id2label[final["preds"][i]],
                    "pred_prob": round(float(pr[final["preds"][i]]), 4),
                    "true_prob": round(float(pr[final["trues"][i]]), 4)})
print(f"\nmisclassified val: {len(mis)}/{len(va)}", flush=True)

# ---- save artefacts
torch.save(model.state_dict(), os.path.join(OUT, "model_state.pt"))
model.save_pretrained(os.path.join(OUT, "model_best"))
tok.save_pretrained(os.path.join(ROOT, "model", "bert-fa-zwnj-base"))

np.save(os.path.join(OUT, "val_probs.npy"), final["probs"].numpy())
np.save(os.path.join(OUT, "test_probs.npy"), test_probs.numpy())

summary = {
    "config": {"max_len": MAX_LEN, "batch": BATCH, "epochs": EPOCHS, "lr": LR,
               "weight_decay": WD, "warmup_ratio": WARMUP_RATIO,
               "warmup_steps": warmup_steps, "steps_per_epoch": steps_per_epoch,
               "total_steps": total_steps, "seed": SEED, "threads": THREADS,
               "device": "cpu", "optimizer": "AdamW", "scheduler": "linear + warmup"},
    "params": {"total": n_all, "trainable": n_train, "classifier": n_cls,
               "backbone": n_all - n_cls},
    "labels": labels,
    "history": history,
    "val": {"loss": final["loss"], "acc": final["acc"], "macro_f1": final["macro_f1"],
            "n": len(va)},
    "confusion_matrix": cm.tolist(),
    "probes": probe_out,
    "misclassified": mis,
    "test_distribution": pred_df["label"].value_counts().to_dict(),
    "train_time_s": time.time() - t_start,
}
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

with open(os.path.join(OUT, "train_log.txt"), "w", encoding="utf-8") as f:
    f.write(f"{n_all}\n{n_cls}\n{pre['loss']}\n")
print("\nDONE", flush=True)

# %% [markdown]
# # بخش ۷ — شبکهٔ عصبی و طبقه‌بندی تصویر (Fashion-MNIST)
#
# ۱۰ کلاس پوشاک، تصاویر خاکستری ۲۸×۲۸. مجموعهٔ آزمون (۱۰٬۰۰۰ تصویر) تا مرحلهٔ نهایی
# دست‌نخورده می‌ماند؛ همهٔ تصمیم‌ها روی اعتبارسنجی گرفته می‌شود.

# %%
import json
import os
import sys
import time
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings('ignore')
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
torch.use_deterministic_algorithms(False)

DATA_DIR = '../Day2_Datasets/03_FashionMNIST'
sys.path.insert(0, DATA_DIR)
from load_fashion import CLASS_NAMES, load_fashion  # noqa: E402

OUT = 'out'
os.makedirs(OUT, exist_ok=True)
DEVICE = 'cpu'

# %% [markdown]
# ## ۷.۱ شناخت داده، تقسیم آموزش/اعتبارسنجی و نرمال‌سازی

# %%
x_all, y_all, x_test_raw, y_test_raw = load_fashion()
print('train images:', x_all.shape, x_all.dtype)
print('train labels:', y_all.shape, y_all.dtype)
print('test  images:', x_test_raw.shape, y_test_raw.shape)

print('\nclass distribution (full train / test):')
for i, name in enumerate(CLASS_NAMES):
    n_tr = int((y_all == i).sum())
    n_te = int((y_test_raw == i).sum())
    print(f'  {i} {name:12s} train={n_tr:5d} test={n_te:4d}')

# %%
fig, axes = plt.subplots(2, 5, figsize=(10, 4.4))
for i, ax in enumerate(axes.ravel()):
    idx = np.where(y_all == i)[0][0]
    ax.imshow(x_all[idx], cmap='gray')
    ax.set_title(CLASS_NAMES[i], fontsize=9)
    ax.axis('off')
plt.suptitle('One sample per class (Fashion-MNIST)', fontsize=11)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec7_samples.png'), dpi=130)
plt.close()

# %% [markdown]
# تقسیم ۵۰٬۰۰۰ / ۱۰٬۰۰۰ با `stratify` تا نسبت کلاس‌ها حفظ شود، و نرمال‌سازی با
# میانگین و انحراف‌معیارِ **فقط مجموعهٔ آموزش**.

# %%
x_tr, x_va, y_tr, y_va = train_test_split(
    x_all, y_all, test_size=10_000, random_state=SEED, stratify=y_all)
print('train:', x_tr.shape[0], '| val:', x_va.shape[0])

mu = float(x_tr.mean() / 255.0)
sd = float(x_tr.std() / 255.0)
print(f'pixel mean={mu:.4f}  std={sd:.4f}  (min={x_tr.min()} max={x_tr.max()})')


def to_tensor(imgs):
    t = torch.from_numpy(imgs.astype(np.float32) / 255.0).unsqueeze(1)
    return (t - mu) / sd


def labels(ys):
    return torch.from_numpy(ys.astype(np.int64))


Xtr, ytr = to_tensor(x_tr), labels(y_tr)
Xva, yva = to_tensor(x_va), labels(y_va)
Xte, yte = to_tensor(x_test_raw), labels(y_test_raw)
print('tensor shapes:', Xtr.shape, Xva.shape, Xte.shape)

# %%
BATCH = 128


def batches(X, y, bs=BATCH, shuffle=False):
    n = len(X)
    order = torch.randperm(n) if shuffle else torch.arange(n)
    for i in range(0, n, bs):
        idx = order[i:i + bs]
        yield X[idx], y[idx]


@torch.no_grad()
def evaluate(model, X, y, bs=1000):
    model.eval()
    preds = []
    for i in range(0, len(X), bs):
        logits = model(X[i:i + bs])
        preds.append(logits.argmax(1))
    p = torch.cat(preds).cpu().numpy()
    return accuracy_score(y.cpu().numpy(), p), p


def train_model(model, Xtr, ytr, Xva, yva, epochs, lr=1e-3, wd=1e-4,
                patience=None, tag='model'):
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    lossf = nn.CrossEntropyLoss()
    hist = {'epoch': [], 'train_loss': [], 'train_acc': [],
            'val_loss': [], 'val_acc': [], 'seconds': []}
    best_acc, best_state = -1.0, None
    t_start = time.perf_counter()

    for ep in range(1, epochs + 1):
        t0 = time.perf_counter()
        model.train()
        total, correct, running = 0, 0, 0.0
        for xb, yb in batches(Xtr, ytr, shuffle=True):
            opt.zero_grad()
            out = model(xb)
            loss = lossf(out, yb)
            loss.backward()
            opt.step()
            running += loss.item() * len(xb)
            correct += (out.argmax(1) == yb).sum().item()
            total += len(xb)
        val_acc, _ = evaluate(model, Xva, yva)
        val_loss = _val_loss(model, Xva, yva, lossf)
        dt = time.perf_counter() - t0
        hist['epoch'].append(ep)
        hist['train_loss'].append(running / total)
        hist['train_acc'].append(correct / total)
        hist['val_loss'].append(val_loss)
        hist['val_acc'].append(val_acc)
        hist['seconds'].append(round(dt, 2))
        print(f'  epoch {ep:2d}/{epochs}  train_loss={running / total:.4f} '
              f'acc={correct / total:.4f} | val_loss={val_loss:.4f} '
              f'val_acc={val_acc:.4f} | {dt:.1f}s')
        if val_acc > best_acc:
            best_acc = val_acc
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if patience and ep - int(np.argmax(hist['val_acc'])) - 1 >= patience:
            print(f'  early stop at epoch {ep} (no val gain for {patience} epochs)')
            break
    hist['total_seconds'] = round(time.perf_counter() - t_start, 2)
    hist['best_val_acc'] = float(best_acc)
    model.load_state_dict(best_state)
    return hist


@torch.no_grad()
def _val_loss(model, X, y, lossf, bs=1000):
    model.eval()
    tot = 0.0
    for i in range(0, len(X), bs):
        tot += lossf(model(X[i:i + bs]), y[i:i + bs]).item() * len(X[i:i + bs])
    return tot / len(X)

# %% [markdown]
# ## ۷.۲ MLP با دو لایهٔ پنهان
#
# `784 → 512 → 256 → 10`، تصاویر تخت‌شده، فعال‌سازی ReLU.

# %%
class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(28 * 28, 512), nn.ReLU(),
            nn.Linear(512, 256), nn.ReLU(),
            nn.Linear(256, 10),
        )

    def forward(self, x):
        return self.net(x)


mlp = MLP()
n_params_mlp = sum(p.numel() for p in mlp.parameters())
print('MLP parameters:', f'{n_params_mlp:,}')
print(mlp)

# %%
print('\ntraining MLP:')
hist_mlp = train_model(mlp, Xtr, ytr, Xva, yva, epochs=12, lr=1e-3, wd=1e-4, tag='mlp')
print(f'MLP best val acc = {hist_mlp["best_val_acc"]:.4f} '
      f'(train time {hist_mlp["total_seconds"]}s)')

# %% [markdown]
# ## ۷.۳ CNN با دو بلوک کانولوشن/Pooling
#
# هر بلوک: `Conv3×3 → BatchNorm → ReLU → MaxPool2`. کنترل بیش‌برازش: **Dropout**
# (۰٫۴ و ۰٫۳) + **weight decay** + **early stopping** روی اعتبارسنجی.

# %%
class CNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.4),
            nn.Linear(64 * 7 * 7, 128), nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


cnn = CNN()
n_params_cnn = sum(p.numel() for p in cnn.parameters())
print('CNN parameters:', f'{n_params_cnn:,}')
print(cnn)

# %%
print('\ntraining CNN:')
hist_cnn = train_model(cnn, Xtr, ytr, Xva, yva, epochs=8, lr=1e-3, wd=1e-4,
                       patience=2, tag='cnn')
print(f'CNN best val acc = {hist_cnn["best_val_acc"]:.4f} '
      f'(train time {hist_cnn["total_seconds"]}s)')

# %%
fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
for name, h, c in [('MLP', hist_mlp, '#3b6ea5'), ('CNN', hist_cnn, '#c0392b')]:
    axes[0].plot(h['epoch'], h['train_loss'], '--', color=c, alpha=.55, label=f'{name} train')
    axes[0].plot(h['epoch'], h['val_loss'], '-o', color=c, ms=3, label=f'{name} val')
    axes[1].plot(h['epoch'], h['train_acc'], '--', color=c, alpha=.55, label=f'{name} train')
    axes[1].plot(h['epoch'], h['val_acc'], '-o', color=c, ms=3, label=f'{name} val')
axes[0].set(xlabel='epoch', ylabel='cross-entropy', title='Loss curves')
axes[1].set(xlabel='epoch', ylabel='accuracy', title='Accuracy curves')
for ax in axes:
    ax.grid(alpha=.3)
    ax.legend(fontsize=7)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec7_curves.png'), dpi=130)
plt.close()
print('curves saved')

# %% [markdown]
# ## ۷.۴ ارزیابی نهایی روی آزمون (فقط یک بار)

# %%
models = {'MLP': (mlp, hist_mlp), 'CNN': (cnn, hist_cnn)}
best_name = max(models, key=lambda k: models[k][1]['best_val_acc'])
best_model = models[best_name][0]
print('selected model:', best_name)

test_acc, test_pred = evaluate(best_model, Xte, yte)
y_true = yte.cpu().numpy()
macro_f1 = f1_score(y_true, test_pred, average='macro')
print(f'TEST accuracy={test_acc:.4f}  macro-F1={macro_f1:.4f}')

cm = confusion_matrix(y_true, test_pred)
cm_norm = cm / cm.sum(axis=1, keepdims=True)
print('\nper-class recall:')
for i, name in enumerate(CLASS_NAMES):
    print(f'  {name:12s} {cm_norm[i, i]:.3f}  (n={cm[i].sum()})')

# %%
fig, ax = plt.subplots(figsize=(7.6, 6.6))
im = ax.imshow(cm_norm, cmap='Blues', vmin=0, vmax=1)
ax.set_xticks(range(10)); ax.set_yticks(range(10))
ax.set_xticklabels(CLASS_NAMES, rotation=45, ha='right', fontsize=8)
ax.set_yticklabels(CLASS_NAMES, fontsize=8)
for i in range(10):
    for j in range(10):
        if cm_norm[i, j] > 0.01:
            ax.text(j, i, f'{cm_norm[i, j]:.2f}', ha='center', va='center', fontsize=6,
                    color='white' if cm_norm[i, j] > .55 else 'black')
ax.set(xlabel='predicted', ylabel='true', title=f'Confusion matrix (row-normalised) — {best_name}')
plt.colorbar(im, ax=ax, fraction=.046)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec7_confusion.png'), dpi=130)
plt.close()

off = cm.copy()
np.fill_diagonal(off, 0)
pairs = []
for i in range(10):
    for j in range(i + 1, 10):
        pairs.append((off[i, j] + off[j, i], i, j))
pairs.sort(reverse=True)
print('\ntop confused pairs:')
for cnt, i, j in pairs[:5]:
    print(f'  {CLASS_NAMES[i]} <-> {CLASS_NAMES[j]}: {cnt} errors '
          f'({off[i, j]} as {CLASS_NAMES[j]}, {off[j, i]} as {CLASS_NAMES[i]})')

# %%
wrong = np.where(test_pred != y_true)[0][:12]
fig, axes = plt.subplots(3, 4, figsize=(9, 7))
for ax, k in zip(axes.ravel(), wrong):
    ax.imshow(x_test_raw[k], cmap='gray')
    ax.set_title(f'true: {CLASS_NAMES[y_true[k]]}\npred: {CLASS_NAMES[test_pred[k]]}', fontsize=7)
    ax.axis('off')
plt.suptitle(f'Misclassified test images — {best_name}', fontsize=11)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec7_errors.png'), dpi=130)
plt.close()
print('error grid saved')

# %%
results = {
    'n_train_full': int(len(x_all)),
    'n_test': int(len(x_test_raw)),
    'n_train': int(len(x_tr)),
    'n_val': int(len(x_va)),
    'pixel_mean': round(mu, 4),
    'pixel_std': round(sd, 4),
    'class_counts_train': {CLASS_NAMES[i]: int((y_all == i).sum()) for i in range(10)},
    'class_counts_test': {CLASS_NAMES[i]: int((y_test_raw == i).sum()) for i in range(10)},
    'mlp': {'params': int(n_params_mlp), 'best_val_acc': hist_mlp['best_val_acc'],
            'train_seconds': hist_mlp['total_seconds'],
            'epochs_run': len(hist_mlp['epoch'])},
    'cnn': {'params': int(n_params_cnn), 'best_val_acc': hist_cnn['best_val_acc'],
            'train_seconds': hist_cnn['total_seconds'],
            'epochs_run': len(hist_cnn['epoch']),
            'seconds_per_epoch': round(float(np.mean(hist_cnn['seconds'])), 2)},
    'selected': best_name,
    'test': {'accuracy': float(test_acc), 'macro_f1': float(macro_f1)},
    'per_class_recall': {CLASS_NAMES[i]: round(float(cm_norm[i, i]), 3) for i in range(10)},
    'top_pairs': [{'pair': f'{CLASS_NAMES[i]} <-> {CLASS_NAMES[j]}', 'errors': int(c),
                   'i_as_j': int(off[i, j]), 'j_as_i': int(off[j, i])}
                  for c, i, j in pairs[:5]],
}
with open(os.path.join(OUT, 'sec7_results.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('saved out/sec7_results.json')

# %% [markdown]
# # بخش ۹ — پردازش صوت و تعمیم به گویندهٔ جدید (Spoken Digits)
#
# تشخیص رقم گفتاری از فایل‌های `{digit}_{speaker}_{index}.wav`. دو طرح ارزیابی:
# ۱) **تقسیم تصادفی فایل** (همهٔ گویندگان در آموزش و آزمون) ۲) **تفکیک بر اساس گوینده**
# (دو گویندهٔ کاملاً دیده‌نشده). تفاوت این دو، همان شکاف تعمیم است.

# %%
import glob
import json
import os
import time
import warnings
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from scipy.fft import dct
from scipy.io import wavfile
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

warnings.filterwarnings('ignore')
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

DATA = '../Day2_Datasets/05_SpokenDigits/recordings'
OUT = 'out'
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## ۹.۱ بررسی داده: نرخ نمونه‌برداری، طول و شمارش

# %%
paths = sorted(glob.glob(os.path.join(DATA, '*.wav')))
print('files:', len(paths))

meta = []
waves = {}
for p in paths:
    name = os.path.basename(p)[:-4]
    digit, speaker, idx = name.split('_')
    sr, x = wavfile.read(p)
    x = x.astype(np.float32) / 32768.0
    waves[name] = x
    meta.append({'name': name, 'digit': int(digit), 'speaker': speaker,
                 'sr': sr, 'n': len(x), 'dur': len(x) / sr})

print('sample rates:', Counter(m['sr'] for m in meta))
durs = np.array([m['dur'] for m in meta])
print('duration: mean %.3f s | min %.3f | max %.3f | median %.3f'
      % (durs.mean(), durs.min(), durs.max(), np.median(durs)))
print('per digit :', dict(sorted(Counter(m['digit'] for m in meta).items())))
print('per speaker:', dict(Counter(m['speaker'] for m in meta)))
print('per speaker x digit (matrix):')
speakers = sorted({m['speaker'] for m in meta})
mat = np.zeros((len(speakers), 10), dtype=int)
for m in meta:
    mat[speakers.index(m['speaker']), m['digit']] += 1
print('        ' + ' '.join(f'{d:>4d}' for d in range(10)))
for s, row in zip(speakers, mat):
    print(f'{s:8s}' + ' '.join(f'{v:>4d}' for v in row))

# %% [markdown]
# ### استخراج Log-Mel و MFCC (پیاده‌سازی با NumPy/SciPy، بدون کتابخانهٔ اضافی)

# %%
SR = 8000
FRAME, HOP, NFFT, N_MELS, N_MFCC = 256, 80, 256, 40, 13


def mel_filterbank(sr=SR, n_fft=NFFT, n_mels=N_MELS, fmin=20.0, fmax=None):
    fmax = fmax or sr / 2
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2)
    hz = mel2hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        lo, ce, hi = bins[m - 1], bins[m], bins[m + 1]
        if ce == lo:
            ce = lo + 1
        if hi == ce:
            hi = ce + 1
        for k in range(lo, ce):
            fb[m - 1, k] = (k - lo) / (ce - lo)
        for k in range(ce, hi):
            fb[m - 1, k] = (hi - k) / (hi - ce)
    return fb


FB = mel_filterbank()
DCT = dct(np.eye(N_MELS), type=2, norm='ortho')[:N_MFCC]


def logmel(x, sr=SR):
    """log-Mel spectrogram: (n_mels, frames)"""
    if len(x) < FRAME:
        x = np.pad(x, (0, FRAME - len(x)))
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])          # pre-emphasis
    n_frames = 1 + (len(x) - FRAME) // HOP
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = x[idx] * np.hamming(FRAME)[None, :]
    spec = np.abs(np.fft.rfft(frames, NFFT)) ** 2
    mel = spec @ FB.T
    return (10 * np.log10(mel + 1e-10)).T      # (n_mels, n_frames)


def mfcc_from_logmel(L):
    return DCT @ L


def delta(feat, N=2):
    pad = np.pad(feat, ((0, 0), (N, N)), mode='edge')
    denom = 2 * sum(n ** 2 for n in range(1, N + 1))
    out = np.zeros_like(feat)
    for n in range(1, N + 1):
        out += n * (pad[:, N + n:N + n + feat.shape[1]] - pad[:, N - n:N - n + feat.shape[1]])
    return out / denom


def summary_features(x, drop_c0=False):
    L = logmel(x)
    M = mfcc_from_logmel(L)
    dM = delta(M)
    if drop_c0:                      # حذف ضریب صفرم (لگاریتم انرژی) که وابسته به گوینده است
        M, dM = M[1:], dM[1:]
    spec = np.abs(np.fft.rfft(x * np.hamming(len(x)))) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    p = spec / (spec.sum() + 1e-12)
    centroid = float((freqs * p).sum())
    bandwidth = float(np.sqrt(((freqs - centroid) ** 2 * p).sum()))
    csum = np.cumsum(p)
    rolloff = float(freqs[np.searchsorted(csum, 0.85)])
    zcr = float(np.mean(np.abs(np.diff(np.sign(x))) > 0))
    return np.concatenate([
        M.mean(1), M.std(1), dM.mean(1), dM.std(1),
        [centroid, bandwidth, rolloff, zcr, len(x) / SR],
    ])


# %% [markdown]
# ### رسم موج و Log-Mel چند نمونه

# %%
fig, axes = plt.subplots(2, 4, figsize=(12, 4.6))
samples = [('0', 'george'), ('3', 'jackson'), ('7', 'lucas'), ('9', 'yweweler')]
for k, (d, s) in enumerate(samples):
    name = f'{d}_{s}_0'
    x = waves[name]
    t = np.arange(len(x)) / SR
    axes[0, k].plot(t, x, lw=.8, color='#3b6ea5')
    axes[0, k].set_title(f'digit {d} — {s}', fontsize=9)
    axes[0, k].set_xlabel('time (s)', fontsize=8)
    if k == 0:
        axes[0, k].set_ylabel('waveform', fontsize=9)
    L = logmel(x)
    im = axes[1, k].imshow(L, aspect='auto', origin='lower', cmap='magma')
    axes[1, k].set_title('log-Mel', fontsize=9)
    axes[1, k].set_xlabel('frame', fontsize=8)
    if k == 0:
        axes[1, k].set_ylabel('mel bin', fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec9_wave_mel.png'), dpi=130)
plt.close()
print('waveform/spectrogram figure saved')

# %% [markdown]
# ## دو طرح تقسیم
#
# | طرح | آموزش | اعتبارسنجی | آزمون | نکته |
# |---|---|---|---|---|
# | تصادفی فایل | ۷۰٪ فایل‌ها | ۱۵٪ | ۱۵٪ | همهٔ گویندگان در هر سه بخش |
# | تفکیک گوینده | ۴ گوینده | `theo` | `yweweler` | صفر اشتراک گوینده بین بخش‌ها |

# %%
import pandas as pd

df = pd.DataFrame(meta)
rng = np.random.RandomState(SEED)
idx = rng.permutation(len(df))
a_tr, a_rest = idx[:int(.70 * len(df))], idx[int(.70 * len(df)):]
a_va, a_te = a_rest[:len(a_rest) // 2], a_rest[len(a_rest) // 2:]
random_split = {'train': df.iloc[a_tr], 'val': df.iloc[a_va], 'test': df.iloc[a_te]}

held = ['theo', 'yweweler']
speaker_split = {
    'train': df[~df.speaker.isin(held)],
    'val': df[df.speaker == 'theo'],
    'test': df[df.speaker == 'yweweler'],
}

for name, sp in [('random', random_split), ('speaker', speaker_split)]:
    print(f'\n{name} split:')
    for part in ['train', 'val', 'test']:
        s = sp[part]
        print(f'  {part:5s} n={len(s):4d} speakers={sorted(s.speaker.unique())}')

# %% [markdown]
# ## ۹.۲ ویژگی‌های MFCC + مدل کلاسیک (SVM)
#
# برای هر فایل بردار ۶۰بعدی ساخته می‌شود: میانگین و انحراف‌معیارِ MFCC (۱۳+۱۳)،
# میانگین و انحراف‌معیارِ دلتا-MFCC (۱۳+۱۳)، و پنج ویژگی طیفی/زمانی (مرکز طیف،
# پهنای باند، roll-off ۸۵٪، نرخ عبور از صفر، طول). استانداردسازی و انتخاب پارامتر
# داخل `Pipeline` و `GridSearchCV` **فقط روی آموزش** انجام می‌شود.

# %%
t0 = time.perf_counter()
F = {name: summary_features(x) for name, x in waves.items()}
print('feature extraction: %.1fs for %d files' % (time.perf_counter() - t0, len(F)))


def build_X(split):
    def mat(part):
        rows = split[part]
        return np.vstack([F[n] for n in rows['name']]), rows['digit'].to_numpy()
    return mat('train'), mat('val'), mat('test')


svm_grid = {'clf__C': [1, 10, 100], 'clf__gamma': ['scale', 0.01]}

svm_results = {}
for scheme in ['random', 'speaker']:
    (Xtr, ytr), (Xva, yva), (Xte, yte) = build_X(
        random_split if scheme == 'random' else speaker_split)
    pipe = Pipeline([('scale', StandardScaler()),
                     ('clf', SVC(kernel='rbf', random_state=SEED))])
    gs = GridSearchCV(pipe, svm_grid, cv=3, scoring='f1_macro', n_jobs=1)
    t0 = time.perf_counter()
    gs.fit(Xtr, ytr)
    dt = time.perf_counter() - t0
    pred_va = gs.predict(Xva)
    pred_te = gs.predict(Xte)
    svm_results[scheme] = {
        'best_params': {k.replace('clf__', ''): str(v) for k, v in gs.best_params_.items()},
        'cv_macro_f1': float(gs.best_score_),
        'val_macro_f1': float(f1_score(yva, pred_va, average='macro')),
        'test_macro_f1': float(f1_score(yte, pred_te, average='macro')),
        'fit_seconds': round(dt, 2),
        'val_pred': pred_va, 'val_true': yva,
        'test_pred': pred_te, 'test_true': yte,
    }
    print(f"SVM [{scheme:7s}] best={gs.best_params_} CV={gs.best_score_:.4f} "
          f"VAL={svm_results[scheme]['val_macro_f1']:.4f} "
          f"TEST={svm_results[scheme]['test_macro_f1']:.4f} ({dt:.1f}s)")

# %%
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
for ax, scheme in zip(axes, ['random', 'speaker']):
    cm = confusion_matrix(svm_results[scheme]['val_true'],
                          svm_results[scheme]['val_pred'], labels=range(10))
    im = ax.imshow(cm, cmap='Blues')
    ax.set_title(f'SVM confusion — {scheme} split (val)', fontsize=9)
    ax.set_xticks(range(10)); ax.set_yticks(range(10))
    ax.set_xlabel('predicted'); ax.set_ylabel('true')
    for i in range(10):
        for j in range(10):
            if cm[i, j]:
                ax.text(j, i, cm[i, j], ha='center', va='center', fontsize=6,
                        color='white' if cm[i, j] > cm.max() / 2 else 'black')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec9_svm_confusion.png'), dpi=130)
plt.close()

# %% [markdown]
# ## ۹.۳ شبکهٔ کانولوشنی کوچک روی Log-Mel
#
# **طول ورودی:** یک ثانیه (۸٬۰۰۰ نمونه) با **zero-padding** یا **truncation**؛ چون
# بلندترین فایل ۱٫۱۶۸ ثانیه و میانه ۰٫۴۹ ثانیه است. Log-Mel با ۴۰ فیلتر مِل و گام
# ۱۰ میلی‌ثانیه → ورودی ثابت **۱ × ۴۰ × ۱۰۱**.

# %%
MAX_LEN = SR  # 1 second
N_FRAMES = 1 + (MAX_LEN - FRAME) // HOP


def pad_or_truncate(x, n=MAX_LEN):
    if len(x) >= n:
        return x[:n]
    return np.pad(x, (0, n - len(x)))


def spec_tensor(x):
    L = logmel(pad_or_truncate(x))
    L = L[:, :N_FRAMES]
    if L.shape[1] < N_FRAMES:
        L = np.pad(L, ((0, 0), (0, N_FRAMES - L.shape[1])), mode='edge')
    L = (L - L.mean()) / (L.std() + 1e-6)
    return torch.tensor(L[None, :, :], dtype=torch.float32)


print('CNN input shape:', spec_tensor(waves['0_george_0']).shape)

# %%
class SmallCNN(nn.Module):
    def __init__(self, n_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
        )
        flat = 32 * (N_MELS // 4) * (N_FRAMES // 4)   # دو بار MaxPool(2)
        self.head = nn.Sequential(
            nn.Flatten(), nn.Dropout(0.3),
            nn.Linear(flat, 64), nn.ReLU(),
            nn.Dropout(0.2), nn.Linear(64, n_classes),
        )

    def forward(self, x):
        return self.head(self.features(x))


def train_cnn(split, epochs=14, bs=64):
    tr, va = split['train'], split['val']
    Xtr = torch.stack([spec_tensor(waves[n]) for n in tr['name']])
    ytr = torch.tensor(tr['digit'].to_numpy())
    Xva = torch.stack([spec_tensor(waves[n]) for n in va['name']])
    yva = torch.tensor(va['digit'].to_numpy())

    model = SmallCNN()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.CrossEntropyLoss()
    hist = {'epoch': [], 'train_loss': [], 'val_macro_f1': []}
    best_f1, best_state = -1, None
    t0 = time.perf_counter()
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(Xtr))
        tot = 0.0
        for i in range(0, len(Xtr), bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            loss = lossf(model(Xtr[idx]), ytr[idx])
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            pv = model(Xva).argmax(1).numpy()
        f1 = f1_score(yva.numpy(), pv, average='macro')
        hist['epoch'].append(ep)
        hist['train_loss'].append(tot / len(Xtr))
        hist['val_macro_f1'].append(float(f1))
        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    hist['train_seconds'] = round(time.perf_counter() - t0, 1)
    return model, hist, best_f1


def eval_cnn(model, part):
    X = torch.stack([spec_tensor(waves[n]) for n in part['name']])
    with torch.no_grad():
        pred = model(X).argmax(1).numpy()
    y = part['digit'].to_numpy()
    return y, pred, float(f1_score(y, pred, average='macro'))


cnn_results = {}
for scheme in ['random', 'speaker']:
    split = random_split if scheme == 'random' else speaker_split
    print(f'\ntraining CNN [{scheme}] ...')
    model, hist, best_val = train_cnn(split)
    y_te, p_te, f1_te = eval_cnn(model, split['test'])
    cnn_results[scheme] = {'val_macro_f1': float(best_val), 'test_macro_f1': f1_te,
                           'train_seconds': hist['train_seconds'],
                           'hist': hist, 'model': model,
                           'test_true': y_te, 'test_pred': p_te}
    print(f'  CNN [{scheme:7s}] VAL={best_val:.4f} TEST={f1_te:.4f} '
          f'({hist["train_seconds"]}s)')
    cnn_results[scheme]['model'] = model

# %%
fig, ax = plt.subplots(figsize=(7.4, 4.2))
for scheme, c in [('random', '#3b6ea5'), ('speaker', '#c0392b')]:
    h = cnn_results[scheme]['hist']
    ax.plot(h['epoch'], h['val_macro_f1'], '-o', ms=3, color=c, label=f'{scheme} split')
ax.set(xlabel='epoch', ylabel='validation macro-F1', title='CNN learning curves')
ax.grid(alpha=.3)
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec9_cnn_curve.png'), dpi=130)
plt.close()

# %% [markdown]
# ## ۹.۴ شکاف تعمیم و خطاهای صوتی

# %%
summary = []
for scheme in ['random', 'speaker']:
    summary.append({
        'scheme': scheme,
        'svm_val': svm_results[scheme]['val_macro_f1'],
        'svm_test': svm_results[scheme]['test_macro_f1'],
        'cnn_val': cnn_results[scheme]['val_macro_f1'],
        'cnn_test': cnn_results[scheme]['test_macro_f1'],
    })
print(json.dumps(summary, indent=2))

# %% [markdown]
# ### آزمایشِ بهبود: حذف ضریب انرژی (c0) از MFCC
#
# `c0` لگاریتم انرژی کل فریم است و بیش از هر ضریب دیگری به **بلندی صدا و فاصله از
# میکروفن** (یعنی هویت گوینده) وابسته است، نه به رقم. حذف آن باید تعمیم بین‌گوینده را
# بهتر کند. این آزمایش فقط روی آموزش/اعتبارسنجی تصمیم گرفته می‌شود.

# %%
F_nc0 = {name: summary_features(x, drop_c0=True) for name, x in waves.items()}
imp = {}
for scheme in ['random', 'speaker']:
    split = random_split if scheme == 'random' else speaker_split

    def mat(part, Fm):
        rows = split[part]
        return np.vstack([Fm[n] for n in rows['name']]), rows['digit'].to_numpy()

    (Xtr2, ytr2), (Xva2, yva2), (Xte2, yte2) = (mat('train', F_nc0),
                                                mat('val', F_nc0),
                                                mat('test', F_nc0))
    pipe2 = Pipeline([('scale', StandardScaler()),
                      ('clf', SVC(kernel='rbf', C=10, gamma='scale', random_state=SEED))])
    pipe2.fit(Xtr2, ytr2)
    imp[scheme] = {
        'val_macro_f1': float(f1_score(yva2, pipe2.predict(Xva2), average='macro')),
        'test_macro_f1': float(f1_score(yte2, pipe2.predict(Xte2), average='macro')),
    }
    print(f'SVM no-c0 [{scheme:7s}] VAL={imp[scheme]["val_macro_f1"]:.4f} '
          f'TEST={imp[scheme]["test_macro_f1"]:.4f}  '
          f'(baseline TEST={svm_results[scheme]["test_macro_f1"]:.4f})')

# %% [markdown]
# ### حساسیت به گوینده: leave-one-speaker-out
#
# با ۶ گوینده، هر بار یکی را کامل کنار می‌گذاریم (آموزش با ۵ گوینده) تا ببینیم
# «سختی گوینده» چقدر متفاوت است و آیا افزودن گوینده کمک می‌کند.

# %%
loso = {}
for s in sorted(df.speaker.unique()):
    tr_s, te_s = df[df.speaker != s], df[df.speaker == s]
    Xtr3 = np.vstack([F[n] for n in tr_s['name']])
    ytr3 = tr_s['digit'].to_numpy()
    Xte3 = np.vstack([F[n] for n in te_s['name']])
    yte3 = te_s['digit'].to_numpy()
    p3 = Pipeline([('scale', StandardScaler()),
                   ('clf', SVC(kernel='rbf', C=10, gamma=0.01, random_state=SEED))]).fit(Xtr3, ytr3)
    loso[s] = float(f1_score(yte3, p3.predict(Xte3), average='macro'))
    print(f'  held out {s:9s} -> macro-F1={loso[s]:.4f}')
print('LOSO mean %.4f | std %.4f | min %.4f | max %.4f'
      % (np.mean(list(loso.values())), np.std(list(loso.values())),
         min(loso.values()), max(loso.values())))

# سه خطای صوتی از آزمون گویندهٔ دیده‌نشده با مدل بهترِ آن طرح
best_scheme = max(['random', 'speaker'],
                  key=lambda s: max(svm_results[s]['test_macro_f1'],
                                    cnn_results[s]['test_macro_f1']))
use_cnn = cnn_results['speaker']['test_macro_f1'] >= svm_results['speaker']['test_macro_f1']
part = speaker_split['test']
if use_cnn:
    y_true, y_pred, _ = eval_cnn(cnn_results['speaker']['model'], part)
    who = 'CNN'
else:
    (Xt, yt), (Xv, yv), (Xe, ye) = build_X(speaker_split)
    y_true, y_pred = ye, svm_results['speaker']['test_pred']
    who = 'SVM'
print(f'\nerror examples from {who} on unseen-speaker test')

recall = {}
for d in range(10):
    m = y_true == d
    recall[d] = float((y_pred[m] == d).mean()) if m.any() else float('nan')
print('per-digit recall (unseen speaker):',
      {d: round(v, 2) for d, v in recall.items()})

# سه خطا با ترکیب (واقعی، پیش‌بینی) متفاوت تا تنوع خطاها دیده شود
wrong, seen_pairs = [], set()
for wi in np.where(y_true != y_pred)[0]:
    pair = (int(y_true[wi]), int(y_pred[wi]))
    if pair in seen_pairs:
        continue
    seen_pairs.add(pair)
    wrong.append(wi)
    if len(wrong) == 3:
        break

fig, axes = plt.subplots(2, 3, figsize=(11, 4.6))
for k, wi in enumerate(wrong):
    name = part['name'].iloc[wi]
    x = waves[name]
    axes[0, k].plot(np.arange(len(x)) / SR, x, lw=.8, color='#c0392b')
    axes[0, k].set_title(f'{name}\ntrue={y_true[wi]} pred={y_pred[wi]}', fontsize=8)
    axes[0, k].set_xlabel('time (s)', fontsize=8)
    L = logmel(x)
    axes[1, k].imshow(L, aspect='auto', origin='lower', cmap='magma')
    axes[1, k].set_xlabel('frame', fontsize=8)
    print(f'  {name}: true={y_true[wi]} pred={y_pred[wi]} dur={len(x)/SR:.2f}s')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec9_errors.png'), dpi=130)
plt.close()

# %%
res = {
    'n_files': len(df),
    'sample_rate': int(df.sr.iloc[0]),
    'duration': {'mean': round(float(durs.mean()), 3),
                 'min': round(float(durs.min()), 3),
                 'max': round(float(durs.max()), 3),
                 'median': round(float(np.median(durs)), 3)},
    'per_digit': dict(sorted(Counter(m['digit'] for m in meta).items())),
    'per_speaker': dict(Counter(m['speaker'] for m in meta)),
    'splits': {
        'random': {p: len(random_split[p]) for p in ['train', 'val', 'test']},
        'speaker': {p: len(speaker_split[p]) for p in ['train', 'val', 'test']},
    },
    'features': {'n_features': int(F[next(iter(F))].shape[0]),
                 'mfcc': N_MFCC, 'n_mels': N_MELS},
    'svm': {s: {k: v for k, v in svm_results[s].items()
                if k not in ('val_pred', 'val_true', 'test_pred', 'test_true')}
            for s in svm_results},
    'cnn': {s: {k: v for k, v in cnn_results[s].items()
                if k not in ('hist', 'model', 'test_true', 'test_pred')}
            for s in cnn_results},
    'summary': summary,
    'improvement_no_c0': imp,
    'loso': {k: round(v, 4) for k, v in loso.items()},
    'loso_mean': round(float(np.mean(list(loso.values()))), 4),
    'per_digit_recall_unseen': {int(d): round(v, 3) for d, v in recall.items()},
    'best_model_unseen': who,
}
with open(os.path.join(OUT, 'sec9_results.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print('\nsaved out/sec9_results.json')

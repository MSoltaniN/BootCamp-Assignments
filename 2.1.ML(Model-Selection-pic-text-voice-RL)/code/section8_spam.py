# %% [markdown]
# # بخش ۸ — پردازش زبان و تشخیص پیامک اسپم
#
# طبقه‌بندی متن پیامک به `ham` یا `spam`. نکتهٔ کلیدی: ۴۰۳ ردیف متن دقیقاً تکراری‌اند،
# پس تقسیم باید **گروهی** باشد تا نسخهٔ تکراری در دو بخش نیفتد و اعتبارسنجی متورم نشود.

# %%
import json
import os
import re
import time
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

warnings.filterwarnings('ignore')
SEED = 42
DATA = '../Day2_Datasets/04_SmsSpam/sms_spam.csv'
OUT = 'out'
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## ۸.۱ شناخت داده و تقسیم گروهی

# %%
df = pd.read_csv(DATA)
df['label'] = df['label'].str.strip().str.lower()
df['y'] = (df['label'] == 'spam').astype(int)

print('rows:', len(df), '| spam: %d (%.2f%%)' % (df.y.sum(), 100 * df.y.mean()))
print('unique texts:', df.text.nunique())
dup_rows = int(df.text.duplicated().sum())
print('exactly duplicated rows (beyond first copy):', dup_rows)

lengths = df.text.str.len()
words = df.text.str.split().str.len()
print('\nchar length  : mean %.1f | median %.0f | p95 %.0f | max %d'
      % (lengths.mean(), lengths.median(), lengths.quantile(.95), lengths.max()))
print('word length  : mean %.1f | median %.0f | p95 %.0f | max %d'
      % (words.mean(), words.median(), words.quantile(.95), words.max()))
print('char length by class:')
print(df.assign(chars=lengths, words=words).groupby('label')[['chars', 'words']]
      .agg(['mean', 'median']).round(1).to_string())

# %% [markdown]
# ### تقسیم گروهی: هر متنِ یکسان کامل به یک بخش می‌رود
#
# ابتدا متن‌های یکتا استخراج می‌شوند (۵٬۱۷۱ متن از ۵٬۵۷۴ ردیف)، سپس **گروه‌ها** با
# `stratify` به ۷۰/۱۵/۱۵ تقسیم می‌شوند و برچسب هر ردیف از گروهش می‌آید. این کار
# جلوگیری می‌کند همان پیامک هم در آموزش دیده شود و هم در اعتبارسنجی/آزمون نمره بگیرد.

# %%
group = (df.groupby('text')
           .agg(y=('y', 'max'), n=('y', 'size'))
           .reset_index())
print('unique groups:', len(group), '| groups with >1 row:', int((group.n > 1).sum()))

g_tr, g_rest = train_test_split(group, test_size=0.30, random_state=SEED,
                                stratify=group['y'])
g_va, g_te = train_test_split(g_rest, test_size=0.50, random_state=SEED,
                              stratify=g_rest['y'])

split_map = {}
for name, g in [('train', g_tr), ('val', g_va), ('test', g_te)]:
    for t in g['text']:
        split_map[t] = name
df['split'] = df['text'].map(split_map)

print('\nsplit sizes (rows):')
for s in ['train', 'val', 'test']:
    sub = df[df.split == s]
    print(f'  {s:5s} rows={len(sub):5d} spam={int(sub.y.sum()):4d} '
          f'({100 * sub.y.mean():5.2f}%) | unique texts={sub.text.nunique()}')

overlap = (set(df[df.split == 'train'].text) & set(df[df.split == 'val'].text))
overlap2 = (set(df[df.split == 'train'].text) & set(df[df.split == 'test'].text))
print('text overlap train/val:', len(overlap), '| train/test:', len(overlap2))

X_tr = df.loc[df.split == 'train', 'text']
y_tr = df.loc[df.split == 'train', 'y']
X_va = df.loc[df.split == 'val', 'text']
y_va = df.loc[df.split == 'val', 'y']
X_te = df.loc[df.split == 'test', 'text']
y_te = df.loc[df.split == 'test', 'y']

# %% [markdown]
# ## ۸.۲ خط پایه: TF-IDF + LogisticRegression
#
# همهٔ مراحل داخل `Pipeline` است؛ `TfidfVectorizer` فقط روی `fit(X_train)` واژگان و
# IDF را می‌آموزد، پس val/test هیچ سهمی در ساخت واژگان ندارند.

# %%
def make_tfidf(max_features=None):
    return TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=max_features,
        sublinear_tf=True,
        strip_accents='unicode',
    )


def make_lr():
    return LogisticRegression(max_iter=2000, C=1.0, solver='liblinear',
                              random_state=SEED)


baseline = Pipeline([('tfidf', make_tfidf()), ('clf', make_lr())])
t0 = time.perf_counter()
baseline.fit(X_tr, y_tr)
lr_time = time.perf_counter() - t0

p_va = baseline.predict_proba(X_va)[:, 1]
pred_va = (p_va >= 0.5).astype(int)
b = {
    'precision': float(precision_score(y_va, pred_va)),
    'recall': float(recall_score(y_va, pred_va)),
    'macro_f1': float(f1_score(y_va, pred_va, average='macro')),
    'pr_auc': float(average_precision_score(y_va, p_va)),
    'fit_seconds': round(lr_time, 3),
}
print('LR baseline (val):', json.dumps(b, indent=2))
print('vocabulary size:', len(baseline.named_steps['tfidf'].vocabulary_))

# %% [markdown]
# ## ۸.۳ مقایسهٔ MultinomialNB و LinearSVC با خط پایه
#
# تنظیم پارامتر فقط روی آموزش/اعتبارسنجی: `alpha` برای NB و `C` برای LinearSVC
# (و برای LR) روی اعتبارسنجی جست‌وجو می‌شود.

# %%
def scores(y_true, score_or_proba):
    """PR-AUC و پیش‌بینی‌های آستانهٔ ۰٫۵ را برمی‌گرداند."""
    return score_or_proba


def evaluate_model(name, pipe, X, y, proba, fit_seconds, params):
    pred = (proba >= 0.5).astype(int)
    return {
        'name': name,
        'precision': float(precision_score(y, pred)),
        'recall': float(recall_score(y, pred)),
        'macro_f1': float(f1_score(y, pred, average='macro')),
        'pr_auc': float(average_precision_score(y, proba)),
        'fit_seconds': round(fit_seconds, 3),
        'params': params,
    }


results = {}
# --- LR با تنظیم C
best_lr = None
for C in [0.3, 1.0, 3.0]:
    pipe = Pipeline([('tfidf', make_tfidf()), ('clf', make_lr().set_params(C=C))])
    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    dt = time.perf_counter() - t0
    pr = pipe.predict_proba(X_va)[:, 1]
    ma = f1_score(y_va, (pr >= .5).astype(int), average='macro')
    print(f'LR C={C}: val macro-F1={ma:.4f} PR-AUC={average_precision_score(y_va, pr):.4f}')
    if best_lr is None or ma > best_lr[0]:
        best_lr = (ma, C, pipe, dt, pr)
_, C_lr, lr_pipe, lr_dt, lr_pr = best_lr
results['logreg'] = evaluate_model('LogisticRegression', lr_pipe, X_va, y_va,
                                   lr_pr, lr_dt, f'C={C_lr}')

# --- MultinomialNB با تنظیم alpha
best_nb = None
for alpha in [0.1, 0.3, 1.0]:
    pipe = Pipeline([('tfidf', make_tfidf()),
                     ('clf', MultinomialNB(alpha=alpha))])
    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    dt = time.perf_counter() - t0
    pr = pipe.predict_proba(X_va)[:, 1]
    ma = f1_score(y_va, (pr >= .5).astype(int), average='macro')
    print(f'NB alpha={alpha}: val macro-F1={ma:.4f} PR-AUC={average_precision_score(y_va, pr):.4f}')
    if best_nb is None or ma > best_nb[0]:
        best_nb = (ma, alpha, pipe, dt, pr)
_, alpha_nb, nb_pipe, nb_dt, nb_pr = best_nb
results['naive_bayes'] = evaluate_model('MultinomialNB', nb_pipe, X_va, y_va,
                                        nb_pr, nb_dt, f'alpha={alpha_nb}')

# --- LinearSVC با تنظیم C
best_svc = None
for C in [0.1, 1.0, 3.0]:
    pipe = Pipeline([('tfidf', make_tfidf()), ('clf', LinearSVC(C=C, random_state=SEED))])
    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    dt = time.perf_counter() - t0
    dec = pipe.decision_function(X_va)
    pred = (dec >= 0).astype(int)
    ma = f1_score(y_va, pred, average='macro')
    print(f'LinearSVC C={C}: val macro-F1={ma:.4f} PR-AUC={average_precision_score(y_va, dec):.4f}')
    if best_svc is None or ma > best_svc[0]:
        best_svc = (ma, C, pipe, dt, dec)
_, C_svc, svc_pipe, svc_dt, svc_dec = best_svc
results['linear_svc'] = evaluate_model('LinearSVC', svc_pipe, X_va, y_va,
                                       svc_dec, svc_dt, f'C={C_svc}')

print('\nvalidation summary:')
for k, v in results.items():
    print(f"  {v['name']:20s} P={v['precision']:.4f} R={v['recall']:.4f} "
          f"macroF1={v['macro_f1']:.4f} PR-AUC={v['pr_auc']:.4f} "
          f"fit={v['fit_seconds']}s ({v['params']})")

# %%
fig, ax = plt.subplots(figsize=(7, 4.6))
for name, pr, color in [('LogisticRegression', lr_pr, '#3b6ea5'),
                        ('MultinomialNB', nb_pr, '#c0392b'),
                        ('LinearSVC (decision)', svc_dec, '#2e7d32')]:
    p, r, _ = precision_recall_curve(y_va, pr)
    ax.plot(r, p, label=f'{name} (AP={average_precision_score(y_va, pr):.3f})',
            color=color)
ax.axhline(y_va.mean(), ls='--', c='grey', label=f'prevalence {y_va.mean():.2f}')
ax.set(xlabel='spam recall', ylabel='spam precision', title='PR curves — validation')
ax.grid(alpha=.3)
ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec8_pr.png'), dpi=130)
plt.close()

# %% [markdown]
# ## ۸.۴ آستانه با Precision ≥ ۰٫۹۰ برای مدل احتمالاتی

# %%
prob_name = 'naive_bayes' if results['naive_bayes']['pr_auc'] >= results['logreg']['pr_auc'] else 'logreg'
prob_pipe = nb_pipe if prob_name == 'naive_bayes' else lr_pipe
pv = nb_pr if prob_name == 'naive_bayes' else lr_pr
print('probabilistic model used for thresholding:', results[prob_name]['name'])

rows = []
for thr in np.round(np.arange(0.05, 0.951, 0.01), 2):
    pred = (pv >= thr).astype(int)
    rows.append((thr, precision_score(y_va, pred), recall_score(y_va, pred)))
sweep = pd.DataFrame(rows, columns=['thr', 'precision', 'recall'])
feasible = sweep[sweep.precision >= 0.90]
if len(feasible):
    best_row = feasible.sort_values(['recall', 'precision'], ascending=False).iloc[0]
else:
    best_row = sweep.sort_values('precision', ascending=False).iloc[0]
thr_best = float(best_row.thr)
print(f'chosen threshold={thr_best:.2f} -> val precision={best_row.precision:.4f} '
      f'recall={best_row.recall:.4f}')

fig, ax = plt.subplots(figsize=(7.4, 4.4))
ax.plot(sweep.thr, sweep.precision, label='precision', color='#3b6ea5')
ax.plot(sweep.thr, sweep.recall, label='recall', color='#c0392b')
ax.axhline(0.90, ls=':', c='k', lw=1, label='precision target 0.90')
ax.axvline(thr_best, ls='--', c='g', label=f'thr={thr_best:.2f}')
ax.set(xlabel='threshold', ylabel='score', title='Threshold sweep on validation')
ax.grid(alpha=.3)
ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec8_threshold.png'), dpi=130)
plt.close()

# %%
pte = prob_pipe.predict_proba(X_te)[:, 1]
pred_te = (pte >= thr_best).astype(int)
test_metrics = {
    'threshold': thr_best,
    'precision': float(precision_score(y_te, pred_te)),
    'recall': float(recall_score(y_te, pred_te)),
    'macro_f1': float(f1_score(y_te, pred_te, average='macro')),
    'pr_auc': float(average_precision_score(y_te, pte)),
    'accuracy': float((pred_te == y_te.to_numpy()).mean()),
}
print('TEST:', json.dumps(test_metrics, indent=2))

cm = confusion_matrix(y_te, pred_te)
print('\nconfusion matrix [ham, spam]:\n', cm)

fig, ax = plt.subplots(figsize=(4.2, 3.6))
ax.imshow(cm, cmap='Blues')
for i in range(2):
    for j in range(2):
        ax.text(j, i, f'{cm[i, j]}', ha='center', va='center',
                color='white' if cm[i, j] > cm.max() / 2 else 'black')
ax.set(xticks=[0, 1], yticks=[0, 1], xlabel='predicted', ylabel='true',
       title=f'Test @ thr={thr_best:.2f}')
ax.set_xticklabels(['ham', 'spam'])
ax.set_yticklabels(['ham', 'spam'])
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec8_confusion.png'), dpi=130)
plt.close()

# %%
test_df = pd.DataFrame({'text': X_te.to_numpy(), 'y': y_te.to_numpy(),
                        'p': pte, 'pred': pred_te})
fp = (test_df[(test_df.pred == 1) & (test_df.y == 0)]
      .sort_values('p', ascending=False).drop_duplicates('text'))
fn = (test_df[(test_df.pred == 0) & (test_df.y == 1)]
      .sort_values('p', ascending=False).drop_duplicates('text'))
print(f'false positives: {len(fp)} | false negatives: {len(fn)}')

errors = []
for _, r in fp.head(3).iterrows():
    errors.append({'type': 'FP', 'p': round(float(r.p), 3),
                   'text': r.text.strip()[:220]})
for _, r in fn.head(2).iterrows():
    errors.append({'type': 'FN', 'p': round(float(r.p), 3),
                   'text': r.text.strip()[:220]})
for e in errors:
    print(f"\n[{e['type']}] p={e['p']}\n  {e['text'][:160]}")

# %%
res = {
    'n_rows': int(len(df)),
    'n_unique_texts': int(df.text.nunique()),
    'n_duplicate_rows': dup_rows,
    'spam_pct': round(100 * float(df.y.mean()), 2),
    'length_chars': {'mean': round(float(lengths.mean()), 1),
                     'median': float(lengths.median()),
                     'p95': float(lengths.quantile(.95)),
                     'max': int(lengths.max())},
    'length_words': {'mean': round(float(words.mean()), 1),
                     'median': float(words.median()),
                     'max': int(words.max())},
    'split': {s: {'rows': int((df.split == s).sum()),
                  'spam': int(df.loc[df.split == s, 'y'].sum()),
                  'spam_pct': round(100 * float(df.loc[df.split == s, 'y'].mean()), 2)}
              for s in ['train', 'val', 'test']},
    'overlap_train_val': len(overlap),
    'overlap_train_test': len(overlap2),
    'baseline_val': b,
    'vocab_size': int(len(baseline.named_steps['tfidf'].vocabulary_)),
    'models_val': results,
    'probabilistic_model': results[prob_name]['name'],
    'threshold': thr_best,
    'threshold_val': {'precision': float(best_row.precision),
                      'recall': float(best_row.recall)},
    'test': test_metrics,
    'confusion': cm.tolist(),
    'errors': errors,
}
with open(os.path.join(OUT, 'sec8_results.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print('\nsaved out/sec8_results.json')

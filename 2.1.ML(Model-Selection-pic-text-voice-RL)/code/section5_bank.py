# %% [markdown]
# # بخش ۵ — مدل‌سازیِ طبقه‌بندی روی دادهٔ بانکی
#
# پیش‌بینی پذیرش سپردهٔ مدت‌دار (`y`) پیش از تماس با مشتری.
# - جداکنندهٔ فایل `;` است و **ترتیب ردیف‌ها زمانی** است (۲۰۰۸ تا ۲۰۱۰).
# - `duration` فقط پس از پایان تماس معلوم می‌شود، پس هدف پیش‌بینی را نشت می‌دهد و حذف می‌شود.
# - تقسیم ۷۰/۱۵/۱۵ با حفظ ترتیب زمانی، بدون بُر زدن.

# %%
import json
import os
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings('ignore')
RANDOM_STATE = 42

DATA = '../Day2_Datasets/01_BankMarketing/bank-additional-full.csv'
OUT = 'out'
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## ۵.۱ شناخت داده: ابعاد، توازن کلاس‌ها، unknown و دو ستون تله

# %%
df = pd.read_csv(DATA, sep=';')
print('shape:', df.shape)

y = (df['y'].astype(str).str.strip().str.lower() == 'yes').astype(int)
pos_rate = y.mean()
print(f'positive: {int(y.sum())} / {len(y)} = {100 * pos_rate:.4f}%')

cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and c != 'y']
unknown_counts = {
    c: int((df[c].astype(str).str.strip() == 'unknown').sum()) for c in cat_cols
}
unknown_counts = {k: v for k, v in unknown_counts.items() if v > 0}
print('unknown:', unknown_counts)

pdays_999 = int((df['pdays'] == 999).sum())
print(f'pdays == 999: {pdays_999} rows ({100 * pdays_999 / len(df):.2f}%)')

dur = df.assign(y=y).groupby('y')['duration']
print('duration mean/median by class:',
      {int(k): (round(v.mean(), 1), float(v.median())) for k, v in dur})

# %% [markdown]
# `duration` در کلاس مثبت میانگین ۵۵۳ ثانیه و در منفی ۲۲۱ ثانیه است؛ یعنی حذف نکردنش
# مدل را به «طول مکالمه» وابسته می‌کند که در لحظهٔ تصمیم (پیش از تماس) وجود ندارد.
#
# `pdays = 999` یعنی «مشتری قبلاً هیچ‌وقت تماس نگرفته» — نه ۹۹۹ روز پیش. پس این مقدار
# یک نشانگر گمشده است و باید به `NaN` + نشانگر دودویی تبدیل شود.

# %% [markdown]
# ## ۵.۲ تقسیم زمانی و Pipeline
#
# شش ویژگی مهندسی‌شده (همه بی‌حالت، بدون نشت):
# `was_contacted_before`، `pdays_since`، `total_contacts`، `prev_success`،
# `is_recession`، `age_bin`.

# %%
def engineer(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out['was_contacted_before'] = (out['pdays'] != 999).astype(int)
    out['pdays_since'] = out['pdays'].where(out['pdays'] != 999)      # 999 -> NaN
    out['total_contacts'] = out['campaign'] + out['previous']
    out['prev_success'] = (out['poutcome'].astype(str) == 'success').astype(int)
    out['is_recession'] = (out['emp.var.rate'] < 0).astype(int)
    out['age_bin'] = pd.cut(
        out['age'], bins=[16, 25, 35, 45, 55, 65, 120],
        labels=['<=25', '26-35', '36-45', '46-55', '56-65', '65+']).astype(object)
    out = out.drop(columns=['duration'])
    out = out.replace('unknown', np.nan)
    for c in out.columns:                      # keep plain object dtype for encoders
        if not pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype(object)
    return out


feat = engineer(df)
X = feat.drop(columns=['y'])
y = (feat['y'].astype(str).str.strip().str.lower() == 'yes').astype(int)

n = len(X)
i1, i2 = int(0.70 * n), int(0.85 * n)
X_tr, X_va, X_te = X.iloc[:i1], X.iloc[i1:i2], X.iloc[i2:]
y_tr, y_va, y_te = y.iloc[:i1], y.iloc[i1:i2], y.iloc[i2:]

for tag, Xs, ys in [('train', X_tr, y_tr), ('val', X_va, y_va), ('test', X_te, y_te)]:
    print(f'{tag:5s} n={len(Xs):5d}  pos={int(ys.sum()):5d}  rate={100 * ys.mean():5.2f}%')

num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
cat_cols = [c for c in X.columns if c not in num_cols]
print('numeric:', len(num_cols), '| categorical:', len(cat_cols))


def make_preprocessor(scale=True):
    num_steps = [('impute', SimpleImputer(strategy='median'))]
    if scale:
        num_steps.append(('scale', StandardScaler()))
    return ColumnTransformer(
        transformers=[
            ('num', Pipeline(num_steps), num_cols),
            ('cat', Pipeline([
                ('impute', SimpleImputer(strategy='most_frequent')),
                ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
            ]), cat_cols),
        ],
        remainder='drop',
        verbose_feature_names_out=False,
    )

# %% [markdown]
# ### رانش شیوع کلاس در طول زمان
#
# نرخ پذیرش از ~۳٪ (۲۰۰۸) به ~۴۶٪ (۲۰۱۰) می‌رسد؛ همبستگی `euribor3m` با شمارهٔ ردیف
# ‎−۰٫۸۵‎ است. پس شیوع کلاس در سه بخش عمداً متفاوت می‌شود و **PR-AUC بین بخش‌ها
# قابل مقایسهٔ مستقیم نیست** (به شیوع وابسته است)؛ `ROC-AUC` این مشکل را ندارد.

# %% [markdown]
# ## ۵.۳ مقایسهٔ مدل‌ها با اعتبارسنجی متناسب با زمان

# %%
models = {
    'majority_baseline': Pipeline([
        ('prep', make_preprocessor()),
        ('clf', DummyClassifier(strategy='most_frequent')),
    ]),
    'logistic_regression': Pipeline([
        ('prep', make_preprocessor()),
        ('clf', LogisticRegression(max_iter=3000, solver='lbfgs', C=1.0,
                                   random_state=RANDOM_STATE)),
    ]),
    'random_forest': Pipeline([
        ('prep', make_preprocessor(scale=False)),
        ('clf', RandomForestClassifier(
            n_estimators=400, min_samples_leaf=100, max_features='sqrt',
            class_weight='balanced_subsample', n_jobs=1, random_state=RANDOM_STATE)),
    ]),
    'hist_gradient_boosting_extra': Pipeline([
        ('prep', make_preprocessor(scale=False)),
        ('clf', HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, max_leaf_nodes=4,
            min_samples_leaf=300, early_stopping=False, random_state=RANDOM_STATE)),
    ]),
}


def score_block(y_true, proba, thr=0.5):
    pred = (proba >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        'pr_auc': float(average_precision_score(y_true, proba)),
        'roc_auc': float(roc_auc_score(y_true, proba)),
        'f1_pos': float(f1_score(y_true, pred, pos_label=1)),
        'precision': float(precision_score(y_true, pred, pos_label=1, zero_division=0)),
        'recall': float(recall_score(y_true, pred, pos_label=1)),
        'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
        'cost': float(5 * fn + fp),
    }


tscv = TimeSeriesSplit(n_splits=5)
cv_results, val_results, train_results, val_proba = {}, {}, {}, {}
for name, pipe in models.items():
    rows = []
    for tr_idx, va_idx in tscv.split(X_tr):
        pipe.fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx])
        rows.append(score_block(y_tr.iloc[va_idx],
                                pipe.predict_proba(X_tr.iloc[va_idx])[:, 1]))
    cv_results[name] = {
        k: float(np.mean([r[k] for r in rows])) for k in ['pr_auc', 'roc_auc', 'f1_pos']
    }
    cv_results[name]['pr_auc_std'] = float(np.std([r['pr_auc'] for r in rows]))
    cv_results[name]['fold_pos_rate'] = float(y_tr.mean())

    pipe.fit(X_tr, y_tr)
    val_proba[name] = pipe.predict_proba(X_va)[:, 1]
    train_results[name] = score_block(y_tr, pipe.predict_proba(X_tr)[:, 1])
    val_results[name] = score_block(y_va, val_proba[name])
    print(f'{name:28s} CV PR-AUC {cv_results[name]["pr_auc"]:.4f} '
          f'±{cv_results[name]["pr_auc_std"]:.4f} | '
          f'CV ROC-AUC {cv_results[name]["roc_auc"]:.4f} | '
          f'VAL PR-AUC {val_results[name]["pr_auc"]:.4f} '
          f'ROC-AUC {val_results[name]["roc_auc"]:.4f} '
          f'F1@.5 {val_results[name]["f1_pos"]:.4f}')

candidates = ['logistic_regression', 'random_forest', 'hist_gradient_boosting_extra']
best_name = max(candidates, key=lambda m: (val_results[m]['roc_auc'],
                                           val_results[m]['pr_auc']))
best_model = models[best_name]
print('\nselected:', best_name)

# %% [markdown]
# ## ۵.۴ انتخاب آستانه با هزینهٔ نامتقارن (FN = ۵×FP)

# %%
COST_FN, COST_FP = 5, 1


def cost_at(y_true, proba, thr):
    pred = (proba >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return float(COST_FN * fn + COST_FP * fp), (int(tn), int(fp), int(fn), int(tp))


pv = val_proba[best_name]
grid = np.round(np.arange(0.02, 0.96, 0.005), 3)
costs = np.array([cost_at(y_va, pv, t)[0] for t in grid])
best_thr = float(grid[int(np.argmin(costs))])
print(f'best threshold={best_thr:.3f} cost={costs.min():,.0f} '
      f'(at 0.5: {cost_at(y_va, pv, 0.5)[0]:,.0f})')

thr_report = {}
for thr in [0.5, best_thr]:
    cost, (tn, fp, fn, tp) = cost_at(y_va, pv, thr)
    pred = (pv >= thr).astype(int)
    thr_report[f'{thr:.3f}'] = {
        'threshold': float(thr), 'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
        'precision': float(precision_score(y_va, pred, pos_label=1, zero_division=0)),
        'recall': float(recall_score(y_va, pred, pos_label=1)),
        'f1': float(f1_score(y_va, pred, pos_label=1)),
        'cost': cost,
    }
    print(f'  thr={thr:.3f}: TN={tn} FP={fp} FN={fn} TP={tp} '
          f'P={thr_report[f"{thr:.3f}"]["precision"]:.3f} '
          f'R={thr_report[f"{thr:.3f}"]["recall"]:.3f} cost={cost:,.0f}')

# %% [markdown]
# ## ۵.۵ اهمیت ویژگی‌ها روی اعتبارسنجی و نتیجهٔ نهایی روی آزمون

# %%
perm = permutation_importance(best_model, X_va, y_va, scoring='roc_auc',
                              n_repeats=8, random_state=RANDOM_STATE, n_jobs=1)
imp = pd.Series(perm.importances_mean, index=X_va.columns).sort_values(ascending=False)
print(imp.head(10).round(4).to_string())

pos_imp = imp.clip(lower=0)
print(f'top-10 share of positive importance: '
      f'{100 * pos_imp.head(10).sum() / pos_imp.sum():.1f}%')

# %%
pt = best_model.predict_proba(X_te)[:, 1]
test_block = score_block(y_te, pt, thr=best_thr)
test_at_05 = score_block(y_te, pt, thr=0.5)
print(f'TEST thr={best_thr:.3f}: PR-AUC {test_block["pr_auc"]:.4f} '
      f'ROC-AUC {test_block["roc_auc"]:.4f} F1 {test_block["f1_pos"]:.4f} '
      f'P {test_block["precision"]:.3f} R {test_block["recall"]:.3f} '
      f'cost {test_block["cost"]:,.0f}')
print(f'TEST @0.5 cost {test_at_05["cost"]:,.0f}')

# %% [markdown]
# ## نمودارها

# %%
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for name in ['logistic_regression', 'random_forest', 'hist_gradient_boosting_extra']:
    p, r, _ = precision_recall_curve(y_va, val_proba[name])
    ax[0].plot(r, p, label=f'{name} (AP={val_results[name]["pr_auc"]:.3f})')
ax[0].axhline(y_va.mean(), ls='--', c='grey', label='prevalence (chance)')
ax[0].set(xlabel='Recall', ylabel='Precision', title='PR curve — validation')
ax[0].legend(fontsize=7)
ax[0].grid(alpha=.3)

ax[1].plot(grid, costs)
ax[1].axvline(best_thr, ls='--', c='r', label=f'best={best_thr:.2f}')
ax[1].axvline(0.5, ls=':', c='k', label='0.50')
ax[1].set(xlabel='threshold', ylabel='validation cost = 5·FN + FP',
          title='Asymmetric cost')
ax[1].legend(fontsize=8)
ax[1].grid(alpha=.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec5_pr_cost.png'), dpi=130)
plt.close()

fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
for k, thr in enumerate([0.5, best_thr]):
    cm = confusion_matrix(y_va, (pv >= thr).astype(int), labels=[0, 1])
    ax[k].imshow(cm, cmap='Blues')
    for i in range(2):
        for j in range(2):
            ax[k].text(j, i, f'{cm[i, j]:,}', ha='center', va='center',
                       color='white' if cm[i, j] > cm.max() / 2 else 'black')
    ax[k].set(title=f'validation @ thr={thr:.2f}', xticks=[0, 1], yticks=[0, 1],
              xlabel='predicted', ylabel='actual')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec5_confusion.png'), dpi=130)
plt.close()

fig, ax = plt.subplots(figsize=(7, 4.2))
imp.head(12)[::-1].plot(kind='barh', ax=ax, color='#3b6ea5')
ax.set(xlabel='drop in ROC-AUC when permuted',
       title='Permutation importance — validation')
ax.grid(alpha=.3, axis='x')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec5_importance.png'), dpi=130)
plt.close()

fig, ax = plt.subplots(figsize=(8, 3.6))
for name, series in [('train', y_tr), ('val', y_va), ('test', y_te)]:
    pass
rates = [100 * y_tr.mean(), 100 * y_va.mean(), 100 * y_te.mean()]
ax.bar(['train (2008-09)', 'val (2009-10)', 'test (2010)'], rates, color='#3b6ea5')
for i, v in enumerate(rates):
    ax.text(i, v + 1, f'{v:.1f}%', ha='center')
ax.set(ylabel='positive rate (%)', title='Chronological split: class-prevalence drift')
ax.grid(alpha=.3, axis='y')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec5_drift.png'), dpi=130)
plt.close()
print('figures ->', OUT)

# %%
results = {
    'n_rows': int(len(df)),
    'n_cols': int(df.shape[1]),
    'positive_count': int(y.sum()),
    'positive_rate_pct': round(100 * pos_rate, 4),
    'unknown_counts': unknown_counts,
    'pdays_999': pdays_999,
    'pdays_999_pct': round(100 * pdays_999 / len(df), 2),
    'split': {t: [len(s), round(100 * r.mean(), 2)]
              for t, s, r in [('train', X_tr, y_tr), ('val', X_va, y_va),
                              ('test', X_te, y_te)]},
    'engineered': ['was_contacted_before', 'pdays_since', 'total_contacts',
                   'prev_success', 'is_recession', 'age_bin'],
    'cv': cv_results,
    'train': train_results,
    'val': val_results,
    'selected_model': best_name,
    'threshold': {'best': best_thr, 'reported': thr_report},
    'test': test_block,
    'test_at_05': test_at_05,
    'importance': {k: float(v) for k, v in imp.head(12).items()},
}
with open(os.path.join(OUT, 'sec5_results.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('saved out/sec5_results.json')

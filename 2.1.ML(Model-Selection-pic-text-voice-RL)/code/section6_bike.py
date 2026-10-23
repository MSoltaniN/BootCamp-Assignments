# %% [markdown]
# # بخش ۶ — رگرسیون و مهندسی ویژگی برای تقاضای دوچرخه
#
# هدف: برآورد `cnt` (تعداد دوچرخهٔ اجاره‌شده) در هر ساعت از ویژگی‌های تقویمی و آب‌وهوایی همان ساعت.
# برای کاربرد آینده‌نگر، هوا باید از پیش معلوم یا پیش‌بینی‌شده باشد؛ پس از هیچ مقدار آینده استفاده نمی‌کنیم.

# %%
import json
import os
import time
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings('ignore')
RANDOM_STATE = 42

DATA = '../Day2_Datasets/02_BikeSharing/hour.csv'
OUT = 'out'
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## ۶.۱ مرتب‌سازی زمانی، تقسیم ۷۰/۱۵/۱۵ و خط پایه

# %%
df = pd.read_csv(DATA, parse_dates=['dteday'])
df = df.sort_values(['dteday', 'hr']).reset_index(drop=True)
print('rows:', len(df), '| range:', df.dteday.min().date(), '->', df.dteday.max().date())

# لیکج obvious
print('casual + registered == cnt for all rows:',
      bool(((df.casual + df.registered) == df.cnt).all()))
print('corr(temp, atemp) = %.4f' % df.temp.corr(df.atemp))

n = len(df)
i1, i2 = int(0.70 * n), int(0.85 * n)
train, val, test = df.iloc[:i1], df.iloc[i1:i2], df.iloc[i2:]
print(f'train {len(train)} ({train.dteday.min().date()}..{train.dteday.max().date()})')
print(f'val   {len(val)} ({val.dteday.min().date()}..{val.dteday.max().date()})')
print(f'test  {len(test)} ({test.dteday.min().date()}..{test.dteday.max().date()})')

# %% [markdown]
# ### خط پایه: میانگین `cnt` به تفکیک ساعت، فقط از آموزش
#
# ساده‌ترین مدل «فصلی» ممکن: برای هر ساعت شبانه‌روز، میانگین تاریخی همان ساعت در آموزش.

# %%
hour_profile = train.groupby('hr')['cnt'].mean()
baseline_val = val['hr'].map(hour_profile).to_numpy()
baseline_mae = mean_absolute_error(val['cnt'], baseline_val)
baseline_rmse = float(np.sqrt(mean_squared_error(val['cnt'], baseline_val)))
print(f'baseline (hour-of-day mean) VAL MAE={baseline_mae:.2f} RMSE={baseline_rmse:.2f}')

# %% [markdown]
# ### ستون‌های نشت‌دار و بی‌فایده
#
# | ستون | وضعیت | دلیل |
# |---|---|---|
# | `casual`، `registered` | **نشت اطلاعات** | اجزای تشکیل‌دهندهٔ هدف‌اند؛ `casual + registered = cnt` در تمام ردیف‌ها |
# | `instant` | شناسهٔ بی‌فایده | شمارهٔ ترتیبی ردیف؛ حامل هیچ اطلاعاتی نیست |
# | `dteday` | شناسه/شاخص زمان | برای مرتب‌سازی و تقسیم استفاده می‌شود، نه به‌عنوان ویژگی (وگرنه مدل روند زمانی را حفظ می‌کند) |
# | `atemp` | هم‌خطی شدید | همبستگی ۰٫۹۸۸ با `temp`؛ نگه داشتن هر دو بی‌فایده و مضر است |

# %% [markdown]
# ## ۶.۲ ویژگی‌های چرخه‌ای و تعاملی
#
# - `hr_sin/hr_cos` با دورهٔ ۲۴، `mnth_sin/mnth_cos` با دورهٔ ۱۲، `weekday_sin/weekday_cos` با دورهٔ ۷
# - تعاملی: `is_rush = workingday × (hr ∈ {7,8,9,17,18,19})` — چون اوج تقاضا در روزهای کاری
#   ساعت ۸ و ۱۷–۱۸ است و در تعطیلات این اوج جابه‌جا می‌شود. بدون این تعامل، مدل خطی
#   نمی‌تواند «شکل» اوج را بین روز کاری و تعطیل تفکیک کند.

# %%
def engineer(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    d['hr_sin'] = np.sin(2 * np.pi * d['hr'] / 24)
    d['hr_cos'] = np.cos(2 * np.pi * d['hr'] / 24)
    d['mnth_sin'] = np.sin(2 * np.pi * d['mnth'] / 12)
    d['mnth_cos'] = np.cos(2 * np.pi * d['mnth'] / 12)
    d['weekday_sin'] = np.sin(2 * np.pi * d['weekday'] / 7)
    d['weekday_cos'] = np.cos(2 * np.pi * d['weekday'] / 7)
    d['is_rush'] = ((d['workingday'] == 1) & d['hr'].isin([7, 8, 9, 17, 18, 19])).astype(int)
    d['work_hour_sin'] = d['workingday'] * d['hr_sin']
    d['work_hour_cos'] = d['workingday'] * d['hr_cos']
    d['weathersit'] = d['weathersit'].replace({4: 3})   # فقط ۳ ردیف؛ ادغام با «باران شدید»
    return d


feat = engineer(df)
DROP = ['instant', 'dteday', 'atemp', 'casual', 'registered', 'cnt']
X = feat.drop(columns=DROP)
y = feat['cnt']

X_tr, X_va, X_te = X.iloc[:i1], X.iloc[i1:i2], X.iloc[i2:]
y_tr, y_va, y_te = y.iloc[:i1], y.iloc[i1:i2], y.iloc[i2:]

num_cols = [c for c in X.columns if c not in ['season', 'weathersit']]
cat_cols = ['season', 'weathersit']
print('numeric (%d):' % len(num_cols), num_cols)
print('categorical:', cat_cols)

# %% [markdown]
# همهٔ تبدیل‌های نیازمند برازش (میانه/میانگین برای پر کردن، میانگین و انحراف‌معیار برای
# استانداردسازی، و دسته‌های one-hot) داخل `Pipeline` هستند و فقط روی `X_tr` برازش می‌شوند.
# هیچ آماره‌ای از val/test محاسبه نمی‌شود.

# %%
def make_prep(scale=True):
    steps = [('impute', SimpleImputer(strategy='median'))]
    if scale:
        steps.append(('scale', StandardScaler()))
    return ColumnTransformer([
        ('num', Pipeline(steps), num_cols),
        ('cat', Pipeline([
            ('impute', SimpleImputer(strategy='most_frequent')),
            ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
        ]), cat_cols),
    ], remainder='drop', verbose_feature_names_out=False)

# %% [markdown]
# ## ۶.۳ مقایسهٔ سه مدل با اعتبارسنجی زمانی

# %%
models = {
    'dummy_median': Pipeline([
        ('prep', make_prep()),
        ('reg', DummyRegressor(strategy='median')),
    ]),
    'ridge': Pipeline([
        ('prep', make_prep()),
        ('reg', Ridge(alpha=1.0, random_state=RANDOM_STATE)),
    ]),
    'hist_gradient_boosting': Pipeline([
        ('prep', make_prep(scale=False)),
        ('reg', HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=20, l2_regularization=1.0,
            early_stopping=False, random_state=RANDOM_STATE)),
    ]),
}


def metrics(y_true, y_pred):
    return {
        'mae': float(mean_absolute_error(y_true, y_pred)),
        'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


tscv = TimeSeriesSplit(n_splits=5)
results, fitted = {}, {}
for name, pipe in models.items():
    t0 = time.perf_counter()
    cv_mae = []
    for tr_idx, va_idx in tscv.split(X_tr):
        pipe.fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx])
        cv_mae.append(mean_absolute_error(
            y_tr.iloc[va_idx], pipe.predict(X_tr.iloc[va_idx])))
    cv_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    pipe.fit(X_tr, y_tr)
    fit_time = time.perf_counter() - t0
    pred_va = pipe.predict(X_va)
    fitted[name] = pred_va

    m = metrics(y_va, pred_va)
    m['cv_mae'] = float(np.mean(cv_mae))
    m['cv_mae_std'] = float(np.std(cv_mae))
    m['fit_seconds'] = round(fit_time, 3)
    m['cv_seconds'] = round(cv_time, 2)
    results[name] = m
    print(f'{name:26s} VAL MAE={m["mae"]:6.2f} RMSE={m["rmse"]:6.2f} | '
          f'CV MAE={m["cv_mae"]:6.2f}±{m["cv_mae_std"]:.2f} | fit {fit_time:.2f}s')

best_name = min(['ridge', 'hist_gradient_boosting'], key=lambda k: results[k]['mae'])
best = models[best_name]
print('\nselected:', best_name)

# %% [markdown]
# ### آزمایشِ بهبود — فقط روی اعتبارسنجی (آزمون دست‌نخورده می‌ماند)
#
# `cnt` یک شمارش است و واریانسش با میانگین رشد می‌کند؛ تابع هدفِ خطای مربعی روی مقدار خام
# ساعت‌های پرتقاضا را بیش از حد وزن می‌دهد. همان مدل با تابع هدفِ پواسون:

# %%
poisson = Pipeline([
    ('prep', make_prep(scale=False)),
    ('reg', HistGradientBoostingRegressor(
        loss='poisson', max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=20, l2_regularization=1.0,
        early_stopping=False, random_state=RANDOM_STATE)),
]).fit(X_tr, y_tr)
poisson_val = metrics(y_va, poisson.predict(X_va))
print(f'poisson variant VAL MAE={poisson_val["mae"]:.2f} RMSE={poisson_val["rmse"]:.2f} '
      f'(current: {results[best_name]["mae"]:.2f} / {results[best_name]["rmse"]:.2f})')

# %% [markdown]
# ## ۶.۴ ارزیابی نهایی روی آزمون (فقط یک بار)

# %%
pred_te = best.predict(X_te)
test_metrics = metrics(y_te, pred_te)
print(f'TEST MAE={test_metrics["mae"]:.2f} RMSE={test_metrics["rmse"]:.2f}')

resid = pred_te - y_te.to_numpy()
by_hour = pd.DataFrame({'hr': X_te['hr'].to_numpy(), 'err': resid,
                        'actual': y_te.to_numpy(), 'pred': pred_te})
hour_stats = by_hour.groupby('hr')['err'].agg(['mean', 'std'])
print('\nmean error by hour (pred - actual):')
print(hour_stats.round(1).to_string())

bins = pd.qcut(by_hour['actual'], 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
print('\nmean error by demand quintile:')
print(by_hour.groupby(bins, observed=True)['err'].agg(['mean', 'count']).round(1).to_string())
print('\nmean error by weathersit:')
print(by_hour.assign(ws=X_te['weathersit'].to_numpy())
      .groupby('ws')['err'].agg(['mean', 'count']).round(1).to_string())
print(f'\noverall bias (mean residual) = {resid.mean():.2f}')

# %% [markdown]
# ## نمودارها

# %%
fig, ax = plt.subplots(2, 1, figsize=(11, 6.4), sharex=False)
seg = slice(0, 400)
ax[0].plot(y_te.to_numpy()[seg], label='actual', lw=1.2, color='#1f3b57')
ax[0].plot(pred_te[seg], label='predicted', lw=1.2, color='#c0392b', alpha=.85)
ax[0].set(title='Test: actual vs predicted (first 400 hours)', ylabel='cnt')
ax[0].legend()
ax[0].grid(alpha=.3)

ax[1].scatter(y_te, pred_te, s=4, alpha=.25, color='#3b6ea5')
lims = [0, max(y_te.max(), pred_te.max()) * 1.02]
ax[1].plot(lims, lims, 'k--', lw=1)
ax[1].set(xlabel='actual cnt', ylabel='predicted cnt', title='Predicted vs actual — test')
ax[1].grid(alpha=.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec6_fit.png'), dpi=130)
plt.close()

fig, ax = plt.subplots(figsize=(9, 4))
ax.errorbar(hour_stats.index, hour_stats['mean'], yerr=hour_stats['std'],
            fmt='o-', capsize=3, color='#c0392b', ecolor='#999')
ax.axhline(0, color='k', lw=.8)
ax.set(xlabel='hour of day', ylabel='mean error (pred - actual)',
       title='Error by hour of day — test')
ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec6_error_hour.png'), dpi=130)
plt.close()

fig, ax = plt.subplots(figsize=(7, 4))
by_hour.groupby(bins, observed=True)['err'].agg(['mean', 'std']).pipe(
    lambda d: ax.bar(range(len(d)), d['mean'], yerr=d['std'], capsize=4, color='#3b6ea5'))
ax.axhline(0, color='k', lw=.8)
ax.set_xticks(range(5))
ax.set_xticklabels(['Q1\nlowest', 'Q2', 'Q3', 'Q4', 'Q5\nhighest'])
ax.set(xlabel='actual demand quintile', ylabel='mean error (pred - actual)',
       title='Error by demand level — test')
ax.grid(alpha=.3, axis='y')
plt.tight_layout()
plt.savefig(os.path.join(OUT, 'sec6_error_demand.png'), dpi=130)
plt.close()
print('figures ->', OUT)

# %%
imp = permutation_importance(best, X_va, y_va, scoring='neg_mean_absolute_error',
                             n_repeats=6, random_state=RANDOM_STATE, n_jobs=1)
imp_s = pd.Series(imp.importances_mean, index=X_va.columns).sort_values(ascending=False)
print('permutation importance (MAE increase):')
print(imp_s.head(8).round(2).to_string())

out = {
    'n_rows': int(len(df)),
    'split': {'train': len(train), 'val': len(val), 'test': len(test)},
    'date_ranges': {
        'train': [str(train.dteday.min().date()), str(train.dteday.max().date())],
        'val': [str(val.dteday.min().date()), str(val.dteday.max().date())],
        'test': [str(test.dteday.min().date()), str(test.dteday.max().date())],
    },
    'baseline': {'mae': float(baseline_mae), 'rmse': float(baseline_rmse)},
    'models': results,
    'selected': best_name,
    'improvement_poisson': poisson_val,
    'test': test_metrics,
    'bias_test': float(resid.mean()),
    'error_by_hour': {int(k): round(float(v), 1) for k, v in hour_stats['mean'].items()},
    'error_by_quintile': {str(k): round(float(v), 1) for k, v in
                          by_hour.groupby(bins, observed=True)['err'].mean().items()},
    'importance': {k: float(v) for k, v in imp_s.head(8).items()},
}
with open(os.path.join(OUT, 'sec6_results.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print('saved out/sec6_results.json')

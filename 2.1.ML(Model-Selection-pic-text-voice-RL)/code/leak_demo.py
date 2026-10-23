import numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score

P = '../Day2_Datasets/01_BankMarketing/bank-additional-full.csv'
df = pd.read_csv(P, sep=';')
df['y2'] = (df['y'].str.strip().str.lower() == 'yes').astype(int)

n = len(df)
i1, i2 = int(.7 * n), int(.85 * n)


def evaluate(keep_duration):
    d = df.copy()
    if not keep_duration:
        d = d.drop(columns=['duration'])
    d = d.replace('unknown', np.nan)
    for c in d.columns:
        if not pd.api.types.is_numeric_dtype(d[c]):
            d[c] = d[c].astype(object)
    X, y = d.drop(columns=['y2', 'y']), d['y2']
    Xtr, Xva = X.iloc[:i1], X.iloc[i1:i2]
    ytr, yva = y.iloc[:i1], y.iloc[i1:i2]
    num = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    cat = [c for c in X.columns if c not in num]
    prep = ColumnTransformer([
        ('n', Pipeline([('i', SimpleImputer(strategy='median')),
                        ('s', StandardScaler())]), num),
        ('c', Pipeline([('i', SimpleImputer(strategy='most_frequent')),
                        ('o', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), cat)])
    pipe = Pipeline([('prep', prep), ('clf', LogisticRegression(max_iter=3000, random_state=42))])
    pipe.fit(Xtr, ytr)
    pr = pipe.predict_proba(Xva)[:, 1]
    return roc_auc_score(yva, pr), average_precision_score(yva, pr)


for keep in [True, False]:
    roc, ap = evaluate(keep)
    tag = 'WITH duration' if keep else 'WITHOUT duration'
    print(f'{tag:18s} val ROC-AUC={roc:.4f}  PR-AUC={ap:.4f}')

# how well does duration alone separate the classes?
d0 = df.loc[df.y2 == 0, 'duration']
d1 = df.loc[df.y2 == 1, 'duration']
print(f'\nduration median: no={d0.median():.0f}s  yes={d1.median():.0f}s')
print(f'share of calls >600s that ended in yes: '
      f'{100 * (df.loc[df.duration > 600, "y2"].mean()):.1f}%  (overall {100 * df.y2.mean():.1f}%)')
print(f'share of calls <=120s that ended in yes: '
      f'{100 * (df.loc[df.duration <= 120, "y2"].mean()):.1f}%')

"""Build layer for the Superstore BI dashboard.

Reads the raw CSV once, computes the reference aggregates with pandas, and
emits a single self-contained HTML page that carries the CSV inside it. The
browser re-derives every number from that CSV, so the page and this script are
two independent implementations of the same aggregation — the page compares
them and reports the result in the footer.

Usage:
    python build.py                 # write out/dashboard.html
    python build.py --answers       # also print the section-1 answers
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CSV = ROOT / "superstore-sales.csv"
TEMPLATE = HERE / "template.html"
OUT = HERE / "out"


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    for col in ("Region", "Category", "Sub-Category", "Segment", "State", "City"):
        df[col] = df[col].astype(str).str.strip()
    df["Order Date"] = pd.to_datetime(df["Order Date"])
    return df


def aggregate(df: pd.DataFrame) -> dict:
    sales = float(df["Sales"].sum())
    profit = float(df["Profit"].sum())
    orders = int(df["Order ID"].nunique())
    sub = df.groupby("Sub-Category")["Profit"].sum()
    region = df.groupby("Region")["Sales"].sum()
    cat = df.groupby("Category")["Profit"].sum()
    year = df.groupby(df["Order Date"].dt.year)["Profit"].sum()
    return {
        "sales": sales,
        "profit": profit,
        "orders": orders,
        "margin": profit / sales,
        "lineItems": int(len(df)),
        "answers": {
            "1.1 total_sales": round(sales, 2),
            "1.2 total_profit": round(profit, 2),
            "1.3 orders": orders,
            "1.4 profit_margin_pct": round(profit / sales * 100, 4),
            "1.5 top_region_by_sales": region.idxmax(),
            "1.6 top_category_by_profit": cat.idxmax(),
            "1.7 worst_subcategory": sub.idxmin(),
            "1.8 best_year_by_profit": int(year.idxmax()),
        },
        "detail": {
            "region_sales": {k: round(float(v), 2) for k, v in region.items()},
            "category_profit": {k: round(float(v), 2) for k, v in cat.items()},
            "subcategory_profit": {k: round(float(v), 2) for k, v in sub.items()},
            "year_profit": {str(k): round(float(v), 2) for k, v in year.items()},
        },
    }


def build() -> tuple[Path, dict]:
    df = load(CSV)
    ref = aggregate(df)
    raw = CSV.read_text(encoding="utf-8")
    digest = hashlib.sha256(CSV.read_bytes()).hexdigest()[:10].upper()
    now = datetime.now()

    html = TEMPLATE.read_text(encoding="utf-8")
    payload = {
        "sales": ref["sales"],
        "profit": ref["profit"],
        "orders": ref["orders"],
        "margin": ref["margin"],
        "lineItems": ref["lineItems"],
    }
    html = html.replace("__CSV_DATA__", raw.replace("</script", "<\\/script"))
    html = html.replace("__REFERENCE__", json.dumps(payload))
    html = html.replace("__BUILD_TIME__", now.strftime("%d %b %Y %H:%M"))
    html = html.replace("__DATA_HASH__", digest)

    OUT.mkdir(exist_ok=True)
    dest = OUT / "dashboard.html"
    dest.write_text(html, encoding="utf-8")
    (HERE / "reference.json").write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest, ref


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", action="store_true", help="print section-1 answers")
    args = ap.parse_args()

    dest, ref = build()
    size = dest.stat().st_size
    print(f"built  {dest}  ({size/1024:.1f} KiB, {ref['lineItems']} rows embedded)")

    if args.answers:
        a = ref["answers"]
        for k, v in a.items():
            print(f"  {k:<26} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

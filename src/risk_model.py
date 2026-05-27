"""Overheating risk model.

Two layers:

  1. Weighted index — explainable, fixed weights documented in METHOD.
     This is the *defensible* score the dashboard uses.

  2. Random Forest classifier trained against the index-derived tier as
     target. The point is not to "validate" the index — that would be
     circular — but to produce a SHAP attribution view of which features
     drive the score, and to serve as a downstream API for the app.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from src.clean_epc import build_housing_features
from src.heat_features import heat_features_per_lad

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
MODELS.mkdir(parents=True, exist_ok=True)

# Index weights — sum to 1.0. Documented in docs/methodology.md.
WEIGHTS = {
    "daytime_heat":     0.22,
    "nighttime_heat":   0.20,
    "warming_trend":    0.10,
    "housing_form":     0.18,   # share of flats, share of EPC D+
    "social_vuln":      0.20,   # rented + over-65 share
    "urban_density":    0.10,   # households per LAD proxy
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6

TIER_BINS = [(0, 30, "Low"), (30, 60, "Medium"), (60, 80, "High"), (80, 101, "Severe")]

FEATURES = [
    "summer_tmax_mean", "summer_tmax_p95",
    "summer_tmin_mean", "summer_tmin_p95",
    "warming_since_baseline_c",
    "share_flats", "share_epc_d_or_worse",
    "share_rented_private", "share_rented_social",
    "share_65plus",
    "total_hh",
]


def _scale(values: pd.Series, low: float, high: float) -> pd.Series:
    """Clip + rescale to 0–100."""
    v = (values - low) / (high - low)
    return (v.clip(0, 1) * 100).fillna(0)


def compute_index(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the overheating risk index per row.

    Uses the strongest signal available:
      - If HadUK-Grid hot-day / tropical-night counts are present, use those.
      - Otherwise fall back to the monthly Tmax p95 / Tmin p95 proxies.
    """
    out = df.copy()

    # Daytime heat — true hot-day count if HadUK available, else Tmax p95 proxy.
    if "hot_days_28" in out.columns and out["hot_days_28"].notna().any():
        # Annual mean count of days > 28°C — 0 to ~15 in current UK climate
        out["sub_daytime_heat"] = _scale(out["hot_days_28"].fillna(0), 0, 15)
    else:
        out["sub_daytime_heat"] = _scale(out["summer_tmax_p95"], 18.0, 26.0)

    # Nighttime heat — true tropical-night count if HadUK available, else Tmin p95 proxy.
    if "tropical_nights_20" in out.columns and out["tropical_nights_20"].notna().any():
        out["sub_nighttime_heat"] = _scale(out["tropical_nights_20"].fillna(0), 0, 10)
    else:
        out["sub_nighttime_heat"] = _scale(out["summer_tmin_p95"], 10.0, 18.0)

    # Warming trend
    out["sub_warming_trend"] = _scale(out["warming_since_baseline_c"], 0.0, 2.5)

    # Housing form — flats + poor EPC
    flat_part = _scale(out["share_flats"], 0.1, 0.7)
    epc_part = _scale(out["share_epc_d_or_worse"], 0.3, 0.7)
    out["sub_housing_form"] = (flat_part + epc_part) / 2

    # Social vulnerability — private rented + over-65 (high rented OR high elderly both increase risk)
    rent_part = _scale(out["share_rented_private"], 0.10, 0.45)
    age_part = _scale(out["share_65plus"].fillna(out["share_65plus"].median()), 0.05, 0.25)
    out["sub_social_vuln"] = (rent_part + age_part) / 2

    # Urban density proxy — total households per LAD (London boroughs ~100k, county districts ~50k)
    out["sub_urban_density"] = _scale(out["total_hh"], 40_000, 200_000)

    out["overheating_risk_score"] = (
        WEIGHTS["daytime_heat"]    * out["sub_daytime_heat"]
        + WEIGHTS["nighttime_heat"]* out["sub_nighttime_heat"]
        + WEIGHTS["warming_trend"] * out["sub_warming_trend"]
        + WEIGHTS["housing_form"]  * out["sub_housing_form"]
        + WEIGHTS["social_vuln"]   * out["sub_social_vuln"]
        + WEIGHTS["urban_density"] * out["sub_urban_density"]
    ).round(2)

    out["risk_tier"] = pd.cut(
        out["overheating_risk_score"],
        bins=[b[0] for b in TIER_BINS] + [TIER_BINS[-1][1]],
        labels=[b[2] for b in TIER_BINS],
        include_lowest=True,
        right=False,
    ).astype(str)

    return out


def build_feature_table() -> pd.DataFrame:
    """End-to-end: assemble the LAD feature table."""
    housing = build_housing_features()
    full = heat_features_per_lad(housing)
    full = compute_index(full)
    cols = ["lad_code", "lad_name"] + FEATURES + [
        "sub_daytime_heat", "sub_nighttime_heat", "sub_warming_trend",
        "sub_housing_form", "sub_social_vuln", "sub_urban_density",
        "overheating_risk_score", "risk_tier", "met_region", "epc_source",
    ]
    full = full[[c for c in cols if c in full.columns]]
    full.to_parquet(PROCESSED / "lad_risk_table.parquet", index=False)
    return full


def train_classifier(df: pd.DataFrame, save: bool = True) -> dict:
    """Train RF on engineered features against the index-derived tier."""
    X = df[FEATURES].fillna(df[FEATURES].median())
    y = df["risk_tier"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if y.nunique() > 1 else None,
    )
    clf = RandomForestClassifier(
        n_estimators=200, max_depth=8, random_state=42, class_weight="balanced",
    )
    clf.fit(X_tr, y_tr)
    metrics = {
        "train_accuracy": float(clf.score(X_tr, y_tr)),
        "test_accuracy":  float(clf.score(X_te, y_te)),
        "feature_importances": dict(zip(FEATURES, [float(v) for v in clf.feature_importances_])),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "classes": list(clf.classes_),
    }
    if save:
        joblib.dump(clf, MODELS / "risk_model.pkl")
        (MODELS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="train the RF classifier")
    args = parser.parse_args()

    print("Building feature table ...")
    df = build_feature_table()
    print(f"  rows: {len(df)}  LADs: {df['lad_code'].nunique()}")
    print(df[["lad_name", "overheating_risk_score", "risk_tier"]].sort_values(
        "overheating_risk_score", ascending=False
    ).head(10).to_string(index=False))

    if args.train:
        print("\nTraining Random Forest ...")
        m = train_classifier(df)
        print(f"  train acc: {m['train_accuracy']:.3f}  test acc: {m['test_accuracy']:.3f}")
        print(f"  saved: models/risk_model.pkl")


if __name__ == "__main__":
    main()

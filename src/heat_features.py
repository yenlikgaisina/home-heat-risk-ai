"""Heat-exposure features derived from Met Office regional monthly series.

Met Office open regional series are *monthly* aggregates, not daily. So we
cannot count "days above 30°C" directly. We construct defensible proxies:

  - summer_tmax_mean  : mean June–August Tmax (latest decade)
  - summer_tmin_mean  : mean June–August Tmin (latest decade)  -> night heat
  - summer_tmax_p95   : 95th percentile of June–August monthly Tmax since 2000
  - warming_rate      : Tmax trend °C/decade vs 1961–1990 baseline

For more granular "hot days" / "hot nights" the methodology doc explains how
to plug in HadUK-Grid daily gridded data if you have CEDA access.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

SUMMER_MONTHS = {"jun", "jul", "aug"}
BASELINE = (1961, 1990)
RECENT = (2014, 2024)


def load_monthly() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "metoffice_monthly.parquet")


def regional_heat_features(monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    """Aggregate Met Office monthly series into per-region heat features."""
    if monthly is None:
        monthly = load_monthly()
    summer = monthly[monthly["month"].isin(SUMMER_MONTHS)].copy()

    recent_mask = summer["year"].between(*RECENT)
    recent = summer[recent_mask]

    pivot_recent = (
        recent.groupby(["region", "variable"])["value"]
        .agg(mean="mean", p95=lambda s: float(np.nanpercentile(s, 95)))
        .reset_index()
    )

    # Wide format
    tmax = pivot_recent[pivot_recent["variable"] == "tmax"].rename(
        columns={"mean": "summer_tmax_mean", "p95": "summer_tmax_p95"}
    )[["region", "summer_tmax_mean", "summer_tmax_p95"]]
    tmin = pivot_recent[pivot_recent["variable"] == "tmin"].rename(
        columns={"mean": "summer_tmin_mean", "p95": "summer_tmin_p95"}
    )[["region", "summer_tmin_mean", "summer_tmin_p95"]]

    feats = tmax.merge(tmin, on="region", how="outer")

    # Warming rate: recent decade mean Tmax minus baseline mean Tmax.
    base = summer[summer["year"].between(*BASELINE) & (summer["variable"] == "tmax")]
    base_mean = base.groupby("region")["value"].mean().rename("baseline_summer_tmax")
    feats = feats.merge(base_mean, on="region", how="left")
    feats["warming_since_baseline_c"] = (
        feats["summer_tmax_mean"] - feats["baseline_summer_tmax"]
    ).round(2)

    feats["summer_tmax_mean"] = feats["summer_tmax_mean"].round(2)
    feats["summer_tmax_p95"] = feats["summer_tmax_p95"].round(2)
    feats["summer_tmin_mean"] = feats["summer_tmin_mean"].round(2)
    feats["summer_tmin_p95"] = feats["summer_tmin_p95"].round(2)
    feats["baseline_summer_tmax"] = feats["baseline_summer_tmax"].round(2)
    return feats


# LAD -> Met Office region mapping for the 41 LADs we care about.
LAD_TO_REGION = {
    # All London boroughs use the SE_and_Central_S_England series
    **{code: "SE_and_Central_S_England" for code in [
        "E09000001", "E09000002", "E09000003", "E09000004", "E09000005", "E09000006",
        "E09000007", "E09000008", "E09000009", "E09000010", "E09000011", "E09000012",
        "E09000013", "E09000014", "E09000015", "E09000016", "E09000017", "E09000018",
        "E09000019", "E09000020", "E09000021", "E09000022", "E09000023", "E09000024",
        "E09000025", "E09000026", "E09000027", "E09000028", "E09000029", "E09000030",
        "E09000031", "E09000032", "E09000033",
    ]},
    # Nottingham + Notts LADs use Midlands series
    **{code: "Midlands" for code in [
        "E06000018", "E07000170", "E07000171", "E07000172", "E07000173",
        "E07000174", "E07000175", "E07000176",
    ]},
}


def heat_features_per_lad(lads: pd.DataFrame) -> pd.DataFrame:
    """Join heat features onto a LAD frame.

    Preferred path: per-LAD HadUK-Grid daily features at
    `data/processed/lad_haduk_features.parquet` (if you've run
    `src/load_haduk.py` + `src/aggregate_haduk.py`). These give true hot-day
    and tropical-night counts per LAD.

    Fallback: Met Office monthly regional series, joined via LAD_TO_REGION.
    Coarser, but works without CEDA access.

    A column `heat_data_source` records which path was used per row.
    """
    haduk_path = PROCESSED / "lad_haduk_features.parquet"
    out = lads.copy()
    out["met_region"] = out["lad_code"].map(LAD_TO_REGION)

    if haduk_path.exists():
        haduk = pd.read_parquet(haduk_path)
        # Use HadUK columns where available; rename to match the index inputs.
        rename = {
            "summer_tmax_mean": "summer_tmax_mean",
            "summer_tmax_p95":  "summer_tmax_p95",
            "summer_tmin_mean": "summer_tmin_mean",
            "summer_tmin_p95":  "summer_tmin_p95",
        }
        out = out.merge(haduk[["lad_code"] + list(rename.keys()) + [
            "hot_days_25", "hot_days_28", "hot_days_30",
            "tropical_nights_20", "warm_nights_18",
        ]], on="lad_code", how="left")
        # warming_since_baseline_c isn't in HadUK output; still pull from regional
        reg = regional_heat_features()
        warming = reg[["region", "warming_since_baseline_c", "baseline_summer_tmax"]]
        out = out.merge(warming, left_on="met_region", right_on="region", how="left")
        out["heat_data_source"] = "hadukgrid_5km_daily"
    else:
        reg = regional_heat_features()
        out = out.merge(reg, left_on="met_region", right_on="region", how="left")
        out["heat_data_source"] = "metoffice_monthly_regional"
        # Surrogate hot-day / tropical-night counts so downstream code doesn't break
        out["hot_days_25"] = np.nan
        out["hot_days_28"] = np.nan
        out["hot_days_30"] = np.nan
        out["tropical_nights_20"] = np.nan
        out["warm_nights_18"] = np.nan
    return out


if __name__ == "__main__":
    feats = regional_heat_features()
    print(feats.to_string(index=False))
    feats.to_parquet(PROCESSED / "heat_features_regional.parquet", index=False)

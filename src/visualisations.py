"""Plotting helpers shared by notebooks and the Streamlit app."""

from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / "outputs" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

TIER_COLORS = {"Low": "#3a9ad9", "Medium": "#f6c844", "High": "#e87d3e", "Severe": "#c0392b"}


def plot_summer_tmax_trend(monthly: pd.DataFrame, region: str = "UK", save: bool = True) -> Path | None:
    """Decadal summer Tmax mean vs baseline."""
    summer = monthly[
        (monthly["variable"] == "tmax")
        & (monthly["region"] == region)
        & (monthly["month"].isin(["jun", "jul", "aug"]))
    ].copy()
    annual = summer.groupby("year")["value"].mean().reset_index()
    annual["decade"] = (annual["year"] // 10) * 10
    by_decade = annual.groupby("decade")["value"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(by_decade["decade"], by_decade["value"], marker="o", linewidth=2, color="#c0392b")
    baseline = annual[annual["year"].between(1961, 1990)]["value"].mean()
    ax.axhline(baseline, linestyle="--", color="gray", label=f"1961–1990 baseline: {baseline:.2f}°C")
    ax.set_title(f"Summer mean Tmax by decade — {region} (Met Office regional series)")
    ax.set_xlabel("Decade")
    ax.set_ylabel("°C")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if save:
        out = CHARTS / f"summer_tmax_decadal_{region}.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        return out
    return None


def plot_risk_ranked(risk_table: pd.DataFrame, top: int = 25, save: bool = True) -> Path | None:
    df = risk_table.sort_values("overheating_risk_score", ascending=True).tail(top)
    colors = [TIER_COLORS.get(t, "#888") for t in df["risk_tier"]]
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(df) + 1))
    ax.barh(df["lad_name"], df["overheating_risk_score"], color=colors)
    ax.set_xlabel("Overheating risk score (0–100)")
    ax.set_title(f"Top {top} LADs by overheating risk (London + Notts)")
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    if save:
        out = CHARTS / "lad_risk_ranked.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        return out
    return None


def plot_feature_importances(metrics: dict, save: bool = True) -> Path | None:
    fi = pd.Series(metrics["feature_importances"]).sort_values()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(fi.index, fi.values, color="#34495e")
    ax.set_title("Random Forest feature importances")
    ax.set_xlabel("Importance")
    fig.tight_layout()
    if save:
        out = CHARTS / "feature_importances.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        return out
    return None

"""Home Heat Risk AI — Streamlit dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.recommendations import HouseholdInput, recommend
from src.risk_model import FEATURES, WEIGHTS, TIER_BINS, compute_index, build_feature_table

PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
CHARTS = ROOT / "outputs" / "charts"

TIER_COLORS = {"Low": "#3a9ad9", "Medium": "#f6c844", "High": "#e87d3e", "Severe": "#c0392b"}

st.set_page_config(page_title="Home Heat Risk AI", page_icon="🌡️", layout="wide")


# ---------------------------------------------------------------------------
# Data loaders (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_risk_table() -> pd.DataFrame:
    path = PROCESSED / "lad_risk_table.parquet"
    if not path.exists():
        return build_feature_table()
    return pd.read_parquet(path)


@st.cache_data
def load_monthly() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "metoffice_monthly.parquet")


@st.cache_data
def load_neso_regional() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "neso_regional_now.parquet")


@st.cache_resource
def load_model():
    path = MODELS / "risk_model.pkl"
    return joblib.load(path) if path.exists() else None


@st.cache_data
def load_metrics() -> dict | None:
    path = MODELS / "metrics.json"
    return json.loads(path.read_text()) if path.exists() else None


# ---------------------------------------------------------------------------
# Sidebar nav
# ---------------------------------------------------------------------------

st.sidebar.title("🌡️ Home Heat Risk AI")
st.sidebar.caption("UK overheating risk — London + Nottingham MVP")
page = st.sidebar.radio(
    "Page",
    [
        "Overview",
        "Heat trends",
        "Housing vulnerability",
        "Risk map",
        "Cooling recommendation",
        "Model interpretability",
        "Policy insights",
        "Responsible AI",
    ],
)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Data: Met Office regional series · ONS Census 2021 (NOMIS) · NESO Carbon "
    "Intensity API. EPC: hybrid — real bulk data where coverage is sufficient, "
    "synthesised fallback otherwise. See data dictionary."
)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

if page == "Overview":
    st.title("Home Heat Risk AI")
    st.markdown(
        "**Research question.** Which UK homes are most vulnerable to overheating, and where "
        "is passive cooling no longer enough?"
    )

    risk = load_risk_table()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Local authorities covered", risk["lad_code"].nunique())
    c2.metric("Mean risk score", f"{risk['overheating_risk_score'].mean():.1f}")
    c3.metric("LADs in High tier", int((risk["risk_tier"] == "High").sum()))
    c4.metric("LADs in Severe tier", int((risk["risk_tier"] == "Severe").sum()))

    # EPC provenance summary — surfaces hybrid coverage up-front.
    epc_counts = risk["epc_source"].value_counts()
    n_real = int(epc_counts.get("real", 0))
    n_low = int(epc_counts.get("synthesized_fallback_low_coverage", 0))
    n_syn = int(epc_counts.get("synthesized", 0))
    n_total = len(risk)
    st.caption(
        f"**EPC source:** real for {n_real}/{n_total} LADs · "
        f"synthesised fallback for {n_low + n_syn} "
        f"({n_low} low coverage, {n_syn} out of scope). "
        "The EPC layer is *hybrid* — see Methodology."
    )
    with st.expander("How EPC coverage works"):
        st.markdown(
            """
            Each local authority's EPC band distribution comes from one of three sources:

            - **`real`** — real EPC certificates from the MHCLG bulk service,
              deduplicated to the latest certificate per UPRN, with **≥ 500**
              certificates in the LAD.
            - **`synthesized_fallback_low_coverage`** — the LAD appears in the
              bulk file but has **< 500 certificates**, so the empirical
              distribution is too noisy to trust. We fall back to a synthesised
              prior built from national EPC priors adjusted for flat share and
              private-rented share.
            - **`synthesized`** — the LAD is not covered by the EPC bulk service
              (Scotland and Northern Ireland). Same synthesised prior is used.

            The threshold (`MIN_REAL_EPC_CERTS = 500` in `src/clean_epc.py`)
            keeps band-share sampling error under ≈ 2 percentage points even
            for the smallest realistic band (~1 % A-rated stock).
            """
        )

    st.markdown("### Top 15 LADs by overheating risk")
    top = risk.sort_values("overheating_risk_score", ascending=False).head(15)
    fig = px.bar(
        top, x="overheating_risk_score", y="lad_name", orientation="h",
        color="risk_tier", color_discrete_map=TIER_COLORS,
        labels={"overheating_risk_score": "Risk score (0–100)", "lad_name": ""},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=520)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### How the score is built")
    weight_df = pd.DataFrame(
        {"factor": list(WEIGHTS.keys()), "weight": list(WEIGHTS.values())}
    ).sort_values("weight", ascending=True)
    fig2 = px.bar(weight_df, x="weight", y="factor", orientation="h")
    fig2.update_layout(height=320, xaxis_tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)


elif page == "Heat trends":
    st.title("Heat trends")
    monthly = load_monthly()
    region_opts = sorted(monthly["region"].unique())
    region = st.selectbox("Region", region_opts, index=region_opts.index("UK") if "UK" in region_opts else 0)

    summer = monthly[
        (monthly["variable"] == "tmax")
        & (monthly["region"] == region)
        & (monthly["month"].isin(["jun", "jul", "aug"]))
    ]
    annual = summer.groupby("year")["value"].mean().reset_index()
    baseline = annual[annual["year"].between(1961, 1990)]["value"].mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=annual["year"], y=annual["value"], mode="lines", name="Annual summer Tmax"))
    annual["rolling10"] = annual["value"].rolling(10, min_periods=1).mean()
    fig.add_trace(go.Scatter(x=annual["year"], y=annual["rolling10"], mode="lines",
                              name="10-year rolling mean", line=dict(color="#c0392b", width=3)))
    fig.add_hline(y=baseline, line_dash="dash",
                  annotation_text=f"1961–1990 baseline: {baseline:.2f}°C")
    fig.update_layout(height=480, yaxis_title="°C", xaxis_title="Year")
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Source: Met Office regional climate series (open). "
        f"Latest decade ({region}) summer Tmax mean: "
        f"**{annual[annual['year'] >= 2014]['value'].mean():.2f}°C** "
        f"vs. 1961–1990 baseline **{baseline:.2f}°C**."
    )

    st.markdown("### Summer night-time heat (Tmin) — the bigger health signal")
    tmin = monthly[
        (monthly["variable"] == "tmin")
        & (monthly["region"] == region)
        & (monthly["month"].isin(["jun", "jul", "aug"]))
    ]
    if not tmin.empty:
        tmin_ann = tmin.groupby("year")["value"].mean().reset_index()
        fig2 = px.line(tmin_ann, x="year", y="value", title=f"{region}: mean summer Tmin")
        fig2.update_layout(height=380, yaxis_title="°C")
        st.plotly_chart(fig2, use_container_width=True)


elif page == "Housing vulnerability":
    st.title("Housing vulnerability")
    risk = load_risk_table()
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(
            risk, x="share_flats", y="share_rented_private",
            color="risk_tier", color_discrete_map=TIER_COLORS,
            size="total_hh", hover_name="lad_name",
            labels={"share_flats": "Share of flats", "share_rented_private": "Share private rented"},
        )
        fig.update_layout(height=480)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.scatter(
            risk, x="share_epc_d_or_worse", y="share_65plus",
            color="risk_tier", color_discrete_map=TIER_COLORS,
            symbol="epc_source",
            symbol_map={
                "real": "circle",
                "synthesized_fallback_low_coverage": "diamond",
                "synthesized": "square",
            },
            size="total_hh", hover_name="lad_name",
            hover_data={"epc_certificates": True, "epc_source": True,
                         "total_hh": False, "risk_tier": False},
            labels={"share_epc_d_or_worse": "Share with EPC D or worse (hybrid)",
                     "share_65plus": "Share aged 65+"},
        )
        fig.update_layout(height=480)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Marker shape encodes EPC provenance: "
            "● real EPC · ◆ synthesised fallback (< 500 certs) · "
            "■ no EPC bulk coverage. Hover for certificate count."
        )

    st.markdown("### Per-LAD detail")
    show = risk.sort_values("overheating_risk_score", ascending=False)[[
        "lad_name", "share_flats", "share_rented_private", "share_65plus",
        "share_epc_d_or_worse", "epc_source", "epc_certificates",
        "overheating_risk_score", "risk_tier",
    ]]
    st.dataframe(show, use_container_width=True, hide_index=True)


elif page == "Risk map":
    st.title("Risk map")
    risk = load_risk_table()
    risk_show = risk.sort_values("overheating_risk_score", ascending=False)
    fig = px.bar(
        risk_show.head(41), x="lad_name", y="overheating_risk_score",
        color="risk_tier", color_discrete_map=TIER_COLORS,
    )
    fig.update_layout(xaxis_tickangle=-65, height=560)
    st.plotly_chart(fig, use_container_width=True)
    st.info(
        "A geospatial choropleth (folium / plotly mapbox + LAD GeoJSON) "
        "is wired in the notebook `04_model_overheating_risk.ipynb`. "
        "It's omitted from the live app to keep the deployment lightweight."
    )

    st.markdown("### Live regional grid carbon")
    neso = load_neso_regional()
    fig2 = px.bar(
        neso.sort_values("intensity_forecast_gco2_kwh"),
        x="region", y="intensity_forecast_gco2_kwh", color="intensity_index",
        color_discrete_map={"very low": "#2ecc71", "low": "#a4d65e", "moderate": "#f6c844",
                            "high": "#e87d3e", "very high": "#c0392b"},
    )
    fig2.update_layout(height=380, xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Source: NESO Carbon Intensity API — current half-hour snapshot.")


elif page == "Cooling recommendation":
    st.title("Cooling recommendation")
    st.caption("Rules-based — not an LLM. Inputs are explicit, output is auditable.")

    risk = load_risk_table()
    lad = st.selectbox("Your local authority", sorted(risk["lad_name"].unique()))
    area_row = risk[risk["lad_name"] == lad].iloc[0]
    area_tier = area_row["risk_tier"]
    st.info(f"Area risk tier: **{area_tier}** (score {area_row['overheating_risk_score']:.1f})")

    # EPC provenance disclosure — silent when data is real, gentle when not.
    epc_src = area_row.get("epc_source", "real")
    epc_n = int(area_row.get("epc_certificates", 0))
    if epc_src == "synthesized_fallback_low_coverage":
        st.caption(
            f"ℹ️ EPC indicator for **{lad}** is a statistical prior — only "
            f"{epc_n:,} certificates in the bulk file. Treat the area EPC mix "
            "as approximate."
        )
    elif epc_src == "synthesized":
        st.caption(
            f"ℹ️ **{lad}** has no EPC bulk coverage; the EPC mix shown is a "
            "synthesised prior from housing and tenure shares."
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        ptype = st.selectbox("Property type", ["flat", "terraced", "semi", "detached"])
        floor = st.selectbox("Floor", ["ground", "mid", "top"])
    with c2:
        epc = st.selectbox("EPC band", ["A", "B", "C", "D", "E", "F", "G"], index=2)
        tenure = st.selectbox("Tenure", ["owned", "private_rented", "social_rented"])
    with c3:
        orient = st.selectbox("Main window orientation", ["south", "west", "east", "north", "unknown"])
        has_ac = st.checkbox("I already have AC")

    # Carbon intensity from cached NESO snapshot
    neso = load_neso_regional()
    if "London" in lad or any(b in lad for b in ["Westminster", "Camden", "Tower Hamlets"]):
        ci_row = neso[neso["region"] == "London"]
    else:
        ci_row = neso[neso["region"] == "East Midlands"]
    ci = ci_row["intensity_index"].iloc[0] if not ci_row.empty else "moderate"

    rec = recommend(HouseholdInput(
        property_type=ptype, floor=floor, epc_band=epc, tenure=tenure,
        orientation=orient, has_ac=has_ac,
        area_risk_tier=area_tier, area_carbon_intensity=ci,
    ))

    st.markdown(f"### {rec.headline}")
    st.markdown("**Recommended actions**")
    for a in rec.actions:
        st.markdown(f"- {a}")
    if rec.avoid:
        st.markdown("**Avoid**")
        for a in rec.avoid:
            st.markdown(f"- {a}")
    st.markdown(f"**Carbon context.** {rec.carbon_note}")
    with st.expander("Why these recommendations?"):
        for r in rec.rationale:
            st.markdown(f"- {r}")


elif page == "Model interpretability":
    st.title("Model interpretability")
    metrics = load_metrics()
    if metrics is None:
        st.warning("Train the model first: `python -m src.risk_model --train`")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Train accuracy", f"{metrics['train_accuracy']:.2%}")
        c2.metric("Test accuracy", f"{metrics['test_accuracy']:.2%}")
        c3.metric("Classes", ", ".join(metrics["classes"]))
        st.caption(
            "Caveat: model trained on index-derived target on n=41. Train≈100% indicates "
            "overfit-to-target — useful for SHAP/feature attribution, not for held-out generalisation."
        )

        fi = pd.Series(metrics["feature_importances"]).sort_values()
        fig = px.bar(fi, orientation="h", labels={"value": "Importance", "index": "Feature"})
        fig.update_layout(height=480, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


elif page == "Policy insights":
    st.title("Policy insights")
    risk = load_risk_table()

    st.markdown("#### Where to focus first")
    severe_or_high = risk[risk["risk_tier"].isin(["High", "Severe"])]
    st.markdown(
        f"- **{len(severe_or_high)} of {len(risk)} LADs** in this MVP sit in High or Severe tiers. "
        f"These contain roughly **{int(severe_or_high['total_hh'].sum()):,}** households between them."
    )
    st.markdown(
        "- Approved Document O (England) currently regulates overheating only in *new* residential builds. "
        "The risk concentrations here are in *existing* dense urban stock — retrofit policy is the lever."
    )
    st.markdown(
        "- Renters and social tenants in High/Severe areas have least agency to install cooling. "
        "Equity-weighted intervention prioritisation should target the joint signal of "
        "high area risk × high private/social rented share."
    )
    flag = risk[(risk["risk_tier"].isin(["High", "Severe"])) & (risk["share_rented_private"] > 0.30)]
    if not flag.empty:
        st.markdown(
            f"**Priority LADs (high risk + >30% private rented):** " +
            ", ".join(flag.sort_values("overheating_risk_score", ascending=False)["lad_name"].head(10))
        )


elif page == "Responsible AI":
    st.title("Responsible AI statement")
    st.markdown(
        """
This is a portfolio data-science project, not an operational tool. Read this before drawing conclusions from it.

**What this is.**

- A documented, auditable overheating risk index built from open Met Office and ONS Census data.
- A rules-based recommendation engine — explicitly not an LLM. The rules live in `src/recommendations.py`.
- A Random Forest model trained against the index-derived tier, used for SHAP-style feature attribution.

**What this is not.**

- This is not a diagnosis of any individual home. It estimates *area-level* exposure risk.
- It does not validate against real indoor temperatures — no such public dataset exists at this granularity.
- The EPC distribution layer is synthesized, not measured. Treat housing-quality signals as priors, not facts.

**Fairness.**

- High risk often co-occurs with renting, lower income, and lower agency to act. The model surfaces this rather than punishing it. Policy actions derived from this work should reduce vulnerability, not penalise vulnerable groups.

**For real decisions.**

- Use this to identify *where to look*, not what to do. Validate any specific intervention with a qualified building assessor and local public-health guidance (UKHSA Heat-Health Alert system).
        """
    )

st.markdown("---")
st.caption("MIT licensed · data licenses per source · build: 2026")

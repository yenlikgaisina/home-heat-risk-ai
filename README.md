# Home Heat Risk AI

A climate adaptation data science project that estimates UK home overheating risk and recommends cooling interventions. MVP covers **London + Nottingham** at local-authority and regional level.

> **Research question.** Which UK homes are most vulnerable to overheating, and where is passive cooling no longer enough?

## What it does

- Combines Met Office regional climate series, ONS Census 2021 housing data, and NESO grid carbon intensity into an explainable overheating risk score (0–100) per area.
- Trains a Random Forest classifier on engineered features to predict risk tier (Low / Medium / High / Severe).
- Recommends a cooling intervention (passive cooling, shading, night-purge ventilation, heat-pump cooling, air conditioning) using a rules engine — not an LLM. The rules are documented, auditable, and defensible.
- Surfaces it all through a Streamlit dashboard with a risk map, area profile, and a household-level recommendation tool.

## What's real vs. synthesized

I've been explicit because honesty matters more here than polish.

| Component | Source | Real or synthesized |
| --- | --- | --- |
| Daily/monthly Tmax & Tmin | Met Office regional climate series (open) | **Real** |
| Grid carbon intensity | NESO Carbon Intensity API (open) | **Real** |
| Housing tenure & accommodation type | ONS Census 2021 via NOMIS (open) | **Real** |
| Population density, vulnerable age share | ONS Census 2021 via NOMIS | **Real** |
| EPC ratings & building age band | Synthesized from Census proxies + national EPC distribution priors | **Synthesized** (the EPC bulk service requires registration) |
| Indoor temperature exceedance | Not used — no public area-level data | N/A |

If you obtain EPC bulk data (register at [epc.opendatacommunities.org](https://epc.opendatacommunities.org/)), drop the CSV into `data/raw/epc/` and re-run `python -m src.clean_epc` to replace the synthesized layer.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Fetch real climate, carbon, and Census data
python -m src.load_data

# 2. Engineer features + train the model
python -m src.risk_model --train

# 3. Run the dashboard
streamlit run app.py
```

## Optional: real daily climate via CEDA HadUK-Grid

The default pipeline uses Met Office *monthly* regional series. If you want
true per-LAD hot-day and tropical-night counts, plug in HadUK-Grid daily 5km
gridded data:

```bash
# 1. Register at https://services.ceda.ac.uk/ and accept the HadUK-Grid licence.
# 2. Export your CEDA credentials.
export CEDA_USER='your_username'
export CEDA_PASS='your_password'

# 3. Probe total bytes before committing (warning: full 2010–2024 set is ~4 GB).
python -m src.load_haduk --start 2010 --end 2024 --summer-only --dry-run

# 4. Download.
python -m src.load_haduk --start 2010 --end 2024 --summer-only

# 5. Aggregate the 5km grid into per-LAD annual hot-day / tropical-night counts.
python -m src.aggregate_haduk --start 2014 --end 2024

# 6. Re-train. The risk index automatically switches to the new features.
python -m src.risk_model --train
```

The pipeline is opt-in and backwards compatible — if `data/processed/lad_haduk_features.parquet` doesn't exist, the index falls back to the monthly regional proxies. The `heat_data_source` column on the risk table tells you which path each LAD used.

**Why this matters.** Monthly Tmax p95 is a defensible proxy but it can't distinguish a heatwave-prone area from a generally-warm-summer area. Daily data lets you count "days above 28°C" and "tropical nights" (Tmin > 20°C), which are the metrics UKHSA actually uses for heat-mortality modelling.

## Repo layout

```
home-heat-risk-ai/
├── app.py                       # Streamlit dashboard
├── requirements.txt
├── data/
│   ├── raw/                     # Cached downloads (gitignored)
│   ├── processed/               # Feature tables (parquet)
│   └── sample/                  # Small sample CSVs for CI / portfolio
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_eda_heat_trends.ipynb
│   ├── 03_housing_risk_features.ipynb
│   ├── 04_model_overheating_risk.ipynb
│   └── 05_policy_insights.ipynb
├── src/
│   ├── load_data.py             # Real-data fetchers
│   ├── clean_epc.py             # EPC ingestion (or synthesis fallback)
│   ├── heat_features.py         # Hot day / hot night counts, trends
│   ├── risk_model.py            # Weighted index + Random Forest
│   ├── recommendations.py       # Cooling intervention rules engine
│   └── visualisations.py        # Shared plotting helpers
├── models/
│   └── risk_model.pkl
├── outputs/
│   ├── charts/
│   └── maps/
└── docs/
    ├── methodology.md
    ├── data_dictionary.md
    └── responsible_ai_statement.md
```

## Methodology in one paragraph

For each area I compute a **weighted overheating risk score** from six factor families — summer daytime heat, night-time heat retention, housing stock vulnerability (flat share, age band, EPC proxy), urban density, social vulnerability (older / renting / lower income), and grid carbon intensity (used to score cooling carbon cost, not risk itself). Weights are documented in `docs/methodology.md` and live in `src/risk_model.py` so you can audit and change them. I also train a Random Forest on the same features against the index-derived tier as a sanity check on which features dominate — SHAP plots show feature attribution. The dashboard exposes both: index for transparency, model for "which signals matter most" interpretation.

## Limitations (read before relying on this)

- Synthesized EPC layer means area-level building risk is a **prior**, not measurement.
- No indoor temperature data — risk is an exposure proxy, not a verified overheating prediction.
- ML model is trained on an index-derived target; it learns the index by construction. It's useful for SHAP interpretability and as a downstream API, but it does not validate the index against ground truth.
- This is a portfolio project, not an operational tool. See `docs/responsible_ai_statement.md`.

## License

MIT for the code. Data licenses follow each upstream source — see `docs/data_dictionary.md`.

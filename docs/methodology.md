# Methodology

## Risk score construction

For each local authority district (LAD) we compute a score from 0 to 100 as a weighted sum of six sub-scores. Each sub-score is itself a clipped linear rescale of one or more raw indicators onto 0–100, with the low/high anchors chosen from the empirical distribution across our 41 LADs plus published UK climate norms.

| Sub-score | Inputs | Low anchor | High anchor | Weight |
| --- | --- | --- | --- | --- |
| Daytime heat | Met Office regional summer Tmax p95 (2014–24) | 18°C | 26°C | 0.22 |
| Night-time heat | Met Office regional summer Tmin p95 (2014–24) | 10°C | 18°C | 0.20 |
| Warming trend | Recent-decade Tmax minus 1961–1990 baseline | 0.0°C | 2.5°C | 0.10 |
| Housing form | Share of flats; share with EPC D or worse (hybrid — see EPC section) | 0.10 / 0.30 | 0.70 / 0.70 | 0.18 |
| Social vulnerability | Share private rented; share aged 65+ | 0.10 / 0.05 | 0.45 / 0.25 | 0.20 |
| Urban density | Total households per LAD | 40 000 | 200 000 | 0.10 |

Weights sum to 1. They are listed in `src/risk_model.py` (`WEIGHTS` dict) — change them there.

Final score is bucketed into four tiers using fixed thresholds: Low 0–29, Medium 30–59, High 60–79, Severe 80–100.

## Why a weighted index, not a learned model

We don't have ground-truth indoor temperature or excess-mortality data at LAD level. Any supervised model would need a synthesized target — which makes it a restatement of the index, not an independent validation. Honest framing:

> The Random Forest classifier is trained against the index-derived tier. It is useful for **feature attribution** (SHAP) and as a serialisable model artefact for downstream use. It does not validate the index.

If you obtain UKHSA heat-mortality data at LAD/region level, you can swap the index target for a real outcome and re-train. Hook is in place: see `src/risk_model.py::train_classifier`.

## Heat features: monthly, not daily

Met Office *open* regional series are monthly aggregates, not daily. We therefore use monthly Tmax and Tmin summer statistics, plus a recent-decade vs. baseline shift. To get true "hot day" / "hot night" counts you need HadUK-Grid daily gridded data via CEDA (registration required). Pseudocode for that pathway is in the methodology section of `notebooks/02_eda_heat_trends.ipynb`.

## EPC layer (hybrid: real where coverage is sufficient, synthesised otherwise)

The EPC band distribution per LAD is assembled from a mix of real and synthesised sources, with the source recorded per row in `epc_source`. The rule:

1. **Real bulk data is preferred.** If the MHCLG EPC bulk CSV is present at `data/raw/epc/all_certificates.csv`, we stream it in chunks, dedupe to the latest certificate per UPRN (the standard practice), and aggregate band counts per LAD.

2. **Coverage threshold gate.** For each LAD covered by the bulk file, we count its real certificates. If the count is **≥ `MIN_REAL_EPC_CERTS` (= 500)**, the real distribution is used and `epc_source = 'real'`. Otherwise — the LAD is in the bulk file but the empirical distribution is too sparse to trust — we fall back to the synthesised prior and mark `epc_source = 'synthesized_fallback_low_coverage'`. The (small) real count is preserved in `epc_certificates` so the dashboard can disclose it.

3. **Out-of-scope fallback.** For LADs not in the bulk file at all (Scotland, NI — the EPC bulk service is England + Wales only), we use the synthesised prior and mark `epc_source = 'synthesized'`. `epc_certificates = 0`.

The synthesised prior is built from:

1. **National prior** — England 2024 headline distribution (A 1% / B 5% / C 40% / D 40% / E 10% / F 3% / G 1%).
2. **Flat-share adjustment** — flats are on average more efficient; we shift mass D/E → B/C proportional to flat share.
3. **Tenure adjustment** — private rented sector is on average less efficient; we shift mass C → D proportional to private rented share.

The threshold and the synthesised priors all live in `src/clean_epc.py` so the choices are auditable. The dashboard's Overview, Housing vulnerability, and Cooling recommendation pages all surface `epc_source` to the user — see the responsible AI statement for what we claim and what we don't.

For LADs flagged `synthesized` or `synthesized_fallback_low_coverage`, any conclusion that depends materially on EPC distribution is a prior, not a measurement. Treat accordingly.

## Recommendations engine

The cooling recommendation engine is a transparent rules engine, not an LLM. Rules live in `src/recommendations.py` as plain Python `if` statements that fire on household inputs and produce an ordered list of actions, things to avoid, and a carbon framing. This is intentional: rules are auditable, traceable, and update under version control. LLMs are not.

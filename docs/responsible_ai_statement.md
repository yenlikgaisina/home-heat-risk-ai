# Responsible AI Statement

This is a portfolio data-science project, not an operational tool. Read this before drawing conclusions from it.

## What this is

- A documented, auditable overheating risk index built from open Met Office and ONS Census data, plus a synthesized EPC layer.
- A rules-based recommendation engine — explicitly not an LLM. The rules live in `src/recommendations.py` and can be diffed under version control.
- A Random Forest model trained against the index-derived tier, used only for feature attribution.

## What this is not

- This is not a diagnosis of any individual home. It estimates *area-level* exposure risk.
- It does not validate against real indoor temperatures — no public dataset of indoor heat exposure exists at this granularity in the UK.
- The EPC distribution layer is synthesized, not measured. Treat housing-quality signals as informed priors, not facts.

## Fairness considerations

High overheating risk often co-occurs with renting, lower household income, and lower agency to act. The model **surfaces** this co-occurrence rather than punishing it: high social vulnerability raises the priority of an area for adaptation support, it does not mark residents as a "risk".

Any policy or product decision derived from this work should:

1. Be targeted at *reducing* vulnerability (subsidising shading, ventilation, retrofit) — not denying services to vulnerable groups.
2. Be checked against an equity-impact assessment before deployment.
3. Avoid the "rich-area pull" of risk maps: high *exposure* and high *vulnerability* are distinct, and a fair tool keeps both visible.

## Honest limitations

- **n = 41 LADs.** This MVP covers London plus the Nottingham travel-to-work area. Model accuracy figures are not generalisable.
- **Synthetic target.** The classifier learns the index by construction. Train accuracy ≈ 100% is overfit-to-target — useful for SHAP, not for held-out generalisation.
- **Monthly climate.** Met Office *open* regional series are monthly. True heatwave counts need HadUK-Grid daily data (CEDA registration required).
- **No indoor measurement.** Risk is an exposure proxy, not a verified prediction of indoor overheating.

## For real decisions

Use this work to identify *where to look*, not what to do. Validate any specific intervention with a qualified building assessor, your local authority's housing energy team, and UKHSA's Heat-Health Alert guidance. For tenant-side issues, contact Citizens Advice or your local council's environmental health team.

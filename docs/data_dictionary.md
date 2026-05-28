# Data Dictionary

## Sources and licenses

| Source | Endpoint | License |
| --- | --- | --- |
| Met Office regional climate series | `https://www.metoffice.gov.uk/pub/data/weather/uk/climate/datasets/{var}/date/{region}.txt` | Open Government Licence v3 |
| NESO Carbon Intensity API | `https://api.carbonintensity.org.uk/...` | CC BY 4.0 |
| ONS Census 2021 via NOMIS | `https://www.nomisweb.co.uk/api/v01/dataset/...` | Open Government Licence v3 |
| MHCLG Domestic EPC bulk service | `https://epc.opendatacommunities.org/` | Custom — requires registration & licence acceptance, redistribution prohibited |

## Files written to `data/processed/`

### `metoffice_monthly.parquet`

Long-format monthly regional climate.

| Column | Type | Notes |
| --- | --- | --- |
| year | int | 1884–present |
| month | str | jan…dec |
| value | float | °C |
| variable | str | tmax / tmin / tmean |
| region | str | UK / England / Midlands / SE_and_Central_S_England |

### `neso_national_recent.parquet`

National GB carbon intensity for the last 24 hours, half-hourly.

| Column | Type | Notes |
| --- | --- | --- |
| from / to | datetime | Half-hour window |
| forecast | int | gCO2/kWh |
| actual | int | gCO2/kWh (may be null for future windows) |
| index | str | very low / low / moderate / high / very high |

### `neso_regional_now.parquet`

Current half-hour snapshot for each GB region.

### `census_tenure.parquet`, `census_accommodation.parquet`

Long-format ONS Census 2021 (TS054, TS044), 41 LADs (33 London + 8 Notts area).

### `housing_features.parquet`

Per-LAD wide-format housing layer assembled by `src/clean_epc.py`.

| Column | Notes |
| --- | --- |
| share_flats | Sum of purpose-built + converted + commercial flat shares |
| share_owned, share_rented_private, share_rented_social | Tenure shares |
| share_65plus | Population aged 65+ (when census_age.parquet present) |
| epc_share_A … epc_share_G | EPC band shares (hybrid — see `epc_source`) |
| share_epc_d_or_worse | Sum of D+E+F+G band shares |
| epc_certificates | Number of real EPC certificates in the LAD after latest-per-UPRN dedup. `0` for LADs with no bulk coverage. |
| epc_source | Provenance of the EPC distribution. See below. |

#### `epc_source` values

The EPC layer is **hybrid** — assembled per-LAD from one of three sources:

| Value | Meaning |
| --- | --- |
| `real` | EPC bulk certificates from MHCLG, latest-per-UPRN deduped, with **≥ 500** certificates in the LAD. The empirical band distribution is used directly. |
| `synthesized_fallback_low_coverage` | The LAD appears in the bulk file but has **< 500** certificates after dedup — the empirical distribution is too noisy to trust. A synthesised prior is used instead; `epc_certificates` reports the (small) real count for transparency. |
| `synthesized` | The LAD is not covered by the EPC bulk service at all (Scotland and Northern Ireland). A synthesised prior is used; `epc_certificates = 0`. |

The threshold lives in `src/clean_epc.py` as `MIN_REAL_EPC_CERTS = 500`. It is chosen so band-share sampling error stays under ~2 percentage points even for the smallest realistic band (~1 % A-rated stock).

The synthesised prior starts from national EPC band proportions (MHCLG English Housing Survey-derived) and shifts mass between bands based on the LAD's flat share (flats lean more efficient) and private-rented share (PRS leans less efficient). The formula is in `synthesize_epc_distribution()`.

### `lad_risk_table.parquet`

The headline output. One row per LAD with the six sub-scores and the final `overheating_risk_score` and `risk_tier`.

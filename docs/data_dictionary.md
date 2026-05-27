# Data Dictionary

## Sources and licenses

| Source | Endpoint | License |
| --- | --- | --- |
| Met Office regional climate series | `https://www.metoffice.gov.uk/pub/data/weather/uk/climate/datasets/{var}/date/{region}.txt` | Open Government Licence v3 |
| NESO Carbon Intensity API | `https://api.carbonintensity.org.uk/...` | CC BY 4.0 |
| ONS Census 2021 via NOMIS | `https://www.nomisweb.co.uk/api/v01/dataset/...` | Open Government Licence v3 |

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
| epc_share_A … epc_share_G | **Synthesized** EPC distribution |
| share_epc_d_or_worse | Synthesized — sum D+E+F+G |
| epc_source | `"synthesized"` until real EPC data is provided |

### `lad_risk_table.parquet`

The headline output. One row per LAD with the six sub-scores and the final `overheating_risk_score` and `risk_tier`.

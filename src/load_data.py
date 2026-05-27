"""Fetch real data from open UK sources and cache locally.

Sources used:
  - Met Office regional climate series (open text files)
  - NESO Carbon Intensity API (open, no auth)
  - ONS Census 2021 via NOMIS API (open, no auth)

Anything that requires registration (Met Office HadUK-Grid via CEDA, EPC bulk
data via opendatacommunities) is NOT fetched here. See clean_epc.py for the
synthesized housing-quality fallback.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Met Office regional series
# ---------------------------------------------------------------------------

# UK-wide and English region time series. Format is a text table with year then
# 12 monthly columns and a few seasonal columns. We parse the monthly columns.
MO_BASE = "https://www.metoffice.gov.uk/pub/data/weather/uk/climate/datasets"

# Region keys map to Met Office filename slugs. Nottingham sits in "Midlands";
# London sits in "South_East_and_Central_South" historically, but Met Office
# also publishes a "England_S" series. We use the broader regional groupings
# the Met Office actually publishes.
MO_REGIONS = {
    "UK": "UK",
    "England": "England",
    "Midlands": "Midlands",            # covers Nottingham
    "SE_and_Central_S_England": "England_SE_and_Central_S",  # covers London
}

MO_VARIABLES = {
    "tmax": "Tmax",
    "tmin": "Tmin",
    "tmean": "Tmean",
}


def _parse_met_office_series(text: str) -> pd.DataFrame:
    """Met Office regional series text -> tidy DataFrame.

    File layout: header lines starting with '#' or text, then rows of
    `year jan feb mar ... dec win spr sum aut ann`. Missing values are '---'.
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "Year", "year")) or "---" not in line and not line[:4].isdigit():
            continue
        parts = line.split()
        if not parts[0].isdigit():
            continue
        rows.append(parts)
    if not rows:
        return pd.DataFrame()
    months = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
    cols = ["year"] + months + ["win", "spr", "sum", "aut", "ann"]
    df = pd.DataFrame(rows, columns=cols[: len(rows[0])])
    df = df.replace("---", pd.NA)
    df["year"] = df["year"].astype(int)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    long = df.melt(
        id_vars="year",
        value_vars=[m for m in months if m in df.columns],
        var_name="month",
        value_name="value",
    )
    long["month_num"] = long["month"].map({m: i + 1 for i, m in enumerate(months)})
    long["date"] = pd.to_datetime(
        long["year"].astype(str) + "-" + long["month_num"].astype(str).str.zfill(2) + "-01"
    )
    return long.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def fetch_met_office(variable: str, region: str) -> pd.DataFrame:
    """Fetch one variable+region from Met Office and parse to tidy frame."""
    var_slug = MO_VARIABLES[variable]
    region_slug = MO_REGIONS[region]
    url = f"{MO_BASE}/{var_slug}/date/{region_slug}.txt"
    cache = RAW / f"metoffice_{variable}_{region}.txt"
    if cache.exists():
        text = cache.read_text()
    else:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        text = resp.text
        cache.write_text(text)
    df = _parse_met_office_series(text)
    df["variable"] = variable
    df["region"] = region
    return df


def fetch_all_met_office() -> pd.DataFrame:
    frames = []
    for var in MO_VARIABLES:
        for reg in MO_REGIONS:
            try:
                frames.append(fetch_met_office(var, reg))
            except Exception as e:  # pragma: no cover
                print(f"  ! {var}/{reg} failed: {e}")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not out.empty:
        out.to_parquet(PROCESSED / "metoffice_monthly.parquet", index=False)
    return out


# ---------------------------------------------------------------------------
# NESO Carbon Intensity
# ---------------------------------------------------------------------------

def fetch_neso_regional() -> pd.DataFrame:
    """Snapshot of current regional carbon intensity. London and East Midlands
    region IDs are 13 and 6 respectively."""
    url = "https://api.carbonintensity.org.uk/regional"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    rows = []
    for window in payload.get("data", []):
        for reg in window.get("regions", []):
            rows.append({
                "from": window["from"],
                "to": window["to"],
                "region_id": reg["regionid"],
                "region": reg["shortname"],
                "intensity_forecast_gco2_kwh": reg["intensity"]["forecast"],
                "intensity_index": reg["intensity"]["index"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_parquet(PROCESSED / "neso_regional_now.parquet", index=False)
    return df


def fetch_neso_intensity_recent(hours: int = 48) -> pd.DataFrame:
    """National GB grid carbon intensity for the last `hours` hours."""
    url = f"https://api.carbonintensity.org.uk/intensity/date"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    intensity = pd.json_normalize(df["intensity"])
    out = pd.concat([df[["from", "to"]], intensity], axis=1)
    out["from"] = pd.to_datetime(out["from"])
    out["to"] = pd.to_datetime(out["to"])
    out.to_parquet(PROCESSED / "neso_national_recent.parquet", index=False)
    return out


# ---------------------------------------------------------------------------
# ONS Census 2021 via NOMIS
# ---------------------------------------------------------------------------

# London and Nottingham local authority district codes.
LONDON_LADS = [
    "E09000001", "E09000002", "E09000003", "E09000004", "E09000005", "E09000006",
    "E09000007", "E09000008", "E09000009", "E09000010", "E09000011", "E09000012",
    "E09000013", "E09000014", "E09000015", "E09000016", "E09000017", "E09000018",
    "E09000019", "E09000020", "E09000021", "E09000022", "E09000023", "E09000024",
    "E09000025", "E09000026", "E09000027", "E09000028", "E09000029", "E09000030",
    "E09000031", "E09000032", "E09000033",
]
NOTTINGHAM_LADS = [
    "E06000018",  # Nottingham UA
    "E07000170",  # Ashfield
    "E07000171",  # Bassetlaw
    "E07000172",  # Broxtowe
    "E07000173",  # Gedling
    "E07000174",  # Mansfield
    "E07000175",  # Newark and Sherwood
    "E07000176",  # Rushcliffe
]
TARGET_LADS = LONDON_LADS + NOTTINGHAM_LADS


def _nomis_csv(dataset: str, params: dict) -> pd.DataFrame:
    base = f"https://www.nomisweb.co.uk/api/v01/dataset/{dataset}.data.csv"
    resp = requests.get(base, params=params, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def fetch_census_tenure() -> pd.DataFrame:
    """TS054: Tenure of household, LAD geography."""
    df = _nomis_csv(
        "NM_2072_1",
        {
            "date": "latest",
            "geography": "TYPE154",  # LADs
            "c2021_tenure_9": "0...8",
            "measures": "20100",
        },
    )
    df = df[df["GEOGRAPHY_CODE"].isin(TARGET_LADS)].copy()
    df = df.rename(columns={
        "GEOGRAPHY_CODE": "lad_code",
        "GEOGRAPHY_NAME": "lad_name",
        "C2021_TENURE_9_NAME": "tenure",
        "OBS_VALUE": "households",
    })
    out = df[["lad_code", "lad_name", "tenure", "households"]]
    out.to_parquet(PROCESSED / "census_tenure.parquet", index=False)
    return out


def fetch_census_accommodation() -> pd.DataFrame:
    """TS044: Accommodation type, LAD. NOMIS dataset NM_2062_1."""
    df = _nomis_csv(
        "NM_2062_1",
        {
            "date": "latest",
            "geography": "TYPE154",
            "c2021_acctype_9": "0...8",
            "measures": "20100",
        },
    )
    df = df[df["GEOGRAPHY_CODE"].isin(TARGET_LADS)].copy()
    df = df.rename(columns={
        "GEOGRAPHY_CODE": "lad_code",
        "GEOGRAPHY_NAME": "lad_name",
        "C2021_ACCTYPE_9_NAME": "accommodation_type",
        "OBS_VALUE": "households",
    })
    out = df[["lad_code", "lad_name", "accommodation_type", "households"]]
    out.to_parquet(PROCESSED / "census_accommodation.parquet", index=False)
    return out


def fetch_census_age() -> pd.DataFrame:
    """TS007A: Age (broad bands), LAD."""
    df = _nomis_csv(
        "NM_2020_1",
        {
            "date": "latest",
            "geography": "TYPE154",
            "c2021_age_19": "0...18",
            "measures": "20100",
        },
    )
    df = df[df["GEOGRAPHY_CODE"].isin(TARGET_LADS)].copy()
    df = df.rename(columns={
        "GEOGRAPHY_CODE": "lad_code",
        "GEOGRAPHY_NAME": "lad_name",
        "C2021_AGE_19_NAME": "age_band",
        "OBS_VALUE": "people",
    })
    out = df[["lad_code", "lad_name", "age_band", "people"]]
    out.to_parquet(PROCESSED / "census_age.parquet", index=False)
    return out


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    print("[1/5] Met Office regional climate series ...")
    mo = fetch_all_met_office()
    print(f"      rows: {len(mo)}")

    print("[2/5] NESO national carbon intensity (recent) ...")
    neso_nat = fetch_neso_intensity_recent()
    print(f"      rows: {len(neso_nat)}")

    print("[3/5] NESO regional carbon intensity (snapshot) ...")
    neso_reg = fetch_neso_regional()
    print(f"      rows: {len(neso_reg)}")

    print("[4/5] ONS Census 2021 — tenure ...")
    ten = fetch_census_tenure()
    print(f"      rows: {len(ten)} ; LADs: {ten['lad_code'].nunique()}")

    print("[5/5] ONS Census 2021 — accommodation type ...")
    acc = fetch_census_accommodation()
    print(f"      rows: {len(acc)} ; LADs: {acc['lad_code'].nunique()}")

    print("\nDone. Files written to data/processed/.")


if __name__ == "__main__":
    main()

"""Housing-quality features per LAD.

The EPC bulk service (epc.opendatacommunities.org) requires registration. To
keep the project runnable end-to-end I synthesize an EPC distribution per LAD
from public proxies — flat share, tenure mix, and national EPC priors. The
README is explicit about this.

If a user drops the real EPC CSV at `data/raw/epc/all_certificates.csv`, this
module switches to using the real distribution. The merge is hybrid: LADs
covered by the bulk file (England + Wales) get the real distribution; LADs
not covered (Scotland, Northern Ireland) keep the synthesized distribution.
The per-row `epc_source` column records which path was used.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

EPC_CSV = RAW / "epc" / "all_certificates.csv"
EPC_BANDS = ["A", "B", "C", "D", "E", "F", "G"]

# Minimum number of real EPC certificates (post-dedup) needed for a LAD's
# real EPC distribution to be considered statistically meaningful. LADs
# below this threshold fall back to the synthesised distribution, tagged
# with epc_source='synthesized_fallback_low_coverage' so downstream
# consumers can flag them. 500 is a rule of thumb: it keeps band-share
# sampling error under ~2 pp for the smallest realistic band (~1% A-rated
# stock) and matches MHCLG's own coverage caveats.
MIN_REAL_EPC_CERTS = 500

# National EPC distribution priors for England 2024 (rounded percentages of
# domestic dwellings — sourced from MHCLG English Housing Survey-derived
# headline figures). Documented in docs/data_dictionary.md.
NATIONAL_EPC_PRIORS = {"A": 0.01, "B": 0.05, "C": 0.40, "D": 0.40, "E": 0.10, "F": 0.03, "G": 0.01}

# Built-form priors per accommodation_type category (heuristic, from English
# Housing Survey patterns). Used only when EPC bulk data not available.
BUILDFORM_PRIORS = {
    "flat_share":    {"top_floor": 0.25, "mid_floor": 0.50, "ground_floor": 0.25},
    "terraced":      {"top_floor": 0.00, "mid_floor": 0.00, "ground_floor": 1.00},
    "detached":      {"top_floor": 0.00, "mid_floor": 0.00, "ground_floor": 1.00},
}


def _normalise_accommodation(acc: pd.DataFrame) -> pd.DataFrame:
    """Collapse 9-way accommodation_type into the broad categories we need."""
    acc = acc.copy()
    acc = acc[acc["accommodation_type"] != "Total: All households"]
    cat_map = {
        "Detached":                                                          "detached",
        "Semi-detached":                                                     "semi",
        "Terraced":                                                          "terraced",
        "In a purpose-built block of flats or tenement":                     "flat_purpose",
        "Part of a converted or shared house, including bedsits":            "flat_converted",
        "In a commercial building, for example, in an office building, hotel or over a shop": "flat_commercial",
        "A caravan or other mobile or temporary structure":                  "mobile",
    }
    acc["cat"] = acc["accommodation_type"].map(cat_map).fillna("other")
    totals = acc.groupby("lad_code")["households"].sum().rename("total_hh")
    out = acc.pivot_table(
        index=["lad_code", "lad_name"],
        columns="cat",
        values="households",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    out = out.merge(totals, on="lad_code")
    for c in ["detached", "semi", "terraced", "flat_purpose", "flat_converted", "flat_commercial", "mobile", "other"]:
        if c not in out.columns:
            out[c] = 0
        out[f"share_{c}"] = (out[c] / out["total_hh"]).round(4)
    out["share_flats"] = (
        out["share_flat_purpose"] + out["share_flat_converted"] + out["share_flat_commercial"]
    ).round(4)
    return out[[
        "lad_code", "lad_name", "total_hh",
        "share_detached", "share_semi", "share_terraced",
        "share_flats", "share_flat_purpose", "share_flat_converted",
    ]]


def _normalise_tenure(ten: pd.DataFrame) -> pd.DataFrame:
    ten = ten.copy()
    ten = ten[ten["tenure"] != "Total: All households"]
    cat = {
        "Owned: Owns outright":                              "own_outright",
        "Owned: Owns with a mortgage or loan":               "own_mortgage",
        "Shared ownership: Shared ownership":                "shared_own",
        "Social rented: Rents from council or Local Authority": "rent_social_la",
        "Social rented: Other social rented":                "rent_social_other",
        "Private rented: Private landlord or letting agency":"rent_private_landlord",
        "Private rented: Other private rented":              "rent_private_other",
        "Lives rent free":                                   "rent_free",
    }
    ten["cat"] = ten["tenure"].map(cat).fillna("other")
    totals = ten.groupby("lad_code")["households"].sum().rename("total_hh_t")
    out = ten.pivot_table(
        index=["lad_code", "lad_name"],
        columns="cat",
        values="households",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    out = out.merge(totals, on="lad_code")
    out["share_owned"] = (
        (out.get("own_outright", 0) + out.get("own_mortgage", 0)) / out["total_hh_t"]
    ).round(4)
    out["share_rented_private"] = (
        (out.get("rent_private_landlord", 0) + out.get("rent_private_other", 0)) / out["total_hh_t"]
    ).round(4)
    out["share_rented_social"] = (
        (out.get("rent_social_la", 0) + out.get("rent_social_other", 0)) / out["total_hh_t"]
    ).round(4)
    return out[["lad_code", "lad_name", "share_owned", "share_rented_private", "share_rented_social"]]


def _normalise_age(age: pd.DataFrame) -> pd.DataFrame:
    age = age.copy()
    age = age[age["age_band"] != "Total: All usual residents"]
    over65_bands = {
        "Aged 65 to 69 years", "Aged 70 to 74 years", "Aged 75 to 79 years",
        "Aged 80 to 84 years", "Aged 85 years and over",
    }
    totals = age.groupby("lad_code")["people"].sum().rename("total_pop")
    over65 = age[age["age_band"].isin(over65_bands)].groupby("lad_code")["people"].sum().rename("pop_65plus")
    out = pd.concat([totals, over65], axis=1).reset_index()
    out["pop_65plus"] = out["pop_65plus"].fillna(0).astype(int)
    out["share_65plus"] = (out["pop_65plus"] / out["total_pop"]).round(4)
    return out


def load_real_epc_distribution(
    csv_path: Path = EPC_CSV, chunksize: int = 500_000
) -> pd.DataFrame:
    """Aggregate the EPC bulk CSV into a per-LAD A–G distribution.

    Streams the CSV in chunks (it's ~4 GB), keeps only the latest certificate
    per UPRN (the standard MHCLG dedup rule), and produces one row per LAD
    with columns ``epc_share_A`` … ``epc_share_G`` plus ``share_epc_d_or_worse``.
    """
    usecols = ["uprn", "inspection_date", "current_energy_rating", "local_authority"]
    dtypes = {
        "uprn": "string",
        "current_energy_rating": "string",
        "local_authority": "string",
    }
    parts: list[pd.DataFrame] = []
    rows_read = 0
    for chunk in pd.read_csv(
        csv_path,
        usecols=usecols,
        dtype=dtypes,
        parse_dates=["inspection_date"],
        chunksize=chunksize,
        low_memory=False,
    ):
        chunk = chunk.dropna(subset=["uprn", "current_energy_rating", "local_authority", "inspection_date"])
        chunk = chunk[chunk["current_energy_rating"].isin(EPC_BANDS)]
        parts.append(chunk)
        rows_read += len(chunk)
        print(f"  read chunk: total kept rows = {rows_read:,}")

    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values("inspection_date", ascending=False).drop_duplicates(subset="uprn", keep="first")
    print(f"  unique UPRNs after latest-per-UPRN dedup: {len(df):,}")

    counts = (
        df.groupby(["local_authority", "current_energy_rating"]).size()
        .unstack(fill_value=0)
        .reindex(columns=EPC_BANDS, fill_value=0)
    )
    totals = counts.sum(axis=1).replace(0, np.nan)
    shares = counts.div(totals, axis=0).round(4)
    shares.columns = [f"epc_share_{b}" for b in EPC_BANDS]
    shares = shares.reset_index().rename(columns={"local_authority": "lad_code"})
    shares["share_epc_d_or_worse"] = (
        shares[["epc_share_D", "epc_share_E", "epc_share_F", "epc_share_G"]].sum(axis=1).round(4)
    )
    shares["epc_certificates"] = counts.sum(axis=1).values
    return shares


def synthesize_epc_distribution(housing_share_flats: float, share_rented_private: float) -> dict[str, float]:
    """Synthesize an EPC band distribution from priors + simple adjustments."""
    dist = NATIONAL_EPC_PRIORS.copy()
    # Flats tend to be more efficient (centrally located, smaller). Shift mass
    # from D/E -> B/C.
    shift = 0.10 * housing_share_flats
    dist["C"] += shift * 0.6
    dist["B"] += shift * 0.4
    dist["D"] -= shift * 0.7
    dist["E"] -= shift * 0.3
    # Private rented sector is on average less efficient. Shift mass C -> D.
    shift2 = 0.08 * share_rented_private
    dist["D"] += shift2
    dist["C"] -= shift2
    # Clamp & renormalize
    dist = {k: max(0.0, v) for k, v in dist.items()}
    s = sum(dist.values())
    return {k: round(v / s, 4) for k, v in dist.items()}


def build_housing_features() -> pd.DataFrame:
    acc = pd.read_parquet(PROCESSED / "census_accommodation.parquet")
    ten = pd.read_parquet(PROCESSED / "census_tenure.parquet")

    acc_n = _normalise_accommodation(acc)
    ten_n = _normalise_tenure(ten)

    housing = acc_n.merge(ten_n, on=["lad_code", "lad_name"])

    # Add an age frame if present
    age_path = PROCESSED / "census_age.parquet"
    if age_path.exists():
        age_n = _normalise_age(pd.read_parquet(age_path))
        housing = housing.merge(age_n[["lad_code", "share_65plus"]], on="lad_code", how="left")
    else:
        housing["share_65plus"] = np.nan

    # Synthesised EPC distribution per LAD (default / fallback path)
    syn_records = []
    for _, row in housing.iterrows():
        dist = synthesize_epc_distribution(
            row["share_flats"],
            row["share_rented_private"],
        )
        syn_records.append({"lad_code": row["lad_code"], **{f"epc_share_{k}": v for k, v in dist.items()}})
    syn_df = pd.DataFrame(syn_records)
    syn_df["share_epc_d_or_worse"] = (
        syn_df[["epc_share_D", "epc_share_E", "epc_share_F", "epc_share_G"]].sum(axis=1).round(4)
    )
    syn_df["epc_source"] = "synthesized"
    syn_df["epc_certificates"] = 0

    # Real EPC distribution per LAD (England + Wales only). Hybrid overlay:
    #   epc_source = 'real'                                 — sufficient real coverage
    #   epc_source = 'synthesized_fallback_low_coverage'    — real data exists but
    #                                                         < MIN_REAL_EPC_CERTS,
    #                                                         distribution is too
    #                                                         noisy to trust → use
    #                                                         synthesized prior
    #   epc_source = 'synthesized'                          — no real data at all
    #                                                         (Scotland/NI not in
    #                                                         the EPC bulk service)
    if EPC_CSV.exists():
        print(f"Loading real EPC bulk file: {EPC_CSV}")
        real_df = load_real_epc_distribution()
        # Split real_df by coverage threshold
        is_sufficient = real_df["epc_certificates"] >= MIN_REAL_EPC_CERTS
        real_ok = real_df[is_sufficient].copy()
        real_ok["epc_source"] = "real"
        real_low = real_df[~is_sufficient].copy()
        # For low-coverage LADs, swap real distribution for the synthesized one
        # but keep the real certificate count so the dashboard can show "only N certs".
        low_codes = set(real_low["lad_code"])
        syn_for_low = (
            syn_df[syn_df["lad_code"].isin(low_codes)]
            .drop(columns=["epc_certificates", "epc_source"])
            .copy()
        )
        # carry forward the (small) real certificate count
        syn_for_low = syn_for_low.merge(
            real_low[["lad_code", "epc_certificates"]], on="lad_code", how="left"
        )
        syn_for_low["epc_source"] = "synthesized_fallback_low_coverage"

        # LADs with no real data at all (set difference)
        all_real_codes = set(real_df["lad_code"])
        syn_only = syn_df[~syn_df["lad_code"].isin(all_real_codes)].copy()
        # syn_only already has epc_source='synthesized' and epc_certificates=0

        epc_df = pd.concat([real_ok, syn_for_low, syn_only], ignore_index=True)
        print(
            f"EPC source: real for {len(real_ok)} LADs, "
            f"synthesized_fallback_low_coverage for {len(syn_for_low)} LADs "
            f"(< {MIN_REAL_EPC_CERTS} certs), "
            f"synthesized for {len(syn_only)} LADs (no coverage)"
        )
    else:
        print(f"No EPC bulk file at {EPC_CSV} — using synthesized distribution for all LADs")
        epc_df = syn_df

    housing = housing.merge(epc_df, on="lad_code", how="left")

    housing.to_parquet(PROCESSED / "housing_features.parquet", index=False)
    return housing


if __name__ == "__main__":
    h = build_housing_features()
    print(h.head().to_string(index=False))
    print(f"\nRows: {len(h)}  LADs: {h['lad_code'].nunique()}")

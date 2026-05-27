"""Aggregate HadUK-Grid daily 5km Tmax/Tmin into per-LAD heat features.

After `src/load_haduk.py` has populated `data/raw/hadukgrid/{tasmax,tasmin}/`,
this module:

1. Lazy-opens every NetCDF for the requested years as an xarray dataset.
2. Pulls LAD2021 polygons for our 41 target LADs from the ONS Open Geography
   Portal (cached locally).
3. Masks the 5km grid by each LAD polygon and computes the LAD-mean daily
   Tmax and Tmin.
4. Reduces to annual heat-exposure features:
       hot_days_25 / hot_days_28 / hot_days_30
       tropical_nights_20 (Tmin > 20°C)
       summer_tmax_p95
       summer_tmin_p95
5. Writes `data/processed/lad_haduk_features.parquet`.

Run with:

    python -m src.aggregate_haduk --start 2014 --end 2024
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

LAD_GEOJSON = RAW / "lad2021_target.geojson"

LONDON_LADS = [
    "E09000001", "E09000002", "E09000003", "E09000004", "E09000005", "E09000006",
    "E09000007", "E09000008", "E09000009", "E09000010", "E09000011", "E09000012",
    "E09000013", "E09000014", "E09000015", "E09000016", "E09000017", "E09000018",
    "E09000019", "E09000020", "E09000021", "E09000022", "E09000023", "E09000024",
    "E09000025", "E09000026", "E09000027", "E09000028", "E09000029", "E09000030",
    "E09000031", "E09000032", "E09000033",
]
NOTTINGHAM_LADS = [
    "E06000018", "E07000170", "E07000171", "E07000172", "E07000173",
    "E07000174", "E07000175", "E07000176",
]
TARGET_LADS = LONDON_LADS + NOTTINGHAM_LADS

ONS_LAD2021_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_December_2021_GB_BFC/FeatureServer/0/query"
)

SUMMER_MONTHS = (6, 7, 8)


def fetch_lad_boundaries() -> "geopandas.GeoDataFrame":  # type: ignore[name-defined]
    """Fetch only our target LADs from the ONS Open Geography Portal."""
    import geopandas as gpd

    if LAD_GEOJSON.exists():
        return gpd.read_file(LAD_GEOJSON)

    # ArcGIS REST: filter to our LAD codes
    codes = "', '".join(TARGET_LADS)
    params = {
        "where": f"LAD21CD IN ('{codes}')",
        "outFields": "LAD21CD,LAD21NM",
        "f": "geojson",
        "outSR": 27700,  # British National Grid — same as HadUK-Grid
        "returnGeometry": "true",
    }
    r = requests.get(ONS_LAD2021_URL, params=params, timeout=60)
    r.raise_for_status()
    LAD_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    LAD_GEOJSON.write_text(r.text)
    return gpd.read_file(LAD_GEOJSON)


def open_haduk_var(variable: str, years: Iterable[int]) -> "xarray.DataArray":  # type: ignore[name-defined]
    """Open every NetCDF for one variable across the requested years."""
    import xarray as xr

    pattern_dir = RAW / "hadukgrid" / variable
    files: list[Path] = []
    for year in years:
        files.extend(sorted(pattern_dir.glob(f"{variable}_hadukgrid_uk_5km_day_{year}*.nc")))
    if not files:
        raise FileNotFoundError(
            f"No NetCDFs found in {pattern_dir} for years {list(years)}. "
            "Run `python -m src.load_haduk` first."
        )
    ds = xr.open_mfdataset(
        [str(f) for f in files],
        combine="by_coords",
        chunks={"time": 31},
    )
    da = ds[variable]
    # HadUK-Grid is on BNG; coords are projection_x_coordinate / projection_y_coordinate
    return da


def lad_means(da: "xarray.DataArray", lads_gdf) -> pd.DataFrame:  # type: ignore[name-defined]
    """Compute per-LAD daily mean of `da` (xarray time, y, x) using polygon masks.

    Implementation: rasterio.features.rasterize gives us an integer-coded LAD
    raster on the same grid as the HadUK-Grid data; xarray groupby on that
    raster gives per-LAD per-day means.
    """
    import xarray as xr
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds

    # Build a raster of LAD codes on the HadUK grid
    x = da["projection_x_coordinate"].values
    y = da["projection_y_coordinate"].values
    height, width = len(y), len(x)
    transform = from_bounds(
        west=x.min() - 2500, south=y.min() - 2500,
        east=x.max() + 2500, north=y.max() + 2500,
        width=width, height=height,
    )
    code_to_int = {code: i + 1 for i, code in enumerate(lads_gdf["LAD21CD"])}
    int_to_code = {i: c for c, i in code_to_int.items()}
    shapes = [(geom, code_to_int[code]) for code, geom in zip(lads_gdf["LAD21CD"], lads_gdf.geometry)]
    raster = rasterize(
        shapes=shapes, out_shape=(height, width), transform=transform, fill=0, dtype="int32",
    )
    # HadUK y axis goes south->north (ascending), rasterio writes north->south. Flip.
    raster = np.flipud(raster)

    mask_da = xr.DataArray(
        raster,
        dims=("projection_y_coordinate", "projection_x_coordinate"),
        coords={"projection_y_coordinate": y, "projection_x_coordinate": x},
        name="lad_id",
    )

    masked = da.where(mask_da > 0)
    # Per-LAD per-day mean — groupby on lad_id, then mean over space.
    grouped = (
        masked.groupby(mask_da.rename("lad_id"))
        .mean(dim=("projection_y_coordinate", "projection_x_coordinate"))
    )
    df = grouped.to_dataframe(name="value").reset_index()
    df["lad_code"] = df["lad_id"].map(int_to_code)
    df = df.dropna(subset=["lad_code", "value"])
    df["date"] = pd.to_datetime(df["time"]).dt.normalize()
    return df[["date", "lad_code", "value"]]


def annual_features(daily: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Turn daily LAD temperatures into annual heat exposure features.

    `kind` is "tmax" or "tmin".
    """
    df = daily.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    summer = df[df["month"].isin(SUMMER_MONTHS)]

    if kind == "tmax":
        out = summer.groupby(["lad_code", "year"]).agg(
            summer_tmax_mean=("value", "mean"),
            summer_tmax_p95=("value", lambda s: np.nanpercentile(s, 95)),
            hot_days_25=("value", lambda s: int((s > 25).sum())),
            hot_days_28=("value", lambda s: int((s > 28).sum())),
            hot_days_30=("value", lambda s: int((s > 30).sum())),
        ).reset_index()
    elif kind == "tmin":
        out = summer.groupby(["lad_code", "year"]).agg(
            summer_tmin_mean=("value", "mean"),
            summer_tmin_p95=("value", lambda s: np.nanpercentile(s, 95)),
            tropical_nights_20=("value", lambda s: int((s > 20).sum())),
            warm_nights_18=("value", lambda s: int((s > 18).sum())),
        ).reset_index()
    else:
        raise ValueError(kind)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=2014)
    p.add_argument("--end", type=int, default=2024)
    args = p.parse_args(argv)
    years = list(range(args.start, args.end + 1))

    print("[1/4] LAD boundaries (ONS, BNG) ...")
    lads = fetch_lad_boundaries()
    print(f"      {len(lads)} LAD polygons")

    print("[2/4] Tmax NetCDFs -> per-LAD daily ...")
    tmax = open_haduk_var("tasmax", years)
    tmax_daily = lad_means(tmax, lads)
    tmax_daily.to_parquet(PROCESSED / "haduk_tmax_daily_lad.parquet", index=False)
    print(f"      {len(tmax_daily):,} daily LAD-rows")

    print("[3/4] Tmin NetCDFs -> per-LAD daily ...")
    tmin = open_haduk_var("tasmin", years)
    tmin_daily = lad_means(tmin, lads)
    tmin_daily.to_parquet(PROCESSED / "haduk_tmin_daily_lad.parquet", index=False)

    print("[4/4] Annual heat exposure features ...")
    tmax_ann = annual_features(tmax_daily, "tmax")
    tmin_ann = annual_features(tmin_daily, "tmin")
    feats = tmax_ann.merge(tmin_ann, on=["lad_code", "year"])

    # Reduce to recent-decade mean per LAD
    feats_decade = feats.groupby("lad_code").mean(numeric_only=True).reset_index()
    feats_decade["years_covered"] = f"{args.start}-{args.end}"
    feats_decade.to_parquet(PROCESSED / "lad_haduk_features.parquet", index=False)

    print(f"\nWrote {len(feats_decade)} LAD rows to data/processed/lad_haduk_features.parquet")
    print(feats_decade.sort_values("hot_days_28", ascending=False).head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

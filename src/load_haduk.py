"""HadUK-Grid daily 5km Tmax/Tmin downloader (CEDA Archive).

Translates the shell script that broke in zsh into Python — no `!=` history-
expansion landmines, proper auth, resume support, and a dry-run that tells
you total bytes before you commit.

Usage
-----

    export CEDA_USER='your_ceda_username'
    export CEDA_PASS='your_ceda_password'

    # See what would be downloaded (no bytes pulled)
    python -m src.load_haduk --start 2010 --end 2024 --dry-run

    # Actually download
    python -m src.load_haduk --start 2010 --end 2024

    # Only summer months (Jun–Aug), which is what the risk model uses
    python -m src.load_haduk --start 2010 --end 2024 --summer-only

Files land in `data/raw/hadukgrid/{tasmax,tasmin}/`. Existing files are
skipped (resume by default) — delete a file to force re-download.
"""

from __future__ import annotations

import argparse
import calendar
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hadukgrid"

BASE = (
    "https://dap.ceda.ac.uk/badc/ukmo-hadobs/data/insitu/MOHC/HadOBS/"
    "HadUK-Grid/v1.3.1.ceda/5km"
)
VERSION_TAG = "v20250415"
VARIABLES = ("tasmax", "tasmin")
SUMMER_MONTHS = {6, 7, 8}


@dataclass
class Target:
    variable: str
    year: int
    month: int
    url: str
    local: Path

    @property
    def stem(self) -> str:
        return self.local.name


def month_end(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def build_targets(start: int, end: int, summer_only: bool = False) -> list[Target]:
    targets: list[Target] = []
    for var in VARIABLES:
        var_dir = RAW / var
        var_dir.mkdir(parents=True, exist_ok=True)
        for year in range(start, end + 1):
            for month in range(1, 13):
                if summer_only and month not in SUMMER_MONTHS:
                    continue
                end_day = month_end(year, month)
                filename = (
                    f"{var}_hadukgrid_uk_5km_day_"
                    f"{year}{month:02d}01-{year}{month:02d}{end_day:02d}.nc"
                )
                url = f"{BASE}/{var}/day/{VERSION_TAG}/{filename}"
                targets.append(Target(var, year, month, url, var_dir / filename))
    return targets


def head_size(url: str, auth: tuple[str, str], timeout: int = 20) -> int | None:
    """Return Content-Length from a HEAD if available."""
    try:
        r = requests.head(url, auth=auth, allow_redirects=True, timeout=timeout)
        if r.status_code == 200:
            cl = r.headers.get("Content-Length")
            return int(cl) if cl else None
    except requests.RequestException:
        return None
    return None


def download_one(t: Target, auth: tuple[str, str], chunk: int = 1024 * 1024) -> tuple[bool, str]:
    """Stream-download one NetCDF. Skip if local file already complete."""
    expected = head_size(t.url, auth)
    if t.local.exists():
        if expected is None or t.local.stat().st_size == expected:
            return True, "skip (already present)"
    headers = {}
    resume_from = 0
    if t.local.exists() and expected and t.local.stat().st_size < expected:
        resume_from = t.local.stat().st_size
        headers["Range"] = f"bytes={resume_from}-"
    mode = "ab" if resume_from else "wb"
    try:
        with requests.get(t.url, auth=auth, headers=headers, stream=True, timeout=60) as r:
            if r.status_code in (401, 403):
                return False, f"auth failed (HTTP {r.status_code}) — check CEDA_USER/CEDA_PASS and that you've accepted the HadUK-Grid licence on the CEDA portal"
            if r.status_code == 404:
                return False, "404 — file path doesn't exist (version tag may have changed)"
            r.raise_for_status()
            with open(t.local, mode) as f:
                for buf in r.iter_content(chunk_size=chunk):
                    if buf:
                        f.write(buf)
    except requests.RequestException as e:
        return False, f"network error: {e}"
    return True, f"ok ({t.local.stat().st_size / 1_048_576:.1f} MB)"


def fmt_bytes(n: float | int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=2010)
    p.add_argument("--end", type=int, default=2024)
    p.add_argument("--summer-only", action="store_true",
                   help="Only download Jun/Jul/Aug — what the heat features actually need")
    p.add_argument("--dry-run", action="store_true",
                   help="HEAD each URL to total expected bytes, don't download")
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after N files (useful for first-run smoke test)")
    args = p.parse_args(argv)

    user = os.environ.get("CEDA_USER")
    pwd = os.environ.get("CEDA_PASS")
    if not user or not pwd:
        print("ERROR: set CEDA_USER and CEDA_PASS env vars.", file=sys.stderr)
        return 2
    auth = (user, pwd)

    targets = build_targets(args.start, args.end, args.summer_only)
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(targets)} target files "
          f"({args.start}–{args.end}{', summer-only' if args.summer_only else ''}).")

    if args.dry_run:
        total = 0
        unknown = 0
        for i, t in enumerate(targets, 1):
            size = head_size(t.url, auth)
            if size:
                total += size
            else:
                unknown += 1
            if i % 20 == 0:
                print(f"  probed {i}/{len(targets)} ... running total {fmt_bytes(total)}")
        print(f"\nTotal expected: {fmt_bytes(total)}"
              + (f" (+ {unknown} files with unknown size)" if unknown else ""))
        return 0

    ok = fail = skip = 0
    total_bytes = 0
    for i, t in enumerate(targets, 1):
        success, msg = download_one(t, auth)
        if success and msg.startswith("skip"):
            skip += 1
        elif success:
            ok += 1
            total_bytes += t.local.stat().st_size
        else:
            fail += 1
        print(f"[{i:>4}/{len(targets)}] {t.stem}: {msg}")
        if fail >= 5:
            print("\nAborting after 5 consecutive failures — fix the auth/network issue and re-run.")
            return 1

    print(f"\nDone. ok={ok} skip={skip} fail={fail} "
          f"downloaded={fmt_bytes(total_bytes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

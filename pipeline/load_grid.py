"""Load and clean CENACE 'Estimacion de Demanda por Balance' for one balance area.

The raw file is a concatenation of many CENACE downloads with *different column
layouts* (3 to 5 numeric columns, extra empty trailing columns, blank cells), and
every operation day appears several times because CENACE republishes it as
revisions (_0 ... _4, _v2, _v3). So a plain pd.read_csv fails. The rules:

1. Parse row by row. The source-file name (ends in .csv) marks the end of the
   numeric block. Numbers = every non-empty cell between Hora and the file name.
   Generation = first number; demand = LAST number (verified in every layout).
2. Skip rows that carry no numbers (CENACE blank rows) and the NUL-padded tail.
3. Keep, for every (day, hour), the row from the most recently published file.
4. Drop hour 25 (daylight-saving duplicate hour, 31 rows).
5. Flag rows whose latest revision is still revision 0 as preliminary.
"""
from __future__ import annotations

import csv
import re
import sys

import pandas as pd

from .config import GRID_COMPARABLE_FROM

PUB_RE = re.compile(r"v(\d{4} \d\d \d\d_\d\d \d\d \d\d)")
REV_RE = re.compile(r"Balance_(\d+)")


def _raise_field_limit() -> None:
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def parse_raw(path) -> tuple[pd.DataFrame, dict]:
    """Parse the raw file into one row per published (day, hour, file)."""
    _raise_field_limit()
    rows, skipped = [], 0
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)  # header (only valid for the oldest layout)
        for x in reader:
            idx = next((j for j, v in enumerate(x) if v.strip().endswith(".csv")), None)
            if idx is None:
                skipped += 1
                continue
            try:
                nums = [float(v) for v in x[4:idx] if v.strip() != ""]
                hora = int(float(x[3]))
            except ValueError:
                skipped += 1
                continue
            if not nums:
                skipped += 1
                continue
            name = x[idx].strip()
            rows.append((x[0], x[2], hora, nums[0], nums[-1], len(nums), name))
    df = pd.DataFrame(rows, columns=["fecha", "area", "hora", "gen_mw", "demand_mw", "n_cols", "archivo"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["publicado"] = pd.to_datetime(
        df["archivo"].str.extract(PUB_RE)[0], format="%Y %m %d_%H %M %S")
    df["revision"] = df["archivo"].str.extract(REV_RE)[0].astype("float")
    stats = {"rows_parsed": len(df), "rows_skipped": skipped}
    return df, stats


def clean(df: pd.DataFrame, stats: dict) -> tuple[pd.DataFrame, dict]:
    stats = dict(stats)
    stats["areas"] = sorted(df["area"].unique().tolist())
    n_before = len(df)
    df = df[df["hora"].between(1, 24)]
    stats["rows_dropped_hour25"] = n_before - len(df)

    df = df.sort_values(["fecha", "hora", "publicado"])
    stats["publications_per_hour_mean"] = round(
        df.groupby(["fecha", "hora"]).size().mean(), 2)
    out = df.drop_duplicates(["fecha", "hora"], keep="last").copy()
    stats["rows_after_dedupe"] = len(out)

    # sanity: values must be physically plausible for a regional grid
    bad = (out["demand_mw"] <= 0) | (out["demand_mw"] > 40000)
    stats["rows_implausible_dropped"] = int(bad.sum())
    out = out[~bad]

    out["hour"] = out["hora"] - 1                      # hour beginning, 0-23
    out["ts"] = out["fecha"] + pd.to_timedelta(out["hour"], unit="h")
    out["comparable"] = out["fecha"] >= pd.Timestamp(GRID_COMPARABLE_FROM)
    out["prelim"] = out["revision"].fillna(-1).eq(0)
    out = out[["ts", "fecha", "hour", "gen_mw", "demand_mw", "comparable", "prelim"]].reset_index(drop=True)

    days = pd.date_range(out["fecha"].min(), out["fecha"].max())
    missing = days.difference(out["fecha"].unique())
    short = out.groupby("fecha").size()
    stats.update({
        "first_day": str(out["fecha"].min().date()),
        "last_day": str(out["fecha"].max().date()),
        "days_missing": int(len(missing)),
        "days_with_fewer_than_24_hours": int((short < 24).sum()),
        "preliminary_days": int(out.loc[out["prelim"], "fecha"].nunique()),
        "preliminary_from": (str(out.loc[out["prelim"], "fecha"].min().date())
                             if out["prelim"].any() else None),
        "comparable_from": GRID_COMPARABLE_FROM,
        "mean_demand_mw_by_year": {
            int(k): round(v, 0) for k, v in
            out.groupby(out["fecha"].dt.year)["demand_mw"].mean().items()},
        "mean_generation_mw_by_year": {
            int(k): round(v, 0) for k, v in
            out.groupby(out["fecha"].dt.year)["gen_mw"].mean().items()},
    })
    return out, stats


def build_grid(path) -> tuple[pd.DataFrame, dict]:
    raw, stats = parse_raw(path)
    return clean(raw, stats)

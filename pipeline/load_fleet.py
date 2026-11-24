"""Load INEGI VMRC (registered motor vehicles in circulation), Nuevo Leon.

INEGI's interactive tool exports one small CSV per year, in latin-1, with blank
lines between rows, thousands separators ("2,447,673") and "-" for zero.
Energy-source detail only exists from 2024; before that every vehicle sits in
'No aplica'. Years 2014-2023 therefore only give a total.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd


def _num(v: str):
    v = v.strip()
    return None if v in ("-", "") else int(v.replace(",", ""))


def parse_file(path: Path) -> pd.DataFrame:
    year = int(re.search(r"(\d{4})\.csv$", path.name).group(1))
    lines = [ln for ln in path.read_text(encoding="latin-1").splitlines() if ln.strip()]
    entity = next(ln for ln in lines if "Ent y mun" in ln).split(":")[1].strip().strip(",").strip()
    head = next(i for i, ln in enumerate(lines) if ln.strip().startswith(", Total"))
    classes = [c.strip() for c in next(csv.reader([lines[head]]))][1:]
    rows = []
    for ln in lines[head + 1:]:
        if ln.startswith("FUENTE"):
            break
        cells = next(csv.reader([ln]))
        source = cells[0].strip()
        for cls, val in zip(classes, cells[1:]):
            rows.append((year, entity, source, cls, _num(val)))
    return pd.DataFrame(rows, columns=["anio", "entidad", "fuente", "clase", "valor"])


def load_fleet(folder: Path) -> tuple[pd.DataFrame, dict]:
    files = sorted(Path(folder).glob("INEGI_exporta_*.csv"))
    df = pd.concat([parse_file(f) for f in files], ignore_index=True)
    df["valor"] = df["valor"].fillna(0).astype(int)

    # integrity: energy sources must add up to the total in every year
    tot = df[(df["fuente"] == "Total") & (df["clase"] == "Total")].set_index("anio")["valor"]
    parts = df[(df["fuente"] != "Total") & (df["clase"] == "Total")].groupby("anio")["valor"].sum()
    mismatch = (tot - parts).abs()
    stats = {
        "years": [int(df["anio"].min()), int(df["anio"].max())],
        "entities": sorted(df["entidad"].unique().tolist()),
        "years_where_sources_do_not_sum_to_total": [int(y) for y in mismatch[mismatch > 0].index],
        "energy_source_detail_years": sorted(
            int(y) for y in df[(df["fuente"].isin(["Eléctrico", "Híbrido"])) & (df["valor"] > 0)]["anio"].unique()),
    }
    total = tot.sort_index()
    stats["total_fleet_by_year"] = {int(k): int(v) for k, v in total.items()}
    # year-over-year changes that look like a break in the series
    yoy = total.pct_change().dropna()
    stats["largest_yoy_moves"] = {int(k): round(float(v), 3) for k, v in yoy.reindex(yoy.abs().nlargest(3).index).items()}
    return df, stats

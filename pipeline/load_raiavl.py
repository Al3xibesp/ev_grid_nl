"""Load and clean INEGI RAIAVL 'Hibridos y electricos' (monthly, by state)."""
from __future__ import annotations

import pandas as pd

from .config import MONTHS_ES

TECH_COLS = ["bev", "phev", "hev"]


def load_raiavl(xlsx) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(xlsx, sheet_name="Tabulado", header=0)
    raw.columns = ["anio", "mes", "estado", "bev", "phev", "hev"]

    # footnote rows ("Notas:", "Fuente: INEGI ...") have a non-numeric year
    df = raw[pd.to_numeric(raw["anio"], errors="coerce").notna()].copy()
    df["anio"] = df["anio"].astype(int)
    df["mes_num"] = df["mes"].map(MONTHS_ES)
    for c in TECH_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["fecha"] = pd.to_datetime({"year": df["anio"], "month": df["mes_num"], "day": 1})

    # months that have not happened yet are all-blank across states: drop them
    has_data = df.groupby("fecha")["bev"].apply(lambda s: s.notna().any())
    last_month = has_data[has_data].index.max()
    stats = {
        "last_month_with_data": str(last_month.date())[:7],
        "future_months_dropped": int((~has_data).sum()),
    }
    df = df[df["fecha"] <= last_month].copy()

    # blank cells inside the published range = state did not report that month
    df["no_reportado"] = df[TECH_COLS].isna().any(axis=1)
    stats["state_months_blank"] = int(df["no_reportado"].sum())
    df[TECH_COLS] = df[TECH_COLS].fillna(0)

    df["es_no_especificado"] = df["estado"].eq("No especificado")
    stats["no_especificado_units"] = int(df.loc[df["es_no_especificado"], TECH_COLS].sum().sum())
    stats["n_states"] = int(df.loc[~df["es_no_especificado"], "estado"].nunique())
    stats["first_month"] = str(df["fecha"].min().date())[:7]
    df = df[["fecha", "anio", "mes_num", "estado", *TECH_COLS, "no_reportado", "es_no_especificado"]]
    return df.sort_values(["fecha", "estado"]).reset_index(drop=True), stats

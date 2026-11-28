"""Paths, constants and event annotations shared by the pipeline and the app."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# Raw inputs (see README for where each comes from)
GRID_RAW = RAW / "nes_demanda_real_balance.csv"      # CENACE, Estimacion de Demanda por Balance, area NES
RAIAVL_XLSX = RAW / "RAIAVL_11.xlsx"                 # INEGI RAIAVL, Hibridos y electricos, by state
FLEET_DIR = RAW / "inegi_vmrc"                       # INEGI VMRC, one CSV per year (Nuevo Leon)

# Processed outputs
GRID_HOURLY = PROCESSED / "nes_hourly.csv.gz"
RAIAVL_CLEAN = PROCESSED / "raiavl_clean.csv"
FLEET_CLEAN = PROCESSED / "fleet_nl.csv"
QUALITY_JSON = PROCESSED / "data_quality.json"
CONTEXT = ROOT / "data" / "context"         # hand-collected context tables (CFE, CENACE, press); see load_context.py

# CENACE changed what "Estimacion de Demanda por Balance" contains on this date:
# before it the column equals generation (net flows to other regions are NOT
# subtracted); from it the net interchange is subtracted. Only the later series
# is comparable demand. See README, "Data issues found".
GRID_COMPARABLE_FROM = "2020-01-01"

MONTHS_ES = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11,
    "Diciembre": 12,
}

# Events drawn on charts. Dates are month starts (RAIAVL) or exact days (grid).
EVENTS = {
    "covid": {"label": "COVID-19 lockdown", "date": "2020-03-23"},
    "uri": {"label": "Feb 2021 winter storm: load shedding in the Northeast", "date": "2021-02-15"},
    "chip_start": {"label": "Chip shortage", "date": "2021-01-01"},
    "chip_end": {"label": "", "date": "2022-12-31"},
    "tariff": {"label": "Jan 2026 tariff change", "date": "2026-01-01"},
    "cenace_def": {"label": "CENACE changes balance definition", "date": "2020-01-01"},
}

# Entity colours (dataviz skill, reference palette, light mode). Colour follows
# the entity, never its rank, so every chart uses the same mapping.
COLORS = {
    "BEV": "#2a78d6",    # slot 1 blue
    "PHEV": "#eb6834",   # slot 2 orange
    "HEV": "#1baf7a",    # slot 3 aqua
    "grid": "#7d8796",   # slate: baseline demand; readable on light and dark themes
    "ev_load": "#2a78d6",
    "muted": "#898781",
    "gridline": "rgba(128,128,128,0.18)",
    "ink": "#8a8a86",    # mid grey: secondary text/marks that must read on both themes
    "ink2": "#8a8a86",
    "summer": "#d9453b",
    "winter": "#7b6ae0",
    "alert": "#e0a100",
}
BLUE_RAMP = {100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef", 300: "#6da7ec",
             350: "#5598e7", 400: "#3987e5", 450: "#2a78d6", 500: "#256abf", 550: "#1c5cab",
             600: "#184f95", 650: "#104281", 700: "#0d366b"}

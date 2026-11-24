"""Build the processed tables the dashboard reads.

Usage (from the repo root):
    python -m pipeline.build

Inputs  (data/raw):  nes_demanda_real_balance.csv, RAIAVL_11.xlsx, inegi_vmrc/*.csv
Outputs (data/processed): nes_hourly.csv.gz, raiavl_clean.csv, fleet_nl.csv, data_quality.json

If the CENACE file is missing (it is 57 MB and not committed to git) the grid
step is skipped and the previously built nes_hourly.csv.gz is kept.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config as C
from .load_fleet import load_fleet
from .load_grid import build_grid
from .load_raiavl import load_raiavl


def main() -> None:
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    quality = {"built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}

    # --- EV sales (RAIAVL) -------------------------------------------------
    raiavl, q = load_raiavl(C.RAIAVL_XLSX)
    raiavl.to_csv(C.RAIAVL_CLEAN, index=False)
    quality["raiavl"] = q
    print("RAIAVL:", len(raiavl), "rows;", q)

    # --- Registered fleet (VMRC) --------------------------------------------
    fleet, q = load_fleet(C.FLEET_DIR)
    fleet.to_csv(C.FLEET_CLEAN, index=False)
    quality["fleet"] = q
    print("Fleet:", len(fleet), "rows;", q["years"], q["largest_yoy_moves"])

    # --- Grid (CENACE NES) --------------------------------------------------
    if C.GRID_RAW.exists():
        grid, q = build_grid(C.GRID_RAW)
        grid.to_csv(C.GRID_HOURLY, index=False, compression="gzip")
        quality["grid"] = q
        print("Grid:", len(grid), "hourly rows;", q["first_day"], "->", q["last_day"],
              "| skipped", q["rows_skipped"], "| prelim days", q["preliminary_days"])
    else:
        print("Grid raw file not found, keeping existing", C.GRID_HOURLY.name)
        if C.QUALITY_JSON.exists():
            quality["grid"] = json.loads(C.QUALITY_JSON.read_text()).get("grid", {})

    C.QUALITY_JSON.write_text(json.dumps(quality, indent=2, default=str))
    print("Wrote", C.QUALITY_JSON)


if __name__ == "__main__":
    main()

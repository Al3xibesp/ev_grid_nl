"""Fleet estimate and charging-load scenario model.

Everything that is an ASSUMPTION (not data) is a named parameter in
`Assumptions` or in `PROFILES`, so the dashboard can expose it as a slider and
the write-up can list it.

Units: fleet in vehicles, power in MW, energy in MWh. Hour 0 = hour beginning 00:00.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# 1. Fleet: what is observed, what is estimated
# --------------------------------------------------------------------------

def nl_annual_sales(raiavl: pd.DataFrame, state: str = "Nuevo León") -> pd.DataFrame:
    """Annual RAIAVL sales for one state, with the number of months reported."""
    d = raiavl[raiavl["estado"] == state]
    g = d.groupby("anio").agg(bev=("bev", "sum"), phev=("phev", "sum"), hev=("hev", "sum"),
                              months=("fecha", "nunique"))
    return g


def observed_bev_fleet(fleet: pd.DataFrame) -> pd.Series:
    """VMRC 'Electrico' registered vehicles (all classes), by year. Only 2024-2025 exist."""
    s = fleet[(fleet["fuente"] == "Eléctrico") & (fleet["clase"] == "Total")].set_index("anio")["valor"]
    return s[s > 0].sort_index()


def total_fleet(fleet: pd.DataFrame) -> pd.Series:
    return fleet[(fleet["fuente"] == "Total") & (fleet["clase"] == "Total")].set_index("anio")["valor"].sort_index()


@dataclass
class FleetEstimate:
    table: pd.DataFrame            # anio, observed, central, low, high
    coverage_multiplier: float     # registered-fleet growth / RAIAVL sales, calibrated on 2025
    holdout_error: float           # error of the proportional method on 2025 (out of sample)
    holdout_pred: float
    nowcast_2026: float            # estimated BEV stock at the last RAIAVL month of 2026
    nowcast_label: str
    registry_share_2025: float     # RAIAVL cumulative BEV / registered BEV, end 2025


def estimate_bev_fleet(raiavl: pd.DataFrame, fleet: pd.DataFrame) -> FleetEstimate:
    """Back-cast the registered battery-electric fleet to 2016.

    Observed: 2024 and 2025 (INEGI VMRC). For earlier years the registered fleet is
    estimated from RAIAVL Nuevo Leon BEV sales:

    * central: anchor on observed 2024 and scale by RAIAVL cumulative BEV sales
      (assumes the registry's coverage of the real market is constant over time).
      Tested out of sample on 2025: the method fitted on 2024 predicts 2025 and is
      compared with the observed 2025 value (`holdout_error`).
    * low: RAIAVL cumulative BEV sales only (coverage = 1, a hard floor).
    * high: step back from 2024 using the coverage multiplier observed in 2025
      (new registered EVs / RAIAVL BEV sales); floored at the RAIAVL cumulative.
    """
    sales = nl_annual_sales(raiavl)
    obs = observed_bev_fleet(fleet)
    y0, y1 = int(obs.index.min()), int(obs.index.max())          # 2024, 2025
    cum = sales["bev"].cumsum()
    years = [y for y in sales.index if y <= y1]

    central = {y: obs[y0] * cum[y] / cum[y0] for y in years}
    low = {y: float(cum[y]) for y in years}

    mult = (obs[y1] - obs[y0]) / sales.loc[y1, "bev"]
    high = {y0: float(obs[y0])}
    for y in range(y0, min(years), -1):                           # stock_{y-1} = stock_y - m * sales_y
        high[y - 1] = max(high[y] - mult * sales.loc[y, "bev"], low[y - 1])

    t = pd.DataFrame({"anio": years})
    t["observed"] = t["anio"].map(obs)
    t["central"] = t["anio"].map(central)
    t["low"] = t["anio"].map(low)
    t["high"] = t["anio"].map(high)
    for c in ("central", "low", "high"):                          # observed years are not estimates
        t.loc[t["observed"].notna(), c] = t.loc[t["observed"].notna(), "observed"]

    pred = obs[y0] * cum[y1] / cum[y0]
    err = pred / obs[y1] - 1

    now_year = int(sales.index.max())
    ytd = sales.loc[now_year]
    nowcast = obs[y1] + mult * ytd["bev"]
    last_m = raiavl["fecha"].max()
    return FleetEstimate(
        table=t, coverage_multiplier=float(mult), holdout_error=float(err), holdout_pred=float(pred),
        nowcast_2026=float(nowcast), nowcast_label=last_m.strftime("%b %Y"),
        registry_share_2025=float(cum[y1] / obs[y1]))


# --------------------------------------------------------------------------
# 2. Forward fleet scenarios
# --------------------------------------------------------------------------

GROWTH_SCENARIOS = {
    # annual growth of NEW plug-in sales after 2026. Labelled as assumptions in the app.
    "Low (+10% / yr)": 0.10,
    "Base (+25% / yr)": 0.25,
    "High (+40% / yr, the 2023-2025 pace)": 0.40,
}


@dataclass
class Assumptions:
    kwh_per_day: float = 7.5          # grid energy per BEV-equivalent per day (~15,000 km/yr x 0.18 kWh/km, + losses)
    phev_weight: float = 0.5          # a plug-in hybrid draws about half of a BEV's grid energy
    phev_multiplier: float = 1.0      # PHEV coverage multiplier (1 = RAIAVL as reported; BYD/Tesla not in RAIAVL)
    baseline_growth: float = 0.02     # organic annual growth of non-EV demand (overridden by data in the app)
    nl_share: float = 0.50            # share of NES demand that is Nuevo Leon (PLACEHOLDER, no source found)
    threshold_pct: float = 5.0        # "material" EV load, as % of NL demand in the same hour
    fleet_growth: float = 0.03        # growth of total vehicle fleet, for EV share only


def plugin_equivalent_stock(raiavl: pd.DataFrame, fleet: pd.DataFrame, est: FleetEstimate,
                            a: Assumptions) -> dict:
    """BEV-equivalent fleet at end 2025 (observed anchor) and the 2026 additions."""
    sales = nl_annual_sales(raiavl)
    obs = observed_bev_fleet(fleet)
    y1 = int(obs.index.max())
    phev_cum = sales.loc[:y1, "phev"].sum()
    s_2025 = obs[y1] + a.phev_weight * a.phev_multiplier * phev_cum

    now_year = int(sales.index.max())
    ytd = sales.loc[now_year]
    months = int(ytd["months"])
    adds_ytd = est.coverage_multiplier * ytd["bev"] + a.phev_weight * a.phev_multiplier * ytd["phev"]
    adds_2026 = adds_ytd * 12 / months                                # annualised (ignores seasonality)
    return {"anchor_year": y1, "stock_2025": float(s_2025), "adds_2026": float(adds_2026),
            "adds_ytd_2026": float(adds_ytd), "months_2026": months,
            "bev_2025": float(obs[y1]), "phev_cum_2025": float(phev_cum)}


def project_stock(base: dict, growth: float, horizon: int, a: Assumptions,
                  total_fleet_2025: float) -> pd.DataFrame:
    """Year-end BEV-equivalent stock 2025..horizon, plus EV share of the total fleet."""
    rows = [{"anio": base["anchor_year"], "adds": np.nan, "stock": base["stock_2025"]}]
    adds, stock = base["adds_2026"], base["stock_2025"]
    for y in range(base["anchor_year"] + 1, horizon + 1):
        if y > base["anchor_year"] + 1:
            adds *= 1 + growth
        stock += adds
        rows.append({"anio": y, "adds": adds, "stock": stock})
    t = pd.DataFrame(rows)
    t["total_fleet"] = total_fleet_2025 * (1 + a.fleet_growth) ** (t["anio"] - base["anchor_year"])
    t["share_pct"] = 100 * t["stock"] / t["total_fleet"]
    return t


# --------------------------------------------------------------------------
# 3. Charging behaviour (ASSUMED hourly profiles, each sums to 1)
# --------------------------------------------------------------------------

def _norm(v):
    v = np.array(v, dtype=float)
    return v / v.sum()


PROFILES = {
    "Unmanaged: plug in after work": _norm(
        [3, 2, 1.5, 1, 1, 1, 1.5, 2, 2.5, 3, 3, 3, 3.5, 3.5, 3.5, 4, 5, 7, 9.5, 11, 11, 9, 6.5, 4.5]),
    "Mixed: home + workplace / public": _norm(
        [2.5, 2, 1.5, 1.5, 1.5, 1.5, 2, 3, 5, 6.5, 7, 7, 6.5, 6, 6, 5.5, 5, 5.5, 6.5, 7, 6.5, 5, 4, 3]),
    # smart / time-of-use charging: vehicles are staggered across the night, not all started at the
    # same minute (a hard 23:00 start would just create a new late-evening peak)
    "Managed: staggered overnight (smart / time-of-use)": _norm(
        [12, 14, 14, 14, 12, 8, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, .5, .5, .5, 2, 5]),
}


def ev_load_mw(stock: float, kwh_per_day: float, profile: np.ndarray) -> np.ndarray:
    """Average power drawn in each hour (MW) by `stock` BEV-equivalents."""
    return stock * kwh_per_day * profile / 1000.0


# --------------------------------------------------------------------------
# 4. Grid baselines from CENACE NES (comparable series only)
# --------------------------------------------------------------------------

def comparable(grid: pd.DataFrame) -> pd.DataFrame:
    return grid[grid["comparable"]]


def growth_stats(grid: pd.DataFrame, first: int = 2022, last: int = 2025) -> dict:
    """Organic growth of NES demand over full, non-disrupted years (2020 = COVID, 2021 = storm)."""
    g = comparable(grid)
    mean = g.groupby(g["fecha"].dt.year)["demand_mw"].mean()
    peak = g.groupby(g["fecha"].dt.year)["demand_mw"].max()
    n = last - first
    return {"cagr_mean": float((mean[last] / mean[first]) ** (1 / n) - 1),
            "cagr_peak": float((peak[last] / peak[first]) ** (1 / n) - 1),
            "first": first, "last": last,
            "mean": mean.round(0).to_dict(), "peak": peak.round(0).to_dict()}


REFERENCE_DAYS = ["Annual peak day", "Typical summer weekday (Jun-Sep)", "Typical winter weekday (Dec-Feb)"]


def reference_day(grid: pd.DataFrame, year: int, kind: str) -> tuple[np.ndarray, str]:
    """24 hourly NES demand values (MW) for a reference day, and a label for it."""
    g = comparable(grid)
    g = g[g["fecha"].dt.year == year]
    if kind == REFERENCE_DAYS[0]:
        day = g.groupby("fecha")["demand_mw"].max().idxmax()
        d = g[g["fecha"] == day].set_index("hour")["demand_mw"].reindex(range(24))
        return d.interpolate().to_numpy(), f"{day:%d %b %Y}"
    months = (6, 7, 8, 9) if kind == REFERENCE_DAYS[1] else (12, 1, 2)
    d = g[g["fecha"].dt.month.isin(months) & (g["fecha"].dt.weekday < 5)]
    return d.groupby("hour")["demand_mw"].mean().reindex(range(24)).to_numpy(), f"{year}, average"


@dataclass
class ScenarioResult:
    baseline_nl: np.ndarray        # NL-attributable baseline demand (MW), 24 h, projected to horizon year
    ev_mw: np.ndarray              # EV charging load (MW), 24 h
    peak_hour: int                 # hour of the baseline peak
    ev_at_peak_mw: float
    ev_pct_at_peak: float          # EV load / NL baseline, same hour
    ev_max_mw: float
    ev_max_hour: int
    new_peak_mw: float
    new_peak_hour: int
    peak_uplift_pct: float         # increase of the daily peak caused by EVs
    daily_ev_mwh: float
    equiv_growth_years: float      # EV peak-hour MW expressed in years of organic growth


def run_scenario(stock: float, a: Assumptions, profile: np.ndarray, baseline_nes: np.ndarray,
                 years_ahead: int) -> ScenarioResult:
    base = baseline_nes * (1 + a.baseline_growth) ** years_ahead * a.nl_share
    ev = ev_load_mw(stock, a.kwh_per_day, profile)
    ph = int(base.argmax())
    total = base + ev
    npk = int(total.argmax())
    organic_mw_per_year = base[ph] * a.baseline_growth
    return ScenarioResult(
        baseline_nl=base, ev_mw=ev, peak_hour=ph, ev_at_peak_mw=float(ev[ph]),
        ev_pct_at_peak=float(100 * ev[ph] / base[ph]), ev_max_mw=float(ev.max()),
        ev_max_hour=int(ev.argmax()), new_peak_mw=float(total.max()), new_peak_hour=npk,
        peak_uplift_pct=float(100 * (total.max() / base.max() - 1)),
        daily_ev_mwh=float(ev.sum()),
        equiv_growth_years=float(ev[ph] / organic_mw_per_year) if organic_mw_per_year > 0 else np.nan)


def tipping_stock(a: Assumptions, profile: np.ndarray, baseline_nes: np.ndarray, years_ahead: int) -> float:
    """Smallest BEV-equivalent fleet that lifts the daily peak by `threshold_pct`.

    The new peak is max_h(base_h + ev_h). It exceeds (1+thr) x old peak as soon as
    some hour h has ev_h >= (1+thr) x old_peak - base_h, so the tipping fleet is the
    minimum over hours of that gap divided by the per-vehicle load in the hour.
    """
    base = baseline_nes * (1 + a.baseline_growth) ** years_ahead * a.nl_share
    gap = (1 + a.threshold_pct / 100) * base.max() - base           # MW of EV load needed in each hour
    per_vehicle_mw = a.kwh_per_day * profile / 1000.0               # MW per vehicle in each hour
    ok = per_vehicle_mw > 1e-12
    return float((gap[ok] / per_vehicle_mw[ok]).min())


def tipping_year(a: Assumptions, profile: np.ndarray, baseline_nes: np.ndarray, base: dict,
                 growth: float, total_fleet_2025: float, last_year: int = 2050):
    """First year in which the projected fleet reaches the tipping fleet (None if never by `last_year`)."""
    path = project_stock(base, growth, last_year, a, total_fleet_2025)
    for _, row in path.iterrows():
        y = int(row["anio"])
        if y <= base["anchor_year"]:
            continue
        if row["stock"] >= tipping_stock(a, profile, baseline_nes, y - base["anchor_year"]):
            return y
    return None

"""Will electric-vehicle growth strain Nuevo Leon's grid?  Streamlit dashboard.

Run:  streamlit run app.py
Data: built by `python -m pipeline.build` (see README).
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import viz
from pipeline import config as C
from pipeline import model as M
from pipeline.load_context import load_context, ref_value

st.set_page_config(page_title="EVs and the Nuevo León grid", page_icon="⚡", layout="wide")

TECH_LABEL = {"bev": "Battery-electric (BEV)", "phev": "Plug-in hybrid (PHEV)", "hev": "Hybrid (HEV)"}
TECH_COLOR = {"bev": C.COLORS["BEV"], "phev": C.COLORS["PHEV"], "hev": C.COLORS["HEV"]}
NL = "Nuevo León"
NL_BLUE = C.COLORS["BEV"]                      # Nuevo León highlight colour (tab 2)
HOURS = [f"{h:02d}:00" for h in range(24)]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1250px;}
h1 {font-size: 2rem !important; letter-spacing: -0.01em;}
div[data-testid="stMetricValue"] {font-size: 1.7rem;}
.small {color:#52514e; font-size:0.9rem;}
.answer {border-left: 4px solid #2a78d6; padding: 0.4rem 1rem; background:#fcfcfb; margin: 0.5rem 0 1rem 0;}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading data…")
def load_all():
    raiavl = pd.read_csv(C.RAIAVL_CLEAN, parse_dates=["fecha"])
    fleet = pd.read_csv(C.FLEET_CLEAN)
    grid = pd.read_csv(C.GRID_HOURLY, parse_dates=["ts", "fecha"])
    quality = json.loads(C.QUALITY_JSON.read_text())
    return raiavl, fleet, grid, quality, load_context()


raiavl, fleet, grid, quality, ctx = load_all()
gq, rq, fq = quality["grid"], quality["raiavl"], quality["fleet"]
last_month = raiavl["fecha"].max()
gcomp = M.comparable(grid)
gstats = M.growth_stats(grid)
est = M.estimate_bev_fleet(raiavl, fleet)
fleet_total = M.total_fleet(fleet)
obs_bev = M.observed_bev_fleet(fleet)
DEFAULT_A = M.Assumptions(baseline_growth=gstats["cagr_peak"])
BASE = M.plugin_equivalent_stock(raiavl, fleet, est, DEFAULT_A)
REF_DAY, REF_LABEL = M.reference_day(grid, 2025, M.REFERENCE_DAYS[0])


def fmt(n, d=0):
    return f"{n:,.{d}f}"


def coverage(title: str, items: list[str]) -> None:
    """Caveats live in a closed expander: available on demand, not in the way."""
    with st.expander(title):
        for t in items:
            st.markdown(f"- {t}")


def table_view(df: pd.DataFrame, label: str = "Show the data behind this chart") -> None:
    with st.expander(label):
        st.dataframe(df, width="stretch")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### Data vintages")
    st.markdown(
        f"- **EV sales (INEGI RAIAVL)**: {last_month:%B %Y} is the latest month. Sales are revised figures. "
        f"Built {quality['built_at_utc']} UTC.\n"
        f"- **Registered fleet (INEGI VMRC)**: {fq['years'][0]}–{fq['years'][1]}; energy-source detail only "
        f"{fq['energy_source_detail_years'][0]}–{fq['energy_source_detail_years'][-1]}.\n"
        f"- **Grid (CENACE, area NES)**: {gq['first_day']} → {gq['last_day']}; comparable demand from "
        f"{gq['comparable_from']}; last {gq['preliminary_days']} days preliminary.")
    st.markdown("- **Context tables**: CFE reliability reports, CENACE, NL Government and press, 2017–2026 "
                "(`data/context/`, each row with its source).")
    st.markdown("### Reading guide")
    st.markdown("**Grid under pressure → EVs rising → will EVs hurt it? → what can you do?**")
    with st.expander("About this dashboard"):
        st.markdown(
            "- **Role:** advisor to the Government of Nuevo León (with CFE and CENACE).\n"
            "- **Decision:** spend on grid upgrades and charging policy now, or wait, and if not, *where*?\n"
            "- **Data:** RAIAVL = EV *sales*; VMRC = EVs *on the road*; CENACE = hourly *grid load*; "
            "CFE reports and press = reliability and 2026 events.")


# ---------------------------------------------------------------- header
st.title("Will electric cars strain Monterrey's grid?")
st.markdown("<span class='small'>Advisory dashboard for the Government of Nuevo León · INEGI RAIAVL, INEGI VMRC "
            "and CENACE data</span>", unsafe_allow_html=True)

tabs = st.tabs(["1 · Grid under pressure", "2 · EV adoption", "3 · Vehicles on the road",
               "4 · Will EVs hurt it?", "5 · What can you do?"])


# =============================================================== helpers for headline numbers
def tipping_table(a: M.Assumptions) -> pd.DataFrame:
    base = M.plugin_equivalent_stock(raiavl, fleet, est, a)
    ref, _ = REF_DAY, REF_LABEL
    rows = {}
    for pname, prof in M.PROFILES.items():
        rows[pname] = {}
        for gname, g in M.GROWTH_SCENARIOS.items():
            y = M.tipping_year(a, prof, ref, base, g, fleet_total[2025])
            rows[pname][gname] = str(y) if y else "after 2050"
    return pd.DataFrame(rows).T


def uplift_at(year: int, growth: float, profile_name: str, a: M.Assumptions):
    base = M.plugin_equivalent_stock(raiavl, fleet, est, a)
    path = M.project_stock(base, growth, year, a, fleet_total[2025])
    stock = float(path.iloc[-1]["stock"])
    res = M.run_scenario(stock, a, M.PROFILES[profile_name], REF_DAY, year - base["anchor_year"])
    return stock, path.iloc[-1]["share_pct"], res


def uplift_by_year(a: M.Assumptions, profile_name: str, ref: np.ndarray) -> dict[str, pd.Series]:
    """% rise in the daily peak from EV charging, each year 2026-2040, for every growth scenario."""
    base = M.plugin_equivalent_stock(raiavl, fleet, est, a)
    out = {}
    for gname, g in M.GROWTH_SCENARIOS.items():
        p = M.project_stock(base, g, 2040, a, fleet_total[2025])
        p = p[p["anio"] >= 2026]
        out[gname] = pd.Series([M.run_scenario(float(r["stock"]), a, M.PROFILES[profile_name], ref,
                                               int(r["anio"]) - base["anchor_year"]).peak_uplift_pct
                                for _, r in p.iterrows()], index=p["anio"].astype(int).to_list())
    return out


def uplift_chart(paths: dict[str, pd.Series], threshold: float, height: int, highlight: str | None = None) -> go.Figure:
    """Peak rise by year, one line per growth scenario, with the 'material' threshold."""
    fig = go.Figure()
    for (gname, ser), col in zip(paths.items(), [C.BLUE_RAMP[250], C.BLUE_RAMP[450], C.BLUE_RAMP[650]]):
        w = 3.5 if gname == highlight else 2.5 if highlight is None else 1.5
        viz.line(fig, ser.index, ser.values, gname, col, width=w, fmt=".1f", unit="%")
        viz.end_label(fig, ser.index[-1], ser.values[-1], gname.split(" (")[0])
    fig.add_hline(y=threshold, line=dict(color=C.COLORS["ink2"], width=1, dash="dot"),
                  annotation_text=f"'Material' = {threshold:g}%", annotation_position="top left",
                  annotation_font=dict(size=11, color=C.COLORS["ink2"]))
    viz.style(fig, height=height, ytitle="Rise in daily peak from EV charging, %")
    fig.update_xaxes(dtick=2)
    return fig


UNMANAGED = list(M.PROFILES)[0]     # worst case in every growth scenario; fixed on tabs 1 and 5
BASE_G = list(M.GROWTH_SCENARIOS)[1]


# =============================================================== TAB 1
with tabs[0]:
    rel, ev26 = ctx["reliability"], ctx["events"]
    st.markdown("## Average reliability improved until 2024; summer 2026 broke the pattern")
    st.markdown("<span class='small'>Official 2025–26 reliability data is not published yet.</span>", unsafe_allow_html=True)

    firms = ev26.loc[ev26["metric"] == "firms_affected_h1", "value"].iloc[0]
    inter = ev26.loc[ev26["metric"] == "cfe_interruptions_jan_aug", "value"].iloc[0]
    k = st.columns([1.1, 1.4, 1.5])
    k[0].metric("NL firms hit, H1 2026", f"{firms:.1f}%",
                help="Share of CAINTRA-surveyed firms affected by interruptions or voltage variations, Jan–Jun 2026.")
    k[1].metric("CFE interruptions, Mexico, Jan–Aug 2026", f"{inter / 1000:,.0f}k",
                help="National total; CFE gives no breakdown by state.")
    k[2].caption("Sources: Líder Empresarial (CAINTRA survey, 2026); N+ (CFE data, 2026). The 317k is national: no state breakdown.")

    x = pd.to_datetime(rel["year"].astype(str) + "-07-01")       # yearly value plotted mid-year
    fig = go.Figure()
    fig.add_shape(type="rect", x0="2025-01-01", x1="2026-12-31", y0=0, y1=1, yref="paper", line=dict(width=0),
                  fillcolor="rgba(137,135,129,0.15)", layer="below")
    fig.add_annotation(x="2025-01-01", y=1, yref="paper", text="2025–26 not yet published", showarrow=False,
                       xanchor="left", yanchor="top", xshift=4, font=dict(size=11, color=C.COLORS["ink2"]))
    viz.line(fig, x, rel["saidi_min_per_user"], "SAIDI: minutes without power per user per year", C.COLORS["grid"],
             width=2.5, fmt=".1f", unit=" min")
    fig.add_hline(y=float(rel["saidi_limit_min"].iloc[0]), line=dict(color="#e34948", width=1, dash="dash"),
                  annotation_text="CFE limit: 50 min", annotation_position="top left",
                  annotation_font=dict(size=11, color=C.COLORS["ink2"]))
    viz.style(fig, height=380, ytitle="Minutes per user per year", hover="closest", legend=False)
    fig.update_yaxes(range=[0, 55])
    fig.update_xaxes(range=["2016-10-01", "2026-12-31"], dtick="M12", tickformat="%Y")
    st.plotly_chart(fig, width="stretch")
    st.caption("SAIDI = minutes without power per user per year, CFE Golfo Norte distribution division. "
               "Source: CFE, PAM RGD 2019–2033 to 2025–2039 editions.")

    # 2026 events on their own time axis: one row; labels alternate above/below and end at their own line,
    # so a label never crosses another event's line
    st.markdown("#### What happened in 2026")
    ev = ev26.sort_values("date").reset_index(drop=True)
    ev["when"] = ev["date"].dt.strftime("%d %b %Y")
    ev.loc[ev["description"].str.contains("placeholder"), "when"] = ev["date"].dt.strftime("%B %Y")
    is_outage = ev["event_type"].eq("outage")
    figt = go.Figure(go.Scatter(
        x=ev["date"], y=[0] * len(ev), mode="markers",
        marker=dict(size=12, color=np.where(is_outage, C.COLORS["BEV"], C.COLORS["muted"]), line=dict(width=1.5, color="white")),
        customdata=ev[["when", "place", "description", "source"]].to_numpy(),
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}<br>"
                      "<i>Source: %{customdata[3]}</i><extra></extra>"))
    offsets = [-34, 34, -72, 72]                                   # px: below, above, further below, further above
    for n, r in ev.iterrows():
        figt.add_annotation(x=r["date"], y=0, text=r["label"], showarrow=True, arrowhead=0, arrowwidth=1,
                            arrowcolor=C.COLORS["ink2"], ax=0, ay=offsets[n % 4], xanchor="right",
                            font=dict(size=11, color=C.COLORS["BEV"] if r["event_type"] == "outage" else C.COLORS["ink2"]))
    figt.add_hline(y=0, line=dict(color=C.COLORS["muted"], width=1))
    viz.style(figt, height=230, legend=False, hover="closest")
    figt.update_yaxes(visible=False, range=[-1, 1])
    figt.update_xaxes(range=["2026-06-01", "2026-10-05"], dtick="M1", tickformat="%b %Y", showgrid=False)
    figt.update_layout(margin=dict(t=10, b=30))
    st.plotly_chart(figt, width="stretch")
    st.caption("Blue = outages. Hover a dot for the full description and source; every event and link is in "
               "data/context/grid_context_2026.csv. End-of-period figures (H1 survey, Jan–Aug total) sit on the period's last day.")
    coverage("About these reliability numbers", [
        "SAIDI is an **average for the whole Golfo Norte division**, wider than the Monterrey metro. A falling average can hide "
        "neighborhoods with repeated outages.",
        "CFE publishes each year's figures in a later planning report (PAM RGD), so 2025 and 2026 are not available yet.",
        "The 2026 events come from press and government statements, not from a measured series; they show what happened, not how much.",
        "The July 2026 outage has a month but no exact day; it is plotted on the 15th. Two figures are national, not Nuevo León: "
        "the 14.8% reserve and the 317k interruptions."])

    st.divider()
    st.markdown("### When does the Northeast grid peak?")
    st.markdown("Hourly demand estimate for CENACE's Northeast (NES) balance area, which includes Monterrey. "
                "EV charging adds load on top of this shape.")

    g1, g2, g3 = st.columns([1.5, 1.2, 1.1])
    yr_lo, yr_hi = g1.slider("Years", 2020, int(gcomp["fecha"].dt.year.max()), (2021, int(gcomp["fecha"].dt.year.max())), key="yrs4")
    season = g2.selectbox("Season (for the two lower charts)", ["All year", "Summer (May–Sep)", "Winter (Dec–Feb)",
                                                              "Shoulder (Mar–Apr, Oct–Nov)"], key="season4")
    daytype = g3.radio("Days", ["All days", "Weekdays", "Weekends"], horizontal=True, key="day4")

    gw = gcomp[(gcomp["fecha"].dt.year >= yr_lo) & (gcomp["fecha"].dt.year <= yr_hi)]
    daily = gw.groupby("fecha")["demand_mw"].max()
    roll = daily.rolling(30, min_periods=15).mean()
    fig = go.Figure()
    viz.line(fig, daily.index, daily.values, "Peak hour of each day", C.COLORS["muted"], width=1, opacity=0.8, unit=" MW")
    viz.line(fig, roll.index, roll.values, "30-day average of daily peak", C.COLORS["grid"], width=2.5, unit=" MW")
    viz.style(fig, height=380, ytitle="Demand, MW")
    lo, hi = daily.index.min(), daily.index.max()
    if gq.get("preliminary_from") and pd.Timestamp(gq["preliminary_from"]) < hi:
        pf = pd.Timestamp(gq["preliminary_from"])
        fig.add_shape(type="rect", x0=pf, x1=hi, y0=0, y1=1, yref="paper", line=dict(width=0),
                      fillcolor="rgba(137,135,129,0.2)", layer="below")
        fig.add_annotation(x=pf, y=0.04, yref="paper", text="Preliminary", showarrow=False, xanchor="left", xshift=3,
                           font=dict(size=11, color=C.COLORS["ink2"]))
    st.plotly_chart(fig, width="stretch")
    table_view(pd.DataFrame({"daily peak MW": daily.round(0), "30-day avg": roll.round(0)}).tail(400), "Show the data (latest 400 days)")

    season_months = {"All year": range(1, 13), "Summer (May–Sep)": (5, 6, 7, 8, 9), "Winter (Dec–Feb)": (12, 1, 2),
                     "Shoulder (Mar–Apr, Oct–Nov)": (3, 4, 10, 11)}
    gd = gw
    if daytype == "Weekdays":
        gd = gd[gd["fecha"].dt.weekday < 5]
    elif daytype == "Weekends":
        gd = gd[gd["fecha"].dt.weekday >= 5]

    h1, h2 = st.columns(2)
    with h1:
        st.markdown("#### Hour of day × month: when demand is highest")
        pv = gd.assign(m=gd["fecha"].dt.month).pivot_table(index="hour", columns="m", values="demand_mw", aggfunc="mean")
        pv = pv.reindex(index=range(24), columns=range(1, 13))
        ramp = [[i / 6, c] for i, c in enumerate([C.BLUE_RAMP[k] for k in (100, 200, 300, 450, 550, 650, 700)])]
        figh = go.Figure(go.Heatmap(z=pv.values, x=MONTH_ABBR, y=HOURS, colorscale=ramp, xgap=2, ygap=2,
                                    colorbar=dict(title="MW", thickness=12),
                                    hovertemplate="%{x} · %{y}<br>%{z:,.0f} MW<extra></extra>"))
        viz.style(figh, height=480, legend=False, hover="closest")
        figh.update_yaxes(autorange="reversed", dtick=2, gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(figh, width="stretch")
        st.caption("Average demand. Evening hours from May to September are the system's binding period: "
                   "air-conditioning load, exactly when EVs are plugged in after work.")
    with h2:
        st.markdown("#### Average daily shape by season")
        figp = go.Figure()
        seasons = [("Summer (May–Sep)", "#e34948"), ("Winter (Dec–Feb)", "#6250d6"), ("Shoulder (Mar–Apr, Oct–Nov)", C.COLORS["muted"])]
        pk = {}
        for name, col in seasons:
            sub = gd[gd["fecha"].dt.month.isin(season_months[name])]
            if sub.empty:
                continue
            prof = sub.groupby("hour")["demand_mw"].mean().reindex(range(24))
            pk[name] = (int(prof.idxmax()), float(prof.max()))
            viz.line(figp, HOURS, prof.values, name.split(" (")[0], col, width=3 if name == season else 2, unit=" MW")
            viz.end_label(figp, HOURS[-1], prof.values[-1], name.split(" (")[0], dx=4)
        viz.style(figp, height=480, ytitle="Average demand, MW")
        figp.update_xaxes(dtick=3)
        st.plotly_chart(figp, width="stretch")
        if pk:
            txt = "; ".join(f"{n.split(' (')[0].lower()} peak at {h:02d}:00 ({fmt(v)} MW)" for n, (h, v) in pk.items())
            st.caption("Average-day peak: " + txt + ".")

    kp = st.columns(4)
    kp[0].metric("Highest hour, 2025", f"{fmt(gstats['peak'][2025])} MW")
    kp[1].metric("Average demand, 2025", f"{fmt(gstats['mean'][2025])} MW")
    kp[2].metric("Peak growth 2022–2025", f"{gstats['cagr_peak']:.1%} / yr")
    kp[3].metric("Average growth 2022–2025", f"{gstats['cagr_mean']:.1%} / yr")

    with st.expander("Why this series starts in 2020, not 2016"):
        m = grid.set_index("ts").resample("MS").agg(demand=("demand_mw", "mean"), gen=("gen_mw", "mean"))
        figb = go.Figure()
        viz.line(figb, m.index, m["gen"], "Generation in the area", C.COLORS["muted"], width=2, unit=" MW")
        viz.line(figb, m.index, m["demand"], "'Demand by balance' as published", C.COLORS["grid"], width=2.5, unit=" MW")
        viz.style(figb, height=330, ytitle="Monthly average, MW")
        st.plotly_chart(figb, width="stretch")
        st.caption(f"Before 2020 the published 'demand by balance' equals generation (about {fmt(gq['mean_demand_mw_by_year']['2019'])} MW in 2019). "
                   f"From January 2020 the net flows out of the area, about {fmt(gq['mean_generation_mw_by_year']['2020'] - gq['mean_demand_mw_by_year']['2020'])} MW, "
                   "are subtracted and the series drops by almost half although nothing physical changed. Only 2020 onward is comparable demand, "
                   "so grid analysis covers about 6.9 years, not ten. The sales and fleet analysis cover the full decade.")

    coverage("Coverage and caveats for this tab", [
        "**NES is a regional balance area, not Monterrey.** It includes load outside Nuevo León, and neighborhood-level stress cannot be seen here.",
        "'Demand by balance' is an **estimate** (generation plus flows with other areas), not metered consumption.",
        f"The latest {gq['preliminary_days']} days (from {gq['preliminary_from']}) are preliminary first estimates; CENACE later revises them.",
        "2020 (COVID) and the February 2021 storm are anomalous years, so growth is computed over 2022–2025.",
        f"Days with 23 hours before 2023 are daylight-saving spring-forward days, not missing data. "
        f"{fmt(gq['rows_skipped'])} blank source rows were skipped and revisions were collapsed to the latest published version.",
        "No temperature data is loaded: heat is visible only through the seasonal shape of demand."])




# =============================================================== TAB 2
with tabs[1]:
    st.markdown("## How fast are EVs being adopted?")
    st.markdown("Monthly sales of electrified light vehicles reported to INEGI. Pick states, technologies and a time window.")

    states_all = sorted(s for s in raiavl["estado"].unique() if s != "No especificado")
    rank = (raiavl[~raiavl["es_no_especificado"] & (raiavl["estado"] != NL)]
            .assign(pi=lambda d: d["bev"] + d["phev"]).groupby("estado")["pi"].sum().sort_values(ascending=False))

    f1, f2, f3 = st.columns([1.4, 1.2, 1.4])
    sel_states = f1.multiselect("States (up to 5)", states_all, default=[NL, "Ciudad de México", "Jalisco"],
                                max_selections=5, key="states")
    sel_techs = f2.multiselect("Technology", list(TECH_LABEL), default=["bev", "phev"],
                               format_func=TECH_LABEL.get, key="techs")
    metric = f3.radio("Measure", ["Monthly units", "12-month rolling total", "Growth vs same 12 months a year earlier"],
                      key="metric")
    first_m, last_m = raiavl["fecha"].min().date(), last_month.date()
    win = st.slider("Time window", min_value=first_m, max_value=last_m, value=(first_m, last_m),
                    format="MMM YYYY", key="win2")

    if not sel_states or not sel_techs:
        st.info("Select at least one state and one technology.")
    else:
        idx = pd.date_range(raiavl["fecha"].min(), last_month, freq="MS")
        d = raiavl.assign(v=raiavl[sel_techs].sum(axis=1))
        by_state = d.pivot_table(index="fecha", columns="estado", values="v", aggfunc="sum").reindex(idx).fillna(0)
        nat = d.groupby("fecha")["v"].sum().reindex(idx).fillna(0)

        def transform(s: pd.Series) -> pd.Series:
            if metric == "Monthly units":
                return s
            r = s.rolling(12).sum()
            if metric == "12-month rolling total":
                return r
            prev = r.shift(12)
            return (r / prev - 1).where(prev >= 50) * 100

        ytitle = {"Monthly units": "Vehicles sold per month", "12-month rolling total": "Vehicles sold, last 12 months"}.get(
            metric, "% change in 12-month total")
        fig = go.Figure()
        win_lo, win_hi = pd.Timestamp(win[0]), pd.Timestamp(win[1])
        mask = (idx >= win_lo) & (idx <= win_hi)
        shown = []
        if len(sel_states) > 1:
            for i, s in enumerate(sel_states):
                col = NL_BLUE if s == NL else C.COLORS["muted"]   # highlight Nuevo León, the rest is context
                y = transform(by_state[s])[mask]
                viz.line(fig, idx[mask], y, s, col, width=3 if s == NL else 1.5,
                         fmt=".1f" if "%" in ytitle else ",.0f", unit="%" if "%" in ytitle else "")
                shown.append(pd.Series(y.values, index=idx[mask], name=s))
                if y.notna().any():
                    viz.end_label(fig, y.dropna().index[-1], y.dropna().iloc[-1], s)
            caption = "Nuevo León in blue, other selected states in grey; selected technologies are added together."
        else:
            s = sel_states[0]
            for t in sel_techs:
                y = transform(by_state[s] if False else d.assign(v=d[t]).pivot_table(
                    index="fecha", columns="estado", values="v", aggfunc="sum").reindex(idx).fillna(0)[s])[mask]
                viz.line(fig, idx[mask], y, TECH_LABEL[t], TECH_COLOR[t],
                         fmt=".1f" if "%" in ytitle else ",.0f", unit="%" if "%" in ytitle else "")
                shown.append(pd.Series(y.values, index=idx[mask], name=TECH_LABEL[t]))
                if y.notna().any():
                    viz.end_label(fig, y.dropna().index[-1], y.dropna().iloc[-1], t.upper())
            caption = f"Colored by technology for {s}."
        viz.style(fig, height=420, ytitle=ytitle)
        st.plotly_chart(fig, width="stretch")
        st.caption(caption + (" Growth rates are hidden where the earlier 12-month total is below 50 vehicles." if "%" in ytitle else ""))
        table_view(pd.concat(shown, axis=1).round(1))

        # national share
        st.markdown("#### Is Nuevo León leading? Its share of national sales")
        share_tech = st.session_state.get("techs", ["bev", "phev"])
        nl_s = d[d["estado"] == NL].set_index("fecha")["v"].reindex(idx).fillna(0).rolling(12).sum()
        nat_s = nat.rolling(12).sum()
        share = (100 * nl_s / nat_s)[mask]
        fig2 = go.Figure()
        viz.line(fig2, idx[mask], share, "Nuevo León share of national sales", NL_BLUE, width=2.5, fmt=".1f", unit="%",
                 showlegend=False)
        viz.style(fig2, height=300, ytitle="% of national sales (12-month rolling)", legend=False)
        st.plotly_chart(fig2, width="stretch")
        st.caption(f"Selected technologies: {', '.join(TECH_LABEL[t] for t in sel_techs)}. "
                   "National total includes the 'No especificado' state row.")

    # last 12 months KPIs (independent of filters)
    pi = raiavl.assign(pi=raiavl["bev"] + raiavl["phev"])
    ly = pi[(pi["fecha"] > last_month - pd.DateOffset(months=12))]
    py = pi[(pi["fecha"] <= last_month - pd.DateOffset(months=12)) & (pi["fecha"] > last_month - pd.DateOffset(months=24))]
    nl_ly, nl_py = ly[ly["estado"] == NL]["pi"].sum(), py[py["estado"] == NL]["pi"].sum()
    rk = ly[~ly["es_no_especificado"]].groupby("estado")["pi"].sum().rank(ascending=False)[NL]
    kk = st.columns(3)
    kk[0].metric(f"Plug-in sales in Nuevo León, 12 months to {last_month:%b %Y}", fmt(nl_ly), f"{nl_ly / nl_py - 1:+.0%} vs prior 12 months")
    kk[1].metric("Rank among states", f"#{int(rk)}")
    kk[2].metric("Share of national plug-in sales", f"{100 * nl_ly / ly['pi'].sum():.1f}%")

    coverage("Coverage and caveats for this tab", [
        "RAIAVL is an administrative record of what **AMIA-affiliated automakers report**. It is not a census. BYD does not report to INEGI "
        "(and press reports say the same of Tesla), so sales of battery-electric and plug-in vehicles are understated.",
        "This table has **no brand dimension**, so panel changes (GAC joining with data back to January 2024, MOTORNATION leaving from "
        "November 2026) can move totals and cannot be isolated here.",
        f"Latest month is **{last_month:%B %Y}**; November and December 2026 do not exist yet. Sales figures are revised figures.",
        f"{rq['state_months_blank']} state-month cells were blank (state did not report) and are counted as zero. "
        f"'No especificado' ({fmt(rq['no_especificado_units'])} units) is excluded from state views but included in national totals."])


# =============================================================== TAB 3
with tabs[2]:
    st.markdown("## How many EVs are actually on the road?")
    st.markdown("Sales tell the flow. The grid cares about the stock. INEGI's registered-vehicle statistics count the stock, "
                "but only separate electric vehicles from 2024. Earlier years are **estimated** from RAIAVL sales.")

    t = est.table
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t["anio"], y=t["high"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t["anio"], y=t["low"], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(42,120,214,0.14)", name="Plausible range (estimated years)",
                             hovertemplate="%{y:,.0f}<extra>Low end</extra>"))
    est_part = t[t["observed"].isna()]
    viz.line(fig, t["anio"], t["central"], "Estimated, central", C.BLUE_RAMP[250], width=2, dash="dot")
    viz.line(fig, t["anio"][t["observed"].notna()], t["observed"].dropna(), "Observed (INEGI VMRC)", C.COLORS["BEV"], width=3)
    fig.add_trace(go.Scatter(x=t["anio"][t["observed"].notna()], y=t["observed"].dropna(), mode="markers",
                             marker=dict(size=10, color=C.COLORS["BEV"], line=dict(width=2, color="#fcfcfb")),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[2026], y=[est.nowcast_2026], mode="markers", name=f"Nowcast, {est.nowcast_label}",
                             marker=dict(size=11, color="#fcfcfb", line=dict(width=2, color=C.COLORS["BEV"])),
                             hovertemplate="%{y:,.0f}<extra>Nowcast</extra>"))
    viz.style(fig, height=400, ytitle="Registered battery-electric vehicles, Nuevo León", hover="x unified")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Estimating earlier years: anchor on observed 2024 and scale by cumulative RAIAVL battery-electric sales. "
               f"Tested out of sample on 2025, the method predicts {fmt(est.holdout_pred)} vs {fmt(obs_bev[2025])} observed "
               f"({est.holdout_error:+.1%}). Low end: RAIAVL sales only. High end: step back using the 2025 ratio of "
               f"registrations to RAIAVL sales ({est.coverage_multiplier:.1f}×). The estimates agree closely from 2022 on and differ "
               f"most before 2021, when numbers are small and irrelevant for the grid. Nowcast = 2025 stock + {est.coverage_multiplier:.1f}× "
               f"RAIAVL sales through {est.nowcast_label}.")
    table_view(t.round(0).rename(columns={"anio": "Year"}))

    a, b = st.columns(2)
    with a:
        st.markdown("#### The registry sees only a fraction")
        cum = M.nl_annual_sales(raiavl)["bev"].cumsum()
        fig3 = go.Figure()
        yrs = [2024, 2025]
        fig3.add_trace(go.Bar(x=[str(y) for y in yrs], y=[obs_bev[y] for y in yrs], name="Registered EVs (VMRC)",
                              marker_color=C.COLORS["BEV"], marker_cornerradius=4,
                              hovertemplate="%{y:,.0f}<extra>Registered EVs (VMRC)</extra>"))
        fig3.add_trace(go.Bar(x=[str(y) for y in yrs], y=[cum[y] for y in yrs], name="All EV sales reported to RAIAVL since 2016",
                              marker_color=C.COLORS["muted"], marker_cornerradius=4,
                              hovertemplate="%{y:,.0f}<extra>RAIAVL cumulative</extra>"))
        viz.style(fig3, height=330, ytitle="Vehicles")
        fig3.update_layout(barmode="group", bargap=0.35)
        st.plotly_chart(fig3, width="stretch")
        st.caption(f"By end of 2025 RAIAVL's cumulative battery-electric sales equal {est.registry_share_2025:.0%} of the registered electric fleet. "
                   "Non-reporting brands, vehicles registered in Nuevo León but sold elsewhere, and fuel coding differences cannot be separated with these tables.")
    with b:
        st.markdown("#### Total registered vehicles, and the 2023 break")
        yrs = fleet_total.index
        fig4 = go.Figure(go.Scatter(x=yrs, y=fleet_total.values, mode="lines+markers", name="Registered vehicles",
                                    line=dict(color=C.COLORS["grid"], width=2.5), marker=dict(size=6),
                                    hovertemplate="%{y:,.0f}<extra>Registered vehicles</extra>"))
        viz.style(fig4, height=330, ytitle="Registered vehicles, Nuevo León", legend=False)
        fig4.update_xaxes(dtick=2, tickangle=0)
        fig4.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig4, width="stretch")
        st.caption(f"Electric share of all registered vehicles: {100 * obs_bev[2024] / fleet_total[2024]:.2f}% (2024) → "
                   f"{100 * obs_bev[2025] / fleet_total[2025]:.2f}% (2025).")

    coverage("Coverage and caveats for this tab", [
        f"INEGI's registered-vehicle table has energy-source detail **only for {fq['energy_source_detail_years'][0]} and "
        f"{fq['energy_source_detail_years'][-1]}**. Everything before is an estimate with a stated range.",
        "The total fleet **drops 17% in 2023** (2.69 million to 2.23 million). INEGI notes that since 2022 a decree to regularize used imported "
        "vehicles affects registrations. I treat 2023 as a series break and never compare across it.",
        "VMRC 'Híbrido' does not separate plug-in from conventional hybrids and is *lower* than RAIAVL's cumulative hybrid sales, "
        "so plug-in hybrids are modeled from RAIAVL with an explicit assumption (tab 4), not from VMRC.",
        "The coverage ratio is calibrated on a single year of change (2024 to 2025). It is a calibration, not a law."])


# =============================================================== TAB 4
with tabs[3]:
    st.markdown("## Will EVs hurt the grid?")
    s35, sh35, r35 = uplift_at(2035, 0.25, UNMANAGED, DEFAULT_A)
    base_year = tipping_table(DEFAULT_A).loc[UNMANAGED, BASE_G]
    reserve = ref_value(ctx["reference"], "operating_reserve_margin_actual")
    alert = ref_value(ctx["reference"], "reserve_margin_alert_threshold")
    emerg = ref_value(ctx["reference"], "reserve_margin_emergency_threshold")
    organic = r35.baseline_nl.max() - REF_DAY.max() * DEFAULT_A.nl_share     # growth of the NL peak 2025 -> 2035, no EVs

    st.markdown(f"<div class='answer'><b>Regionally no, locally yes.</b> The national grid kept a {reserve:.1f}% reserve in summer 2026 "
                f"and EV charging adds {r35.peak_uplift_pct:.1f}% to the 2035 peak (base; 5% around {base_year}). "
                "But 2026's outages came from aging distribution transformers, which is where home charging concentrates.</div>",
                unsafe_allow_html=True)

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("#### Spare generation at the 2026 summer peak")
        figr = go.Figure(go.Indicator(
            mode="gauge+number", value=reserve, number=dict(suffix="%", valueformat=".2f", font=dict(size=40)),
            gauge=dict(
                axis=dict(range=[0, 20], ticksuffix="%", tickvals=[0, emerg, alert, 10, 15, 20]),   # 20% = chosen scale max
                bar=dict(color=C.COLORS["grid"], thickness=0.3),
                steps=[dict(range=[0, emerg], color="rgba(227,73,72,0.45)"),
                       dict(range=[emerg, alert], color="rgba(237,161,0,0.45)"),
                       dict(range=[alert, 20], color="rgba(137,135,129,0.15)")],
                borderwidth=0)))
        figr.update_layout(height=230, margin=dict(l=30, r=30, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)",
                           font=dict(color=C.COLORS["ink"]))
        st.plotly_chart(figr, width="stretch")
        st.caption(f"Operating reserve margin, national grid (SIN), summer 2026 peak of about 55,600 MW. Red: emergency (< {emerg:g}%); "
                   f"amber: alert ({emerg:g}–{alert:g}%). The 20% end of the scale is chosen for display. "
                   "Sources: Forbes México (CENACE) for the margin; El Financiero for the thresholds.")
    with b2:
        st.markdown("#### Nuevo León peak in 2035, MW")
        bars = pd.Series({"EV charging, busiest hour": r35.ev_max_mw, "Ordinary demand growth, 2025–2035": organic,
                          "NL peak 2035 without EVs": r35.baseline_nl.max()})
        figb3 = go.Figure(go.Bar(x=bars.values, y=bars.index, orientation="h",
                                 marker_color=[C.COLORS["BEV"], C.COLORS["grid"], C.COLORS["muted"]], marker_cornerradius=4,
                                 text=[f"{fmt(v)} MW" for v in bars.values], textposition="outside",
                                 hovertemplate="%{x:,.0f} MW<extra></extra>"))
        viz.style(figb3, height=230, legend=False, hover="closest")
        figb3.update_xaxes(range=[0, bars.max() * 1.2], showticklabels=False)
        st.plotly_chart(figb3, width="stretch")
        st.caption("Source: this dashboard's model (CENACE NES demand × 50% Nuevo León share placeholder, base growth, unmanaged charging).")

    coverage("Regional vs local: what to keep in mind", [
        "The grid series is the CENACE **Northeast (NES) balance area**, not Monterrey alone. Local overloads on neighborhood "
        "feeders and transformers are invisible in regional data and could matter long before the system does.",
        "The vehicle registry misses brands that do not report (BYD, and per press reports Tesla): it sees only about "
        f"{est.registry_share_2025:.0%} of the battery-electric fleet that INEGI's registration data counts. Tab 3 shows how this is handled.",
        "Everything after 2026 is a scenario, not a forecast. The Nuevo León share of the regional grid is a placeholder (50%).",
        f"A residential distribution transformer typically serves {ctx['reference'].set_index('metric').loc['homes_per_distribution_transformer', 'value']} "
        "homes (typical range, US patent 9403441): a few home chargers on one street can overload it while the system has spare capacity.",
        "The reserve margin is for Mexico's national grid (SIN), not Nuevo León: it says whether there is enough generation, "
        "not whether local wires can deliver it."])

    st.divider()
    st.markdown("### What happens when EVs meet the evening peak?")
    st.markdown("Pick a growth scenario. The model adds EV charging to the Northeast grid's load on its 2025 peak day, scaled to "
                "Nuevo León. **Only the grid shape and the 2024–25 fleet are measured; everything else is an assumption, shown below.**")

    HORIZON = 2035                     # fixed: the headline year
    day_kind = M.REFERENCE_DAYS[0]     # fixed: annual peak day (worst day of the year)
    growth_name = st.radio("Scenario: growth of new plug-in sales after 2026", list(M.GROWTH_SCENARIOS), index=1,
                           horizontal=True, key="gr")

    A = DEFAULT_A
    base = M.plugin_equivalent_stock(raiavl, fleet, est, A)
    gr = M.GROWTH_SCENARIOS[growth_name]
    prof = M.PROFILES[UNMANAGED]
    ref, ref_label = REF_DAY, REF_LABEL
    path = M.project_stock(base, gr, 2040, A, fleet_total[2025])
    row = path[path["anio"] == HORIZON].iloc[0]
    res = M.run_scenario(float(row["stock"]), A, prof, ref, HORIZON - base["anchor_year"])
    ty = M.tipping_year(A, prof, ref, base, gr, fleet_total[2025])

    with st.container(border=True):
        st.markdown(f"**Assumptions in this scenario** ({growth_name.split(' (')[0]})")
        a1, a2, a3 = st.columns(3)
        a1.markdown(f"- New plug-in sales grow **{gr:.0%} a year** after 2026\n"
                    f"- **{A.kwh_per_day:g} kWh** of grid energy per vehicle per day")
        a2.markdown(f"- A plug-in hybrid draws **{A.phev_weight:.0%}** of a battery-electric's energy\n"
                    f"- Charging: **unmanaged**, plug in after work (worst case)")
        a3.markdown(f"- 'Material' = peak rises **≥ {A.threshold_pct:g}%**\n"
                    f"- Nuevo León = **{A.nl_share:.0%}** of Northeast demand (placeholder)")
        st.caption(f"Fixed for every scenario: year {HORIZON}; reference day = 2025 annual peak day ({ref_label}); "
                   f"other demand grows {A.baseline_growth:.1%} a year (Northeast peak, 2022–2025).")

    m1 = st.columns(4)
    m1[0].metric(f"Plug-in fleet in {HORIZON} (BEV-equivalents)", fmt(row["stock"]), f"{row['share_pct']:.1f}% of all vehicles", delta_color="off")
    m1[1].metric("EV charging raises the daily peak by", f"{res.peak_uplift_pct:.1f}%")
    m1[2].metric(f"Year the peak rises ≥ {A.threshold_pct:g}%", str(ty) if ty else "after 2050")
    m1[3].metric("EV load at its busiest hour", f"{fmt(res.ev_max_mw)} MW", f"at {res.ev_max_hour:02d}:00", delta_color="off")
    m2 = st.columns(4)
    m2[0].metric("EV load at the system's peak hour", f"{fmt(res.ev_at_peak_mw)} MW", f"{res.ev_pct_at_peak:.1f}% of NL demand then", delta_color="off")
    m2[1].metric("Equals years of ordinary demand growth", f"{res.equiv_growth_years:.1f}")
    m2[2].metric("EV energy per day", f"{fmt(res.daily_ev_mwh)} MWh")
    m2[3].metric("Baseline peak hour", f"{res.peak_hour:02d}:00")

    st.markdown(f"#### Nuevo León load on a peak-demand day, {HORIZON}")
    figa = go.Figure()
    figa.add_trace(go.Scatter(x=HOURS, y=res.baseline_nl, name="Other demand (Northeast shape × NL share)", mode="lines",
                              stackgroup="one", line=dict(width=0.5, color=C.COLORS["grid"]), fillcolor="rgba(82,81,78,0.30)",
                              hovertemplate="%{y:,.0f} MW<extra>Other demand</extra>"))
    figa.add_trace(go.Scatter(x=HOURS, y=res.ev_mw, name="EV charging", mode="lines", stackgroup="one",
                              line=dict(width=0.5, color=C.COLORS["ev_load"]), fillcolor="rgba(42,120,214,0.75)",
                              hovertemplate="%{y:,.0f} MW<extra>EV charging</extra>"))
    figa.add_hline(y=res.baseline_nl.max(), line=dict(color=C.COLORS["ink2"], width=1, dash="dot"),
                   annotation_text="Today's peak (grown to this year, without EVs)", annotation_position="top left",
                   annotation_font=dict(size=11, color=C.COLORS["ink2"]))
    viz.style(figa, height=400, ytitle="MW")
    figa.update_xaxes(dtick=3)
    figa.update_yaxes(rangemode="tozero")
    st.plotly_chart(figa, width="stretch")
    st.caption(f"New peak {fmt(res.new_peak_mw)} MW at {res.new_peak_hour:02d}:00 vs {fmt(res.baseline_nl.max())} MW without EVs.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### EV effect on the peak, by year and growth path")
        paths = uplift_by_year(A, UNMANAGED, ref)
        st.plotly_chart(uplift_chart(paths, A.threshold_pct, 360, highlight=growth_name), width="stretch")
        table_view(pd.DataFrame(paths).round(2), "Show the data (% rise in peak)")
    with c2:
        st.markdown(f"#### Does charging behavior matter? Fleet size × charging, {HORIZON}")
        sizes = [50_000, 100_000, 250_000, 500_000, 750_000, 1_000_000, 1_500_000]
        z = [[M.run_scenario(s, A, p_, ref, HORIZON - base["anchor_year"]).peak_uplift_pct for s in sizes] for p_ in M.PROFILES.values()]
        ramp = [[i / 6, c] for i, c in enumerate([C.BLUE_RAMP[k] for k in (100, 200, 300, 450, 550, 650, 700)])]
        figs = go.Figure(go.Heatmap(z=z, x=[f"{s // 1000}k" if s < 1_000_000 else f"{s / 1e6:g}M" for s in sizes],
                                    y=[k.split(":")[0] for k in M.PROFILES], colorscale=ramp, zmin=0, zmax=15,
                                    xgap=2, ygap=2, texttemplate="%{z:.1f}%", showscale=False,
                                    hovertemplate="%{y}, %{x} vehicles<br>peak +%{z:.1f}%<extra></extra>"))
        viz.style(figs, height=360, legend=False, hover="closest", xtitle="Plug-in fleet (BEV-equivalents)")
        figs.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(figs, width="stretch")
        st.caption("Cell value = how much EV charging lifts the daily peak. Fleet size moves it far more than charging behavior. "
                   f"Current fleet ≈ {fmt(BASE['stock_2025'])} (end 2025).")

    st.markdown("**Year EV charging lifts the peak by 5%, for every growth path and charging behavior**")
    st.dataframe(tipping_table(A), width="stretch")

    vemo_mw = 65 * 0.120
    st.caption(f"Context: one operator announced 65 fast chargers of 120 kW in Nuevo León by end-2026 (El Financiero, June 2026), "
               f"about {vemo_mw:.1f} MW of nameplate capacity, roughly {100 * vemo_mw / (ref.max() * A.nl_share):.2f}% of today's peak in the model. "
               "Public fast charging is small next to home charging.")

    coverage("What is data and what is assumption", [
        "**Data:** the shape and size of Northeast demand (CENACE), registered electric vehicles in 2024–25 (INEGI), annual sales since 2016 (RAIAVL).",
        "**Estimated:** electric fleet before 2024 and the 2026 nowcast (from RAIAVL sales and a ratio calibrated on one year).",
        "**Assumed:** growth after 2026, kWh per vehicle, how and when people charge, the plug-in hybrid weight, the share of the Northeast that is "
        "Nuevo León (**placeholder 50%**), and what counts as 'material'. All are listed in the assumptions box above.",
        "Regional totals hide local stress: a street with many EVs can overload a transformer while the system looks fine."])




# =============================================================== TAB 5
with tabs[4]:
    st.markdown("## What can you do?")
    plan = ctx["plan"].sort_values("amount_million_mxn")
    ev_money = plan.loc[plan["mentions_ev_charging"].str.lower() == "yes", "amount_million_mxn"].sum()
    r1, r2 = st.columns([1, 1.25])
    with r1:
        st.markdown("#### The NL + CFE grid plan, million MXN")
        st.markdown(f"<span style='color:{C.COLORS['BEV']};font-size:1.1rem'><b>{ev_money:,.0f} earmarked for EV charging</b></span>",
                    unsafe_allow_html=True)
        figp = go.Figure(go.Bar(x=plan["amount_million_mxn"], y=plan["component"].str.replace(r" \(.*\)", "", regex=True),
                                orientation="h", marker_color=C.COLORS["grid"], marker_cornerradius=4,
                                text=[f"{v:,.0f}" for v in plan["amount_million_mxn"]], textposition="outside",
                                customdata=plan[["funder", "what_it_buys"]].to_numpy(),
                                hovertemplate="%{x:,.0f} M MXN · %{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
        viz.style(figp, height=300, legend=False, hover="closest")
        figp.update_xaxes(range=[0, plan["amount_million_mxn"].max() * 1.3], showticklabels=False)
        st.plotly_chart(figp, width="stretch")
        st.caption(f"Source: Gobierno de Nuevo León, 18 Aug 2026. The three parts add to {plan['amount_million_mxn'].sum():,.0f} "
                   "million MXN; the announcement rounds to 10,000. Transmission (6 projects) and distribution are CFE; mobile substations are the State. "
                   "Hover a bar for what it buys.")
    with r2:
        st.markdown("#### Recommendations")
        st.markdown(
        "1. **Do not fund generation or transmission *for EVs* now.** Ordinary demand growth is the bigger driver for the next decade, and EV "
        "charging stays below a 5% rise in the peak until the mid-2030s under base growth.\n"
        "2. **Watch the growth rate first, charging behavior second.** In the model, how fast plug-in sales grow moves the 5% date by "
        "about ten years; when people charge moves it by one or two. Time-of-use tariffs are still worth piloting with CFE, but as a "
        "refinement, not the main lever.\n"
        "3. **Ask CFE for feeder- and transformer-level load in the Monterrey metro** and overlay it with municipal EV counts from the state's "
        "own vehicle-registration records. That is where the real risk sits and where this dashboard is blind.\n"
        "4. **Fix the measurement gap.** The state's registration data counts every EV regardless of brand. Publish it by municipality and "
        "energy source, and ask INEGI to resolve the plug-in hybrid coding.\n"
        "5. **Set triggers, not dates.** Sales are already growing at the High-scenario pace (about 40% a year). If that pace holds "
        "through 2027, the 5% rise moves to about 2034, so start grid planning with CFE by about 2030. Re-run this dashboard each "
        "year with new INEGI and CENACE data.")


    with st.expander("What this data cannot see"):
        st.markdown(
        "- **Brands that do not report.** BYD, and per press reports Tesla, are missing from RAIAVL. The registered fleet is about "
        f"{1 / est.registry_share_2025:.0f}× the registry's cumulative sales, so true adoption is larger than any sales chart shows.\n"
        "- **Where in the metro EVs are.** Both INEGI tables stop at the state; CENACE's series is a region. Feeder and transformer load "
        "(San Pedro, Monterrey, Apodaca…) is where stress would appear first.\n"
        "- **Origin, price and plant-level detail.** RAIAVL has no imports by country of origin, prices or plant output, so it "
        "cannot explain *why* sales move (tariffs, Chinese entrants, incentives).\n"
        "- **Charging behavior.** Nobody here has measured when Nuevo León's EV owners charge. The hourly shapes are assumptions.\n"
        "- **Heat.** Temperature drives the peak and is not loaded; demand's seasonal shape is the only proxy.\n"
        "- **Series breaks.** CENACE's definition change (Jan 2020) and INEGI's fleet break (2023) limit how far back the grid "
        "and stock comparisons go.")

    with st.expander("Sources"):
        st.markdown(
        "- INEGI. *Registro Administrativo de la Industria Automotriz de Vehículos Ligeros (RAIAVL)*, tabulado Híbridos y eléctricos.\n"
        "- INEGI. *Estadística de Vehículos de Motor Registrados en Circulación (VMRC)*, Nuevo León, consulta interactiva.\n"
        "- CENACE. *Estimación de Demanda por Balance*, área NES (Noreste); region codes from CENACE's Demanda Regional page.\n"
        "- El Financiero, 18 June 2026, Vemo charging stations in Nuevo León.\n"
        "- El Imparcial, 22–23 July 2025: an industry executive (Huawei Digital Power) says the grid shows signs of saturation, "
        "the claim this dashboard tests.\n"
        "- CFE. *Programa de Ampliación y Modernización de las Redes Generales de Distribución (PAM RGD)*, 2019–2033 to 2025–2039 editions: "
        "SAIDI, SAIFI and CAIDI for the Golfo Norte division.\n"
        "- Gobierno de Nuevo León, 18 Aug 2026: NL + CFE plan to strengthen the grid.\n"
        "- Forbes México (CENACE data), 2026: reserve margin, peak demand, installed capacity. El Financiero, 6 Jun 2024: alert and emergency thresholds.\n"
        "- 2026 events: Posta, Zeta Tijuana, Diario de Yucatán, N+ (CFE data), Líder Empresarial (CAINTRA), H. Congreso de Nuevo León. "
        "Every row in `data/context/grid_context_2026.csv` carries its own link.")
    st.markdown("<span class='small'>Code and pipeline: see README. Data processing is done in code (pipeline/), not by hand.</span>",
                unsafe_allow_html=True)

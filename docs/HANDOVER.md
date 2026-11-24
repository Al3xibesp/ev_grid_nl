# Handover for the Documentator: EV adoption vs. Monterrey's grid

Prepared 23 Nov 2026 for Alex (Tecnológico de Monterrey). Everything below is what the Documentator needs to document this project without re-deriving it.

## 1. The assignment and why it matters

- **Course deliverable:** individual data-visualization assignment, "The Emerging Stories of Mexico's Automotive Industry". A Streamlit dashboard (Plotly/Seaborn/Matplotlib) built on INEGI's RAIAVL registry.
- **Requirements:**
  - Data cleaned in code: harmonized names, proper monthly dates, preliminary vs revised figures.
  - At least 10 years of monthly data, with seasonality handled (YoY, YTD, 12-month rolling).
  - At least 2 filter dimensions plus a time window.
  - Annotated events: pandemic, chip shortage, Jan 2026 tariff change, brands entering or leaving the registry.
  - On-screen honesty about coverage gaps and series breaks.
  - A narrative: role, stakeholders, decision, justification of tables, guiding questions, limitations, recommendations.
- **Submission:** Streamlit app link (presented in class), write-up of at most 2 pages, code repo including the load/clean script.
- **Grading:** the professor says 100/100 is the only acceptable grade and gives feedback in class for iteration.
- **Brief location:** Alex's Drive folder https://drive.google.com/drive/folders/1XPXhMk9r7b9orQYfj8PrrEXLglACiaqJ (docx id 11vviRNOpoIPPzTAQhPU9-_Zo-y6JZPiy). The first folder link Alex gave was the wrong one.

**Alex's framing**
- Role: advisor to the Government of Nuevo León.
- Question: "Will increased electric car sales negatively impact Nuevo León's electric grid, specifically in Monterrey?"
- Decision: whether and when the state should act on charging infrastructure and grid reinforcement.
- Why it matters: Nuevo León is industrial (66% of consumption), demand is already growing, and EV sales are accelerating from a very small base.

**Option C (chosen by Alex).** The registry alone cannot answer a grid question, so the question became a scenario question ("when would EVs matter, and under what adoption path?"). Three datasets were added: registered vehicles (VMRC), hourly regional grid demand (CENACE), and a scenario model. Temperature and charger data were planned but not obtained (see section 7).

## 2. Data sources

| Source | What it is | Key facts |
|---|---|---|
| INEGI RAIAVL "Híbridos y eléctricos" | Monthly light-vehicle sales by state: BEV, PHEV, HEV | Jan 2016 to Oct 2026. Nov–Dec 2026 dropped as future. 38 blank state-months. Has a "No especificado" row. Misses brands that do not report (BYD, and per press Tesla). |
| INEGI VMRC | Registered vehicles in circulation, Nuevo León | 12 latin-1 CSVs, 2014–2025. Blank lines between rows, thousands separators, "-" means 0. Energy source exists only for 2024–2025 ("No aplica" before). |
| CENACE "Estimación de Demanda por Balance", area NES | Hourly demand, Noreste region (includes Monterrey) | 2016-01-29 to 2026-11-08. Several row layouts. Up to 5 revisions per date. Rule: keep the latest revision. Hour 25 dropped. Last 42 days are preliminary. |

**Discarded file:** `nor_demanda_real_balance.csv` was the wrong area (NOR = Noroeste: Sonora/Sinaloa) and was truncated at Dec 2021. Alex then supplied the NES file. Region codes: NOR = Noroeste, NES = Noreste, NTE = Norte.

## 3. Key decisions and the reasoning behind them

1. **Grid series starts 2020-01-01.** Before that date the published "demand by balance" is roughly gross generation (about 10 GW). From 2020 it subtracts flows to other regions (about 6–7 GW). Only 2020 onward is comparable, which gives about 6.9 years. This is a series break and is shown on screen.
2. **Pandemic and storm.** 2020 is COVID. The 15 Feb 2021 minimum (about 1.1 GW) is real winter-storm load shedding, not a data error.
3. **VMRC fleet break in 2023.** The total fleet falls from 2.686M to 2.233M (−16.9%), likely a registry cleanup or the 2022 decree on used imports. Never compare across it.
4. **Fleet estimate for years before 2024.** Proportional back-cast: central estimate = observed 2024 stock × cumulative RAIAVL BEV sales.
   - Holdout test on 2025: +5.4% error.
   - Low case: RAIAVL cumulative only.
   - High case: step back using a 2025 coverage multiplier of 4.78 (ΔVMRC electric ÷ RAIAVL BEV in 2025).
   - 2026 is a nowcast.
5. **PHEV modeled from RAIAVL.** VMRC "Híbrido" is lower than RAIAVL cumulative hybrids, so VMRC cannot be used for PHEVs.
6. **Scenario model** (`pipeline/model.py`):
   - Defaults: 7.5 kWh/day per BEV, PHEV weight 0.5, baseline demand growth about 2% (the app uses the data value, about 2.1%), threshold 5% peak rise, fleet growth 3%.
   - Growth scenarios: Low +10%, Base +25%, High +40% per year.
   - Hourly charging profiles: Unmanaged, Mixed, Managed (staggered overnight).
   - **`nl_share = 0.50` is an unsourced placeholder** for Nuevo León's share of the NES region.
7. **Dataviz rules applied:** validated categorical palette, thin marks, direct labels, table view, no dual axis.

## 4. Verified results (numbers the write-up can cite)

An independent recomputation matched the app.

- **Nuevo León BEV sales, 2016–2026 (10 months):** 16, 16, 14, 18, 47, 69, 497, 943, 1,422, 1,605, 2,626.
- **Nuevo León PHEV sales, same years:** 66, 84, 127, 109, 168, 326, 451, 572, 750, 1,440, 3,447.
- **Fleet (VMRC):** electric vehicles 17,091 (2024) → 24,761 (2025), which is 0.92% of 2,698,327 registered vehicles. Registry cumulative BEV sales cover only 18.8% of registered EVs, hence the multiplier of 4.779.
- **NES annual peak (MW):** 2020 9,215; 2021 9,530; 2022 10,084; 2023 10,878; 2024 11,023; 2025 10,729; 2026 11,531. Peak CAGR 2022–25 is 2.09%. The mean 2025 load is 7,277 MW. The 2025 peak was on 13 Aug at 16:00.
- **Scenario (defaults, Base +25%/yr, unmanaged):**
  - Stock at end-2025: 26,808 BEV-equivalents.
  - 2035 stock: 596,337 (about 16% of the fleet).
  - EV load peaks at 480 MW at 19:00.
  - Peak rise: +1.0% in 2030, +3.3% in 2035.
  - Organic demand growth over 10 years (about 1,233 MW) is larger than the EV load.
- **Year the peak rises 5% (Base):** unmanaged 2036, mixed 2038, managed 2037. Across all scenarios the range is 2034 (High, unmanaged) to 2047 (Low, mixed).
- **Tipping fleet in 2035:** unmanaged 736,261; mixed 945,622; managed 847,362 (formula equals brute force).
- **Key insight:** the NES demand curve is flat (minimum/maximum ratio 0.79), because the region is industrial. Shifting charging to night therefore helps only slightly regionally. The growth path of adoption decides when impact arrives. The case for managed charging is local (feeders and transformers), which this data cannot see.

**Answer to the question, in one line:** at the regional level, EVs are not a threat this decade. Organic demand growth dwarfs EV load, and a 5% peak rise needs roughly 700–950k EVs. Local distribution is the real risk, and the data cannot show it.

## 5. Provenance of the code

- **Corrected on 23 Nov:** an earlier version of this section said the repo's origin was unknown. That was wrong. The session log shows Claude wrote the pipeline, `model.py`, `viz.py`, `config.toml` and `app.py` in this same session on 22 Nov (local time, about 20:09–20:14), after Alex supplied the three datasets.
- After that, Claude audited the code:
  - A scratch rebuild of the pipeline gave byte-identical processed files (hash match).
  - Headline numbers were recomputed independently and matched.
  - The tipping year was checked by brute force.
  - 23 widget paths were run headlessly with Streamlit AppTest, with no exceptions.
- Claude then fixed two bugs in `app.py` on 23 Nov:
  1. `NameError: NL_COLOR` became `viz.NL_COLOR`.
  2. All 15 `use_container_width=True` became `width="stretch"`.
  - Original backup: `/tmp/claude-0/-home-claude/cadacf07-31ce-5eda-9909-1a70480150ad/scratchpad/app.py.orig`.
- Alex supplied only the raw data and the question. The code is Claude-written, so Alex must understand it well enough to explain it in class and should disclose the AI assistance if the course requires it.

## 6. File map

```
ev_grid_nl/
├── app.py                      Streamlit app, 6 tabs (42 KB)
├── viz.py                      plotting helpers, NL_COLOR
├── .streamlit/config.toml      theme (light), headless, no telemetry
├── pipeline/
│   ├── config.py               paths, GRID_COMPARABLE_FROM, COLORS, EVENTS
│   ├── load_grid.py            CENACE parser (revisions, layouts, hour 25)
│   ├── load_fleet.py           VMRC parser
│   ├── load_raiavl.py          RAIAVL cleaner
│   ├── model.py                scenario model
│   └── build.py                run: python -m pipeline.build  (from repo root)
├── data/
│   ├── raw/                    RAIAVL_11.xlsx, nes_demanda_real_balance.csv (57 MB), inegi_vmrc/*.csv
│   └── processed/              nes_hourly.csv.gz, raiavl_clean.csv, fleet_nl.csv, data_quality.json
├── tests/                      empty
└── docs/                       this file
```

**App tabs:** 1 The question · 2 EV adoption · 3 Vehicles on the road · 4 The grid · 5 Collision: scenarios · 6 Limits & recommendations.

**Run locally:** `pip install streamlit plotly pandas numpy openpyxl`, then `streamlit run app.py`. The sandbox used Python 3.13, Streamlit 1.67, Plotly 7.1, pandas 3.0.

## 7. Limitations the write-up must state

- NES is a region, not Monterrey.
- "Demand by balance" is an estimate.
- BYD and Tesla are missing from RAIAVL.
- VMRC energy source exists only for 2024–2025, and the total fleet breaks in 2023.
- The coverage multiplier is calibrated on one year.
- `nl_share = 0.50` is unsourced.
- Charging profiles and 7.5 kWh/day are assumptions.
- No temperature data: the API was unreachable from the sandbox, and the app says so.
- No brand dimension in the EV table, so panel changes (e.g. GAC, MOTORNATION) cannot be isolated.

## 8. Open items (nothing below is done yet)

**Content fixes in `app.py`**
1. Rewrite Recommendation #2 (about lines 608–619). It claims charging timing matters as much as fleet size, and the model contradicts that. The model shows timing moves the 5% date by about 1 year, while the growth path moves it by up to a decade.
2. Rewrite the Recommendation #5 trigger. A 5% fleet share gives only about +1% peak rise (unmanaged, 2030: 156k EVs, 126 MW).
3. Verify or replace the "El Imparcial, 22–23 July 2025 / Huawei Digital Power" source line (about line 627). The headline attributes the claim to CFE. The Milenio article on Huawei is a possible replacement.
4. Optionally add one sentence about the flat demand curve to the tab 1 answer box.

**Missing deliverables**
5. README, `requirements.txt` (streamlit>=1.50), `.gitignore` (exclude the 57 MB raw CENACE file).
6. Unit tests in `tests/`.
7. Write-up of at most 2 pages.
8. Visual QA with screenshots of all six tabs.
9. Deploy to Streamlit Community Cloud (needs Alex's GitHub and Streamlit accounts) to get the required link.
10. Hand over the repo (zip) to Alex.

## 9. What Alex should be able to explain in class

- Why the NOR file was discarded, and why the grid series starts in 2020.
- Why the fleet before 2024 is an estimate, and how it was validated (+5.4% holdout, low/central/high).
- Why the VMRC 2023 drop is not an EV effect.
- Why 5% is the threshold (an assumption), and why the answer is "not at the regional level this decade".
- Why timing of charging matters little regionally and a lot locally.
- How the code works, since Claude wrote it. Walk through the pipeline and the model before class.

## 10. Notion-ready task list

Notion is Alex's project-management tool. Suggested columns: Task, Status, Notes.

| Task | Status |
|---|---|
| Choose role and question | Done |
| Locate brief in Drive | Done |
| Reframe question (Option C) | Done |
| Obtain RAIAVL, VMRC, CENACE NES data | Done |
| Audit pipeline and app | Done |
| Fix `NL_COLOR` and deprecation bugs | Done |
| Rewrite Recommendations #2 and #5 | To do |
| Verify or replace the El Imparcial/Huawei source | To do |
| README, `requirements.txt`, `.gitignore` | To do |
| Unit tests | To do |
| Visual QA (6 tabs) | To do |
| 2-page write-up | To do |
| Deploy to Streamlit Cloud | To do |
| Read through the code so Alex can explain it | To do |
| Rehearse the class presentation | To do |

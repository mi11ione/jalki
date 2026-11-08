"""Facts checker for C2 (runs first, must pass). Copies c1-yield-b/packfacts.py checks (stated package facts)
and adds the C2-specific stated facts from TASKS_AND_SCORING.md / SCENARIOS_AND_RISK.md / SIMULATION_DESIGN.md:
  * C2 template = FI_SW x 5 crops x 3 SSPs + SE_SKANE pea x 3 SSPs = 18 rows, period 2041-2060;
  * daily weather: historical 1991-2026, ssp126/245/585 2027-2060, 84 cells, complete days;
  * climate_change_signals: 3 SSPs x 12 months, period '2041-2060 vs 1991-2020'.
Exit 1 on failure."""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c1_yields"))
import boot  # noqa: E402
import runpy
from pathlib import Path
import pandas as pd

D = Path(boot.DATA)
print("== c1-yield-b package facts (re-run) ==")
try:
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c1_yields", "packfacts.py"), run_name="__main__")
except SystemExit as e:
    if e.code:
        print("PACKAGE FACTS FAILED"); sys.exit(1)

print("== C2 facts ==")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


tpl = pd.read_csv(D / "tasks/templates/C2_climate_yield_risk_submission.csv")
exp = {("FI_SW", c, s) for c in ["pea", "potato", "carrot", "spinach", "turnip_rape"] for s in ["ssp126", "ssp245", "ssp585"]}
exp |= {("SE_SKANE", "pea", s) for s in ["ssp126", "ssp245", "ssp585"]}
got = set(zip(tpl.region, tpl.crop, tpl.scenario))
check("C2 template = 18 region x crop x SSP rows", got == exp and len(tpl) == 18, len(tpl))
check("C2 period = 2041-2060", set(tpl.period) == {"2041-2060"})
w = pd.read_parquet(D / "data/04_climate/weather_daily_1991_2060.parquet", columns=["cell_id", "date", "scenario"])
w["year"] = w.date.dt.year
yr = w.groupby("scenario").year.agg(["min", "max"])
check("daily historical 1991-2026", tuple(yr.loc["historical"]) == (1991, 2026), tuple(yr.loc["historical"]))
for s in ("ssp126", "ssp245", "ssp585"):
    check(f"daily {s} 2027-2060", tuple(yr.loc[s]) == (2027, 2060), tuple(yr.loc[s]))
nd = w.groupby(["scenario", "cell_id", "year"]).size()
check("every cell-year has 365/366 days", nd.between(365, 366).all(), (int(nd.min()), int(nd.max())))
check("84 cells in daily weather", w.cell_id.nunique() == 84, w.cell_id.nunique())
sg = pd.read_csv(D / "data/04_climate/climate_change_signals.csv")
check("signals: 3 SSPs x 12 months, 2041-2060 vs 1991-2020",
      len(sg) == 36 and set(sg.period) == {"2041-2060 vs 1991-2020"} and set(sg.scenario) == {"ssp126", "ssp245", "ssp585"})
jja = sg[sg.month.between(6, 8)].groupby("scenario").delta_tmean_c.mean()
check("summer warming ordered ssp126 < ssp245 < ssp585", jja.is_monotonic_increasing, jja.round(2).to_dict())
if fails:
    print("C2 FACTS FAILED:", fails); sys.exit(1)
print("ALL C2 FACTS HOLD")

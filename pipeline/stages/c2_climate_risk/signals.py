"""Does each single SSP realisation (2041-2060) reproduce the stated ensemble signals (vs 1991-2020)?
Also: summer interannual variability (sd of Apr-Sep mean T and total precip) history vs future, per region.
Prints a table; writes out/pet_ratio.csv (PET ratio per region x scenario x month, realisation-based) for the delta method."""
from ccn_paths import PACKAGE, stage_dir
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c1_yields"))
import boot  # noqa: E402
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(boot.DATA)
OUT = stage_dir("c2_climate_risk") / "out"
OUT.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
mo = pd.read_csv(D / "data/04_climate/weather_monthly_1991_2060.csv")
grid = pd.read_csv(D / "data/01_master/climate_grid_cells.csv")[["cell_id", "region"]]
mo = mo.merge(grid, on="cell_id")
print(mo.columns.tolist())
base = mo[(mo.scenario == "historical") & mo.year.between(1991, 2020)]
sg = pd.read_csv(D / "data/04_climate/climate_change_signals.csv")
rows = []
for s in ("ssp126", "ssp245", "ssp585"):
    fut = mo[(mo.scenario == s) & mo.year.between(2041, 2060)]
    for reg in ("FI_SW", "SE_SKANE"):
        b = base[base.region == reg].groupby("month")[["tmean_c", "precip_mm", "pet_mm"]].mean()
        f = fut[fut.region == reg].groupby("month")[["tmean_c", "precip_mm", "pet_mm"]].mean()
        for m in range(1, 13):
            g = sg[(sg.scenario == s) & (sg.month == m)].iloc[0]
            rows.append(dict(scenario=s, region=reg, month=m, dT_real=f.tmean_c[m] - b.tmean_c[m], dT_sig=g.delta_tmean_c,
                             pf_real=f.precip_mm[m] / b.precip_mm[m], pf_sig=g.precip_factor, pet_ratio=f.pet_mm[m] / b.pet_mm[m]))
r = pd.DataFrame(rows)
r.to_csv(OUT / "pet_ratio.csv", index=False)
gs = r[r.month.between(4, 9)].groupby(["scenario", "region"])[["dT_real", "dT_sig", "pf_real", "pf_sig", "pet_ratio"]].mean()
print("Apr-Sep mean: realisation delta vs stated signal")
print(gs.round(3).to_string())
print("Apr-Sep per-month |dT_real - dT_sig| max:", round((r[r.month.between(4, 9)].dT_real - r[r.month.between(4, 9)].dT_sig).abs().max(), 2))
# variability
gsn = mo[mo.month.between(4, 9)].groupby(["scenario", "region", "year"]).agg(t=("tmean_c", "mean"), p=("precip_mm", "sum")).reset_index()
gsn["p"] = gsn.p / gsn.groupby(["scenario", "region", "year"]).p.transform("size")  # cells summed -> per-cell
cnt = mo[mo.month.between(4, 9)].groupby(["scenario", "region", "year"]).cell_id.nunique().reset_index(name="nc")
gsn = gsn.merge(cnt)
v = []
for (s, reg), g in gsn.groupby(["scenario", "region"]):
    yrs = (1991, 2020) if s == "historical" else (2041, 2060)
    g = g[g.year.between(*yrs)]
    v.append(dict(scenario=s, region=reg, years=f"{yrs[0]}-{yrs[1]}", sd_T=g.t.std(), cv_P=g.p.std() / g.p.mean()))
print("Apr-Sep interannual variability (region mean of cells):")
print(pd.DataFrame(v).round(3).to_string(index=False))

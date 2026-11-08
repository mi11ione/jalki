"""Facts checker: the package must satisfy the facts its own docs state, before any analysis.
Sources: DATA_DICTIONARY.md row counts, SIMULATION_DESIGN.md 'World at a glance' and calibration table,
TASKS_AND_SCORING.md C1 setting. Prints ALL BRIEF FACTS HOLD or the failures. Exit 1 on failure."""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
from pathlib import Path
import pandas as pd

D = Path(boot.DATA)
fails, n = [], 0


def check(name, ok, detail=""):
    global n
    n += 1
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


par = pd.read_csv(D / "data/01_master/parcels.csv")
ch = pd.read_csv(D / "data/03_farming/parcel_crop_history_and_plan.csv")
sv = pd.read_csv(D / "data/03_farming/farm_survey_fi.csv")
fh = pd.read_csv(D / "data/03_farming/foodhills_odlingsdata_se.csv", sep=";", decimal=",")
mo = pd.read_csv(D / "data/04_climate/weather_monthly_1991_2060.csv")
grid = pd.read_csv(D / "data/01_master/climate_grid_cells.csv")
reg = pd.read_csv(D / "data/01_master/farm_registry.csv")
tpl = pd.read_csv(D / "tasks/templates/C1_yields_2027_2031_submission.csv")

check("parcels rows = 14,213", len(par) == 14213, len(par))
check("crop history rows = 284,260", len(ch) == 284260, len(ch))
check("farm survey rows = 3,437", len(sv) == 3437, len(sv))
check("foodhills rows = 2,683", len(fh) == 2683, len(fh))
check("weather monthly rows = 139,104", len(mo) == 139104, len(mo))
check("climate grid = 84 cells (36 FI, 48 SE)", len(grid) == 84 and (grid.region == "FI_SW").sum() == 36, grid.region.value_counts().to_dict())
seg = reg.segment.value_counts().to_dict()
check("farms 680 = 150 veg + 230 oil + 300 se_pea", seg == {"se_pea": 300, "oil": 230, "veg": 150}, seg)
check("crop history declared 2012-2026, planned 2027-2031",
      set(ch[ch.status == "declared"].year) == set(range(2012, 2027)) and set(ch[ch.status == "planned"].year) == set(range(2027, 2032)))
check("historical weather to 2026, SSPs 2027-2060",
      mo[mo.scenario == "historical"].year.max() == 2026 and mo[mo.scenario == "ssp245"].year.min() == 2027 and mo[mo.scenario == "ssp245"].year.max() == 2060)
crops = ["pea", "potato", "carrot", "spinach", "turnip_rape"]
pl = ch[(ch.status == "planned") & ch.crop.isin(crops)]
pl = pl.merge(reg[["farm_id", "region"]], on="farm_id")
pl = pl[~((pl.region == "SE_SKANE") & (pl.crop != "pea"))]
check("template rows = planned contract-crop parcel-years", len(tpl) == len(pl), f"{len(tpl)} vs {len(pl)}")
k = tpl.merge(par[["parcel_id", "area_ha"]], on="parcel_id", suffixes=("", "_p"))
check("template area = parcel area (±0.01 ha)", (k.area_ha - k.area_ha_p).abs().max() < 0.011, round((k.area_ha - k.area_ha_p).abs().max(), 4))
fi_pea_ha = ch[(ch.crop == "pea") & (ch.year == 2025)].merge(par[["parcel_id", "area_ha"]]).merge(reg[["farm_id", "region"]])
fi_pea_ha = fi_pea_ha[fi_pea_ha.region == "FI_SW"].area_ha.sum()
check("FI contract peas ~2,000 ha in 2025 (±25 %)", 1500 <= fi_pea_ha <= 2500, round(fi_pea_ha))
s = sv[(sv.year >= 2022) & (sv.year <= 2024)]
s = s[s.yield_t_ha < 2.5 * s.groupby("crop").yield_t_ha.transform("median")]
tgt = {"potato": 31, "carrot": 48, "turnip_rape": 1.3, "pea": 3.0}
for c, t in tgt.items():
    m = s[s.crop == c].yield_t_ha.median()
    check(f"survey {c} median 2022-24 within ±15 % of doc target {t} t/ha", abs(m / t - 1) <= 0.15, round(m, 2))
resp = sv[sv.year >= 2020].groupby("year").size().mean() / max(1, reg[reg.segment.isin(["veg", "oil"])].shape[0])
check("survey present for every FI season 2012-2026", set(sv.year) == set(range(2012, 2027)))
check("foodhills seasons 2018-2026", set(fh["skördeår"]) == set(range(2018, 2027)))
print(f"{n - len(fails)}/{n} facts hold")
if fails:
    print("FACTS FAILED:", fails)
    sys.exit(1)
print("ALL BRIEF FACTS HOLD")

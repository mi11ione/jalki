"""Facts checker: the package must satisfy every D1-relevant fact its docs state.
  python stages/d1_model_b/packfacts.py      -> prints ALL BRIEF FACTS HOLD or the failures."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import Counter
from lib import read, catchments, monitored, load_dev

par = read("data/01_master/parcels.csv"); cat = catchments(); mon = monitored()
reg = read("data/01_master/farm_registry.csv")
ch = read("data/03_farming/parcel_crop_history_and_plan.csv")
sv = read("data/03_farming/farm_survey_fi.csv"); se = read("data/03_farming/foodhills_odlingsdata_se.csv", ";")
miss = sum(p["p_test_mgl_latest"] == "" for p in par) / len(par)
regions = Counter(c["region"] for c in cat.values())
facts = [
    ("14,213 parcels (SIMULATION_DESIGN)", len(par) == 14213),
    ("42 catchments, 28 FI + 14 SE (SIMULATION_DESIGN)", len(cat) == 42 and regions["FI_SW"] == 28 and regions["SE_SKANE"] == 14),
    ("15 monitored stations (TASKS_AND_SCORING)", len(mon) == 15 and sum(c["monitoring_station"] == "True" for c in cat.values()) == 15),
    ("monitored years 2019-2025", all(sorted(m) == list(range(2019, 2026)) for m in mon.values())),
    ("680 contract farms: 150 veg, 230 oil, 300 SE pea", len(reg) == 680 and Counter(r["segment"] for r in reg) == Counter(veg=150, oil=230, se_pea=300)),
    ("soil-P test ~18% missing (NATURE_SBTN)", 0.16 <= miss <= 0.20),
    ("crop history 284,260 rows (DATA_DICTIONARY)", len(ch) == 284260),
    ("farm survey 3,437 rows", len(sv) == 3437),
    ("Foodhills file 2,683 rows", len(se) == 2683),
    ("dev key has 6 catchments", len(load_dev()) == 6),
    ("every parcel maps to a listed catchment", all(p["catchment_id"] in cat for p in par)),
]
bad = [f for f, ok in facts if not ok]
for f, ok in facts:
    print(("OK   " if ok else "FAIL ") + f)
print(f"soil-P missing share = {miss:.3f}")
print("ALL BRIEF FACTS HOLD" if not bad else f"FACTS FAILED: {bad}")

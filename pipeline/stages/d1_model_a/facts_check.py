"""Twin facts check: the package must match the counts stated in SIMULATION_DESIGN.md / TASKS_AND_SCORING.md."""
import collections
from d1lib import rd, DATA, TWIN
par = rd(DATA / "01_master" / "parcels.csv"); cat = rd(DATA / "06_nature" / "catchments.csv")
mon = rd(DATA / "06_nature" / "monitored_catchment_loads.csv"); fr = rd(DATA / "01_master" / "farm_registry.csv")
dev = rd(TWIN / "tasks" / "dev" / "D1_dev_catchments_2025.csv")
reg = collections.Counter(c["region"] for c in cat)
checks = [
    ("parcels == 14213", len(par) == 14213),
    ("catchments == 42 (28 FI, 14 SE)", len(cat) == 42 and reg["FI_SW"] == 28 and reg["SE_SKANE"] == 14),
    ("contract farms == 680 (150 veg, 230 oil, 300 SE pea)", len(fr) == 680 and collections.Counter(f["segment"] for f in fr) == {"veg": 150, "oil": 230, "se_pea": 300}),
    ("monitored stations == 15, years 2019-2025", len({m["catchment_id"] for m in mon}) == 15 and {m["year"] for m in mon} == {str(y) for y in range(2019, 2026)}),
    ("monitoring_station flag matches load file", {c["catchment_id"] for c in cat if c["monitoring_station"] == "True"} == {m["catchment_id"] for m in mon}),
    ("dev catchments == 6", len(dev) == 6),
    ("soil-P test missing ~18 %", abs(sum(p["p_test_mgl_latest"] == "" for p in par) / len(par) - 0.18) < 0.01),
]
for n, ok in checks:
    print(("PASS " if ok else "FAIL ") + n)
print("FACTS_OK" if all(ok for _, ok in checks) else "FACTS_FAIL")

"""Facts check on the pack: row counts and calibration facts the documents state. Exits non-zero if one fails.
Run: python stages/b_pathways/s05_facts.py"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import pandas as pd
import lib_clean as L
from ccn_tools import io as IO, reference_calculator as RC, score as SC

raw = IO.load_raw(L.DATA)
d = L.DATA / "data"
facts = [
    ("ERP lines 7,427", len(raw["erp"]), 7427), ("meter rows 610", len(raw["energy_meter"]), 610), ("farms 680", len(raw["farm_registry"]), 680),
    ("parcels 14,213", len(raw["parcels"]), 14213), ("levers 30", len(pd.read_csv(d / "05_scenarios" / "decarbonisation_levers.csv")), 30),
    ("scenario rows 49", len(pd.read_csv(d / "05_scenarios" / "transition_scenarios.csv")), 49),
    ("scenarios 7", pd.read_csv(d / "05_scenarios" / "transition_scenarios.csv").scenario.nunique(), 7),
    ("Foodhills rows 2,683", len(pd.read_csv(d / "03_farming" / "foodhills_odlingsdata_se.csv", sep=";")), 2683),
    ("Grain trade divestment dated 2022-05-31", int(pd.read_csv(d / "05_scenarios" / "structural_events.csv").date.eq("2022-05-31").sum()), 1),
    ("Foodhills acquisition dated 2025-11-27", int(pd.read_csv(d / "05_scenarios" / "structural_events.csv").date.eq("2025-11-27").sum()), 1),
]
T = IO.naive_canonical(raw)
for y, want in ((2023, 25.54), (2024, 23.24)):
    k = pd.read_csv(L.DATA / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv")
    facts.append((f"naive A2 dev {y} = documented baseline {want}", SC.score_a2(RC.summarise(RC.compute_inventory(T, y)), k)["score"], want))
_, C = L.load_clean()
e = C["energy"].query("year==2025 and carrier=='electricity'").mwh.sum()
facts.append(("cleaned 2025 electricity = calibration target 37,222 MWh", round(e), 37222))
bad = 0
for name, got, want in facts:
    ok = got == want
    bad += not ok
    print("OK  " if ok else "FAIL", name, "| got", got)
print("PACK NOTE: START_HERE lists data/00_apetit_original; present here:", (d / "00_apetit_original").exists(), "(not used by this ticket)")
print("PACK NOTE: DATA_DICTIONARY lists company code C400; ERP rows with it:", int((raw["erp"].company_code == "C400").sum()))
print("PACK NOTE: tasks/templates holds a B template:", any("B" == p.name[0] for p in (L.DATA / "tasks" / "templates").iterdir()), "| tasks/dev holds a B key:", any(p.name.startswith("B") for p in (L.DATA / "tasks" / "dev").iterdir()))
print("ALL BRIEF FACTS HOLD" if not bad else f"{bad} FACTS FAILED")
sys.exit(1 if bad else 0)

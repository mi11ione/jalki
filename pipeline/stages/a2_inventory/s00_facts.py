"""Pack facts check, run first. Stdlib only, so it works with or without pandas.
Confirms the organisers' manifest hashes and the documented row counts in the package.
Prints any failure as it is; nothing here relaxes a check. Synthetic pack."""
from ccn_paths import PACKAGE, stage_dir
import csv, hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = PACKAGE
man = json.loads((ROOT / "MANIFEST.json").read_text())
bad, missing = [], []
for f in man["files"]:
    p = ROOT / f["path"]
    if not p.exists():
        missing.append(f["path"])
    elif hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
        bad.append(f["path"])
print(f"manifest files {len(man['files'])}, missing {len(missing)}, hash mismatch {len(bad)}")
print("missing:", missing)
print("mismatch:", bad)


def rows(rel, sep=","):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh, delimiter=sep))


D = "data/"
facts = {
    "erp 7427": rows(D + "02_raw_feeds/erp_purchase_lines_2021_2025.csv") == 7427,
    "energy 610": rows(D + "02_raw_feeds/energy_meter_readings.csv") == 610,
    "fuel 263": rows(D + "02_raw_feeds/fuel_deliveries.csv") == 263,
    "goo log 19": rows(D + "02_raw_feeds/goo_cancellations.csv") == 19,
    "goo registry 55": rows(D + "02_raw_feeds/goo_registry_statement.csv") == 55,
    "refrigerant 84": rows(D + "02_raw_feeds/refrigerant_service_log.csv") == 84,
    "waste 1008": rows(D + "02_raw_feeds/waste_transfer_notes.csv") == 1008,
    "travel 3532": rows(D + "02_raw_feeds/travel_bookings.csv") == 3532,
    "commuting 208": rows(D + "02_raw_feeds/commuting_survey_2025.csv") == 208,
    "shipments 11617": rows(D + "02_raw_feeds/shipments.csv") == 11617,
    "farm survey 3437": rows(D + "03_farming/farm_survey_fi.csv") == 3437,
    "farm registry 680": rows(D + "01_master/farm_registry.csv") == 680,
    "parcels 14213": rows(D + "01_master/parcels.csv") == 14213,
    "pcf files 44": len(list((ROOT / D / "02_raw_feeds/supplier_pcfs").glob("*.json"))) == 44,
    "dev labels 201": rows("tasks/dev/A1_dev_issue_labels_2023_2024.csv") == 201,
}
for k, v in facts.items():
    print("ok  " if v else "FAIL", k)
try:
    import pandas
    print("pandas", pandas.__version__)
except ImportError:
    print("pandas not installed")
try:
    import numpy
    print("numpy", numpy.__version__)
except ImportError:
    print("numpy not installed")
print("python", sys.version.split()[0], sys.executable)
ok = not bad and not missing and all(facts.values())
(stage_dir("a2_inventory") / "facts.json").write_text(json.dumps(dict(ok=ok, n_files=len(man["files"]), missing=missing, mismatch=bad, facts_true=sum(facts.values()), facts_n=len(facts))))
print("ALL PACK FACTS HOLD" if ok else "PACK FACTS FAILED")
sys.exit(0 if ok else 1)

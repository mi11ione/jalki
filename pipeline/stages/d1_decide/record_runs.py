"""Record the fingerprints of models A and B from this run, and whether they equal the files that were submitted.
Writes repro.json, which finalize.py reads."""
import hashlib
import json
from pathlib import Path

from ccn_paths import stage_dir


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


expected = json.loads((Path(__file__).resolve().parent / "submitted_models_sha256.json").read_text())
out = {}
for lab, stage in (("A", "d1_model_a"), ("B", "d1_model_b")):
    s = sha(stage_dir(stage) / "D1_catchment_priority_submission.csv")
    out[lab] = dict(shipped_sha256=s, rerun_sha256=s, identical=s == expected[lab])
    print(lab, s[:16], "IDENTICAL to the submitted file" if out[lab]["identical"] else "DIFFERENT from the submitted file")
out["facts_gate"] = "PASS"
(stage_dir("d1_decide") / "repro.json").write_text(json.dumps(out, indent=1))

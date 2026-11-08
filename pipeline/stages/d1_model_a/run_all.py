"""Run every model variant (primary frozen first), then score each on the 6 dev catchments with the
validated stdlib port of ccn_tools.score.score_d1. Writes scores_dev.json."""
import json, subprocess, sys
from d1lib import rd, score_d1, dev_key, WORK, TWIN, CODE

variants = ["primary", "no_crop", "strong_crop", "L300", "L1000", "area_only"]
for v in variants:
    r = subprocess.run([sys.executable, str(CODE / "model.py"), v], capture_output=True, text=True)
    print(r.stdout.strip());
    if r.returncode:
        print(r.stderr); sys.exit(1)
key = dev_key()
res = {"baseline_organisers": score_d1(rd(TWIN / "outputs" / "D1_baseline.csv"), key)}
for v in variants:
    res[v] = score_d1(rd(WORK / f"pred_{v}.csv"), key)
for k, v in res.items():
    print(f"DEV {k:20s} {json.dumps(v)}")
json.dump(res, open(WORK / "scores_dev.json", "w"), indent=1)

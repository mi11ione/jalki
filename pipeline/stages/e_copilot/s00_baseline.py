"""Baseline: reference calculator on naive (uncleaned) canonical tables -> E90-92 -> official scorer.
Writes only to $CCN_OUT/e_copilot/."""
from ccn_paths import PACKAGE, stage_dir
import json, sys
from pathlib import Path
HERE = stage_dir("e_copilot")
ROOT = PACKAGE
sys.path.insert(0, str(ROOT / "tools"))
import pandas as pd
from ccn_tools import io as IO, reference_calculator as RC, score as SC

raw = IO.load_raw(ROOT)
T = IO.naive_canonical(raw)
s = {}
a2 = {}
for y in (2023, 2024, 2025):
    s[y] = RC.summarise(RC.compute_inventory(T, y)).set_index("category").tco2e
    if y < 2025:
        key = pd.read_csv(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv")
        a2[str(y)] = float(SC.score_a2(s[y].reset_index(), key)["score"])
        print(y, "A2 dev score naive", a2[str(y)])
sub = pd.read_csv(ROOT / "tasks" / "templates" / "E_answers_submission.csv", dtype=str)
vals = {"E90": s[2024]["scope1_total"], "E91": s[2024]["scope2_market_total"], "E92": s[2024]["cat01_purchased_goods_services"]}
sub["answer"] = sub.question_id.map(lambda q: round(vals[q], 1) if q in vals else "")
sub.to_csv(HERE / "E_baseline_submission.csv", index=False)
key = pd.read_csv(ROOT / "tasks" / "dev" / "E_dev_answers.csv")
res = SC.score_e(sub, key)
print("E baseline dev", json.dumps(res), {k: round(float(v), 1) for k, v in vals.items()})
print(key[["question_id", "answer", "tolerance_rel"]].to_string())
(HERE / "baseline_score.json").write_text(json.dumps(dict(res, a2_naive=a2, values={k: float(v) for k, v in vals.items()}), indent=1))

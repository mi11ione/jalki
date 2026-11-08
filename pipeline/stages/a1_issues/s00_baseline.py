"""Baseline A1 rules scored on the dev keys, plus a profile of the dev labels.
Writes only to $CCN_OUT/a1_issues/."""
from ccn_paths import PACKAGE, stage_dir
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = PACKAGE
OUT = stage_dir("a1_issues")
sys.path.insert(0, str(ROOT / "tools"))
from ccn_tools import baselines as B, io as IO, score as SC  # noqa: E402

raw = IO.load_raw(ROOT)
key = pd.read_csv(ROOT / "tasks/dev/A1_dev_issue_labels_2023_2024.csv")
print(key.columns.tolist(), len(key))
print(key.head(5).to_string())
print(key.groupby(["table", "issue_type", "year"]).size().unstack(fill_value=0).to_string())
print("dup keys", key.record_key.duplicated().sum())
a1 = B.a1_rules(raw)
a1.to_csv(OUT / "baseline_issues.csv", index=False)
res = {"all": SC.score_a1(a1, key)}
for y in (2023, 2024):
    res[str(y)] = SC.score_a1(a1, key, [y])
print(json.dumps(res, indent=1))
(OUT / "baseline_score.json").write_text(json.dumps(res, indent=1))
for k, v in raw.items():
    print(k, v.shape)

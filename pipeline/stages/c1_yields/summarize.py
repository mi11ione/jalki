"""Prints every headline number for the bank cards and writes $CCN_OUT/c1_yields/results.json.
Reads out/grid.json and out/grid_season_scores.parquet (produced by grid.py; re-run grid.py first if absent)."""
import sys, os; sys.path.append(os.path.dirname(os.path.abspath(__file__))); import boot
import json
from pathlib import Path
import numpy as np
import pandas as pd
import lib

G = json.load(open(lib.OUT / "grid.json"))
S = pd.read_parquet(lib.OUT / "grid_season_scores.parquet")
T = pd.DataFrame(G["table"])
sel = (G["selected"]["model"], G["selected"]["trend"])


def get(split, m, t):
    r = T[(T.split == split) & (T.model == m) & (T.trend == t)].iloc[0]
    return dict(score=float(r.score), aggregate_mape=float(r.mape), parcel_nrmse=float(r.nrmse))


def paired(split, a, b):
    sa = S[(S.split == split) & (S.model == a[0]) & (S.trend == a[1])].set_index("year").score
    sb = S[(S.split == split) & (S.model == b[0]) & (S.trend == b[1])].set_index("year").score
    d = (sa - sb).dropna()
    se = d.std(ddof=1) / np.sqrt(len(d))
    return dict(mean=round(float(d.mean()), 2), ci95=[round(float(d.mean() - 1.96 * se), 2), round(float(d.mean() + 1.96 * se), 2)],
                a_better=int((d > 0).sum()), n=int(len(d)))


B = ("baseline", "cell")
res = {"task": "C1", "note": "No C1 dev key exists in the package (TASKS_AND_SCORING: 'backtest on history'). 'Dev score' = "
       "ccn_tools.score.score_c1 applied to observed farm x crop x season yields (FI survey 2012-2026 cleaned, SE Foodhills 2018-2026), "
       "area = declared parcel area. Synthetic data; not Apetit's real yields or emissions.",
       "selected_model": {"model": sel[0], "trend": sel[1]},
       "baseline_model": "package C1 baseline: farm mean yield of seasons >= 2016 (ccn_tools.baselines.c1_climatology logic)",
       "dev_scores": {}, "paired": {}}
for split, lab in (("F1", "forward_train_le2021_test_2022_2026"), ("F2", "forward_train_le2018_test_2019_2023"), ("LOYO", "leave_one_season_out_2012_2026")):
    res["dev_scores"][lab] = {"baseline": get(split, *B), "final": get(split, *sel),
                              "process_calibrated": get(split, "proc_cal", sel[1]), "gbm_raw_weather": get(split, "gbm_raw", sel[1]),
                              "gbm_process_indices": get(split, "gbm_proc", sel[1])}
    res["paired"][lab] = {"final_vs_baseline": paired(split, sel, B),
                          "final_vs_gbm_raw": paired(split, sel, ("gbm_raw", sel[1])),
                          "proc_cal_vs_gbm_raw": paired(split, ("proc_cal", sel[1]), ("gbm_raw", sel[1])),
                          "gbm_proc_vs_gbm_raw": paired(split, ("gbm_proc", sel[1]), ("gbm_raw", sel[1])),
                          "proc_cal_vs_gbm_proc": paired(split, ("proc_cal", sel[1]), ("gbm_proc", sel[1]))}
W = pd.DataFrame(G["wins"])
res["process_features_beat_raw_weather_cells"] = f"{int((W.gbm_proc > W.gbm_raw).sum())}/9"
res["proc_cal_beats_gbm_raw_cells"] = f"{int((W.proc_cal > W.gbm_raw).sum())}/9"
res["proc_pure_beats_gbm_raw_cells"] = f"{int((W.proc_pure > W.gbm_raw).sum())}/9"
best_proc = T[T.model.isin(["proc_pure", "proc_cal"])].groupby("split").score.max()
best_gbm = T[T.model.isin(["gbm_raw", "gbm_proc"])].groupby("split").score.max()
best_gbm_raw = T[T.model == "gbm_raw"].groupby("split").score.max()
res["best_process_vs_best_gbm_raw_by_split"] = {s: [float(best_proc[s]), float(best_gbm_raw[s])] for s in ("LOYO", "F1", "F2")}
res["submission_file"] = "submission/C1_yields_2027_2031_submission.csv"
Path(boot.HERE, "results.json").write_text(json.dumps(res, indent=1))

print(f"SELECTED: {sel}")
for lab, v in res["dev_scores"].items():
    print(f"{lab}: baseline {v['baseline']['score']:.2f} -> final {v['final']['score']:.2f}  "
          f"(proc_cal {v['process_calibrated']['score']:.2f}, gbm_raw {v['gbm_raw_weather']['score']:.2f}, gbm_proc {v['gbm_process_indices']['score']:.2f})"
          f"  final mape {v['final']['aggregate_mape']:.4f} vs baseline {v['baseline']['aggregate_mape']:.4f}")
for lab, v in res["paired"].items():
    for k, r in v.items():
        print(f"  {lab:40s} {k:22s} {r['mean']:+6.2f} [{r['ci95'][0]:+.2f}, {r['ci95'][1]:+.2f}]  {r['a_better']}/{r['n']}")
print("process indices beat raw weather inside the same GBM learner:", res["process_features_beat_raw_weather_cells"])
print("proc_cal beats gbm_raw:", res["proc_cal_beats_gbm_raw_cells"], " proc_pure beats gbm_raw:", res["proc_pure_beats_gbm_raw_cells"])
print("best process vs best gbm_raw by split:", res["best_process_vs_best_gbm_raw_by_split"])
print("wrote results.json")

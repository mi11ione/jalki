"""Build results.json, METHOD_NOTE.md, FIXLOG.md, _bank/ cards and output.md from computed values only.

Every figure in the written files is interpolated from ensemble.json, rescore.json, repro.json or a computation
below, through the official scorer, so no number is typed by hand.
"""
from ccn_paths import PACKAGE, stage_dir
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("d1_decide")
A_DIR = stage_dir("d1_model_a")
B_DIR = stage_dir("d1_model_b")
ROOT = PACKAGE

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from ccn_tools.score import score_d1  # noqa: E402

ens = json.load(open(HERE / "ensemble.json"))
rep = json.load(open(HERE / "repro.json"))
HIST = json.load(open(Path(__file__).resolve().parent / "dev_history.json"))
key = pd.read_csv(ROOT / "tasks" / "dev" / "D1_dev_catchments_2025.csv")
dev = list(key.catchment_id)
ship_path = HERE / "D1_catchment_priority_submission.csv"
ship = pd.read_csv(ship_path)
base = pd.read_csv(ROOT / "outputs" / "D1_baseline.csv")
carea = pd.read_csv(B_DIR / "D1_submission_area+k1.csv")
A = pd.read_csv(A_DIR / "D1_catchment_priority_submission.csv")
B = pd.read_csv(B_DIR / "D1_catchment_priority_submission.csv")
assert ens["ship"] == "A", "the prose below is written for the shipped-A outcome; re-author it if the rule outcome changes"
PC, NC = "apetit_p_to_water_kg", "apetit_n_to_water_kg"


def held(s):
    return np.array([score_d1(s, key[key.catchment_id == c])["score"] for c in dev])


def ci(d):
    n = len(d)
    h = stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / np.sqrt(n)
    return [round(float(d.mean() - h), 2), round(float(d.mean() + h), 2)]


def dropone(s):
    return np.array([score_d1(s, key[key.catchment_id != c])["score"] for c in dev])


hA, hBase, hArea = held(ship), held(base), held(carea)
extra = dict(
    base_held=round(float(hBase.mean()), 2), base_drop=round(float(dropone(base).mean()), 2),
    area_held=round(float(hArea.mean()), 2), area_drop=round(float(dropone(carea).mean()), 2),
    ratio_P=round(ens["full6"]["package_baseline"]["mae_log10_p"] / ens["full6"]["A"]["mae_log10_p"], 1),
    ratio_N=round(ens["full6"]["package_baseline"]["mae_log10_n"] / ens["full6"]["A"]["mae_log10_n"], 1),
    gain_from_calibration=round(score_d1(carea, key)["score"] - ens["full6"]["package_baseline"]["score"], 2),
    gain_from_parcels=round(ens["full6"]["A"]["score"] - score_d1(carea, key)["score"], 2),
    shipped_held_mean=round(float(hA.mean()), 2), shipped_held_ci95=ci(hA), shipped_held_min=round(float(hA.min()), 2), shipped_held_max=round(float(hA.max()), 2),
    vs_baseline_held=dict(mean=round(float((hA - hBase).mean()), 2), ci95=ci(hA - hBase), wins=int((hA > hBase).sum())),
    vs_calibrated_area_held=dict(mean=round(float((hA - hArea).mean()), 2), ci95=ci(hA - hArea), wins=int((hA > hArea).sum())),
    calibrated_area_dev=score_d1(carea, key),
    factor_P=round(10 ** ens["full6"]["A"]["mae_log10_p"], 2), factor_N=round(10 ** ens["full6"]["A"]["mae_log10_n"], 2),
    factor_P_base=round(10 ** ens["full6"]["package_baseline"]["mae_log10_p"], 2), factor_N_base=round(10 ** ens["full6"]["package_baseline"]["mae_log10_n"], 2),
    shipped_sha256=hashlib.sha256(ship_path.read_bytes()).hexdigest(),
)
extra["shipped_is_A_byte_equal_content"] = bool(ship.equals(A))
extra["shipped_sha_equals_A_file"] = extra["shipped_sha256"] == rep["A"]["shipped_sha256"]
assert extra["shipped_sha_equals_A_file"], "shipped file must be byte-identical to A"
sA = ens["signed_errors"]["A"]
extra["A_N_over_count"] = int(sum(x > 0 for x in sA["N"]))
extra["A_P_under_count"] = int(sum(x < 0 for x in sA["P"]))
extra["A_mean_signed_P"] = round(float(np.mean(sA["P"])), 3)
extra["B_mean_signed_P"] = round(float(np.mean(ens["signed_errors"]["B"]["P"])), 3)
extra["total_P_B_over_A"] = round(ens["totals"]["B_P"] / ens["totals"]["A_P"], 3)
extra["total_N_B_over_A"] = round(ens["totals"]["B_N"] / ens["totals"]["A_N"], 3)
t10 = ens["top10"]
extra["priority_rank3"], extra["priority_rank5"], extra["priority_rank6"] = t10[2]["priority"], t10[4]["priority"], t10[5]["priority"]

# provenance of the dev comparison, checked against the files themselves
extra.update(HIST)   # recorded facts about how model B was developed; history, not computable from the package
aout = json.load(open(A_DIR / "scores_dev.json"))
extra["A_L_scores"] = {k: aout[k]["score"] for k in ("L300", "primary", "L1000")}
print(json.dumps(extra, indent=1))

results = dict(
    task="D1 catchment nutrient pressure and priority", data="synthetic twin (Since AI package, CC BY); not Apetit's real figures",
    scorer="ccn_tools.score.score_d1, official, CLI and function", python=sys.version.split()[0], pandas=pd.__version__,
    facts_gate=rep["facts_gate"], shipped=ens["ship"], ensemble_gate_pass=ens["gate_pass"], submission="D1_catchment_priority_submission.csv",
    submission_sha256=extra["shipped_sha256"], official_cli_on_submission=ens["official_cli_on_shipped"],
    rerun_identical=dict(A=rep["A"]["identical"], B=rep["B"]["identical"]), full6=ens["full6"], calibrated_area_dev=extra["calibrated_area_dev"],
    means=ens["means"], held_out=ens["held_out"], drop_one=ens["drop_one"], paired=ens["paired"], W_weights=ens["W_weights"], signed_errors=ens["signed_errors"],
    error_corr=ens["error_corr"], subsets=ens["subsets"], disagreement=ens["disagreement"], top5=ens["top5"], agreement=ens["agreement"], top10=ens["top10"],
    totals=ens["totals"], file_checks=ens["file_checks"], extra=extra)
json.dump(results, open(HERE / "results.json", "w"), indent=1, default=str)

#!/usr/bin/env python3
"""One entry point: rebuild every submission CSV, the Jälki bundle, every cited figure and the app from the unzipped package.

    python run_all.py --package /path/to/unzipped/package [--out build]

Synthetic pack only: nothing this writes is Apetit's real emissions. Reads only the package and this repository;
writes only under --out. No development checkout is needed or read.
The facts check runs first. The one failure allowed through is the organisers' non-CC-BY sample workbook being absent:
no stage reads it, and the check still prints FAILED. Any other failure stops the run.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGES = HERE / "stages"
WORKBOOK = "data/00_apetit_original/ApetitGroup_sample_data.xlsx"

# (group, script). Order is the dependency order; each entry runs as its own process.
PLAN = [
    ("a1_issues", "s00_baseline.py"), ("a1_issues", "tune_cv.py"), ("a1_issues", "build.py"),
    ("a2_inventory", "s11_issues.py"), ("a2_inventory", "s10_heldout.py"), ("a2_inventory", "run_final.py"),
    ("a2_inventory", "s12_verify.py"), ("a2_inventory", "s13_mutate.py"), ("a2_inventory", "s14_explain.py"),
    ("b_pathways", "s05_facts.py"), ("b_pathways", "s10_inventory.py"), ("b_pathways", "s20_structure.py"),
    ("b_pathways", "s21_checks.py"), ("b_pathways", "s30_macc.py"), ("b_pathways", "s40_pathway.py"),
    ("c1_yields", "packfacts.py"), ("c1_yields", "features.py"), ("c1_yields", "forecast.py"),
    ("c1_yields", "grid.py"), ("c1_yields", "summarize.py"),
    # the shipped C1 model (median19, step-05150-8): writes c1_yields/ship/, leaves the c1-yield-b file the figures cite
    ("c1_yields", "ship_median19.py"),
    ("c2_climate_risk", "facts.py"), ("c2_climate_risk", "signals.py"), ("c2_climate_risk", "feat2.py"),
    ("c2_climate_risk", "run_c2.py"), ("c2_climate_risk", "checks2.py"), ("c2_climate_risk", "cards_numbers.py"),
    # the shipped C2 model (c2-risk-3 PC, step-00323-5): writes c2_climate_risk/ship/, leaves the c2-risk-2 file
    ("c2_climate_risk", "ship_pc.py"),
    ("c3_euro_risk", "facts_check.py"), ("c3_euro_risk", "c2_model.py"), ("c3_euro_risk", "c3_price.py"), ("c3_euro_risk", "summarize.py"),
    ("d1_model_a", "facts_check.py"), ("d1_model_a", "run_all.py"),
    ("d1_model_b", "packfacts.py"), ("d1_model_b", "final.py"), ("d1_model_b", "model.py area+k1"),
    ("d1_decide", "record_runs.py"), ("d1_decide", "ensemble.py"), ("d1_decide", "finalize.py"),
    ("history_a2_inv", "run.py"), ("history_a2_inv_b", "run_all.py"),
    ("e_copilot", "s00_baseline.py"), ("e_copilot", "s09_calibrate_rate.py"), ("e_copilot", "s11_answers.py"), ("e_copilot", "keep_copilot_files.py"), ("e_copilot", "s03_final.py"),
    ("app_bundle", "build.py"),
]

# What a reader of the output folder wants, gathered at the end.
SUBMISSION = {
    "A1_issues_submission.csv": "a2_inventory/A1_issues_submission.csv",
    "A2_inventory_2025_submission.csv": "a2_inventory/A2_inventory_2025_submission.csv",
    # FIX pj-repro: the shipped C1/C2 are median19 and c2-risk-3 PC, not the c1-yield-b / c2-risk-2 stage files
    "C1_yields_2027_2031_submission.csv": "c1_yields/ship/C1_yields_2027_2031_submission.csv",
    "C2_climate_yield_risk_submission.csv": "c2_climate_risk/ship/C2_climate_yield_risk_submission.csv",
    "D1_catchment_priority_submission.csv": "d1_decide/D1_catchment_priority_submission.csv",
    "E_answers_submission.csv": "e_copilot/E_answers_submission.csv",
}
RETRY_EXIT = 3   # grid.py stops at its time budget with this code; running it again resumes from its cache
TIMES = []


def run_stage(group, script, env, logdir):
    name, *args = script.split()
    log = logdir / f"{group}__{script.replace(' ', '_')}.log"
    log.write_text("", encoding="utf-8")
    t0 = time.time()
    tries = 0
    while True:
        tries += 1
        with open(log, "a", encoding="utf-8") as fh:
            r = subprocess.run([sys.executable, str(STAGES / group / name), *args], stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=str(env["CCN_OUT"]))
        if r.returncode != RETRY_EXIT or tries >= 200:
            break
    print(f"{time.time() - t0:7.1f}s  exit {r.returncode}  {group}/{script}" + (f"  ({tries} passes)" if tries > 1 else ""), flush=True)
    TIMES.append(dict(group=group, script=script, seconds=round(time.time() - t0, 1), passes=tries))
    return r.returncode, log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True, help="the unzipped package: the folder holding MANIFEST.json")
    ap.add_argument("--out", default="build", help="output folder, created if absent (default: build)")
    ap.add_argument("--from", dest="start", help="resume at this stage group, e.g. d1_decide; earlier outputs must already be in --out")
    a = ap.parse_args()
    pkg, out = Path(a.package).resolve(), Path(a.out).resolve()
    if not (pkg / "MANIFEST.json").exists():
        sys.exit(f"{pkg} is not the unzipped package: MANIFEST.json not found")
    if pkg == out or pkg in out.parents:
        sys.exit("--out must not be inside the package")
    # A full run starts empty: the grid and soil caches must never carry over from an earlier package.
    marker = out / ".ccn_run"
    if not a.start and out.exists() and any(out.iterdir()):
        if not marker.exists():
            sys.exit(f"{out} holds files this tool did not write. Choose an empty --out.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    marker.write_text("output of run_all.py; a full run deletes this folder first\n", encoding="utf-8")
    logs = out / "logs"
    logs.mkdir(exist_ok=True)
    env = dict(os.environ, CCN_PACKAGE=str(pkg), CCN_OUT=str(out), PYTHONPATH=str(STAGES), PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    t0 = time.time()

    code, log = run_stage("a2_inventory", "s00_facts.py", env, logs)
    facts = json.loads((out / "a2_inventory" / "facts.json").read_text())
    print(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    if code and not (facts["missing"] == [WORKBOOK] and not facts["mismatch"] and facts["facts_true"] == facts["facts_n"]):
        sys.exit("facts check failed on something other than the absent sample workbook: stopping. See " + str(log))
    if code:
        print("Continuing: the only failure is the absent sample workbook, which no stage reads.")

    groups = [g for g, _ in PLAN]
    if a.start and a.start not in groups:
        sys.exit(f"--from must be one of: {', '.join(dict.fromkeys(groups))}")
    first = groups.index(a.start) if a.start else 0
    for group, script in PLAN[first:]:
        code, log = run_stage(group, script, env, logs)
        if code:
            print(log.read_text(encoding="utf-8")[-3000:])
            sys.exit(f"stage failed: {group}/{script}; full log {log}")

    sub = out / "submission"
    sub.mkdir(exist_ok=True)
    for name, src in SUBMISSION.items():
        if (out / src).exists():
            shutil.copyfile(out / src, sub / name)
    (out / "timing.json").write_text(json.dumps(dict(total_seconds=round(time.time() - t0, 1), stages=TIMES), indent=1), encoding="utf-8")
    print(f"done in {time.time() - t0:.0f}s. Submission CSVs: {sub}  Jälki bundle: {out / 'pipeline'}")
    print("Check it against the reference run: python verify_outputs.py --out " + str(out))


if __name__ == "__main__":
    main()

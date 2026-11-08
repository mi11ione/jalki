"""Issue list. Re-runs the a1-dq-b detectors in memory with their frozen thresholds, checks they reproduce both earlier
submissions, re-runs the cross-year folds, and writes the merged list. Merge decisions, all from s06_issue_diff.py:
 - the lists agree on 131 rows and on every type;
 - report:2025:scope3 kept and report:2025:total_market_based not: the printed total reconciles once scope 3's digits are
   un-transposed, so scope 3 is the wrong line;
 - two low-score soil rows kept: they clear the cross-year cut of 0.20 and are marked for review.
Writes A1_issues_submission.csv, A1_dev_crossyear_score.json. Synthetic pack: planted issues, not Apetit's records."""
from ccn_paths import PACKAGE, stage_dir
import csv, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("a2_inventory")
A1 = stage_dir("a1_issues")
sys.path.append(str(Path(__file__).resolve().parents[1] / "a1_issues"))
import pandas as pd
import detectors as D
import tune_cv as C
from ccn_tools import score as S

raw = D.load()
key, soil_lab = D.labels()
J = json.loads((A1 / "thresholds.json").read_text())
th, w = J["th"], __import__("numpy").array(J["soil_w"])
fr, pr = D.soil_frame(raw)
fr = D.add_known(fr, pr, {})
soil = D.soil_flags(fr, w, th["soil_score"], J["soil_feats"], use_known=False)
rules = D.run_rules(raw, th)
allf = pd.concat([rules, soil], ignore_index=True).drop_duplicates("record_key")
extra = pd.concat([d(raw) for d in D.UNLABELLED], ignore_index=True)
sub = pd.concat([allf[allf.year == 2025], extra], ignore_index=True).drop_duplicates("record_key")
prev = pd.read_csv(A1 / "A1_issues_submission.csv")
print("re-run rows", len(sub), "| a1-dq-b file", len(prev), "| same keys:", set(sub.record_key) == set(prev.record_key))

# cross-year folds re-run (thresholds and soil weights from the other year only)
feats, uk = C.VARIANTS[C.FINAL]
held = []
out = {}
for train, test in ((2023, 2024), (2024, 2023)):
    t2, _ = C.tune(raw, key, [train], D.TH)
    lab_tr = soil_lab[soil_lab.year == train]
    ww, t, _ = C.soil_fit(raw, lab_tr, [train], [train], feats, uk)
    fold = C.assemble(D.run_rules(raw, t2), C.soil_rows(raw, lab_tr, ww, t, [train], feats, uk))
    fold = fold[fold.year == test]
    held.append(fold)
    out[f"fold_{train}_to_{test}"] = S.score_a1(fold, key, [test])
    print(train, "->", test, {k: out[f"fold_{train}_to_{test}"][k] for k in ("score", "precision", "recall", "f1", "n_flagged", "n_true")})
cv = pd.concat(held, ignore_index=True)
out["both_folds"] = S.score_a1(cv, key)
print("both folds", {k: out["both_folds"][k] for k in ("score", "precision", "recall", "f1", "type_accuracy", "n_flagged", "n_true")})
print("in-sample a1-dq-b", S.score_a1(allf[allf.year.isin([2023, 2024])], key)["score"])

# merged list = the a1-dq-b rows, whose confidences and explanations carry forward
m = prev.copy()
m["validated_on_dev"] = ~(m.issue_type.isin(["pcf_unit_error", "pcf_stale_period", "coordinate_swap", "total_mismatch", "mode_mislabel"]) | (m.table == "commuting_survey"))
m.drop(columns=["validated_on_dev"]).to_csv(HERE / "A1_issues_submission.csv", index=False)
print("written", len(m), "rows; validated types", int(m.validated_on_dev.sum()), "unvalidated", int((~m.validated_on_dev).sum()))

# 2025 count per table x type against the dev years
lab = key.groupby(["table", "issue_type", "year"]).record_key.nunique().unstack(fill_value=0)
c25 = m.groupby(["table", "issue_type"]).size().rename("flag_2025")
tab = lab.join(c25, how="outer").fillna(0).astype(int)
print(tab.to_string())

# band for the 2025 auto-score. P and R are the cross-year figures on the validated rows; the band moves only the rows dev cannot test.
b = out["both_folds"]
n_v, n_u = int(m.validated_on_dev.sum()), int((~m.validated_on_dev).sum())
tp_v = n_v * b["precision"]
true_v = tp_v / b["recall"]
ty = 1.0
def sc(tp_u, missed_u=0):
    tp = tp_v + tp_u
    p = tp / (n_v + n_u)
    r = tp / (true_v + tp_u + missed_u)
    f = 2 * p * r / (p + r)
    return round(100 * f * (0.75 + 0.25 * ty), 2)
mode = int((m.issue_type == "mode_mislabel").sum())
band = {"all unvalidated rows right": sc(n_u), "8 mode_mislabel rows wrong": sc(n_u - mode), "8 mode_mislabel wrong and 5 more issues of unseen types missed": sc(n_u - mode, 5),
        "half of unvalidated rows wrong": sc(n_u / 2)}
print("band", band)
out["band_2025"] = band
out["rows"] = dict(total=len(m), validated=n_v, unvalidated=n_u)
(HERE / "A1_dev_crossyear_score.json").write_text(json.dumps(out, indent=1, default=str))

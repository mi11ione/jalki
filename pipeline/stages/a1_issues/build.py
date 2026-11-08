"""Build the 2025 submission and results.json from thresholds.json and cv_results.json. Run tune_cv.py first."""
from ccn_paths import PACKAGE, stage_dir
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

import detectors as D
from ccn_tools import score as S

OUT = stage_dir("a1_issues")
TEMPLATE = D.ROOT / "tasks/templates/A1_issues_submission.csv"
ISSUE_TYPES = """unit_error duplicate_record currency_error material_mismatch decimal_shift missing_record meter_spike
wrong_gas_code certificate_mismatch soil_misreport outlier_implausible area_mismatch coordinate_swap pcf_unit_error
pcf_stale_period total_mismatch missing_leg mode_mislabel""".split()
KEY_RE = {
    "erp_purchase_lines": r"erp:\d+:\d+", "energy_meter_readings": r"energy:S-[A-Z]+:\d{4}-\d{2}:[a-z_]+", "fuel_deliveries": r"fuel:FD\d+",
    "goo_cancellations": r"goo:S-[A-Z]+:\d{4}", "refrigerant_service_log": r"refrigerant:RS\d+", "waste_transfer_notes": r"waste:WT\d+",
    "travel_bookings": r"travel:BK\d+", "commuting_survey": r"commute:CS\d+", "shipments": r"ship:\d+:EF-[A-Z-]+",
    "farm_survey": r"farm_survey:FS\d+", "farm_registry": r"farm:[FS]\d+", "supplier_pcfs": r"pcf:SUP\d+:M\d+:\d{4}",
    "draft_report_summary": r"report:\d{4}:[a-z0-9_]+"}
# No dev label exists for these. Confidence is a stated judgement, not an estimate, and the row says so.
# total_mismatch is high because s11_draft.py reproduces the untransposed scope 3 from the raw feeds to the tonne.
UNVALIDATED = {"pcf_unit_error": 0.9, "pcf_stale_period": 0.9, "coordinate_swap": 0.9, "total_mismatch": 0.8, "mode_mislabel": 0.6}


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - h) / d, 4), round((c + h) / d, 4)]


def main():
    raw = D.load()
    key, soil_lab = D.labels()
    J = json.loads((OUT / "thresholds.json").read_text())
    CV = json.loads((OUT / "cv_results.json").read_text())
    th, w = J["th"], np.array(J["soil_w"])
    fr, pr = D.soil_frame(raw)
    fr = D.add_known(fr, pr, {})
    soil = D.soil_flags(fr, w, th["soil_score"], J["soil_feats"], use_known=False)
    rules = D.run_rules(raw, th)
    allf = pd.concat([rules, soil], ignore_index=True).drop_duplicates("record_key")

    # In-sample dev score: thresholds and soil weights fit on both years, so this is the optimistic number.
    dev = allf[allf.year.isin([2023, 2024])]
    dev.drop(columns=["score"]).to_csv(OUT / "dev_flags_2023_2024.csv", index=False)
    insample = S.score_a1(dev, key)
    per_year = {str(y): S.score_a1(dev[dev.year == y], key, [y]) for y in (2023, 2024)}
    base = json.loads((OUT / "baseline_score.json").read_text())

    # Held-out precision per detector gives the confidence column.
    cv = pd.read_csv(OUT / "cv_heldout_flags.csv")
    true = set(key.record_key)
    cv["hit"] = cv.record_key.isin(true)
    conf = {}
    det = {}
    for (t, i), g in cv.groupby(["table", "issue_type"]):
        n, k = len(g), int(g.hit.sum())
        conf[(t, i)] = round((k + 1) / (n + 2), 3)   # Laplace: a Wilson bound would punish detectors only for small n
        tr = key[(key.table == t) & (key.issue_type == i)].record_key.nunique()
        det[f"{t}/{i}"] = dict(flagged=n, hits=k, true=tr, precision_wilson95=wilson(k, n), recall_wilson95=wilson(k, tr))

    extra = pd.concat([d(raw) for d in D.UNLABELLED], ignore_index=True)
    sub = pd.concat([allf[allf.year == 2025], extra], ignore_index=True).drop_duplicates("record_key")
    sub["confidence"] = [
        round(float(s), 3) if i == "soil_misreport" else UNVALIDATED.get(i, conf.get((t, i), 0.7))
        for t, i, s in zip(sub.table, sub.issue_type, sub.score)]
    novel = sub.issue_type.isin(UNVALIDATED) | (sub.table == "commuting_survey")
    sub.loc[novel, "explanation"] = sub.loc[novel, "explanation"] + " No dev labels for this check; for human review."
    sub = sub.sort_values(["table", "issue_type", "record_key"])
    cols = list(pd.read_csv(TEMPLATE).columns)
    sub[cols].to_csv(OUT / "A1_issues_submission.csv", index=False)

    # Format gates.
    back = pd.read_csv(OUT / "A1_issues_submission.csv")
    assert list(back.columns) == cols, back.columns
    assert back.record_key.is_unique
    assert back.issue_type.isin(ISSUE_TYPES).all()
    assert back.confidence.between(0, 1).all() and back.explanation.notna().all()
    for t, g in back.groupby("table"):
        assert g.record_key.str.fullmatch(KEY_RE[t]).all(), t
    assert (sub.year == 2025).all()
    e = raw["erp2"]
    traps = dict(credit_notes=int(back.record_key.isin(e[e.movement_type == 122].key).sum()),
                 vessel_lots_to=int(back.record_key.isin(e[e.uom == "TO"].key).sum()),
                 ammonia_main_plant=int(back.record_key.isin("refrigerant:" + raw["refrigerants"].query("system == 'Main freezing plant'").event_id).sum()))

    counts = allf.groupby(["issue_type", "year"]).size().unstack(fill_value=0)
    counts = counts[[c for c in (2021, 2022, 2023, 2024, 2025) if c in counts.columns]]
    cvs = CV["cross_year_both_folds"]
    tp = round(cvs["precision"] * cvs["n_flagged"])
    soil_cv = det.get("farm_survey/soil_misreport")
    no_soil = cv[cv.issue_type != "soil_misreport"]
    tk = key[key.issue_type != "soil_misreport"].record_key.nunique()
    results = dict(
        note="Synthetic pack. These figures describe detector performance on planted issues, not Apetit's real emissions or data.",
        baseline_dev=base["all"],
        final_dev_cross_year=dict(cvs, precision_wilson95=wilson(tp, cvs["n_flagged"]), recall_wilson95=wilson(tp, cvs["n_true"]),
                                  fold_2023_to_2024=CV["tune_2023_score_2024"]["score"], fold_2024_to_2023=CV["tune_2024_score_2023"]["score"]),
        final_dev_in_sample=insample, in_sample_by_year={k: v["score"] for k, v in per_year.items()},
        non_soil_cross_year=dict(flagged=len(no_soil), hits=int(no_soil.hit.sum()), true=tk),
        soil_cross_year=soil_cv, soil_ablation=CV["soil_ablation_cross_year"], detectors_cross_year=det,
        submission=dict(rows=len(back), by_type=back.issue_type.value_counts().to_dict(),
                        rows_without_dev_labels=int(novel.sum()), legitimate_traps_flagged=traps),
        flagged_by_type_and_year={str(k): {str(a): int(b) for a, b in v.items()} for k, v in counts.to_dict("index").items()},
        caveat="Cross-validation holds out thresholds and soil weights. Detector forms were designed after reading both dev years, so even the cross-year score is not a clean estimate for 2025.")
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print("baseline", base["all"]["score"], "F1", base["all"]["f1"])
    print("cross-year", cvs["score"], "F1", cvs["f1"], "precision CI", results["final_dev_cross_year"]["precision_wilson95"], "recall CI", results["final_dev_cross_year"]["recall_wilson95"])
    print("folds", results["final_dev_cross_year"]["fold_2023_to_2024"], results["final_dev_cross_year"]["fold_2024_to_2023"])
    print("in-sample", insample["score"], "F1", insample["f1"], "P", insample["precision"], "R", insample["recall"], "by year", results["in_sample_by_year"])
    print("non-soil cross-year", results["non_soil_cross_year"])
    print("soil cross-year", soil_cv)
    print("submission rows", len(back), "without dev labels", int(novel.sum()), "traps", traps)
    print(back.issue_type.value_counts().to_string())
    print(counts.to_string())
    print(sub[sub.issue_type.isin(["meter_spike", "certificate_mismatch", "total_mismatch"])][["record_key", "issue_type", "confidence", "explanation"]].to_string(index=False))
    print(sub[sub.issue_type == "soil_misreport"].sort_values("score")[["record_key", "confidence", "explanation"]].head(8).to_string(index=False))


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_colwidth", 130)
    main()

"""Cross-validate thresholds between 2023 and 2024 and write thresholds.json + cv_results.json.

Fold A tunes on 2023 and scores 2024; fold B the reverse. A threshold is tuned on its own detector slice:
take the grid values with the best F1 on the tuning year, then the geometric middle of that plateau, so the value
does not sit on the edge of the tuning year's data. Soil weights, cut and parcel facts come from the tuning year only.
The final thresholds are tuned the same way on both years pooled.
"""
from ccn_paths import PACKAGE, stage_dir
import json
from pathlib import Path

import numpy as np
import pandas as pd

import detectors as D

from ccn_tools import score as S  # noqa: E402  (detectors.py puts the tools on sys.path)

OUT = stage_dir("a1_issues")
BASE = ["row_map", "row_lowclay", "farm_map", "row_report"]
# Every soil variant tried, in the order tried. The final one is named here and nowhere else.
VARIANTS = {"map_share_only": (["row_map"], False), "+low_clay": (["row_map", "row_lowclay"], False),
            "+farm_share": (["row_map", "row_lowclay", "farm_map"], False), "+reports": (BASE, False),
            "+other_year_parcel_facts": (BASE, True), "+step_at_30pct": (BASE + ["ge30"], False),
            "+step_and_parcel_facts": (BASE + ["ge30"], True)}
FINAL = "+reports"   # the simplest variant within one row of the best F1

SPECS = [  # threshold, detector, table, issue type, grid
    ("erp_unit_ratio", D.erp_unit, "erp_purchase_lines", "unit_error", np.geomspace(20, 900, 40)),
    ("erp_dec_hi", D.erp_decimal, "erp_purchase_lines", "decimal_shift", np.geomspace(1.3, 9.5, 30)),
    ("erp_dec_lo", D.erp_decimal, "erp_purchase_lines", "decimal_shift", np.geomspace(0.105, 0.78, 30)),
    ("cur_native_share", D.erp_currency_native, "erp_purchase_lines", "currency_error", np.linspace(0.05, 0.95, 19)),
    ("spend_ratio", D.erp_currency_spend, "erp_purchase_lines", "currency_error", np.geomspace(1.2, 12, 30)),
    ("capex_excess", D.erp_currency_capex, "erp_purchase_lines", "currency_error", np.geomspace(1.02, 4.9, 30)),
    ("energy_unit_ratio", D.energy_unit, "energy_meter_readings", "unit_error", np.geomspace(5, 900, 30)),
    ("energy_spike_ratio", D.energy_spike, "energy_meter_readings", "meter_spike", np.geomspace(1.1, 4.5, 30)),
    ("fuel_ratio", D.fuel_unit, "fuel_deliveries", "unit_error", np.geomspace(0.0005, 0.5, 30)),
    ("ref_kg", D.ref_unit, "refrigerant_service_log", "unit_error", np.geomspace(20, 2500, 30)),
    ("waste_ratio", D.waste_unit, "waste_transfer_notes", "unit_error", np.geomspace(0.003, 0.3, 30)),
    ("area_tol", D.survey_area, "farm_survey", "area_mismatch", np.geomspace(0.002, 0.28, 30)),
    ("n_lo", D.survey_n, "farm_survey", "decimal_shift", np.geomspace(0.11, 0.7, 30)),
    ("n_hi", D.survey_n, "farm_survey", "decimal_shift", np.geomspace(1.4, 9, 30)),
    ("yield_ratio", D.survey_yield, "farm_survey", "outlier_implausible", np.geomspace(1.2, 6, 30)),
    ("leg_share", D.ship_leg, "shipments", "missing_leg", np.linspace(0.05, 0.95, 19)),
]


def f1(flag, true):
    tp = len(flag & true)
    return 2 * tp / (len(flag) + len(true)) if flag or true else 1.0


def tune(raw, key, years, th0):
    th = dict(th0)
    log = {}
    for name, det, table, itype, grid in SPECS:
        true = set(key[(key.table == table) & (key.issue_type == itype) & key.year.isin(years)].record_key)
        sc = []
        for v in grid:
            r = det(raw, {**th, name: float(v)})
            sc.append(f1(set(r[r.year.isin(years)].record_key), true))
        sc = np.array(sc)
        best = sc.max()
        idx = np.where(sc >= best - 1e-12)[0]
        run = idx[np.argmin(np.abs(idx - idx.mean()))]    # plateau centre, on the grid
        lo = hi = run
        while lo - 1 in idx:
            lo -= 1
        while hi + 1 in idx:
            hi += 1
        val = float(np.sqrt(grid[lo] * grid[hi])) if grid[lo] > 0 else float(grid[run])
        th[name] = val
        log[name] = dict(value=round(val, 4), plateau=[round(float(grid[lo]), 4), round(float(grid[hi]), 4)], tune_f1=round(float(best), 4))
    return th, log


def soil_fit(raw, soil_lab, train_years, evidence_years, feats=D.SOIL_FEATURES, use_known=True):
    """Fit soil weights and pick the cut on train_years. Parcel facts come from evidence_years only."""
    f, pr = D.soil_frame(raw)
    f = D.add_known(f, pr, D.parcel_truth(pr, soil_lab, evidence_years) if use_known else {})
    tr = f[f.year.isin(train_years) & (f.soil_type_reported == "Mineral soil")]
    y = tr.key.isin(soil_lab.record_key).values.astype(float)
    w = D.fit_logit(tr[feats].values, y)
    p = D.soil_score(tr, w, feats)
    grid = np.linspace(0.05, 0.9, 35)
    sc = np.array([f1(set(tr.key[p >= t]), set(tr.key[y == 1])) for t in grid])
    idx = np.where(sc >= sc.max() - 1e-12)[0]
    return w, float(grid[idx].mean()), float(sc.max())


def soil_rows(raw, soil_lab, w, t, evidence_years, feats=D.SOIL_FEATURES, use_known=True):
    f, pr = D.soil_frame(raw)
    f = D.add_known(f, pr, D.parcel_truth(pr, soil_lab, evidence_years) if use_known else {})
    return D.soil_flags(f, w, t, feats, use_known)


def assemble(rules, soil):
    r = pd.concat([rules, soil], ignore_index=True)
    return r.drop_duplicates("record_key")   # rules first: a survey row with a hard error keeps that type


def main():
    raw = D.load()
    key, soil_lab = D.labels()
    res = {}
    held = []
    feats, uk = VARIANTS[FINAL]
    for train, test in ((2023, 2024), (2024, 2023)):
        th, log = tune(raw, key, [train], D.TH)
        lab_tr = soil_lab[soil_lab.year == train]
        w, t, f1tr = soil_fit(raw, lab_tr, [train], [train], feats, uk)
        fold = assemble(D.run_rules(raw, th), soil_rows(raw, lab_tr, w, t, [train], feats, uk))
        fold = fold[fold.year == test]
        held.append(fold)
        res[f"tune_{train}_score_{test}"] = S.score_a1(fold, key, [test])
        res[f"tune_{train}_score_{test}"]["soil_cut"] = round(t, 3)
        res[f"tune_{train}_thresholds"] = log
        print(train, "->", test, res[f"tune_{train}_score_{test}"])
    cv = pd.concat(held, ignore_index=True)
    cv.to_csv(OUT / "cv_heldout_flags.csv", index=False)
    res["cross_year_both_folds"] = S.score_a1(cv, key)
    print("CV pooled", res["cross_year_both_folds"])

    # Soil ablation, on the same two folds. Variants are listed so the search is visible.
    ab = {}
    for name, (vf, vk) in VARIANTS.items():
        tp = fl = tr = 0
        for train, test in ((2023, 2024), (2024, 2023)):
            lt = soil_lab[soil_lab.year == train]
            w, t, _ = soil_fit(raw, lt, [train], [train], vf, vk)
            r = soil_rows(raw, lt, w, t, [train], vf, vk)
            fl_set = set(r[r.year == test].record_key)
            true = set(soil_lab[soil_lab.year == test].record_key)
            tp += len(fl_set & true); fl += len(fl_set); tr += len(true)
        ab[name] = dict(tp=tp, flagged=fl, true=tr, precision=round(tp / fl, 3) if fl else 0, recall=round(tp / tr, 3), f1=round(2 * tp / (fl + tr), 3))
        print(name, ab[name])
    res["soil_ablation_cross_year"] = ab

    # Soil cut from the cross-year curve: weights fit on one year, F1 read on the other, summed over both folds.
    grid = np.round(np.arange(0.05, 0.61, 0.025), 3)
    tp = np.zeros(len(grid)); fl = np.zeros(len(grid))
    fr, _ = D.soil_frame(raw)
    for train, test in ((2023, 2024), (2024, 2023)):
        lt = soil_lab[soil_lab.year == train]
        wf, _, _ = soil_fit(raw, lt, [train], [train], feats, uk)
        te = fr[(fr.year == test) & (fr.soil_type_reported == "Mineral soil")]
        p = D.soil_score(te, wf, feats)
        yt = te.key.isin(soil_lab.record_key).values
        for i, c in enumerate(grid):
            tp[i] += (yt & (p >= c)).sum(); fl[i] += (p >= c).sum()
    curve = 2 * tp / (fl + len(soil_lab))
    best = np.where(curve >= curve.max() - 1e-12)[0]
    cut = float(grid[best].mean())
    res["soil_cut_curve"] = {str(c): dict(tp=int(a), flagged=int(b), f1=round(float(v), 3)) for c, a, b, v in zip(grid, tp, fl, curve)}
    print("soil cut curve", {str(c): round(float(v), 3) for c, v in zip(grid, curve)}, "chosen", round(cut, 3))

    th, log = tune(raw, key, [2023, 2024], D.TH)
    w, t, f1p = soil_fit(raw, soil_lab, [2023, 2024], [2023, 2024], feats, uk)
    t = cut
    th["soil_score"] = t
    res["final_thresholds"] = log
    res["final_soil"] = dict(variant=FINAL, weights=dict(zip(["intercept"] + feats, np.round(w, 3).tolist())), cut=round(t, 3), in_sample_f1=round(f1p, 3))
    (OUT / "thresholds.json").write_text(json.dumps(dict(th=th, soil_w=w.tolist(), soil_feats=feats, soil_known=uk), indent=1))
    (OUT / "cv_results.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k.startswith("final")}, indent=1))


if __name__ == "__main__":
    main()

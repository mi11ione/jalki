"""Scoring for the auto-scored tasks.  The same code is used by the organisers with the private
answer keys; with the public dev keys you can score yourself.

    python -m ccn_tools.score A1 --submission my_issues.csv --key tasks/dev/A1_dev_issue_labels_2023_2024.csv
    python -m ccn_tools.score A2 --submission my_inventory_2024.csv --key tasks/dev/A2_dev_inventory_2024.csv
    python -m ccn_tools.score D1 --submission my_d1.csv --key tasks/dev/D1_dev_catchments_2025.csv
    python -m ccn_tools.score E  --submission my_answers.csv --key tasks/dev/E_dev_answers.csv
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

A2_WEIGHTS = {
    "scope1_total": 0.15, "scope2_location_total": 0.03, "scope2_market_total": 0.12, "scope3_total": 0.20,
    "cat01_purchased_goods_services": 0.20, "cat02_capital_goods": 0.03, "cat03_fuel_energy": 0.04,
    "cat04_upstream_transport": 0.08, "cat05_waste": 0.04, "cat06_business_travel": 0.02, "cat07_employee_commuting": 0.02,
    "cat09_downstream_transport": 0.04, "cat11_use_of_sold_products": 0.015, "cat12_end_of_life": 0.015,
}
A2_TOL = 0.05   # full credit at 0 % error, zero credit at >= 5 % error (linear)


def score_a1(sub: pd.DataFrame, key: pd.DataFrame, years=None) -> dict:
    if years is not None:
        key = key[key.year.isin(years)]
    k = key.groupby("record_key").issue_type.apply(set).reset_index()   # a record may carry several issue types
    s = sub.dropna(subset=["record_key"]).drop_duplicates("record_key")
    if "year" in s.columns and "year" in key.columns:
        yrs = set(key.year.dropna().astype(int))
        s = s[s.year.isna() | s.year.isin(yrs)]
    m = s.merge(k, on="record_key", how="inner", suffixes=("_pred", "_true"))
    tp = len(m)
    prec = tp / len(s) if len(s) else 0.0
    rec = tp / len(k) if len(k) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    type_acc = float(np.mean([p in t for p, t in zip(m.issue_type_pred, m.issue_type_true)])) if tp else 0.0
    by_type = key.assign(found=key.record_key.isin(s.record_key)).groupby("issue_type").found.mean().round(3).to_dict()
    return dict(score=round(100 * f1 * (0.75 + 0.25 * type_acc), 2), precision=round(prec, 4), recall=round(rec, 4), f1=round(f1, 4),
                type_accuracy=round(type_acc, 4), n_flagged=int(len(s)), n_true=int(len(k)), recall_by_type=by_type)


def score_a2(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    t = key.set_index("category").tco2e
    p = sub.set_index("category").tco2e
    detail, tot = {}, 0.0
    for cat, w in A2_WEIGHTS.items():
        if cat not in t or pd.isna(p.get(cat, np.nan)):
            detail[cat] = dict(error_pct=None, credit=0.0)
            continue
        err = abs(p[cat] - t[cat]) / max(abs(t[cat]), 1e-9)
        cr = max(0.0, 1 - err / A2_TOL)
        tot += w * cr
        detail[cat] = dict(error_pct=round(100 * err, 2), credit=round(cr, 3))
    return dict(score=round(100 * tot / sum(A2_WEIGHTS.values()), 2), detail=detail)


def score_c1(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    m = key.merge(sub[["parcel_id", "year", "crop", "yield_t_ha_pred"]], on=["parcel_id", "year", "crop"], how="left")
    cov = float(m.yield_t_ha_pred.notna().mean())
    m["yield_t_ha_pred"] = m.yield_t_ha_pred.fillna(0.0)
    m["prod_t"] = m.yield_t_ha_true * m.area_ha
    m["prod_p"] = m.yield_t_ha_pred * m.area_ha
    agg = m.groupby(["region", "crop", "year"])[["prod_t", "prod_p"]].sum()
    mape = float((abs(agg.prod_p - agg.prod_t) / agg.prod_t).mean())
    nrmse = float(m.groupby("crop").apply(lambda g: np.sqrt(((g.yield_t_ha_pred - g.yield_t_ha_true) ** 2).mean()) / g.yield_t_ha_true.mean(), include_groups=False).mean())
    sc = 100 * (0.6 * max(0, 1 - mape / 0.15) + 0.4 * max(0, 1 - nrmse / 0.35))
    return dict(score=round(sc, 2), aggregate_mape=round(mape, 4), parcel_nrmse=round(nrmse, 4), coverage=round(cov, 4))


def score_c2(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    m = key.merge(sub, on=["region", "crop", "scenario", "period"], how="left", suffixes=("_true", "_pred"))
    mae_pct = float((m.mean_yield_change_pct_pred - m.mean_yield_change_pct_true).abs().fillna(100).mean())
    mae_p = float((m.p_bad_year_pred - m.p_bad_year_true).abs().fillna(1).mean())
    sc = 100 * (0.7 * max(0, 1 - mae_pct / 5) + 0.3 * max(0, 1 - mae_p / 0.1))
    return dict(score=round(sc, 2), mae_yield_change_pp=round(mae_pct, 3), mae_p_bad_year=round(mae_p, 4))


def score_d1(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    key = key.copy()
    if "priority_score" not in key and "priority_score_true" in key:
        key = key.rename(columns={"priority_score_true": "priority_score"})
    if "priority_score" not in key:   # dev key: loads only -> rank part scored on loads
        key["priority_score"] = key.apetit_p_to_water_kg / key.apetit_p_to_water_kg.median() + 0.5 * key.apetit_n_to_water_kg / key.apetit_n_to_water_kg.median()
    m = key[["catchment_id", "apetit_p_to_water_kg", "apetit_n_to_water_kg", "priority_score"]].merge(
        sub[["catchment_id", "apetit_p_to_water_kg", "apetit_n_to_water_kg", "priority_rank"]], on="catchment_id", how="left", suffixes=("_true", "_pred"))
    rk_true = m.priority_score.rank(ascending=False)
    rho = float(pd.Series(rk_true).corr(m.priority_rank.fillna(len(m)), method="spearman")) if len(m) > 2 else float("nan")
    k = min(5, len(m))
    top_t = set(m.loc[rk_true <= k, "catchment_id"])
    top_p = set(m.sort_values("priority_rank").catchment_id.head(k))
    overlap = len(top_t & top_p) / k
    act = m.apetit_p_to_water_kg_true > 1.0   # catchments with Apetit sourcing
    def mae(col):
        t = np.log10(m.loc[act, col + "_true"].clip(lower=0.1))
        p = np.log10(m.loc[act, col + "_pred"].fillna(0.1).clip(lower=0.1))
        return float((t - p).abs().mean()) if act.any() else 0.0
    mp, mn = mae("apetit_p_to_water_kg"), mae("apetit_n_to_water_kg")
    sc = 100 * (0.1 * max(0, rho if not np.isnan(rho) else 0) + 0.1 * overlap + 0.4 * max(0, 1 - mp / 0.15) + 0.4 * max(0, 1 - mn / 0.15))
    return dict(score=round(sc, 2), spearman=round(rho, 4), top5_overlap=round(overlap, 3), mae_log10_p=round(mp, 4), mae_log10_n=round(mn, 4))


def score_e(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    k = key[key.kind == "numeric"]
    m = k.merge(sub[["question_id", "answer"]], on="question_id", how="left", suffixes=("_true", "_pred"))
    ok = []
    for _, r in m.iterrows():
        try:
            pred = float(str(r.answer_pred).replace(",", ".").replace("%", ""))
            tv = float(r.answer_true)
            tol = float(r.tolerance_rel) if pd.notna(r.tolerance_rel) else 0.03
            ok.append(abs(pred - tv) <= tol * max(abs(tv), 1e-9))
        except (ValueError, TypeError):
            ok.append(False)
    acc = float(np.mean(ok)) if ok else 0.0
    return dict(score=round(100 * acc, 2), correct=int(sum(ok)), n=int(len(ok)))


SCORERS = {"A1": score_a1, "A2": score_a2, "C1": score_c1, "C2": score_c2, "D1": score_d1, "E": score_e}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=list(SCORERS))
    ap.add_argument("--submission", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--years", nargs="*", type=int)
    a = ap.parse_args()
    sub = pd.read_csv(a.submission)
    key = pd.read_csv(a.key)
    res = score_a1(sub, key, a.years) if a.task == "A1" else SCORERS[a.task](sub, key)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Print the headline shares from c3_eur_risk.csv and write results.json (re-runs nothing heavy).
Run order: facts_check.py -> c2_model.py -> plant_test.py -> c3_price.py -> irrigation_did.py -> summarize.py"""
from common import *  # noqa
import json, re, subprocess, sys

C = pd.read_csv(OUT / "c3_eur_risk.csv")
pr = prices(); p26 = pr[pr.year == 2026].set_index("item").contract_price_eur_t
item = {("FI_SW", "pea"): "pea", ("SE_SKANE", "pea"): "pea_SE", ("FI_SW", "potato"): "potato", ("FI_SW", "carrot"): "carrot",
        ("FI_SW", "spinach"): "spinach", ("FI_SW", "turnip_rape"): "turnip_rape"}
h = C[C.scenario == "historical"].copy()
h["contract_eur"] = [r.plan_t * p26[item[(r.region, r.crop)]] for r in h.itertuples()]
for s in ["historical", "ssp245"]:
    g = C[C.scenario == s]
    pea = g[g.crop == "pea"].eur_yr.sum(); tot = g.eur_yr.sum()
    print(f"{s}: peas (FI+SE) {pea:.0f} of {tot:.0f} EUR/yr expected premium cost = {100 * pea / tot:.1f} %")
print(f"peas share of 2025 contract value: {100 * h[h.crop == 'pea'].contract_eur.sum() / h.contract_eur.sum():.1f} % "
      f"(contract value total {h.contract_eur.sum() / 1e6:.2f} MEUR)")
print(f"today's expected premium cost as % of contract value: {100 * h.eur_yr.sum() / h.contract_eur.sum():.2f} %")

B = pd.read_csv(OUT / "c2_backtest.csv")
mape_m = float(((B.model_t - B.obs_t).abs() / B.obs_t).mean()); mape_c = float(((B.compar_t - B.obs_t).abs() / B.obs_t).mean())
res = {
    "note": "No official dev key exists for C2 or C3 (TASKS_AND_SCORING.md: C2 hidden truth, C3 rubric). Scores below are our own "
            "leave-one-year-out backtest of region x crop x year production 2012-2026, scored with the C1 aggregate rule "
            "(full credit at 0 % MAPE, none at 15 %). Synthetic data; not Apetit's real figures.",
    "baseline": {"name": "farm historical mean yield (current planning practice, = C2 'no change')", "mape": round(mape_c, 4),
                 "backtest_score": round(100 * max(0, 1 - mape_c / 0.15), 2)},
    "final": {"name": "weather-response model (c2_model.py)", "mape": round(mape_m, 4), "backtest_score": round(100 * max(0, 1 - mape_m / 0.15), 2)},
    "c3_eur_per_yr": {s: round(float(C[C.scenario == s].eur_yr.sum()), 0) for s in ["historical", "ssp126", "ssp245", "ssp585"]},
    "c2_submission": "c3_euro_risk/C2_submission.csv",
    "c3_table": "c3_euro_risk/c3_eur_risk.csv",
}
json.dump(res, open(OUT / "results.json", "w"), indent=1)
print(json.dumps(res, indent=1))

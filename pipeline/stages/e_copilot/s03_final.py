"""Task E, all questions: final answers, intervals, cross-track checks, dev score, results.json.
Run: python stages/e_copilot/s03_final.py   (synthetic twin; not Apetit's actual figures)"""
import json
import numpy as np, pandas as pd
import lib_e as L
HERE, W, ROOT = L.HERE, L.W, L.ROOT

base = L.build(); A, X = L.numeric(base)
low, _ = L.numeric(L.build(0.8, 0.2, 0.0))
high, _ = L.numeric(L.build(1.0, 0.6, 0.002))
L.build()  # restore module state

# 1. reproduction of e-copilot's submission
ec = pd.read_csv(HERE / "e_copilot_answers.csv", dtype=str).set_index("question_id")
ROUND = dict(E08=0, E12=0, E15=1, E16=3, E17=3, E05=2, E06=2, E07=2, E11=2, E18=1, E19=2)
rnd = {q: (int(round(v)) if q == "E08" else round(v, ROUND.get(q, 1))) for q, v in A.items()}
mism = {q: (ec.loc[q, "answer"], rnd[q]) for q in rnd if float(ec.loc[q, "answer"]) != float(rnd[q])}
print("1. numeric answers re-run vs e-copilot submission, mismatches:", mism or "none")

# 2. cross-track 2025 inventories (separate pipelines)
s = X["s"][~X["s"].index.duplicated()]
tr ={t: pd.read_csv(W / p / "A2_inventory_2025_submission.csv").drop_duplicates("category").set_index("category").tco2e for t, p in (("a2-inv", "history_a2_inv"), ("a2-inv-b", "history_a2_inv_b"), ("b-path/outputs", "b_pathways/outputs"))}
cmp_rows = ["scope1_total", "scope2_location_total", "scope2_market_total", L.KEY1, "scope3_total"]
xt = pd.DataFrame({"e-copilot": s.reindex(cmp_rows), **{k: v.reindex(cmp_rows) for k, v in tr.items()}})
xt["spread_pct"] = 100 * (xt.max(axis=1) / xt.min(axis=1) - 1)
print("2. cross-track 2025 inventory\n", xt.round(2).to_string())
s12_agree = bool(xt.loc[["scope1_total", "scope2_location_total", "scope2_market_total"]].iloc[:, :4].round(2).nunique(axis=1).eq(1).all())
print("   S1, S2 location, S2 market identical to 0.01 t across 4 pipelines:", s12_agree)
cat1_lo, cat1_hi = float(xt.loc[L.KEY1].iloc[:4].min()), float(xt.loc[L.KEY1].iloc[:4].max())
e05_rng = (A["E05"] * float(s[L.KEY1]) / cat1_hi, A["E05"] * float(s[L.KEY1]) / cat1_lo)
print("   E05 if cat 1 denominator taken from the other pipelines (numerator fixed): %.2f-%.2f %%" % e05_rng)
bp = json.loads((W / "b_pathways" / "outputs" / "structure.json").read_text())["reported"]
bp_flag_share = 100 * bp["flag"] / bp["total"]
print("   FLAG 2025: e-copilot %.1f t (%.2f %%), b-path %.1f t (%.2f %%)" % (X["flag"], A["E06"], bp["flag"], bp_flag_share))
print("   E21 with b-path FLAG %.1f; E20 with pro-forma Foodhills 12-month S1+2 %.1f" % (bp["flag"] * (1 - 0.0303 * 7), json.loads((W / "b_pathways" / "outputs" / "pathway_summary.json").read_text())["base"]["s12"] * (1 - 0.042 * 7)))

# 3. E18 leave-one-year-out backtest (fix: e-copilot's backtest used the mean ratio including the test year)
prod, act = X["prod"], X["act"]; ratio = {y: act[y] / prod[y] for y in act}
err_loo, err_prod, err_surv = [], [], []
sv = base["sv"]; p = sv[sv.crop == "pea"].assign(t=lambda d: d.area_ha * d.yield_t_ha).groupby("year").t.sum()
for y in range(2022, 2026):
    true = 100 * (act[y] / act[y - 1] - 1)
    err_loo.append(100 * (prod[y] * np.mean([ratio[z] for z in ratio if z != y]) / act[y - 1] - 1) - true)
    err_prod.append(100 * (prod[y] / prod[y - 1] - 1) - true)
    err_surv.append(100 * (p[y] / p[y - 1] - 1) - true)
rmse = lambda e: float(np.sqrt(np.mean(np.square(e))))
e18 = dict(answer=A["E18"], rmse_loo=rmse(err_loo), alt_production_change=float(100 * (prod[2026] / prod[2025] - 1)), rmse_production_change=rmse(err_prod),
           alt_survey_only=float(100 * (p[2026] / p[2025] - 1)), rmse_survey_only=rmse(err_surv))
print("3. E18", {k: round(v, 2) for k, v in e18.items()})

# 4. water (E12) and naive reading
naive_w = X["wd"] + X["reused"] - X["dc"]
print("4. E12 GRI 303 consumption %.0f m3; counting reused water as withdrawal gives %.0f m3 (+%.1f %%)" % (A["E12"], naive_w, 100 * (naive_w / A["E12"] - 1)))

# 5. dev score
key = pd.read_csv(ROOT / "tasks" / "dev" / "E_dev_answers.csv")
EST = {"E05": "cat 1 denominator differs 0.35 % across pipelines; soil model", "E06": "FLAG includes modelled organic soil", "E07": "ESTIMATE: true soil hidden", "E08": "ESTIMATE: expected count",
       "E16": "ESTIMATE: soil model; non-respondents use crop means", "E17": "ESTIMATE: soil model", "E18": "ESTIMATE: no 2026 Finnish ERP", "E21": "illustrative; FLAG depends on soil model", "E09": "two gap-filled months", "E11": "one gap-filled biogas month"}
sub = pd.read_csv(ROOT / "tasks" / "templates" / "E_answers_submission.csv", dtype=str)
sub["answer"] = [str(rnd[q]) if q in rnd else ec.loc[q, "answer"] for q in sub.question_id]
sub["evidence"] = [ec.loc[q, "evidence"] for q in sub.question_id]
i34 = sub.question_id == "E34"
sub.loc[i34, "answer"] = "FLAG: on-farm N2O (direct and indirect) and CH4, drained organic soils, liming, plus land-use change and soil carbon where accounted. Non-FLAG: fertiliser manufacture, farm diesel, electricity, pesticides, processing."
sub.loc[i34, "evidence"] = "data/07_frameworks/framework_digest.md 'FLAG' lines 22-24; docs/METHODOLOGY.md s5 'FLAG (SBTi) part'"
i18 = sub.question_id == "E18"
sub.loc[i18, "evidence"] = (f"2025 = ERP M110 {act[2025]:.1f} t; 2026 = crop-plan pea area x 2026 survey yield ({prod[2026]:.1f} t) x mean 2021-25 delivered/production ratio; "
                            f"ESTIMATE: ERP ends 2025; leave-one-year-out backtest RMSE {e18['rmse_loo']:.1f} pp; alternative production-change reading {e18['alt_production_change']:.1f} %; script stages/e_copilot/s03_final.py")
sub.to_csv(HERE / "E_answers_submission.csv", index=False)
dev = SC_ = L.SC.score_e(pd.read_csv(HERE / "E_answers_submission.csv"), key)
print("5. official dev score", dev)

# 6. intervals table
rng = {q: (min(low[q], high[q], A[q]), max(low[q], high[q], A[q])) for q in A}
rows = []
for q in [f"E{i:02d}" for i in range(1, 22)]:
    lo, hi = rng[q]
    note = EST.get(q, "record-based")
    if q == "E18":
        lo, hi = A[q] - e18["rmse_loo"], A[q] + e18["rmse_loo"]
    rows.append((q, rnd[q], round(lo, 3), round(hi, 3), note))
T = pd.DataFrame(rows, columns=["q", "answer", "low", "high", "basis"])
print("6. answers with soil-sensitivity range (E18: +/- LOO RMSE)\n", T.to_string(index=False))

res = dict(task="E-all", synthetic_data_note="Synthetic twin; not Apetit's actual figures.", reused="stages/e_copilot (pipeline, cleaning, soil table), cross-checked against a2-inv, a2-inv-b, b-path",
           facts_check=json.loads((W / "a2_inventory" / "results.json").read_text())["facts_check"],
           answers=A, rounded=rnd, ranges={q: list(rng[q]) for q in A}, e18=e18, dev_score=dev, reproduction_mismatches=mism,
           cross_track={c: {k: float(v) for k, v in xt.loc[c].items()} for c in cmp_rows}, s12_identical_4_pipelines=s12_agree,
           e05_range_cross_track=list(e05_rng), flag_bpath=dict(t=bp["flag"], share=bp_flag_share), e12_naive_m3=naive_w,
           unbacked=["E07, E08, E16, E17: depend on hidden soil; modelled", "E18: no 2026 Finnish delivery record; forecast", "E30-E39: cite package digest only, not primary standards"])
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float, ensure_ascii=False))
print("wrote E_answers_submission.csv, results.json")

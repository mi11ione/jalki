"""Final D1 run (frozen variant chosen on monitored LOCO before dev was scored).
  python stages/d1_model_b/final.py
Writes D1_catchment_priority_submission.csv and results.json in this folder and prints every number used."""
import sys, os, math, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
from lib import load_dev, score_d1, priority_ranks, write_submission, read, HERE, median, STATE_WEIGHT

FINAL = "full+k1+noLS+noK"
dev = load_dev()


def run(variant, write=None):
    M.FLAGS = set(variant.split("+"))
    cat, mon, farmI, farmA, contractI, contractA = M.build(variant)
    co = {j: M.fit(cat, mon, farmI, farmA, j) for j in (0, 1)}
    q = {c: 1 - float(cat[c]["nutrient_retention_frac_estimate"]) for c in cat}
    P = {c: q[c] * co[0][0] * contractI[c][0] for c in cat}
    N = {c: q[c] * co[1][0] * contractI[c][1] for c in cat}
    rk, pr = priority_ranks(cat, P, N)
    if write:
        write_submission(HERE / write, cat, P, N, rk)
    sub = {c: (round(P[c], 2), round(N[c], 1), rk[c]) for c in cat}
    return dict(cat=cat, mon=mon, farmI=farmI, farmA=farmA, contractI=contractI, contractA=contractA, co=co,
                P=P, N=N, rk=rk, pr=pr, sub=sub, q=q, score=score_d1(sub, dev))


res = {"note": "Synthetic twin (Since AI 2026 Apetit package, CC BY). Not Apetit's real loads.",
       "variant_final": FINAL}

# 1. baseline (package rule, ported) and calibrated-area comparator
base = {r["catchment_id"]: (float(r["apetit_p_to_water_kg"]), float(r["apetit_n_to_water_kg"]), int(r["priority_rank"]))
        for r in read("outputs/D1_baseline.csv")}
res["dev_baseline_package_area_rule"] = score_d1(base, dev)
A = run("area+k1")
res["dev_area_calibrated_k1"] = A["score"]
F = run(FINAL, write="D1_catchment_priority_submission.csv")
res["dev_final"] = F["score"]
print("DEV baseline (package rule):", res["dev_baseline_package_area_rule"])
print("DEV area x monitored-calibrated coefficient:", A["score"])
print("DEV FINAL parcel index:", F["score"])
for lab, sc in (("baseline", res["dev_baseline_package_area_rule"]), ("area_calibrated", A["score"]), ("final", F["score"])):
    print(f"DEV error as factor ({lab}): P x{10 ** sc['mae_log10_p']:.2f}  N x{10 ** sc['mae_log10_n']:.2f}")

# 2. jackknife over the 6 dev catchments (deterministic, no resampling)
jk = []
for drop in dev:
    sub_dev = {c: v for c, v in dev.items() if c != drop}
    jk.append(score_d1(F["sub"], sub_dev)["score"])
jkb = []
for drop in dev:
    sub_dev = {c: v for c, v in dev.items() if c != drop}
    jkb.append(score_d1(base, sub_dev)["score"] )
res["dev_final_jackknife_range"] = [min(jk), max(jk)]
res["dev_baseline_jackknife_range"] = [min(jkb), max(jkb)]
print("DEV jackknife (drop one of 6) final:", min(jk), "-", max(jk), " baseline:", min(jkb), "-", max(jkb))

# 3. per-dev-catchment errors
res["dev_per_catchment_log10_pred_over_true"] = {
    c: dict(P=round(math.log10(F["P"][c] / dev[c][0]), 3), N=round(math.log10(F["N"][c] / dev[c][1]), 3)) for c in dev}

# 4. calibration: coefficients, LOCO interval on Apetit totals, load split at monitored outlets (2025)
cat, mon = F["cat"], F["mon"]
for j, nut in ((0, "P"), (1, "N")):
    s, sk, b = F["co"][j]
    tot = sum((F["P"] if j == 0 else F["N"]).values())
    locos = []
    for c in mon:
        s2, _, _ = M.fit(cat, mon, F["farmI"], F["farmA"], j, exclude=(c,))
        locos.append(tot * s2 / s)
    # split of 2025 monitored outlet load into Apetit contract parcels / other crops on contract farms / non-contract farmland / background
    ap = oth = nc = bg = 0.0
    for c in mon:
        x = M.design(cat, F["farmI"], F["farmA"], c, 2025, j)
        apc = F["q"][c] * s * F["contractI"][c][j]
        ap += apc; oth += s * x[0] - apc; nc += s * x[1]; bg += b * x[2]
    obs = sum(mon[c][2025][j] for c in mon)
    T = ap + oth + nc + bg
    sh_ap, sh_bg = [], []
    for ex in mon:
        s2, _, b2 = M.fit(cat, mon, F["farmI"], F["farmA"], j, exclude=(ex,))
        a2 = t2 = g2 = 0.0
        for c in mon:
            x = M.design(cat, F["farmI"], F["farmA"], c, 2025, j)
            a2 += F["q"][c] * s2 * F["contractI"][c][j]; t2 += s2 * (x[0] + x[1]) + b2 * x[2]; g2 += b2 * x[2]
        sh_ap.append(a2 / t2); sh_bg.append(g2 / t2)
    res[f"{nut}_share_LOCO_range"] = dict(apetit=[round(min(sh_ap), 4), round(max(sh_ap), 4)],
                                         background=[round(min(sh_bg), 3), round(max(sh_bg), 3)])
    print(nut, "LOCO share ranges:", res[f"{nut}_share_LOCO_range"])
    res[f"{nut}_calibration"] = dict(
        export_scale=round(s, 5), background_kg_per_km2_nonfield=round(b, 2),
        apetit_total_2025_kg=round(tot), apetit_total_LOCO_range_kg=[round(min(locos)), round(max(locos))],
        monitored_2025_observed_kg=round(obs), monitored_2025_modelled_kg=round(T),
        share_apetit_contract_parcels=round(ap / T, 3), share_other_crops_on_contract_farms=round(oth / T, 3),
        share_noncontract_farmland=round(nc / T, 3), share_natural_background=round(bg / T, 3))
    print(nut, res[f"{nut}_calibration"])

# 5. per-ha intensity of Apetit parcels vs catchment farmland average (index ratio, 2025, all catchments)
for j, nut in ((0, "P"), (1, "N")):
    ci = sum(F["contractI"][c][j] for c in cat) / sum(F["contractA"].values())
    fi = sum(F["farmI"][c][2025][j] for c in cat) / sum(F["farmA"].values())
    res[f"{nut}_apetit_parcel_intensity_vs_contract_farm_mean"] = round(ci / fi, 3)
    print(nut, "Apetit-parcel per-ha index / contract-farm mean:", round(ci / fi, 3))

# 6. pessimistic re-run: perturb a-priori constants one at a time (no refit of the choice)
pert = {}
saved = (M.LAMBDA_M, dict(M.C_CROP), M.CATCH_P, M.CATCH_N, M.BUFFER_PP, dict(M.N_REMOVAL_PER_T))
def restore():
    M.LAMBDA_M, M.CATCH_P, M.CATCH_N, M.BUFFER_PP = saved[0], saved[2], saved[3], saved[4]
    M.C_CROP.clear(); M.C_CROP.update(saved[1]); M.N_REMOVAL_PER_T.clear(); M.N_REMOVAL_PER_T.update(saved[5])
for name, fn in [("lambda_200m", lambda: setattr(M, "LAMBDA_M", 200.0)),
                 ("lambda_800m", lambda: setattr(M, "LAMBDA_M", 800.0)),
                 ("row_crop_C_1.3", lambda: M.C_CROP.update(potato=1.3, carrot=1.3, spinach=1.2)),
                 ("no_catch_crop_effect", lambda: (setattr(M, "CATCH_P", 1.0), setattr(M, "CATCH_N", 1.0))),
                 ("buffer_0.5", lambda: setattr(M, "BUFFER_PP", 0.5)),
                 ("pea_N_removal_x1.5", lambda: M.N_REMOVAL_PER_T.update(pea=15.0)),
                 ("rape_N_removal_x0.75", lambda: M.N_REMOVAL_PER_T.update(turnip_rape=24.75))]:
    fn()
    R = run(FINAL)
    pert[name] = dict(dev=R["score"]["score"], top5=sorted(R["cat"], key=lambda c: R["rk"][c])[:5],
                      P_total=round(sum(R["P"].values())), N_total=round(sum(R["N"].values())))
    restore()
res["dev_pessimistic_perturbations"] = pert
for k, v in pert.items():
    print("PERTURB", k, v)
print("DEV min under perturbations:", min(v["dev"] for v in pert.values()))
print("SE catchments in top5 under perturbations:", sorted({sum(c.startswith("CS") for c in v["top5"]) for v in pert.values()}))

# 7. ranking summary (all 42 catchments)
order = sorted(cat, key=lambda c: F["rk"][c])
res["top10"] = [dict(rank=F["rk"][c], catchment=c, region=cat[c]["region"], status=cat[c]["ecological_status_class"],
                     water=cat[c]["receiving_water_type"], p_kg=round(F["P"][c], 1), n_kg=round(F["N"][c]),
                     contract_ha=round(F["contractA"][c], 1), priority=round(F["pr"][c], 3)) for c in order[:10]]
base_rank = {c: base[c][2] for c in cat}
res["top5_final"] = order[:5]
res["top5_baseline"] = sorted(cat, key=lambda c: base_rank[c])[:5]
res["top5_shared_with_baseline"] = len(set(order[:5]) & set(res["top5_baseline"]))
# per-ha delivered P/N for Apetit parcels: spread across catchments
iph = sorted(F["P"][c] / F["contractA"][c] for c in cat if F["contractA"][c] > 20)
iphn = sorted(F["N"][c] / F["contractA"][c] for c in cat if F["contractA"][c] > 20)
res["apetit_P_kg_per_ha_to_water_range"] = [round(iph[0], 3), round(median(iph), 3), round(iph[-1], 3)]
res["apetit_N_kg_per_ha_to_water_range"] = [round(iphn[0], 2), round(median(iphn), 2), round(iphn[-1], 2)]
print("top10:"); [print("  ", r) for r in res["top10"]]
print("top5 final", order[:5], "baseline", res["top5_baseline"], "shared", res["top5_shared_with_baseline"])
print("Apetit P kg/ha to water min/median/max (catchments >20 contract ha):", res["apetit_P_kg_per_ha_to_water_range"])
print("Apetit N kg/ha to water min/median/max:", res["apetit_N_kg_per_ha_to_water_range"])
with open(HERE / "results.json", "w") as f:
    json.dump(res, f, indent=1)
print("wrote results.json and D1_catchment_priority_submission.csv")

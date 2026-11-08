"""A2 attempt b, end to end: facts check -> baseline score -> dev validation (2023, 2024) -> 2025 inventory.

    python stages/history_a2_inv_b/run_all.py

Writes into $CCN_OUT/history_a2_inv_b/: A2_inventory_2025_submission.csv, results.json, corrections_log.csv,
factors_used.csv, dev_pred_2023.csv, dev_pred_2024.csv.  Synthetic twin data: not Apetit's real emissions.
"""
from ccn_paths import PACKAGE, stage_dir
import csv, json, os, collections
import inv

HERE = str(stage_dir("history_a2_inv_b"))
TEMPLATE = os.path.join(inv.ROOT, "tasks/templates/A2_inventory_2025_submission.csv")

# ---------------------------------------------------------------- 0. facts the brief / METHODOLOGY state
facts = []
en = inv.rd("02_raw_feeds/energy_meter_readings.csv")
bju = [r for r in en if r["site_id"] == "S-BJU" and float(r["value"]) > 0]
facts.append(("Foodhills (S-BJU) energy only from Dec 2025", all(r["year"] == "2025" and r["month"] == "12" for r in bju) and len(bju) > 0))
erp = inv.rd("02_raw_feeds/erp_purchase_lines_2021_2025.csv")
facts.append(("No Swedish contract-pea (M114) deliveries in 2025", not any(r["material_id"] == "M114" and r["posting_date"][:4] == "2025" for r in erp)))
facts.append(("Grain-trade (divested 2022) not in activity data", not any(inv.MAT[r["material_id"]]["default_ef_id"] == "EF-SPEND-GRAIN-TRADE" for r in erp)))
facts.append(("Dev truths 2023 and 2024 present", all(os.path.exists(os.path.join(inv.ROOT, "tasks/dev/A2_dev_inventory_%d.csv" % y)) for y in (2023, 2024))))
for name, ok in facts:
    print("FACT %-55s %s" % (name, "holds" if ok else "FAILS"))
assert all(ok for _, ok in facts), "facts check failed"
print("facts check: all hold\n")

# ---------------------------------------------------------------- 1. baseline (organisers' naive pipeline outputs)
results = {"note": "Synthetic twin data (Since AI 2026 / Apetit challenge). Not Apetit's real emissions.", "baseline": {}, "dev": {}}
for y in (2023, 2024):
    b = {r["category"]: float(r["tco2e"]) for r in csv.DictReader(open(os.path.join(inv.ROOT, "outputs/A2_baseline_inventory_%d.csv" % y), encoding="utf-8"))}
    sc, _ = inv.score(b, inv.load_key(y))
    results["baseline"][str(y)] = sc
    print("BASELINE naive pipeline %d dev score %.2f" % (y, sc))

# ---------------------------------------------------------------- 2. dev validation
mult_pooled = inv.calibrate_org_mult((2023, 2024))
mult_only = {2023: inv.calibrate_org_mult((2023,)), 2024: inv.calibrate_org_mult((2024,))}
print("\norganic-area uplift: pooled %.4f, fit-2023 %.4f, fit-2024 %.4f" % (mult_pooled, mult_only[2023], mult_only[2024]))
for y in (2023, 2024):
    key = inv.load_key(y)
    other = 2024 if y == 2023 else 2023
    runs = {"method_only": {"org_mult": 1.0}, "held_out_uplift": {"org_mult": mult_only[other]}, "pooled_uplift_in_sample": {"org_mult": mult_pooled}}
    results["dev"][str(y)] = {}
    for name, o in runs.items():
        inv.LOG.clear()
        pred, aux = inv.inventory(y, o)
        sc, det = inv.score(pred, key)
        results["dev"][str(y)][name] = {"score": sc, "error_pct": {k: (round(v[0], 3) if v[0] is not None else None) for k, v in det.items()}}
        print("DEV %d %-24s score %.2f   cat1 err %+.3f%%  scope3 err %+.3f%%  scope2_market err %+.2f%%" % (
            y, name, sc, 100 * (pred["cat01_purchased_goods_services"] / key["cat01_purchased_goods_services"] - 1),
            100 * (pred["scope3_total"] / key["scope3_total"] - 1), 100 * (pred["scope2_market_total"] / key["scope2_market_total"] - 1)))
        if name == "held_out_uplift":
            with open(os.path.join(HERE, "dev_pred_%d.csv" % y), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["year", "line", "pred_tco2e", "true_tco2e", "error_pct"])
                for k, v in pred.items():
                    t = key.get(k)
                    w.writerow([y, k, round(v, 2), t, round(100 * (v - t) / t, 3) if t else ""])

# ---------------------------------------------------------------- 3. 2025 inventory
inv.LOG.clear()
opts = {"org_mult": mult_pooled}
pred, aux = inv.inventory(2025, opts)
c1 = aux["cat1"]
notes = {
    "fugitive_refrigerants": "service-log top-ups x AR6 GWP; grams-in-kg and ammonia-code-on-HFC-system fixed (corrections_log.csv)",
    "stationary_and_mobile_combustion": "fuel deliveries - stock change (m3-as-litre fixed) x NCV x fossil factor + S-BJU natural gas (Dec only); biogenic fuels in memo",
    "scope2_location:purchased_electricity": "cleaned meter MWh x national production factor (FI 0.026, SE 0.012)",
    "scope2_market:purchased_electricity": "(MWh - registry GoO, same-year production, capped at use) x residual mix; head office has no GoO",
    "cat01_purchased_goods_services": "ERP kg (dupes, units, decimal shifts, material codes fixed) x valid PCF else library default; services spend x EEIO; contract farms bottom-up per METHODOLOGY s5",
    "cat02_capital_goods": "capex_projects EUR x EEIO (machinery 0.29, construction 0.25 kg/EUR)",
    "cat03_fuel_energy": "fuel MWh x WTT + electricity MWh x upstream/T&D",
    "cat04_upstream_transport": "inbound tkm x GLEC-style WTW factor; missing sea legs added at median km of the material's other lots",
    "cat05_waste": "transfer notes (tonnes-as-kg fixed) x treatment factor + third-party wastewater m3 x 0.7 kg",
    "cat06_business_travel": "flight/train pkm x factor + hotel nights; re-imported bookings dropped",
    "cat07_employee_commuting": "2025 survey (m-as-km fixed, Finnish mode labels mapped) site mean x site headcount; 46 wk, EV 0.03, carpool half a car",
    "cat09_downstream_transport": "outbound tkm x factor + third-party frozen pallet-days x 0.21 kg",
    "cat11_use_of_sold_products": "t sold x use-phase kWh/kg x grid factor of the market (location-based choice)",
    "cat12_end_of_life": "packaging kg/t x Finnish treatment mix factors",
    "scope1_total": "refrigerants + combustion", "scope2_location_total": "electricity + purchased heat (none in 2025)",
    "scope2_market_total": "electricity + purchased heat (none in 2025)", "scope3_total": "sum of categories 1-12 above",
    "biogenic_co2_scope1": "memo: wood chips, oilseed side streams, biogas, bio share of diesel",
}
out_rows = []
for r in csv.DictReader(open(TEMPLATE, encoding="utf-8")):
    k = r["category"]
    if r["scope"] in ("scope2_location", "scope2_market"):
        k = r["scope"] + ":" + r["category"]
    out_rows.append([r["scope"], r["category"], round(pred[k], 2), notes.get(k, "")])
sub_path = os.path.join(HERE, "A2_inventory_2025_submission.csv")
with open(sub_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["scope", "category", "tco2e", "method_note"])
    w.writerows(out_rows)
print("\n2025 INVENTORY (synthetic twin)")
for r in out_rows:
    print("  %-16s %-36s %12.2f" % (r[0], r[1], r[2]))
print("  cat1 parts: goods %.0f, services %.0f, contract farms %.0f (FLAG part %.0f), organic-area uplift %.4f" % (c1["goods"], c1["services"], c1["farm"], c1["farm_flag"], mult_pooled))

# corrections log (2025 run) + factors used
with open(os.path.join(HERE, "corrections_log.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["year", "table", "record_key", "correction", "reason"])
    w.writerows(inv.LOG)
by_table = collections.Counter(t for _, t, _, _, _ in inv.LOG)
print("  corrections logged for 2025: %d %s" % (len(inv.LOG), dict(by_table)))
with open(os.path.join(HERE, "factors_used.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ef_id_or_constant", "value", "unit", "source"])
    lib = {r["ef_id"]: r for r in inv.rd("01_master/emission_factor_library.csv")}
    for k in sorted(lib):
        w.writerow([k, lib[k]["kgco2e_per_unit"], "kg CO2e/" + lib[k]["unit"], "emission_factor_library.csv (%s)" % lib[k]["reference_source"]])
    for name, d in (("GRID_FI_LB", inv.GRID_FI_LB), ("RESIDUAL_FI", inv.RESIDUAL_FI), ("RESIDUAL_SE", inv.RESIDUAL_SE), ("HEAT_LB_EF", inv.HEAT_LB_EF),
                    ("FUEL_EF_t_per_MWh", inv.FUEL_EF), ("BIOGENIC_t_per_MWh", inv.BIO_EF), ("NCV", inv.NCV), ("GWP_AR6", inv.GWP), ("FARM", inv.FARM)):
        w.writerow([name, json.dumps(d), "see METHODOLOGY.md", "tools/ccn_tools/factors.py / METHODOLOGY.md"])
    w.writerow(["ORG_AREA_UPLIFT", round(mult_pooled, 4), "x soil-map organic area", "calibrated on 2023+2024 public truths (inv.calibrate_org_mult)"])

# sensitivities for 2025 (each one changes a single assumption)
sens = {}
for name, o in {"no_organic_uplift": {"org_mult": 1.0}, "uplift_fit_2023_only": {"org_mult": mult_only[2023]},
                "uplift_fit_2024_only": {"org_mult": mult_only[2024]}, "pcf_repair_instead_of_default": {"org_mult": mult_pooled, "pcf_policy": "repair"},
                "farm_map_soil_only_no_reported_organic": {"org_mult": mult_pooled, "trust_reported_organic": False}}.items():
    inv.LOG.clear()
    p2, _ = inv.inventory(2025, o)
    sens[name] = {"cat01": round(p2["cat01_purchased_goods_services"], 1), "scope3_total": round(p2["scope3_total"], 1),
                  "cat01_delta_pct": round(100 * (p2["cat01_purchased_goods_services"] / pred["cat01_purchased_goods_services"] - 1), 3)}
    print("  sensitivity %-40s cat1 %10.0f (%+.2f%%)" % (name, p2["cat01_purchased_goods_services"], sens[name]["cat01_delta_pct"]))

results["organic_area_uplift"] = {"pooled": round(mult_pooled, 4), "fit_2023": round(mult_only[2023], 4), "fit_2024": round(mult_only[2024], 4)}
results["inventory_2025"] = {r[1] if r[0] not in ("scope2_location", "scope2_market") else r[0] + ":" + r[1]: r[2] for r in out_rows}
results["cat1_parts_2025"] = {"goods": round(c1["goods"], 1), "services": round(c1["services"], 1), "contract_farms": round(c1["farm"], 1), "contract_farms_flag": round(c1["farm_flag"], 1)}
results["sensitivity_2025"] = sens
results["corrections_2025"] = dict(by_table)
json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=2)
print("\nwrote", sub_path, "and results.json")

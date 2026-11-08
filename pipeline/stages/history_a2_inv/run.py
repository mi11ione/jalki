"""A2 final run. One command:  python stages/history_a2_inv/run.py
Writes (all in $CCN_OUT/history_a2_inv/):
  A2_inventory_2025_submission.csv   template format (scope, category, tco2e, method_note)
  inventory_lines_{2023,2024,2025}.csv  every line item with its factor basis (audit trail)
  inventory_summary_{2023,2024}.csv    dev-year summaries scored against the public truths
  corrections_log.csv                  every correction: table, record_key, field, old, new, rule, reason
  farm_footprints.csv                  contract-farm footprint per farm x crop x year
  results.json                         baseline and final dev scores, per-line errors, 2025 totals
Synthetic data (Since AI / Apetit twin, CC BY). These are NOT Apetit's real emissions."""
from ccn_paths import PACKAGE, stage_dir
import csv, json
from pathlib import Path
import lib, pipeline, farm

OUT = stage_dir("history_a2_inv")
TEMPLATE = lib.ROOT / "tasks" / "templates" / "A2_inventory_2025_submission.csv"


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


NOTES = {
    "fugitive_refrigerants": "kg top-up x AR6 GWP100; gas codes/units fixed (R-REF-1/2)",
    "stationary_and_mobile_combustion": "fuel MWh (NCV, deliveries - stock change) x fossil EF; m3-as-litre fixed (R-FUEL-1)",
    "purchased_electricity": "location: MWh x grid avg; market: (MWh - registry GoO, same vintage, capped) x residual mix",
    "cat01_purchased_goods_services": "kg x valid PACT PCF else library EF; spend x EEIO; FI contract farms per-ha x register area incl. organic soils",
    "cat02_capital_goods": "capex spend x EEIO (SEK-as-EUR fixed, R-ERP-5)",
    "cat03_fuel_energy": "fuel WTT + electricity upstream/T&D",
    "cat04_upstream_transport": "inbound tkm x WTW EF; missing sea legs added (R-SHIP-1)",
    "cat05_waste": "t x treatment EF + 3rd-party wastewater m3; t-as-kg fixed (R-WASTE-1)",
    "cat06_business_travel": "pkm x EF + hotel nights; re-imported duplicates dropped (R-TRAVEL-1)",
    "cat07_employee_commuting": "2025 survey mean x site headcount; metres-as-km and mode labels fixed (R-COMM-1/2)",
    "cat09_downstream_transport": "outbound tkm x WTW EF + frozen pallet-days",
    "cat11_use_of_sold_products": "freezer+cooking kWh/kg x market grid factor",
    "cat12_end_of_life": "packaging put on market x Finnish treatment mix",
}


def main():
    raw = lib.load_raw()
    T0 = lib.naive_canonical(raw)
    baseline = {y: lib.score_a2(lib.summarise(*lib.compute_inventory(T0, y)), lib.dev_key(y))[0] for y in (2023, 2024)}
    res, log, T = pipeline.run()
    results = {"note": "Synthetic twin data (CC BY). Not Apetit's real emissions.",
               "baseline_dev_score": baseline, "baseline_dev_mean": round(sum(baseline.values()) / 2, 2),
               "final_dev_score": {}, "final_dev_detail": {}}
    for y in (2023, 2024, 2025):
        rows = res[y]["rows"]
        write_csv(OUT / f"inventory_lines_{y}.csv", rows, ["year", "scope", "category", "line_item", "tco2e", "basis"])
        if y < 2025:
            s, d = res[y]["score"]
            results["final_dev_score"][y] = s
            results["final_dev_detail"][y] = {k: dict(error_pct=v[0], credit=v[1], ours=v[2] if len(v) > 2 else None, truth=v[3] if len(v) > 3 else None) for k, v in d.items()}
            write_csv(OUT / f"inventory_summary_{y}.csv", res[y]["summary"], ["scope", "category", "tco2e"])
            print(y, "baseline", baseline[y], "-> final", s)
            for k, v in d.items():
                print(f"    {k:32s} err {v[0]:6.2f}%  credit {v[1]:.3f}")
    results["final_dev_mean"] = round(sum(results["final_dev_score"].values()) / 2, 2)
    # submission in template format
    summ = {(r["scope"], r["category"]): r["tco2e"] for r in res[2025]["summary"]}
    tmpl = lib.read(TEMPLATE)
    sub = []
    for t in tmpl:
        v = summ.get((t["scope"], t["category"]), 0.0)
        note = NOTES.get(t["category"], "sum of lines above" if t["scope"] == "total" else ("biogenic CO2 memo, outside Scope 1" if t["scope"] == "memo" else ""))
        sub.append(dict(scope=t["scope"], category=t["category"], tco2e=round(v, 2), method_note=note))
    missing = [k for k in summ if k not in {(t["scope"], t["category"]) for t in tmpl} and abs(summ[k]) > 0.005]
    write_csv(OUT / "A2_inventory_2025_submission.csv", sub, ["scope", "category", "tco2e", "method_note"])
    write_csv(OUT / "corrections_log.csv", log, ["table", "record_key", "field", "old", "new", "rule", "reason"])
    write_csv(OUT / "farm_footprints.csv", T["farm_footprints"], ["farm_id", "crop", "year", "region", "area_ha", "org_ha", "mineral_kg_ha", "kg", "tco2e", "src"])
    results["submission_2025"] = {r["category"]: r["tco2e"] for r in sub}
    results["lines_not_in_template_2025"] = missing
    results["n_corrections"] = len(log)
    results["org_scale"] = round(farm.ORG_SCALE, 4)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print("dev mean baseline", results["baseline_dev_mean"], "-> final", results["final_dev_mean"])
    print("2025 submission:")
    for r in sub:
        print(f"    {r['scope']:16s} {r['category']:34s} {r['tco2e']:12.2f}")
    print("2025 lines not in template:", missing, "| corrections logged:", len(log))


if __name__ == "__main__":
    main()

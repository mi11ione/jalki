"""One command: python stages/a2_inventory/run_final.py
Builds the 2025 inventory and the audit trail. Writes into $CCN_OUT/a2_inventory/:
  A2_inventory_2025_submission.csv
  audit/lines.csv        one row per inventory line
  audit/edges.csv        one row per line x source record: raw value, clean value, factor, tonnes, corrections
  audit/corrections.csv  one row per correction, 2025 only, with rule, reason, evidence level and approval state
  audit/factors.csv      every factor used, with value, unit and source
  audit/issues.csv       the issue list, each row joined to its corrections, lines and tonnes
  audit/manifest.json    schema, counts, hashes of every input and output
  results.json
Run s11_issues.py first. Synthetic pack, not Apetit's real emissions."""
from ccn_paths import PACKAGE, stage_dir
import csv, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = stage_dir("a2_inventory")
import lib, final_pipeline as P, lineage

AUD = HERE / "audit"
AUD.mkdir(exist_ok=True)
YEAR = 2025
DEV_VALIDATED = {"R-ERP-0", "R-ERP-1", "R-ERP-2", "R-ERP-3", "R-ERP-4", "R-ERP-5", "R-EN-1", "R-FUEL-1", "R-GOO-1", "R-REF-1", "R-REF-2", "R-WASTE-1", "R-TRAVEL-1", "R-SV-1", "R-SV-2", "R-SV-3"}
ESTIMATES = {"R-EN-2", "R-EN-3", "R-EN-4", "R-SHIP-1", "R-SOIL-REVIEW"}
NOTES = {
    "fugitive_refrigerants": "kg top-up x AR6 GWP100; gas codes and units fixed",
    "stationary_and_mobile_combustion": "fuel MWh (NCV, deliveries less stock change) x fossil factor; m3-as-litre fixed",
    "purchased_electricity": "location: MWh x grid; market: (MWh less same-vintage registry GoO, capped) x residual mix",
    "cat01_purchased_goods_services": "kg x valid PCF else library default; spend x EEIO; FI contract farms per ha x register area incl. organic soils (k fitted)",
    "cat02_capital_goods": "capex spend x EEIO; SEK booked as EUR fixed",
    "cat03_fuel_energy": "fuel WTT + electricity upstream and T&D",
    "cat04_upstream_transport": "inbound tkm x WTW factor; missing sea legs added",
    "cat05_waste": "t x treatment factor + third-party wastewater; tonnes-as-kg fixed",
    "cat06_business_travel": "pkm x factor + hotel nights; re-imported duplicates dropped",
    "cat07_employee_commuting": "2025 survey site mean x site headcount; metres-as-km and mode labels fixed",
    "cat09_downstream_transport": "outbound tkm x WTW factor + frozen pallet-days",
    "cat11_use_of_sold_products": "use-phase kWh/kg x market grid",
    "cat12_end_of_life": "packaging put on market x Finnish treatment mix",
}


def write(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def facts_text():
    """The status as the facts check printed it this run. Never typed: on the full package the workbook is present."""
    f = json.loads((HERE / "facts.json").read_text())
    if f["ok"]:
        return f"PASSED: {f['n_files']} of {f['n_files']} manifest files; {f['facts_true']} of {f['facts_n']} row-count facts hold"
    return (f"FAILED on {len(f['missing']) + len(f['mismatch'])} of {f['n_files']} manifest files (the non-CC-BY workbook is absent from twin/data); "
            f"{f['facts_true']} of {f['facts_n']} row-count facts hold; no script reads the workbook")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key_year(raw):
    """record_key -> reporting year, for rows the log does not date."""
    y = {}
    for e in raw["erp"]:
        y[f"erp:{e['doc_no']}:{int(e['line_no'])}"] = int(e["posting_date"][:4])
    for d in raw["fuel_deliveries"]:
        y[f"fuel:{d['delivery_id']}"] = int(d["year"])
    for r in raw["refrigerants"]:
        y[f"refrigerant:{r['event_id']}"] = int(r["year"])
    for w in raw["waste"]:
        y[f"waste:{w['transfer_note']}"] = int(w["year"])
    for t in raw["travel"]:
        y[f"travel:{t['booking_id']}"] = int(t["year"])
    for s in raw["farm_survey"]:
        y[f"farm_survey:{s['survey_id']}"] = int(s["year"])
    for c in raw["commuting"]:
        y[f"commute:{c['response_id']}"] = YEAR
    docy = {e["doc_no"]: int(e["posting_date"][:4]) for e in raw["erp"]}
    return y, docy


def main():
    raw, c, log, rows1, truth, ks = P.prepare()
    k = ks["pooled"]
    issues = lib.read(HERE / "A1_issues_submission.csv")
    ykey, docy = key_year(raw)

    def year_of(l):
        key = l["record_key"]
        if key in ykey:
            return ykey[key]
        p = key.split(":")
        if p[0] == "energy":
            return int(p[2][:4])
        if p[0] in ("goo", "pcf"):
            return int(p[-1])
        if p[0] == "ship":
            return docy.get(p[1])
        return None

    # issue rows with no numeric correction still enter the log, so every issue has a trail
    area = {}
    for h in c["crop_history"]:
        pass
    a_reg, _ = __import__("farm").register(c)
    sv_by_id = {s["survey_id"]: s for s in raw["farm_survey"]}
    for i in issues:
        key, typ = i["record_key"], i["issue_type"]
        if typ == "area_mismatch":
            s = sv_by_id[key.split(":")[1]]
            reg = a_reg[(s["farm_id"], s["crop"], int(s["year"]))]
            log.append(dict(table="farm_survey", record_key=key, field="area_ha", old=s["area_ha"], new=round(reg, 2), rule="R-SV-3",
                            reason="survey area differs from declared parcels; the farm line uses the parcel register, so the survey value is not used"))
        elif typ == "soil_misreport":
            log.append(dict(table="farm_survey", record_key=key, field="soil_type_reported", old="Mineral soil", new="unchanged (review)", rule="R-SOIL-REVIEW",
                            reason="detector doubts the report; the row keeps the map-based estimate until an expert decides. " + i["explanation"]))
        elif typ == "coordinate_swap":
            log.append(dict(table="farm_registry", record_key=key, field="lat/lon", old="as filed", new="swap proposed (review)", rule="R-FARM-COORD", reason=i["explanation"]))
        elif typ == "total_mismatch":
            log.append(dict(table="draft_report_summary", record_key=key, field="tco2e", old="as printed", new="draft not used", rule="R-REPORT", reason=i["explanation"]))

    log25 = [l for l in log if (year_of(l) == YEAR) or l["record_key"].startswith(("farm:", "report:"))]
    seen, uniq = set(), []
    for l in log25:   # the fit passes clean the survey more than once; keep one row per correction
        sig = (l["record_key"], l["field"], str(l["old"]), str(l["new"]), l["rule"])
        if sig not in seen:
            seen.add(sig)
            uniq.append(l)
    for n, l in enumerate(uniq, 1):
        l["id"] = f"C{n:04d}"
        l["year"] = YEAR
        l["evidence_level"] = "estimate" if l["rule"] in ESTIMATES else ("rule_validated_on_dev_labels" if l["rule"] in DEV_VALIDATED else "no_dev_labels")
        l["approval"] = "pending_expert_approval"

    T, rows, bio, summ = P.year_result(c, k, YEAR)
    edges, factors = lineage.build(raw, c, T, YEAR, uniq, k)
    for n, e in enumerate(edges, 1):
        e["edge_id"] = f"E{n:06d}"

    # double entry: edge sums against the reference-method lines
    by_line = defaultdict(float)
    for e in edges:
        by_line[e["line_id"]] += e["tco2e"]
    ref_lines = {lineage.line_id(r["scope"], r["category"], r["line_item"]): r for r in rows}
    worst = max(abs(by_line.get(kk, 0.0) - r["tco2e"]) for kk, r in ref_lines.items())
    extra = [kk for kk in by_line if kk not in ref_lines and not kk.startswith("memo|")]
    assert not extra, extra[:5]
    assert worst < 1e-6, worst
    bio_edges = sum(v for kk, v in by_line.items() if kk.startswith("memo|"))
    assert abs(bio_edges - bio) < 1e-6, (bio_edges, bio)
    print(f"double entry: {len(ref_lines)} lines, largest gap {worst:.2e} t; biogenic memo {bio_edges:.2f}")

    # lines
    tmpl = lib.read(lib.ROOT / "tasks" / "templates" / "A2_inventory_2025_submission.csv")
    per = defaultdict(lambda: dict(n=0, corrected=0, estimated=0, facs=set()))
    est_ids = {l["id"] for l in uniq if l["evidence_level"] == "estimate"}
    for e in edges:
        p = per[e["line_id"]]
        p["n"] += 1
        ids = set(e["correction_ids"].split(";")) - {""}
        if ids:
            p["corrected"] += 1
        if ids & est_ids:
            p["estimated"] += 1
        if e["factor_id"]:
            p["facs"].add(e["factor_id"])
    lines = []
    for kk, r in ref_lines.items():
        cat = "cat01_purchased_goods_services" if r["category"] in ("cat01_purchased_goods", "cat01_purchased_services") else r["category"]
        p = per[kk]
        lines.append(dict(line_id=kk, year=YEAR, scope=r["scope"], category=r["category"], submission_category=cat, line_item=r["line_item"], tco2e=r["tco2e"], basis=r["basis"],
                          n_edges=p["n"], n_edges_corrected=p["corrected"], n_edges_estimated=p["estimated"], factor_ids=";".join(sorted(p["facs"])[:12]), n_factors=len(p["facs"])))
    for kk, v in by_line.items():
        if kk.startswith("memo|"):
            p = per[kk]
            lines.append(dict(line_id=kk, year=YEAR, scope="memo", category="biogenic_co2_scope1", submission_category="biogenic_co2_scope1", line_item=kk.split("|")[2], tco2e=v, basis="MWh x biogenic factor, outside Scope 1",
                              n_edges=p["n"], n_edges_corrected=p["corrected"], n_edges_estimated=p["estimated"], factor_ids=";".join(sorted(p["facs"])), n_factors=len(p["facs"])))

    # submission
    S = {(r["scope"], r["category"]): r["tco2e"] for r in summ}
    sub = []
    for t in tmpl:
        v = S.get((t["scope"], t["category"]), 0.0)
        note = NOTES.get(t["category"], "sum of the lines above" if t["scope"] == "total" else "biogenic CO2, outside Scope 1")
        sub.append(dict(scope=t["scope"], category=t["category"], tco2e=round(v, 2), method_note=note))
    write(HERE / "A2_inventory_2025_submission.csv", sub, ["scope", "category", "tco2e", "method_note"])

    # issues joined to corrections, lines, tonnes
    corr_by_key = defaultdict(list)
    for l in uniq:
        corr_by_key[l["record_key"]].append(l["id"])
    e_by_key = defaultdict(list)
    for e in edges:
        e_by_key[e["record_key"]].append(e)
    head_scopes = ("scope1|", "scope2_market|", "scope3|")
    out_issues = []
    UNVAL = ("pcf_unit_error", "pcf_stale_period", "coordinate_swap", "total_mismatch", "mode_mislabel")
    for n, i in enumerate(issues, 1):
        key = i["record_key"]
        es = e_by_key.get(key, [])
        eff = sum(e["tco2e"] - e["tco2e_if_raw"] for e in es if e["line_id"].startswith(head_scopes))
        lids = sorted({e["line_id"] for e in es})
        treat = "corrected"
        if i["issue_type"] == "soil_misreport":
            treat = "review_only: estimate kept, expert decides"
        elif i["issue_type"] == "area_mismatch":
            treat = "no_effect: register area already used"
        elif i["issue_type"] == "coordinate_swap":
            treat = "no_emission_line"
        elif i["issue_type"] == "total_mismatch":
            treat = "draft_not_used"
        elif i["issue_type"].startswith("pcf_"):
            treat = "factor_replaced_by_library_default"
        unval = i["issue_type"] in UNVAL or i["table"] == "commuting_survey"
        out_issues.append(dict(issue_id=f"I{n:04d}", table=i["table"], record_key=key, issue_type=i["issue_type"], confidence=i["confidence"], explanation=i["explanation"], validated_on_dev=not unval, treatment=treat,
                               correction_ids=";".join(corr_by_key.get(key, [])), line_ids=";".join(lids), tco2e_effect=round(eff, 3) if es and treat == "corrected" else ""))
    write(AUD / "issues.csv", out_issues, ["issue_id", "table", "record_key", "issue_type", "confidence", "explanation", "validated_on_dev", "treatment", "correction_ids", "line_ids", "tco2e_effect"])

    edge_cols = ["edge_id", "line_id", "sub_line", "record_key", "source_file", "source_row", "role", "raw_value", "raw_unit", "clean_value", "clean_unit", "factor_id", "factor_value", "factor_unit", "multiplier", "tco2e", "tco2e_if_raw", "correction_ids"]
    write(AUD / "edges.csv", edges, edge_cols)
    write(AUD / "lines.csv", lines, ["line_id", "year", "scope", "category", "submission_category", "line_item", "tco2e", "basis", "n_edges", "n_edges_corrected", "n_edges_estimated", "n_factors", "factor_ids"])
    write(AUD / "corrections.csv", uniq, ["id", "year", "table", "record_key", "field", "old", "new", "rule", "reason", "evidence_level", "approval"])
    write(AUD / "factors.csv", sorted(factors.values(), key=lambda f: f["factor_id"]), ["factor_id", "value", "unit", "source"])

    used = sorted({e["source_file"] for e in edges} | {"data/01_master/emission_factor_library.csv", "data/01_master/materials.csv", "data/03_farming/parcel_crop_history_and_plan.csv"})
    man = dict(note="Synthetic pack (Since AI 2026). Not Apetit's real emissions. No line is approved: approval is pending for every correction.", year=YEAR, run="python run_all.py --package <path>",
               fitted_parameters={"ORG_MAP_SCALE_K": k}, schema=dict(
                   chain="submission row -> lines.csv (submission_category) -> edges.csv (line_id) -> source_file + source_row; edges.factor_id -> factors.csv; edges.correction_ids -> corrections.csv; issues.csv joins record_key to both",
                   tonnes="edges.tco2e = clean_value x factor_value x multiplier; roles driver, dropped and evidence carry 0 t",
                   source_row="1-based line in the source file, header is line 1; blank means the record has no raw row (imputed) or a JSON source"),
               counts=dict(lines=len(lines), edges=len(edges), corrections=len(uniq), factors=len(factors), issues=len(out_issues)),
               inputs={f: sha(lib.ROOT / f) for f in used},
               outputs={p.name: sha(p) for p in sorted(AUD.glob("*.csv"))} | {"A2_inventory_2025_submission.csv": sha(HERE / "A2_inventory_2025_submission.csv")} if sys.version_info >= (3, 9) else {})
    (AUD / "manifest.json").write_text(json.dumps(man, indent=1))

    hd = json.loads((HERE / "heldout.json").read_text())
    a1 = json.loads((HERE / "A1_dev_crossyear_score.json").read_text())
    farm25 = P.farm_total(rows1, YEAR, k)
    org25 = sum(1 for r in T["farm_footprints"] if r["year"] == YEAR)
    results = dict(note="Synthetic twin data. Not Apetit's real emissions.", facts_check=facts_text(),
                   inventory_2025={r["category"]: r["tco2e"] for r in sub if r["scope"] in ("scope1", "scope3", "total", "memo")} | {"scope2_location:purchased_electricity": S[("scope2_location", "purchased_electricity")], "scope2_market:purchased_electricity": S[("scope2_market", "purchased_electricity")]},
                   farm_line_2025=round(farm25, 2), farm_line_range=[round(farm25 - hd["worst_farm_err_t"], 1), round(farm25 + hd["worst_farm_err_t"], 1)], k=hd["k"],
                   a2_held_out={y: hd["folds"][y]["score"] for y in hd["folds"]}, a2_held_out_mean=round(sum(hd["folds"][y]["score"] for y in hd["folds"]) / 2, 2),
                   a2_in_sample={y: hd["folds"][y]["in_sample_score"] for y in hd["folds"]}, a2_2025_score_scenarios=hd["score_2025_scenarios"], pcf_paths_t=dict(unit=hd["pcf"]["unit_t"], stale=hd["pcf"]["stale_t"]),
                   a1_cross_year=a1["both_folds"], a1_folds={k2: v["score"] for k2, v in a1.items() if k2.startswith("fold_")}, a1_band_2025=a1["band_2025"], a1_rows=a1["rows"],
                   audit=man["counts"], rows_farm_2025=org25)
    (HERE / "results.json").write_text(json.dumps(results, indent=1, default=str))
    for r in sub:
        print(f"{r['scope']:16s} {r['category']:34s} {r['tco2e']:12.2f}")
    print("counts", man["counts"], "| k", round(k, 4), "| farm", round(farm25, 2))
    miss = [i["record_key"] for i in out_issues if not i["correction_ids"]]
    print("issues with no correction row:", miss)
    tab = defaultdict(int)
    for l in uniq:
        tab[l["rule"]] += 1
    print("2025 corrections by rule", dict(sorted(tab.items())))
    issue_keys = {i["record_key"] for i in out_issues}
    print("2025 corrections with no issue row:", sorted({l["record_key"] for l in uniq if l["record_key"] not in issue_keys}))
    top = sorted((i for i in out_issues if i["tco2e_effect"] != ""), key=lambda i: -abs(i["tco2e_effect"]))[:8]
    print("largest issue effects (clean minus raw, t):", [(i["record_key"], i["issue_type"], i["tco2e_effect"]) for i in top])


if __name__ == "__main__":
    main()

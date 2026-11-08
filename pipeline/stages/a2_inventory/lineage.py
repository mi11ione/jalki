"""Record-level lineage. For one year, rebuild every inventory line as a sum of edges, one per source record:

    tco2e = clean_value x factor_value x multiplier

Written independently of lib.compute_inventory on purpose: run_final.py and s12_verify.py require the two to agree line
by line, so this is double entry, not a report on the numbers. Roles:
  activity  carries tonnes       deduction  carries negative tonnes (GoO cover, stock build)
  driver    feeds a factor or area, carries no tonnes of its own (survey row, ERP delivery, headcount)
  dropped   a record removed by a correction (duplicate), 0 t, kept so a reviewer can see why it is not counted
  evidence  a record that decided a treatment (rejected PCF, internal GoO log row), 0 t
Synthetic pack, not Apetit's real emissions."""
from collections import defaultdict
import lib, farm
from ccn_tools import factors as F

SRC = {
    "erp": "data/02_raw_feeds/erp_purchase_lines_2021_2025.csv", "energy": "data/02_raw_feeds/energy_meter_readings.csv",
    "fuel": "data/02_raw_feeds/fuel_deliveries.csv", "fuelstock": "data/02_raw_feeds/fuel_stock_changes.csv",
    "goo": "data/02_raw_feeds/goo_cancellations.csv", "gooreg": "data/02_raw_feeds/goo_registry_statement.csv",
    "heat": "data/02_raw_feeds/heat_supplier_factors.csv", "refrigerant": "data/02_raw_feeds/refrigerant_service_log.csv",
    "waste": "data/02_raw_feeds/waste_transfer_notes.csv", "wastewater": "data/02_raw_feeds/wastewater_third_party.csv",
    "travel": "data/02_raw_feeds/travel_bookings.csv", "commute": "data/02_raw_feeds/commuting_survey_2025.csv",
    "headcount": "data/02_raw_feeds/headcount.csv", "ship": "data/02_raw_feeds/shipments.csv",
    "warehouse": "data/02_raw_feeds/frozen_warehousing.csv", "sales": "data/02_raw_feeds/sales_volumes.csv",
    "farm_survey": "data/03_farming/farm_survey_fi.csv", "parcel": "data/01_master/parcels.csv",
}
NCV = lib.NCV


def line_id(scope, category, item):
    return f"{scope}|{category}|{item}"


def build(raw, c, T, year, log, k):
    edges, factors = [], {}
    corr = defaultdict(list)
    for l in log:
        corr[l["record_key"]].append(l["id"])
    EF = {e["ef_id"]: e for e in raw["ef_library"]}
    country = {s["site_id"]: s["country"] for s in raw["sites"]}
    mm = {m["material_id"]: m for m in raw["materials"]}
    rawerp = {f"erp:{e['doc_no']}:{int(e['line_no'])}": e for e in raw["erp"]}
    rawen = {f"energy:{m['site_id']}:{int(m['year'])}-{int(m['month']):02d}:{m['carrier']}": m for m in raw["energy_meter"]}
    rawfuel = {d["delivery_id"]: d for d in raw["fuel_deliveries"]}
    rawref = {r["event_id"]: r for r in raw["refrigerants"]}
    rawwaste = {w["transfer_note"]: w for w in raw["waste"]}
    rawcom = {x["response_id"]: x for x in raw["commuting"]}
    rawsv = {s["survey_id"]: s for s in raw["farm_survey"]}

    def fac(fid, value, unit, source):
        factors.setdefault(fid, dict(factor_id=fid, value=value, unit=unit, source=source))
        return fid, value, unit

    def lib_ef(ef_id):
        e = EF[ef_id]
        return fac(ef_id, e["kgco2e_per_unit"], f"kg CO2e/{e['unit']}", f"emission_factor_library.csv ({e['reference_source']}; {e['value_status']}; v{e['version']})")

    def const(name, value, unit, doc):
        return fac(name, value, unit, f"tools/ccn_tools/factors.py, documented in docs/METHODOLOGY.md {doc}")

    def edge(lid, key, src, row, role, raw_v, raw_u, val, unit, f, mult, sub="", raw_t=None):
        t = val * f[1] * mult if f else 0.0
        edges.append(dict(line_id=lid, sub_line=sub, record_key=key, source_file=SRC.get(src, src), source_row=row, role=role, raw_value=raw_v, raw_unit=raw_u,
                          clean_value=val, clean_unit=unit, factor_id=f[0] if f else "", factor_value=f[1] if f else "", factor_unit=f[2] if f else "", multiplier=mult,
                          tco2e=t, tco2e_if_raw=t if raw_t is None else raw_t, correction_ids=";".join(corr.get(key, []))))
        return t

    # ---- energy: meter rows and fuel deliveries
    en = [e for e in T["energy"] if e["year"] == year and e["month"] != 0]
    dl = [d for d in c["fuel_deliveries"] if int(d["year"]) == year]
    st = [s for s in c["fuel_stock"] if int(s["year"]) == year]
    dl_sites = {(d["site_id"], d["carrier"]) for d in dl}

    def raw_mwh(key):
        m = rawen.get(key)
        if not m:
            return None, "", 0.0
        return m["value"], m["unit"], (m["value"] / 1000 if m["unit"] == "kWh" else m["value"])

    def fuel_edges(lid, site, carrier, f, mult=1.0):
        """Every record behind one (site, carrier) fuel quantity, at factor f per MWh."""
        for e in en:
            if e["site_id"] == site and e["carrier"] == carrier:
                rv, ru, rm = raw_mwh(e["key"])
                edge(lid, e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", f, mult, raw_t=rm * f[1] * mult)
        for d in dl:
            if d["site_id"] == site and d["carrier"] == carrier:
                ncv = NCV[carrier]
                key = f"fuel:{d['delivery_id']}"
                r = rawfuel[d["delivery_id"]]
                edge(lid, key, "fuel", d["_src_row"], "activity", r["quantity"], r["unit"], d["quantity"], d["unit"], f, mult * ncv, raw_t=r["quantity"] * f[1] * mult * ncv)
        for s in st:
            if s["site_id"] == site and s["carrier"] == carrier and (site, carrier) in dl_sites:
                edge(lid, f"fuelstock:{site}:{carrier}:{year}", "fuelstock", s["_src_row"], "deduction", s["stock_change"], s["unit"], -s["stock_change"], s["unit"], f, mult * NCV[carrier])

    fuel_keys = sorted({(e["site_id"], e["carrier"]) for e in en if e["carrier"] not in ("electricity", "steam", "district_heat")} | dl_sites)
    for site, car in fuel_keys:
        fuel_edges(line_id("scope1", "stationary_and_mobile_combustion", f"{site}:{car}"), site, car,
                   const(f"FUEL_EF:{car}", F.FUEL_EF_T_PER_MWH[car], "t CO2e/MWh", "s3"))
        if F.FUEL_BIOGENIC_T_PER_MWH.get(car):
            fuel_edges(line_id("memo", "biogenic_co2_scope1", f"{site}:{car}"), site, car,
                       const(f"FUEL_BIOGENIC:{car}", F.FUEL_BIOGENIC_T_PER_MWH[car], "t CO2/MWh", "s3"))
    for car in sorted({k[1] for k in fuel_keys}):
        f = lib_ef(F.FUEL_WTT[car])
        for site, c2 in fuel_keys:
            if c2 == car:
                fuel_edges(line_id("scope3", "cat03_fuel_energy", f"wtt:{car}"), site, car, f, 0.001)

    # ---- refrigerants
    for r in c["refrigerants"]:
        if int(r["year"]) == year:
            f = const(f"GWP:{r['refrigerant']}", F.REFRIGERANT_GWP[r["refrigerant"]], "kg CO2e/kg", "s3 (AR6)")
            rr = rawref[r["event_id"]]
            raw_gwp = F.REFRIGERANT_GWP[rr["refrigerant"]]
            edge(line_id("scope1", "fugitive_refrigerants", f"{r['site_id']}:{r['refrigerant']}"), f"refrigerant:{r['event_id']}", "refrigerant", r["_src_row"], "activity",
                 rr["kg_added"], f"kg ({rr['refrigerant']})", r["kg_added"], "kg", f, 0.001, raw_t=rr["kg_added"] * raw_gwp / 1000)

    # ---- electricity
    reg = defaultdict(list)
    for g in raw["goo_registry"]:
        if int(g["consumption_year"]) == year and g["production_period_start"][:4] == str(year):
            reg[g["beneficiary_site"]].append(g)
    goolog = {g["site_id"]: g for g in raw["goo"] if int(g["year"]) == year}
    for site in sorted({e["site_id"] for e in en if e["carrier"] == "electricity"}):
        ctry = country.get(site, "FI")
        lb = const(f"GRID_{ctry}_LB:{year}", (F.GRID_FI_LB if ctry == "FI" else F.GRID_SE_LB)[year], "t CO2e/MWh", "s3")
        res = const(f"RESIDUAL_{ctry}:{year}", (F.RESIDUAL_FI if ctry == "FI" else F.RESIDUAL_SE)[year], "t CO2e/MWh", "s3")
        up = lib_ef(f"EF-ELEC-UPSTREAM-{ctry}")
        rows = [e for e in en if e["site_id"] == site and e["carrier"] == "electricity"]
        mwh = sum(e["mwh"] for e in rows)
        l_lb, l_mb, l_up = line_id("scope2_location", "purchased_electricity", site), line_id("scope2_market", "purchased_electricity", site), line_id("scope3", "cat03_fuel_energy", f"elec_upstream:{site}")
        for e in rows:
            rv, ru, rm = raw_mwh(e["key"])
            edge(l_lb, e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", lb, 1.0, raw_t=rm * lb[1])
            edge(l_mb, e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", res, 1.0, raw_t=rm * res[1])
            edge(l_up, e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", up, 0.001, raw_t=rm * up[1] / 1000)
        tot = sum(g["mwh"] for g in reg.get(site, []))
        covered = min(mwh, tot)
        for g in reg.get(site, []):
            edge(l_mb, f"gooreg:{g['cancellation_id']}", "gooreg", g["_src_row"], "deduction", g["mwh"], "MWh", -g["mwh"] * covered / tot, "MWh", res, 1.0)
        if site in goolog:
            edge(l_mb, f"goo:{site}:{year}", "goo", goolog[site]["_src_row"], "evidence", goolog[site]["mwh_cancelled"], f"MWh (vintage {int(goolog[site]['vintage_year'])})", 0.0, "MWh", None, 0.0)

    # ---- purchased heat
    heat = [e for e in en if e["carrier"] in ("steam", "district_heat")]
    for site in sorted({e["site_id"] for e in heat}):
        sup = [h for h in raw["heat_suppliers"] if h["site_id"] == site and int(h["year"]) == year]
        lbf = const(f"HEAT_LB_EF:{year}", F.HEAT_LB_EF[year], "t CO2e/MWh", "s3")
        mbf = fac(f"HEAT_SUPPLIER:{site}:{year}", sup[0]["t_per_mwh"] if sup else 0.0, "t CO2e/MWh", "heat_supplier_factors.csv")
        for e in heat:
            if e["site_id"] == site:
                rv, ru, rm = raw_mwh(e["key"])
                edge(line_id("scope2_location", "purchased_heat_steam", site), e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", lbf, 1.0, raw_t=rm * lbf[1])
                edge(line_id("scope2_market", "purchased_heat_steam", site), e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", mbf, 1.0, raw_t=rm * mbf[1])
    for e in heat:
        rv, ru, rm = raw_mwh(e["key"])
        f = lib_ef("EF-HEAT-UPSTREAM")
        edge(line_id("scope3", "cat03_fuel_energy", "heat_upstream"), e["key"], "energy", e["_src_row"], "activity", rv, ru, e["mwh"], "MWh", f, 0.001, raw_t=rm * f[1] / 1000)

    # ---- purchases
    pcf_y = {(p["supplier_id"], p["material_id"]): p["kgco2e_per_kg"] for p in T["pcf_used"] if p["year"] == year}
    rejected = {(p["supplier_id"], p["material_id"]): p for p in raw["pcfs"] if p["year"] == year and (p["supplier_id"], p["material_id"]) not in pcf_y}
    svc = {k_ for k_, m in mm.items() if m["material_group"] == "service"}
    cap = {k_ for k_, m in mm.items() if m["material_group"] == "capex"}

    def goods_factor(sup, mat):
        if (sup, mat) in pcf_y:
            p = next(x for x in raw["pcfs"] if x["year"] == year and x["supplier_id"] == sup and x["material_id"] == mat)
            return fac(f"PCF:{sup}:{mat}:{year}", pcf_y[(sup, mat)], "kg CO2e/kg", f"data/02_raw_feeds/supplier_pcfs/{p['file']} (PACT; period {p['ref_start']}..{p['ref_end']})")
        return lib_ef(mm[mat]["default_ef_id"])

    def naive_kg(e):
        return e["quantity"] * 1000 if e["uom"] == "TO" else (e["quantity"] if e["uom"] == "KG" else 0.0)

    def naive_eur(e):
        return e["net_amount"] / F.FX_PER_EUR.get(e["currency"], 1.0)

    seen_rej = set()
    for p in T["purchases"]:
        if p["year"] != year:
            continue
        mat, sup, key = p["material_id"], p["supplier_id"], p["key"]
        r = rawerp[key]
        if mat in svc or mat in cap:
            f = lib_ef(mm[mat]["default_ef_id"])
            cat = "cat01_purchased_services" if mat in svc else "cat02_capital_goods"
            edge(line_id("scope3", cat, mat), key, "erp", p["_src_row"], "activity", r["net_amount"], r["currency"], p["amount_eur"], "EUR", f, 0.001,
                 raw_t=naive_eur(r) * f[1] / 1000)
        elif mm[mat]["default_ef_id"] == "FARM":
            continue
        else:
            f = goods_factor(sup, mat)
            lid = line_id("scope3", "cat01_purchased_goods", f"{mat}:{sup}")
            rf = goods_factor(sup, r["material_id"]) if mm[r["material_id"]]["default_ef_id"] != "FARM" else f
            edge(lid, key, "erp", p["_src_row"], "activity", r["quantity"], r["uom"], p["qty_kg"], "kg", f, 0.001, raw_t=naive_kg(r) * rf[1] / 1000)
            if (sup, mat) in rejected and (sup, mat) not in seen_rej:
                seen_rej.add((sup, mat))
                q = rejected[(sup, mat)]
                edge(lid, f"pcf:{sup}:{mat}:{year}", f"data/02_raw_feeds/supplier_pcfs/{q['file']}", None, "evidence", q["value"], "pCfExcludingBiogenic as filed", 0.0, "kg CO2e/kg", None, 0.0)

    # ---- contract farms
    par = {p["parcel_id"]: p for p in c["parcels"]}
    rowp = defaultdict(list)
    for h in c["crop_history"]:
        if h["status"] == "declared" and int(h["year"]) == year and h["parcel_id"] in par:
            rowp[(h["farm_id"], h["crop"])].append(h["parcel_id"])
    deliv = defaultdict(list)
    for p in T["purchases"]:
        if p["year"] == year and p["material_id"] in lib.CROP_MAT:
            deliv[(p["supplier_id"], lib.CROP_MAT[p["material_id"]])].append(p)
    fac("ORG_SOIL_ADDON", farm.ORG_ADD, "kg CO2e/ha/yr", "docs/METHODOLOGY.md s5: 29.0 t CO2 + 13 kg N2O-N, AR6")
    fac("ORG_MAP_SCALE_K", k, "x soil-map organic share", "fitted on the public 2023+2024 truths (final_pipeline.fit_k); the only fitted number in the inventory")
    for r in T["farm_footprints"]:
        if r["year"] != year:
            continue
        lid = line_id("scope3", "cat01_purchased_goods", f"contract_farming:{r['region']}:{r['crop']}")
        sub = f"farm:{r['farm_id']}:{r['crop']}:{year}"
        a = r["area_ha"]
        kgha = r["mineral_kg_ha"] + farm.ORG_ADD * (r["org_ha"] / a if a else 0.0)
        share_how = "farmer reports organic" if r["reported_organic"] else f"min(1, k x map share {r['map_share']:.4f})"
        f = fac(f"FARMROW:{r['farm_id']}:{r['crop']}:{year}", kgha, "kg CO2e/ha",
                f"docs/METHODOLOGY.md s5: mineral {r['mineral_kg_ha']:.1f} kg/ha ({r['src']}) + ORG_SOIL_ADDON x organic share {r['org_ha']/a if a else 0:.4f} ({share_how})")
        ids = rowp.get((r["farm_id"], r["crop"]), [])
        if ids:
            for pid in ids:
                p = par[pid]
                edge(lid, f"parcel:{pid}", "parcel", p["_src_row"], "activity", p["area_ha"], f"ha (map soil {p['soil_class_soilmap']})", p["area_ha"], "ha", f, 0.001, sub=sub)
        else:
            s = rawsv[r["survey_id"]]
            edge(lid, f"farm_survey:{r['survey_id']}", "farm_survey", s["_src_row"], "activity", s["area_ha"], "ha", a, "ha", f, 0.001, sub=sub)
        if r["survey_id"] and ids:
            s = rawsv[r["survey_id"]]
            edge(lid, f"farm_survey:{r['survey_id']}", "farm_survey", s["_src_row"], "driver", s["soil_type_reported"], "survey row", 0.0, "", None, 0.0, sub=sub)
        for p in deliv.get((r["farm_id"], r["crop"]), []):
            rr = rawerp[p["key"]]
            edge(lid, p["key"], "erp", p["_src_row"], "driver", rr["quantity"], rr["uom"], p["qty_kg"], "kg delivered", None, 0.0, sub=sub)

    # ---- transport, warehousing
    for s in T["shipments"]:
        if int(s["year"]) != year:
            continue
        cat = "cat04_upstream_transport" if s["direction"] == "inbound" else "cat09_downstream_transport"
        f = lib_ef(s["ef_id"])
        lid = line_id("scope3", cat, f"{s['direction']}:{s['ef_id']}")
        if s["shipment_id"] == "IMPUTED":
            edge(lid, f"ship:{s['ref_doc']}:{s['ef_id']}", "ship", None, "activity", None, "", s["tkm"], "tkm", f, 0.001, raw_t=0.0)
        else:
            edge(lid, f"ship:{s['shipment_id']}", "ship", s["_src_row"], "activity", s["tkm"], "tkm", s["tkm"], "tkm", f, 0.001)
    for w in T["warehousing"]:
        if int(w["year"]) == year:
            edge(line_id("scope3", "cat09_downstream_transport", "frozen_warehousing"), f"warehouse:{year}", "warehouse", w["_src_row"], "activity", w["pallet_days"], "pallet-days", w["pallet_days"], "pallet-days", lib_ef("EF-PALLETDAY-FROZEN"), 0.001)

    # ---- waste
    for w in c["waste"]:
        if int(w["year"]) != year:
            continue
        ww = lib.waste_row(w)
        f = lib_ef(ww["ef_id"])
        r = rawwaste[w["transfer_note"]]
        edge(line_id("scope3", "cat05_waste", f"{w['site_id']}:{w['waste_stream']}"), f"waste:{w['transfer_note']}", "waste", w["_src_row"], "activity", r["quantity"], "kg",
             ww["t"], "t", f, 0.001, raw_t=r["quantity"] / 1000 * f[1] / 1000)
    for w in T["wastewater"]:
        if int(w["year"]) == year:
            edge(line_id("scope3", "cat05_waste", "wastewater_third_party"), f"wastewater:{w['site_id']}:{year}", "wastewater", w["_src_row"], "activity", w["m3"], "m3", float(w["m3"]), "m3", lib_ef("EF-WASTEWATER-MUNI"), 0.001)

    # ---- travel
    fl, rl, ht = lib_ef("EF-PKM-FLIGHT-SHORT"), lib_ef("EF-PKM-TRAIN"), lib_ef("EF-HOTEL-NIGHT")
    for t in T["travel"]:
        if int(t["year"]) != year:
            continue
        key = f"travel:{t['booking_id']}"
        if t["mode"] == "flight":
            edge(line_id("scope3", "cat06_business_travel", "flights"), key, "travel", t["_src_row"], "activity", t["pkm"], "pkm", t["pkm"], "pkm", fl, 0.001)
        elif t["mode"] == "train":
            edge(line_id("scope3", "cat06_business_travel", "rail"), key, "travel", t["_src_row"], "activity", t["pkm"], "pkm", t["pkm"], "pkm", rl, 0.001)
        edge(line_id("scope3", "cat06_business_travel", "hotels"), key, "travel", t["_src_row"], "activity", t["nights"], "nights", t["nights"], "nights", ht, 0.001)

    # ---- commuting (reference method: survey mean per site x site headcount)
    car_ = EF["EF-PKM-CAR"]["kgco2e_per_unit"]
    mode_f = {"car": lib_ef("EF-PKM-CAR"), "bus": lib_ef("EF-PKM-BUS"), "train": lib_ef("EF-PKM-TRAIN"),
              "carpool": fac("COMMUTE:carpool", car_ / 2, "kg CO2e/pkm", "reference calculator: car factor / 2"),
              "bike_walk": fac("COMMUTE:bike_walk", 0.0, "kg CO2e/pkm", "reference calculator"),
              "ev_car": fac("COMMUTE:ev_car", 0.03, "kg CO2e/pkm", "reference calculator")}
    hc = {h["site_id"]: h for h in T["headcount"] if int(h["year"]) == year}
    bysite = defaultdict(list)
    for x in T["commuting_survey"]:
        bysite[x["site_id"]].append(x)
    for site, xs in sorted(bysite.items()):
        n, h = len(xs), hc.get(site)
        head = h["headcount"] if h else 0
        lid = line_id("scope3", "cat07_employee_commuting", site)
        for x in xs:
            f = mode_f.get(x["mode"], mode_f["car"])
            r = rawcom[x["response_id"]]
            mult = head / n / 1000
            edge(lid, f"commute:{x['response_id']}", "commute", x["_src_row"], "activity", r["one_way_km"], f"km one way ({r['mode']})", x["one_way_km"] * 2 * x["days_on_site_per_week"] * 46, "pkm/yr", f, mult,
                 raw_t=r["one_way_km"] * 2 * r["days_on_site_per_week"] * 46 * mode_f.get(r["mode"], mode_f["car"])[1] * mult)
        if h:
            edge(lid, f"headcount:{site}:{year}", "headcount", h["_src_row"], "driver", head, "year-end headcount", 0.0, "", None, 0.0)

    # ---- sold products
    for s in T["sales"]:
        if int(s["year"]) != year:
            continue
        g, mk, t = s["product_group"], s["market"], s["t_sold"]
        key = f"sales:{year}-{int(s['month']):02d}:{g}:{s['site_id']}:{mk}"
        use = F.USE_PHASE_KWH_PER_KG[g]
        if use > 0:
            f = fac(f"USE:{g}:{mk}:{year}", use * F.MARKET_GRID[mk][year], "t CO2e/t sold", f"docs/METHODOLOGY.md s4: {use} kWh/kg x market grid {F.MARKET_GRID[mk][year]}")
            edge(line_id("scope3", "cat11_use_of_sold_products", f"{g}:{mk}"), key, "sales", s["_src_row"], "activity", t, "t", t, "t", f, 1.0)
        pl, bd = F.PACK_KG_PER_T[g]
        f = fac(f"EOL:{g}", pl / 1000 * F.EOL_PLASTIC_EF_T + bd / 1000 * F.EOL_BOARD_EF_T, "t CO2e/t sold", f"docs/METHODOLOGY.md s4: {pl} kg plastic, {bd} kg board per t, Finnish treatment mix")
        edge(line_id("scope3", "cat12_end_of_life", f"{g}:{mk}"), key, "sales", s["_src_row"], "activity", t, "t", t, "t", f, 1.0)

    # ---- records a correction removed: 0 t, but a reviewer can still reach them
    for l in log:
        if l["new"] != "dropped":
            continue
        if l["table"] == "erp" and l["record_key"] in rawerp:
            r = rawerp[l["record_key"]]
            if r["posting_date"][:4] != str(year):
                continue
            mat, sup = r["material_id"], r["supplier_id"]
            if mat in lib.CROP_MAT:
                lid, f = line_id("scope3", "cat01_purchased_goods", f"contract_farming:FI_SW:{lib.CROP_MAT[mat]}"), None
            elif mat in svc or mat in cap:
                lid, f = line_id("scope3", "cat01_purchased_services" if mat in svc else "cat02_capital_goods", mat), lib_ef(mm[mat]["default_ef_id"])
            else:
                lid, f = line_id("scope3", "cat01_purchased_goods", f"{mat}:{sup}"), goods_factor(sup, mat)
            amount = naive_eur(r) if (mat in svc or mat in cap) else naive_kg(r)
            edge(lid, l["record_key"], "erp", r["_src_row"], "dropped", r["quantity"], r["uom"], 0.0, "dropped", f, 0.001, raw_t=(amount * f[1] / 1000) if f else 0.0)
        elif l["table"] == "travel":
            bid = l["record_key"].split(":")[1]
            r = next(t for t in raw["travel"] if t["booking_id"] == bid)
            if int(r["year"]) != year:
                continue
            f = fl if r["mode"] == "flight" else rl
            edge(line_id("scope3", "cat06_business_travel", "flights" if r["mode"] == "flight" else "rail"), l["record_key"], "travel", r["_src_row"], "dropped", r["pkm"], "pkm", 0.0, "dropped", f, 0.001, raw_t=r["pkm"] * f[1] / 1000)
            edge(line_id("scope3", "cat06_business_travel", "hotels"), l["record_key"], "travel", r["_src_row"], "dropped", r["nights"], "nights", 0.0, "dropped", ht, 0.001, raw_t=r["nights"] * ht[1] / 1000)
    return edges, factors

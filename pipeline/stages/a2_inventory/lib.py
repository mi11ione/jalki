"""Pure-Python port of ccn_tools (io.naive_canonical, farm_calculator, reference_calculator,
score.score_a2). The method is re-implemented line by line from
<package>/tools/ccn_tools/*.py. It was checked against the organisers'
published naive baseline scores."""
from ccn_paths import PACKAGE, stage_dir
import csv, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = PACKAGE
D = ROOT / "data"
R = D / "02_raw_feeds"
from ccn_tools import factors as F  # pure-python constants module

CROP_MAT = {"M100": "turnip_rape", "M110": "pea", "M111": "potato", "M112": "carrot", "M113": "spinach"}


def num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return x


def read(path, numeric=(), sep=","):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=sep))
    for i, r in enumerate(rows):
        r["_src_row"] = i + 2          # line number in the source file (header is line 1): the click-to-source anchor
        for c in numeric:
            r[c] = num(r[c])
    return rows


def boolv(x):
    return str(x).strip().lower() in ("true", "1", "yes")


def load_raw():
    raw = {
        "sites": read(D / "01_master" / "sites.csv"),
        "materials": read(D / "01_master" / "materials.csv"),
        "suppliers": read(D / "01_master" / "suppliers.csv"),
        "ef_library": read(D / "01_master" / "emission_factor_library.csv", ["kgco2e_per_unit", "flag_share"]),
        "farm_registry": read(D / "01_master" / "farm_registry.csv"),
        "parcels": read(D / "01_master" / "parcels.csv", ["area_ha"]),
        "erp": read(R / "erp_purchase_lines_2021_2025.csv", ["quantity", "net_amount", "movement_type", "line_no"]),
        "energy_meter": read(R / "energy_meter_readings.csv", ["year", "month", "value"]),
        "fuel_deliveries": read(R / "fuel_deliveries.csv", ["year", "quantity"]),
        "fuel_stock": read(R / "fuel_stock_changes.csv", ["year", "stock_change"]),
        "goo": read(R / "goo_cancellations.csv", ["year", "mwh_cancelled", "vintage_year"]),
        "goo_registry": read(R / "goo_registry_statement.csv", ["consumption_year", "mwh"]),
        "heat_suppliers": read(R / "heat_supplier_factors.csv", ["year", "t_per_mwh"]),
        "refrigerants": read(R / "refrigerant_service_log.csv", ["year", "kg_added"]),
        "waste": read(R / "waste_transfer_notes.csv", ["year", "month", "quantity"]),
        "wastewater": read(R / "wastewater_third_party.csv", ["year", "m3"]),
        "travel": read(R / "travel_bookings.csv", ["year", "pkm", "nights"]),
        "commuting": read(R / "commuting_survey_2025.csv", ["one_way_km", "days_on_site_per_week"]),
        "headcount": read(R / "headcount.csv", ["year", "headcount"]),
        "shipments": read(R / "shipments.csv", ["year", "t", "km", "tkm"]),
        "warehousing": read(R / "frozen_warehousing.csv", ["year", "pallet_days"]),
        "sales": read(R / "sales_volumes.csv", ["year", "month", "t_sold", "net_sales_eur"]),
        "capex": read(R / "capex_projects.csv", ["year", "capex_eur"]),
        "farm_survey": read(D / "03_farming" / "farm_survey_fi.csv",
                            ["year", "area_ha", "n_mineral_kg_ha", "n_manure_kg_ha", "p_kg_ha", "diesel_l_ha",
                             "lime_t_ha", "sprays", "catch_crop_share", "yield_t_ha"]),
        "crop_history": read(D / "03_farming" / "parcel_crop_history_and_plan.csv", ["year"]),
    }
    pcfs = []
    for f in sorted((R / "supplier_pcfs").glob("*.json")):
        js = json.loads(f.read_text())
        sup, mat, year = f.stem.split("_")
        p = js["pcf"]
        pcfs.append(dict(file=f.name, supplier_id=sup, material_id=mat, year=int(year),
                         value=float(p["pCfExcludingBiogenic"]), declared_unit=p["declaredUnit"],
                         ref_start=p["referencePeriodStart"][:10], ref_end=p["referencePeriodEnd"][:10], js=js))
    raw["pcfs"] = pcfs
    return raw


# ---------------------------------------------------------------- farm calculator (port)
def farm_kg_ha(r, grid=0.03):
    E = F.FARM_EF
    n2o = E["n2o_n_to_n2o"] * E["n2o_gwp"]
    z = lambda v: 0.0 if v is None else v
    nmin, nman, yld = z(r["n_mineral_kg_ha"]), z(r["n_manure_kg_ha"]), r["yield_t_ha"]
    res_n = F.RESIDUE_N_PER_T[r["crop"]] * yld
    low = "low-carbon" in (r.get("fertiliser_product") or "")
    fert = E["fert_n_prod_lowcarbon"] if low else E["fert_n_prod"]
    p = z(r["p_kg_ha"])
    c_fert = nmin * fert + p * E["fert_p_prod"] + p * 2.2 * E["fert_k_prod"]
    c_dir = (nmin * E["ef1_synthetic"] + (nman + res_n) * E["ef1_organic"]) * n2o
    c_ind = ((nmin * E["frac_gasf"] + nman * E["frac_gasm"]) * E["ef4_n2o_n"] + (nmin + nman + res_n) * E["frac_leach"] * E["ef5_n2o_n"]) * n2o
    c_dsl = z(r["diesel_l_ha"]) * (E["diesel_ttw"] + E["diesel_wtt"])
    c_lime = z(r["lime_t_ha"]) * E["lime"] * 1000
    co2 = (E["org_soil_co2_grass_t_ha"] if r["crop"] == "grass_ley" else E["org_soil_co2_t_ha"]) * 1000
    c_org = (co2 + E["org_soil_n2o_n_kg_ha"] * n2o) if r["organic_soil"] else 0.0
    c_spr = z(r["sprays"]) * E["spray_pass"]
    kwh = F.MGMT_NORMS[r["crop"]]["kwh_t"] * yld + (180.0 if boolv(r["irrigated"]) else 0.0)
    return c_fert + c_dir + c_ind + c_dsl + c_lime + c_org + c_spr + kwh * grid


def median(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


# ---------------------------------------------------------------- naive canonical (port)
def naive_canonical(raw):
    T = {k: raw[k] for k in ("sites", "materials", "ef_library", "headcount", "warehousing", "wastewater")}
    T["goo"] = [dict(site_id=g["site_id"], year=g["year"], vintage_year=g["vintage_year"], mwh_cancelled=g["mwh_cancelled"]) for g in raw["goo"]]
    T["heat_suppliers"] = raw["heat_suppliers"]
    pur = []
    for e in raw["erp"]:
        q = e["quantity"]
        qty = q * 1000 if e["uom"] == "TO" else (q if e["uom"] == "KG" else 0.0)
        pur.append(dict(e, year=int(e["posting_date"][:4]), qty_kg=qty,
                        amount_eur=e["net_amount"] / F.FX_PER_EUR.get(e["currency"], 1.0)))
    T["purchases"] = pur
    en = []
    for m in raw["energy_meter"]:
        en.append(dict(site_id=m["site_id"], year=int(m["year"]), month=int(m["month"]), carrier=m["carrier"], _src_row=m.get("_src_row"),
                       mwh=m["value"] / 1000 if m["unit"] == "kWh" else m["value"], key=f"energy:{m['site_id']}:{int(m['year'])}-{int(m['month']):02d}:{m['carrier']}"))
    T["energy"] = en + fuel_energy(raw["fuel_deliveries"], raw["fuel_stock"])
    T["refrigerants"] = [dict(site_id=r["site_id"], year=int(r["year"]), refrigerant=r["refrigerant"], kg_added=r["kg_added"], event_id=r["event_id"]) for r in raw["refrigerants"]]
    T["waste"] = [waste_row(w) for w in raw["waste"]]
    T["travel"] = raw["travel"]
    T["commuting_survey"] = raw["commuting"]
    T["shipments"] = raw["shipments"]
    T["sales"] = raw["sales"]
    T["pcf_used"] = [dict(year=p["year"], supplier_id=p["supplier_id"], material_id=p["material_id"], kgco2e_per_kg=p["value"]) for p in raw["pcfs"]]
    T["capex"] = raw["capex"]
    T["farm_footprints"] = naive_farm_footprints(raw, pur)
    return T


NCV = {"lng": F.NCV["lng_t"], "lpg": F.NCV["lpg_t"], "light_fuel_oil": F.NCV["lfo_l"], "diesel": F.NCV["diesel_l"]}


def fuel_energy(deliv, stock):
    q = defaultdict(float)
    for d in deliv:
        q[(d["site_id"], d["carrier"], int(d["year"]))] += d["quantity"]
    sc = {(s["site_id"], s["carrier"], int(s["year"])): s["stock_change"] for s in stock}
    return [dict(site_id=k[0], carrier=k[1], year=k[2], month=0, mwh=(v - sc.get(k, 0.0)) * NCV[k[1]]) for k, v in q.items()]


WASTE_EF = {"anaerobic_digestion": "EF-WASTE-BIO-AD", "composting": "EF-WASTE-BIO-COMPOST", "incineration": "EF-WASTE-MIXED-INC",
            "recycling": "EF-WASTE-RECYCLE", "landfill_codigestion": "EF-WASTE-SPENTEARTH"}


def waste_row(w, t=None):
    ef = "EF-WASTE-PLASTIC-INC" if w["waste_stream"] == "plastic_waste" else WASTE_EF.get(w["treatment"])
    return dict(site_id=w["site_id"], year=int(w["year"]), waste_stream=w["waste_stream"], ef_id=ef,
                t=w["quantity"] / 1000 if t is None else t, transfer_note=w["transfer_note"])


def survey_kgkg(sv_rows, organic_fn=None):
    out = {}
    for s in sv_rows:
        r = dict(s)
        r["organic_soil"] = organic_fn(s) if organic_fn else (s["soil_type_reported"] or "").lower().startswith("organic")
        r["kg_ha"] = farm_kg_ha(r)
        out[(s["farm_id"], s["crop"], int(s["year"]))] = r["kg_ha"] / (s["yield_t_ha"] * 1000)
    return out


def naive_farm_footprints(raw, pur, sv_rows=None, organic_fn=None, fill="median"):
    sv_rows = raw["farm_survey"] if sv_rows is None else sv_rows
    kk = survey_kgkg(sv_rows, organic_fn)
    by_cy = defaultdict(list)
    for (f, c, y), v in kk.items():
        by_cy[(c, y)].append(v)
    avg = {k: median(v) for k, v in by_cy.items()}
    d = defaultdict(float)
    for p in pur:
        if p["material_id"] in CROP_MAT:
            d[(p["supplier_id"], CROP_MAT[p["material_id"]], p["year"])] += p["qty_kg"]
    out = []
    for (farm, crop, y), kg in d.items():
        v = kk.get((farm, crop, y))
        src = "survey"
        if v is None:
            v, src = avg.get((crop, y)), "crop-year median"
        if v is None:
            continue
        out.append(dict(farm_id=farm, crop=crop, year=y, region="FI_SW", kg=kg, kg_per_kg=v, tco2e=kg * v / 1000, src=src))
    return out


# ---------------------------------------------------------------- reference calculator (port)
def compute_inventory(T, year):
    EF = {e["ef_id"]: e["kgco2e_per_unit"] for e in T["ef_library"]}
    rows = []

    def add(scope, cat, item, t, basis=""):
        rows.append(dict(year=year, scope=scope, category=cat, line_item=item, tco2e=float(t), basis=basis))

    def grp(rows_, keyf, valf):
        g = defaultdict(float)
        for r in rows_:
            g[keyf(r)] += valf(r)
        return g

    en = [e for e in T["energy"] if e["year"] == year]
    fuels = [e for e in en if e["carrier"] not in ("electricity", "steam", "district_heat")]
    bio = 0.0
    for (site, carrier), mwh in sorted(grp(fuels, lambda r: (r["site_id"], r["carrier"]), lambda r: r["mwh"]).items()):
        add("scope1", "stationary_and_mobile_combustion", f"{site}:{carrier}", mwh * F.FUEL_EF_T_PER_MWH[carrier], "fuel MWh x fossil EF")
        bio += mwh * F.FUEL_BIOGENIC_T_PER_MWH.get(carrier, 0.0)
    rf = [r for r in T["refrigerants"] if r["year"] == year]
    for (site, gas), kg in sorted(grp(rf, lambda r: (r["site_id"], r["refrigerant"]), lambda r: r["kg_added"]).items()):
        add("scope1", "fugitive_refrigerants", f"{site}:{gas}", kg * F.REFRIGERANT_GWP[gas] / 1000, "kg top-up x GWP100")
    country = {s["site_id"]: s["country"] for s in T["sites"]}
    goo = grp([g for g in T["goo"] if g["year"] == year and g["vintage_year"] == year], lambda r: r["site_id"], lambda r: r["mwh_cancelled"])
    for site, mwh in sorted(grp([e for e in en if e["carrier"] == "electricity"], lambda r: r["site_id"], lambda r: r["mwh"]).items()):
        c = country.get(site, "FI")
        lb = (F.GRID_FI_LB if c == "FI" else F.GRID_SE_LB)[year]
        res = (F.RESIDUAL_FI if c == "FI" else F.RESIDUAL_SE)[year]
        covered = min(mwh, goo.get(site, 0.0))
        add("scope2_location", "purchased_electricity", site, mwh * lb, "MWh x grid average")
        add("scope2_market", "purchased_electricity", site, (mwh - covered) * res, "uncovered MWh x residual mix")
    heat = [e for e in en if e["carrier"] in ("steam", "district_heat")]
    for site, mwh in sorted(grp(heat, lambda r: r["site_id"], lambda r: r["mwh"]).items()):
        sup = [h for h in T["heat_suppliers"] if h["site_id"] == site and h["year"] == year]
        mb = sup[0]["t_per_mwh"] if sup else 0.0
        add("scope2_location", "purchased_heat_steam", site, mwh * F.HEAT_LB_EF[year], "MWh x national heat average")
        add("scope2_market", "purchased_heat_steam", site, mwh * mb, "MWh x supplier-specific EF")
    pur = [p for p in T["purchases"] if p["year"] == year]
    mm = {m["material_id"]: m for m in T["materials"]}
    svc = {k for k, m in mm.items() if m["material_group"] == "service"}
    cap = {k for k, m in mm.items() if m["material_group"] == "capex"}
    pcf_y = {(p["supplier_id"], p["material_id"]): p["kgco2e_per_kg"] for p in T["pcf_used"] if p["year"] == year}
    goods = [p for p in pur if p["material_id"] not in svc | cap]
    for (mat, sup), kg in sorted(grp(goods, lambda r: (r["material_id"], r["supplier_id"]), lambda r: r["qty_kg"]).items()):
        m = mm[mat]
        if m["default_ef_id"] == "FARM":
            continue
        if (sup, mat) in pcf_y:
            ef, basis = pcf_y[(sup, mat)], "supplier PCF (PACT)"
        else:
            ef, basis = EF[m["default_ef_id"]], m["default_ef_id"]
        add("scope3", "cat01_purchased_goods", f"{mat}:{sup}", kg * ef / 1000, basis)
    ff = [f for f in T["farm_footprints"] if f["year"] == year]
    for (crop, region), t in sorted(grp(ff, lambda r: (r["crop"], r["region"]), lambda r: r["tco2e"]).items()):
        add("scope3", "cat01_purchased_goods", f"contract_farming:{region}:{crop}", t, "farm-specific footprint x delivered kg")
    for mat, eur in sorted(grp([p for p in pur if p["material_id"] in svc], lambda r: r["material_id"], lambda r: r["amount_eur"]).items()):
        add("scope3", "cat01_purchased_services", mat, eur * EF[mm[mat]["default_ef_id"]] / 1000, "spend x EEIO")
    for mat, eur in sorted(grp([p for p in pur if p["material_id"] in cap], lambda r: r["material_id"], lambda r: r["amount_eur"]).items()):
        add("scope3", "cat02_capital_goods", mat, eur * EF[mm[mat]["default_ef_id"]] / 1000, "capex spend x EEIO")
    for carrier, mwh in sorted(grp(fuels, lambda r: r["carrier"], lambda r: r["mwh"]).items()):
        add("scope3", "cat03_fuel_energy", f"wtt:{carrier}", mwh * EF[F.FUEL_WTT[carrier]] / 1000, "fuel MWh x WTT")
    for site, mwh in sorted(grp([e for e in en if e["carrier"] == "electricity"], lambda r: r["site_id"], lambda r: r["mwh"]).items()):
        c = country.get(site, "FI")
        add("scope3", "cat03_fuel_energy", f"elec_upstream:{site}", mwh * EF[f"EF-ELEC-UPSTREAM-{c}"] / 1000, "MWh x upstream+T&D")
    if heat:
        add("scope3", "cat03_fuel_energy", "heat_upstream", sum(h["mwh"] for h in heat) * EF["EF-HEAT-UPSTREAM"] / 1000, "MWh x upstream")
    sh = [s for s in T["shipments"] if int(s["year"]) == year]
    for (direction, ef_id), tkm in sorted(grp(sh, lambda r: (r["direction"], r["ef_id"]), lambda r: r["tkm"]).items()):
        cat = "cat04_upstream_transport" if direction == "inbound" else "cat09_downstream_transport"
        add("scope3", cat, f"{direction}:{ef_id}", tkm * EF[ef_id] / 1000, "tkm x WTW EF")
    wh = [w for w in T["warehousing"] if int(w["year"]) == year]
    if wh:
        add("scope3", "cat09_downstream_transport", "frozen_warehousing", sum(w["pallet_days"] for w in wh) * EF["EF-PALLETDAY-FROZEN"] / 1000, "pallet-days x EF")
    ws = [w for w in T["waste"] if w["year"] == year]
    for (site, stream, ef_id), t in sorted(grp(ws, lambda r: (r["site_id"], r["waste_stream"], r["ef_id"]), lambda r: r["t"]).items()):
        add("scope3", "cat05_waste", f"{site}:{stream}", t * EF[ef_id] / 1000, "t x treatment EF")
    ww = [w for w in T["wastewater"] if int(w["year"]) == year]
    add("scope3", "cat05_waste", "wastewater_third_party", sum(w["m3"] for w in ww) * EF["EF-WASTEWATER-MUNI"] / 1000, "m3 x EF")
    tr = [t for t in T["travel"] if int(t["year"]) == year]
    add("scope3", "cat06_business_travel", "flights", sum(t["pkm"] for t in tr if t["mode"] == "flight") * EF["EF-PKM-FLIGHT-SHORT"] / 1000, "pkm x EF")
    add("scope3", "cat06_business_travel", "rail", sum(t["pkm"] for t in tr if t["mode"] == "train") * EF["EF-PKM-TRAIN"] / 1000, "pkm x EF")
    add("scope3", "cat06_business_travel", "hotels", sum(t["nights"] for t in tr) * EF["EF-HOTEL-NIGHT"] / 1000, "nights x EF")
    hc = {h["site_id"]: h["headcount"] for h in T["headcount"] if int(h["year"]) == year}
    mode_ef = {"car": EF["EF-PKM-CAR"], "carpool": EF["EF-PKM-CAR"] / 2, "bus": EF["EF-PKM-BUS"], "train": EF["EF-PKM-TRAIN"], "bike_walk": 0.0, "ev_car": 0.03}
    bysite = defaultdict(list)
    for c in T["commuting_survey"]:
        bysite[c["site_id"]].append(c["one_way_km"] * 2 * c["days_on_site_per_week"] * 46 * mode_ef.get(c["mode"], EF["EF-PKM-CAR"]))
    for site, v in sorted(bysite.items()):
        add("scope3", "cat07_employee_commuting", site, sum(v) / len(v) * hc.get(site, 0) / 1000, "survey mean x headcount")
    sales = grp([s for s in T["sales"] if int(s["year"]) == year], lambda r: (r["product_group"], r["market"]), lambda r: r["t_sold"])
    for (g, market), t in sorted(sales.items()):
        kwh = t * 1000 * F.USE_PHASE_KWH_PER_KG[g]
        if kwh > 0:
            add("scope3", "cat11_use_of_sold_products", f"{g}:{market}", kwh * F.MARKET_GRID[market][year] / 1000, "kWh x market grid")
        pl, bd = F.PACK_KG_PER_T[g]
        add("scope3", "cat12_end_of_life", f"{g}:{market}", t * pl / 1000 * F.EOL_PLASTIC_EF_T + t * bd / 1000 * F.EOL_BOARD_EF_T, "packaging t x EoL EF")
    return rows, bio


def summarise(rows, bio):
    s = defaultdict(float)
    for r in rows:
        cat = "cat01_purchased_goods_services" if r["category"] in ("cat01_purchased_goods", "cat01_purchased_services") else r["category"]
        s[(r["scope"], cat)] += r["tco2e"]
    out = [dict(scope=k[0], category=k[1], tco2e=v) for k, v in s.items()]
    for sc in ("scope1", "scope2_location", "scope2_market", "scope3"):
        out.append(dict(scope="total", category=f"{sc}_total", tco2e=sum(r["tco2e"] for r in rows if r["scope"] == sc)))
    out.append(dict(scope="memo", category="biogenic_co2_scope1", tco2e=bio))
    return out


A2_WEIGHTS = {"scope1_total": 0.15, "scope2_location_total": 0.03, "scope2_market_total": 0.12, "scope3_total": 0.20,
              "cat01_purchased_goods_services": 0.20, "cat02_capital_goods": 0.03, "cat03_fuel_energy": 0.04,
              "cat04_upstream_transport": 0.08, "cat05_waste": 0.04, "cat06_business_travel": 0.02, "cat07_employee_commuting": 0.02,
              "cat09_downstream_transport": 0.04, "cat11_use_of_sold_products": 0.015, "cat12_end_of_life": 0.015}


def dev_key(year):
    return {r["category"]: float(r["tco2e"]) for r in read(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{year}.csv")}


def score_a2(summary, key):
    p = {r["category"]: r["tco2e"] for r in summary}
    tot, detail = 0.0, {}
    for cat, w in A2_WEIGHTS.items():
        if cat not in key or cat not in p:
            detail[cat] = (None, 0.0)
            continue
        err = abs(p[cat] - key[cat]) / max(abs(key[cat]), 1e-9)
        cr = max(0.0, 1 - err / 0.05)
        tot += w * cr
        detail[cat] = (round(100 * err, 2), round(cr, 3), round(p[cat], 2), key[cat])
    return round(100 * tot / sum(A2_WEIGHTS.values()), 2), detail

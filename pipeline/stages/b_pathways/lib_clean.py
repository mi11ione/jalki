"""Rule-based cleaning: raw feeds -> canonical tables for the reference calculator.
Never reads answer keys or issue labels. Every change appends one row to LOG with its reason, so all years,
including 2025 (no public key), go through identical rules."""
from ccn_paths import PACKAGE, stage_dir
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
import pandas as pd

DATA = PACKAGE
sys.path.insert(0, str(DATA / "tools"))
from ccn_tools import io as IO, factors as F  # noqa: E402
from ccn_tools.farm_calculator import farm_footprint_per_ha  # noqa: E402

LOG = []
CROP_MAT = {"M100": "turnip_rape", "M110": "pea", "M111": "potato", "M112": "carrot", "M113": "spinach"}


def log(table, key, year, rule, field, old, new, reason):
    LOG.append(dict(table=table, record_key=key, year=year, rule=rule, field=field, old=old, new=new, reason=reason))


# ---------------------------------------------------------------- energy meters
def clean_energy(raw):
    em = raw["energy_meter"].copy()
    em["mwh"] = np.where(em.unit == "kWh", em.value / 1000, em.value)
    # R1 kWh in the MWh column
    med = em[em.mwh > 0].groupby(["site_id", "carrier", "year"]).mwh.transform("median")
    em["med"] = med
    hit = em.mwh > 200 * em.med
    for _, r in em[hit].iterrows():
        log("energy", f"energy:{r.site_id}:{r.year}-{r.month:02d}:{r.carrier}", r.year, "E1", "value", r.mwh, r.mwh / 1000, "kWh reported in MWh column (>200x site-carrier-year median)")
    em.loc[hit, "mwh"] /= 1000
    # seasonal index per site-carrier, from years with at least 10 months
    em2 = em[em.mwh > 0].copy()
    em2["ymed"] = em2.groupby(["site_id", "carrier", "year"]).mwh.transform("median")
    em2["n"] = em2.groupby(["site_id", "carrier", "year"]).mwh.transform("size")
    full = em2[em2.n >= 10].copy()
    full["rel"] = full.mwh / full.ymed
    idx = full.groupby(["site_id", "carrier", "month"]).rel.median()
    rows = []
    for (s, c, y), g in em.groupby(["site_id", "carrier", "year"]):
        g = g[g.mwh > 0]
        if s == "S-BJU" or len(g) == 0:
            continue
        have = {int(m): v for m, v in zip(g.month, g.mwh)}
        lev = [v / idx.get((s, c, m), 1.0) for m, v in have.items() if idx.get((s, c, m), 0) > 0]
        level = float(np.median(lev))
        for m, v in have.items():
            exp = level * idx.get((s, c, m), 1.0)
            if len(g) >= 6 and exp > 0 and v > 2.2 * exp:
                log("energy", f"energy:{s}:{y}-{m:02d}:{c}", y, "E2", "value", v, exp, "meter spike (>2.2x seasonal expectation); replaced by expectation")
                em.loc[(em.site_id == s) & (em.carrier == c) & (em.year == y) & (em.month == m), "mwh"] = exp
        lo, hi = min(have), max(have)
        miss = [m for m in range(1, 13) if m not in have and ((lo < m < hi) or len(g) >= 10)]
        for m in miss:
            exp = level * idx.get((s, c, m), 1.0)
            log("energy", f"energy:{s}:{y}-{m:02d}:{c}", y, "E3", "value", np.nan, exp, "missing meter month inside operating window; filled with seasonal expectation")
            rows.append(dict(site_id=s, year=y, month=m, carrier=c, mwh=exp))
    em = pd.concat([em[["site_id", "year", "month", "carrier", "mwh"]], pd.DataFrame(rows)], ignore_index=True)
    # fuels
    fd = raw["fuel_deliveries"].copy()
    hit = (fd.unit == "l") & (fd.quantity < 1000)
    for _, r in fd[hit].iterrows():
        log("fuel", f"fuel:{r.delivery_id}", r.year, "F1", "quantity", r.quantity, r.quantity * 1000, "m3 keyed as litres")
    fd.loc[hit, "quantity"] *= 1000
    ncv = {"lng": F.NCV["lng_t"], "lpg": F.NCV["lpg_t"], "light_fuel_oil": F.NCV["lfo_l"], "diesel": F.NCV["diesel_l"]}
    fy = fd.groupby(["site_id", "carrier", "year"]).quantity.sum().reset_index()
    fy = fy.merge(raw["fuel_stock"][["site_id", "carrier", "year", "stock_change"]], on=["site_id", "carrier", "year"], how="left").fillna({"stock_change": 0})
    fy["mwh"] = (fy.quantity - fy.stock_change) * fy.carrier.map(ncv)
    fy["month"] = 0
    return pd.concat([em, fy[["site_id", "year", "month", "carrier", "mwh"]]], ignore_index=True)


# ---------------------------------------------------------------- refrigerants
def clean_refrigerants(raw):
    rf = raw["refrigerants"].copy()
    dom = rf[rf.refrigerant != "R717_ammonia"].groupby("system").refrigerant.agg(lambda s: s.value_counts().index[0])
    amm = rf.groupby("system").refrigerant.agg(lambda s: s.value_counts().index[0])
    for i, r in rf.iterrows():
        if r.refrigerant == "R717_ammonia" and amm.get(r.system) != "R717_ammonia" and r.system in dom.index:
            log("refrigerant", f"refrigerant:{r.event_id}", r.year, "R1", "refrigerant", r.refrigerant, dom[r.system], "ammonia code on a system that runs a synthetic gas")
            rf.at[i, "refrigerant"] = dom[r.system]
    med = rf.groupby(["system", "refrigerant"]).kg_added.transform("median")
    hit = (rf.kg_added > 30 * med) & (rf.kg_added > 300)
    for _, r in rf[hit].iterrows():
        log("refrigerant", f"refrigerant:{r.event_id}", r.year, "R2", "kg_added", r.kg_added, r.kg_added / 1000, "grams in kg column")
    rf.loc[hit, "kg_added"] /= 1000
    return rf[["site_id", "year", "refrigerant", "kg_added", "system"]]


# ---------------------------------------------------------------- GoO
def clean_goo(raw):
    g = pd.read_csv(DATA / "data" / "02_raw_feeds" / "goo_registry_statement.csv")
    g["vintage_year"] = g.production_period_start.str[:4].astype(int)
    out = g.rename(columns={"consumption_year": "year", "beneficiary_site": "site_id", "mwh": "mwh_cancelled"})
    bad = out[out.vintage_year != out.year]
    for _, r in bad.iterrows():
        log("goo", f"goo:{r.site_id}:{r.year}", r.year, "G1", "vintage", r.year, r.vintage_year, "registry production period is not the consumption year: does not count")
    int_ = raw["goo"].merge(out.groupby(["site_id", "year"]).mwh_cancelled.sum().rename("reg").reset_index(), on=["site_id", "year"], how="left")
    for _, r in int_[(int_.vintage_year != int_.year) | ((int_.mwh_cancelled - int_.reg).abs() > 1)].iterrows():
        log("goo", f"goo:{r.site_id}:{r.year}", r.year, "G2", "mwh/vintage", r.mwh_cancelled, r.reg, "internal log disagrees with the registry; registry is authoritative")
    return out[["year", "site_id", "mwh_cancelled", "vintage_year"]]


# ---------------------------------------------------------------- ERP
def clean_erp(raw):
    e = raw["erp"].copy()
    e["year"] = e.posting_date.str[:4].astype(int)
    e["key"] = "erp:" + e.doc_no.astype(str) + ":" + e.line_no.astype(str)
    # M1 material text disagrees with material id: the text on the document decides
    text2id = raw["materials"].set_index("erp_name").material_id.to_dict()
    tid = e.material_text.map(text2id)
    hit = tid.notna() & (tid != e.material_id)
    for _, r in e[hit].iterrows():
        log("erp", r.key, r.year, "M1", "material_id", r.material_id, text2id[r.material_text], "material id disagrees with document text")
    e.loc[hit, "material_id"] = tid[hit]
    # D1 duplicate postings
    k = ["supplier_id", "material_id", "quantity", "net_amount"]
    rec = e[e.movement_type == 101]
    dup = rec[rec.duplicated(k, keep="first") & (rec.uom != "EUR")]
    for _, r in dup.iterrows():
        log("erp", r.key, r.year, "D1", "*", "row", "dropped", "duplicate posting: same supplier, material, quantity, amount")
    e = e.drop(dup.index)
    e["qty_kg"] = np.where(e.uom == "TO", e.quantity * 1000, np.where(e.uom == "KG", e.quantity, 0.0))
    e["amount_eur"] = e.net_amount / e.currency.map(F.FX_PER_EUR).fillna(1.0)
    # price-ratio repairs, goods receipts only
    g = (e.movement_type == 101) & (e.uom != "EUR") & (e.qty_kg > 0)
    p = (e.amount_eur / e.qty_kg).where(g)
    ratio = p / p.groupby(e.material_id).transform("median")
    e["ratio"] = ratio
    sek_mats = set(raw["erp"][raw["erp"].currency == "SEK"].material_id)
    for i, r in e[g].iterrows():
        q = r.ratio
        if q > 300:
            log("erp", r.key, r.year, "U1", "quantity", r.qty_kg, r.qty_kg * 1000, "tonnes keyed with uom KG (unit price ~1000x material median)")
            e.at[i, "qty_kg"] = r.qty_kg * 1000
        elif 10.2 < q < 12.8 and r.material_id in sek_mats and r.currency == "EUR":
            log("erp", r.key, r.year, "C1", "currency", "EUR", "SEK", "SEK amount tagged EUR (ratio ~11.4); quantity unaffected")
            e.at[i, "amount_eur"] = r.net_amount / F.FX_PER_EUR["SEK"]
        elif 7.5 < q < 13.5:
            log("erp", r.key, r.year, "S1", "quantity", r.qty_kg, r.qty_kg * 10, "decimal shift: quantity 10x too small")
            e.at[i, "qty_kg"] = r.qty_kg * 10
        elif 0.075 < q < 0.135:
            log("erp", r.key, r.year, "S2", "quantity", r.qty_kg, r.qty_kg / 10, "decimal shift: quantity 10x too large")
            e.at[i, "qty_kg"] = r.qty_kg / 10
    # services: spend lines ~11.4x the material-year median are SEK tagged EUR
    sv = e[(e.uom == "EUR") & e.material_id.isin(["M900", "M901", "M902", "M903"])]
    m = sv.groupby(["material_id", "year"]).amount_eur.transform("median")
    for i, r in sv[sv.amount_eur > 6 * m].iterrows():
        new = r.net_amount / F.FX_PER_EUR["SEK"]
        log("erp", r.key, r.year, "C2", "amount", r.amount_eur, new, "service line >6x material-year median: SEK amount tagged EUR")
        e.at[i, "amount_eur"] = new
    # capex: project register is the reconciled source for category 2
    cap = pd.read_csv(DATA / "data" / "02_raw_feeds" / "capex_projects.csv")
    cap["material_id"] = cap.capex_type.map({"machinery": "M950", "construction": "M951"})
    reg = cap.groupby(["year", "material_id"]).capex_eur.sum().reset_index()
    old = e[e.material_id.isin(["M950", "M951"])].groupby("year").amount_eur.sum()
    new = reg.groupby("year").capex_eur.sum()
    for y in old.index:
        if abs(old[y] - new.get(y, 0)) > 1:
            log("erp", f"capex:{y}", y, "K1", "amount", old[y], new.get(y, 0), "ERP capex disagrees with the project register; register used")
    e = e[~e.material_id.isin(["M950", "M951"])]
    add = reg.rename(columns={"capex_eur": "amount_eur"}).assign(qty_kg=0.0, supplier_id="CAPEX_REGISTER", uom="EUR", movement_type=101)
    return pd.concat([e, add], ignore_index=True)


# ---------------------------------------------------------------- other feeds
def clean_waste(raw):
    w = raw["waste"].copy()
    med = w.groupby(["site_id", "waste_stream"]).quantity.transform("median")
    hit = w.quantity < med / 100
    for _, r in w[hit].iterrows():
        log("waste", f"waste:{r.transfer_note}", r.year, "W1", "quantity", r.quantity, r.quantity * 1000, "tonnes keyed as kg")
    w.loc[hit, "quantity"] *= 1000
    w["t"] = w.quantity / 1000
    efmap = {"anaerobic_digestion": "EF-WASTE-BIO-AD", "composting": "EF-WASTE-BIO-COMPOST", "incineration": "EF-WASTE-MIXED-INC",
             "recycling": "EF-WASTE-RECYCLE", "landfill_codigestion": "EF-WASTE-SPENTEARTH"}
    w["ef_id"] = w.treatment.map(efmap)
    w.loc[w.waste_stream == "plastic_waste", "ef_id"] = "EF-WASTE-PLASTIC-INC"
    return w


def clean_travel(raw):
    t = raw["travel"].copy()
    d = t.duplicated(["traveller_id", "travel_date", "route", "pkm", "nights"], keep="first")
    for _, r in t[d].iterrows():
        log("travel", f"travel:{r.booking_id}", r.year, "T1", "*", "row", "dropped", "re-imported booking: same traveller, date, route, distance, nights")
    return t[~d]


def clean_commuting(raw):
    c = raw["commuting"].copy()
    hit = c.one_way_km > 500
    for _, r in c[hit].iterrows():
        log("commuting", f"commute:{r.response_id}", 2025, "Q1", "one_way_km", r.one_way_km, r.one_way_km / 1000, "metres in km column")
    c.loc[hit, "one_way_km"] /= 1000
    mp = {"Car": "car", "auto": "car", "henkilöauto": "car", "linja-auto": "bus"}
    for _, r in c[c["mode"].isin(mp)].iterrows():
        log("commuting", f"commute:{r.response_id}", 2025, "Q2", "mode", r["mode"], mp[r["mode"]], "free-text mode mapped to code")
    c["mode"] = c["mode"].replace(mp)
    return c


def clean_shipments(raw, erp):
    s = raw["shipments"].copy()
    ib = s[s.direction == "inbound"].copy()
    ib["ref_doc"] = ib.ref_doc.astype(str)
    mat = erp.dropna(subset=["doc_no"]).drop_duplicates("doc_no").set_index("doc_no")[["material_id", "origin_country"]]
    ib = ib.join(mat, on="ref_doc")
    sea = ib[ib.ef_id.str.contains("SHIP|ROPAX")]
    legs = sea.groupby(["material_id", "origin_country"]).agg(ef=("ef_id", lambda x: x.value_counts().index[0]), km=("km", "median"), n=("km", "size")).reset_index()
    docs = ib.groupby("ref_doc").agg(n=("ef_id", "size"), material_id=("material_id", "first"), origin_country=("origin_country", "first"), t=("t", "first"), year=("year", "first"))
    # a material where >=90 % of lots carry a second leg must have one
    share = docs.groupby("material_id").n.apply(lambda x: (x >= 2).mean())
    need = docs[(docs.n == 1) & docs.material_id.map(share).ge(0.9)].reset_index()
    need = need.merge(legs, on=["material_id", "origin_country"], how="inner", suffixes=("", "_l"))
    rows = []
    for _, r in need.iterrows():
        log("shipments", f"ship:{r.ref_doc}:{r.ef}", r.year, "L1", "tkm", np.nan, r.t * r.km, "import lot has no sea/Ro-Pax leg; rebuilt from the standard leg of that material-origin")
        rows.append(dict(year=r.year, direction="inbound", ref_doc=r.ref_doc, ef_id=r.ef, t=r.t, km=r.km, tkm=r.t * r.km))
    return pd.concat([s, pd.DataFrame(rows)], ignore_index=True)


def clean_pcfs(raw):
    p = raw["pcfs"].copy()
    ok = []
    for _, r in p.iterrows():
        k = f"pcf:{r.supplier_id}:{r.material_id}:{r.year}"
        if int(r.ref_start[:4]) != r.year:
            log("pcf", k, r.year, "P1", "period", r.ref_start, "invalid", "reference period does not cover the year: stale PCF, material default used")
        elif r.value > 50:
            log("pcf", k, r.year, "P2", "value", r.value, "invalid", "value is per tonne, not per declared kg: invalid PCF, material default used")
        else:
            ok.append(True)
            continue
        ok.append(False)
    return p[ok].rename(columns={"value": "kgco2e_per_kg"})[["year", "supplier_id", "material_id", "kgco2e_per_kg"]]


# ---------------------------------------------------------------- farms
def clean_survey(raw):
    s = raw["farm_survey"].copy()
    med = s.groupby("crop").yield_t_ha.transform("median")
    hit = s.yield_t_ha > 3 * med
    for _, r in s[hit].iterrows():
        log("farm_survey", f"farm_survey:{r.survey_id}", r.year, "Y1", "yield_t_ha", r.yield_t_ha, r.yield_t_ha / 10, "yield >3x crop median: decimal shift")
    s.loc[hit, "yield_t_ha"] /= 10
    nmed = s.groupby("crop").n_mineral_kg_ha.transform("median")
    q = s.n_mineral_kg_ha / nmed
    hi, lo = q > 5, (q < 0.2) & (s.n_mineral_kg_ha > 0) & (s.crop != "pea") & (~s.fertiliser_product.fillna("").str.contains("organic"))
    for _, r in s[hi].iterrows():
        log("farm_survey", f"farm_survey:{r.survey_id}", r.year, "N1", "n_mineral", r.n_mineral_kg_ha, r.n_mineral_kg_ha / 10, "mineral N >5x crop median: decimal shift")
    for _, r in s[lo].iterrows():
        log("farm_survey", f"farm_survey:{r.survey_id}", r.year, "N2", "n_mineral", r.n_mineral_kg_ha, r.n_mineral_kg_ha * 10, "mineral N <0.2x crop median: decimal shift")
    s.loc[hi, "n_mineral_kg_ha"] /= 10
    s.loc[lo, "n_mineral_kg_ha"] *= 10
    return s


def organic_share(raw):
    """Share of a farm-crop-year's declared area on soil-map organic parcels. The map is ~88 % accurate."""
    ch = raw["crop_history"].merge(raw["parcels"][["parcel_id", "area_ha", "soil_class_soilmap"]], on="parcel_id")
    ch["org_ha"] = ch.area_ha.where(ch.soil_class_soilmap == "organic", 0.0)
    return ch.groupby(["farm_id", "crop", "year"])[["area_ha", "org_ha"]].sum().reset_index()


def components(df, grid=0.03):
    """Per-hectare split of farm_footprint_per_ha into FLAG and non-FLAG parts, mineral-soil basis.
    Same formulas as ccn_tools.farm_calculator; organic soil is added separately so a share can be applied."""
    E = F.FARM_EF
    n2o = E["n2o_n_to_n2o"] * E["n2o_gwp"]
    nmin, nman = df.n_mineral_kg_ha.fillna(0).values, df.n_manure_kg_ha.fillna(0).values
    yld = df.yield_t_ha.values
    res = df.crop.map(F.RESIDUE_N_PER_T).values * yld
    low = df.fertiliser_product.fillna("").str.contains("low-carbon").values
    fert = np.where(low, E["fert_n_prod_lowcarbon"], E["fert_n_prod"])
    pk = df.p_kg_ha.fillna(0).values
    o = pd.DataFrame(index=df.index)
    o["fert_n"] = nmin * fert
    o["fert_pk"] = pk * E["fert_p_prod"] + pk * 2.2 * E["fert_k_prod"]
    o["n2o_dir"] = (nmin * E["ef1_synthetic"] + (nman + res) * E["ef1_organic"]) * n2o
    o["n2o_ind"] = ((nmin * E["frac_gasf"] + nman * E["frac_gasm"]) * E["ef4_n2o_n"] + (nmin + nman + res) * E["frac_leach"] * E["ef5_n2o_n"]) * n2o
    o["diesel"] = df.diesel_l_ha.fillna(0).values * (E["diesel_ttw"] + E["diesel_wtt"])
    o["lime"] = df.lime_t_ha.fillna(0).values * E["lime"] * 1000
    o["spray"] = df.sprays.fillna(0).values * E["spray_pass"]
    kwh = df.crop.map({c: v["kwh_t"] for c, v in F.MGMT_NORMS.items()}).values * yld + np.where(df.irrigated.fillna(False).values.astype(bool), 180.0, 0.0)
    o["elec"] = kwh * grid
    return o


FLAG_PARTS = ["n2o_dir", "n2o_ind", "lime"]
NONFLAG_PARTS = ["fert_n", "fert_pk", "diesel", "spray", "elec"]
ORG_KG_HA = F.FARM_EF["org_soil_co2_t_ha"] * 1000 + F.FARM_EF["org_soil_n2o_n_kg_ha"] * F.FARM_EF["n2o_n_to_n2o"] * F.FARM_EF["n2o_gwp"]


def farm_table(raw, erp, soil="map"):
    """farm x crop x year: tCO2e with FLAG/non-FLAG parts, allocated to delivered kg.
    soil='map': soil-map organic share; soil='reported': farmer's report (current practice); soil='none'."""
    s = clean_survey(raw)
    c = components(s)
    s = pd.concat([s, c], axis=1)
    s["mineral_kg_ha"] = c.sum(axis=1)
    os_ = organic_share(raw)
    s = s.merge(os_, on=["farm_id", "crop", "year"], how="left")
    s["share_map"] = (s.org_ha / s.area_ha_y).fillna(0) if "area_ha_y" in s else 0
    return s


def load_clean():
    raw = IO.load_raw(DATA)
    T = {k: raw[k] for k in ("sites", "materials", "ef_library", "heat_suppliers", "headcount", "warehousing", "wastewater", "sales")}
    T["heat_suppliers"] = raw["heat_suppliers"]
    T["energy"] = clean_energy(raw)
    T["refrigerants"] = clean_refrigerants(raw)
    T["goo"] = clean_goo(raw)
    erp = clean_erp(raw)
    T["purchases"] = erp
    T["waste"] = clean_waste(raw)
    T["travel"] = clean_travel(raw)
    T["commuting_survey"] = clean_commuting(raw)
    T["shipments"] = clean_shipments(raw, erp)
    T["pcf_used"] = clean_pcfs(raw)
    return raw, T

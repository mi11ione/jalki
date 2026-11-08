"""A1 detectors: one narrow detector per (table, issue_type).

Every detector returns rows: table, record_key, issue_type, year, score, explanation.
`score` is the statistic the threshold acts on. Thresholds live in TH and are tuned by tune_cv.py.
No detector reads a label, except soil evidence, which takes labels of *other* years explicitly.
Synthetic data: nothing here describes Apetit's real emissions.
"""
from __future__ import annotations
from ccn_paths import PACKAGE, stage_dir

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = PACKAGE
sys.path.insert(0, str(ROOT / "tools"))
from ccn_tools import factors as F, io as IO  # noqa: E402

COLS = ["table", "record_key", "issue_type", "year", "score", "explanation"]
PROFILE_CLEAN = 2.0   # meter readings beyond this multiple of their neighbours do not teach the seasonal profile

# Starting values only; tune_cv.py picks the values actually used and writes thresholds.json.
TH = dict(
    erp_unit_ratio=300.0,      # price / material-year median at or above: quantity is 1000x too small
    erp_dec_hi=5.0,            # price ratio at or above: quantity is 10x too small
    erp_dec_lo=0.2,            # price ratio at or below: quantity is 10x too large
    cur_native_share=0.5,      # supplier-material non-EUR share at or above makes EUR-tagged rows suspect
    spend_ratio=4.0,           # opex spend line / material median at or above: SEK booked as EUR
    capex_excess=3.0,          # ERP capex sum / capex register at or above: line-level check runs
    energy_unit_ratio=100.0,   # reading / seasonal expectation at or above: kWh in the MWh column
    energy_spike_ratio=2.0,    # reading / seasonal expectation at or above: meter spike
    fuel_ratio=0.01,           # delivery / site-carrier median at or below: m3 keyed as litres
    ref_kg=500.0,              # kg added on a non-ammonia system at or above: grams in the kg column
    waste_ratio=0.02,          # note / stream median at or below: tonnes keyed as kg
    area_tol=0.05,             # |ln(survey area / declared parcel area)| at or above
    n_lo=0.2,                  # N / crop median at or below (N > 0): decimal slipped left
    n_hi=5.0,                  # N / crop median at or above: decimal slipped right
    yield_ratio=3.0,           # yield / crop median at or above
    leg_share=0.5,             # share of (material, origin) lots with a sea leg at or above
    soil_score=0.5,            # soil detector probability at or above
)


def out(df, table, itype, keycol, score, expl, year="year"):
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLS)
    return pd.DataFrame(dict(table=table, record_key=df[keycol].values, issue_type=itype,
                             year=df[year].astype(int).values, score=np.asarray(df[score], float),
                             explanation=df[expl].values))


def load():
    raw = IO.load_raw(ROOT)
    raw["goo_registry"] = pd.read_csv(ROOT / "data/02_raw_feeds/goo_registry_statement.csv")
    raw["capex"] = pd.read_csv(ROOT / "data/02_raw_feeds/capex_projects.csv")
    raw["draft"] = pd.read_csv(ROOT / "data/05_scenarios/draft_report_summary_2025.csv")
    e = raw["erp"].copy()
    e["year"] = e.posting_date.str[:4].astype(int)
    e["key"] = "erp:" + e.doc_no + ":" + e.line_no.astype(str)
    e["kg"] = np.where(e.uom == "TO", e.quantity * 1000, e.quantity)
    e["eur"] = e.net_amount / e.currency.map(F.FX_PER_EUR)
    raw["erp2"] = e
    return raw


# ---------------------------------------------------------------- ERP
def erp_goods(raw):
    e = raw["erp2"]
    g = e[(e.uom != "EUR") & (e.movement_type == 101) & (e.kg > 0)].copy()   # credit notes never enter
    g["up"] = g.eur / g.kg
    g["ratio"] = g.up / g.groupby(["material_id", "year"]).up.transform("median")
    return g


def erp_duplicates(raw):
    e = raw["erp2"]
    n = e[e.movement_type == 101].sort_values(["posting_date", "doc_no"], kind="stable")
    k = ["supplier_id", "material_id", "quantity", "net_amount"]
    d = n[n.duplicated(k, keep="first")].copy()
    first = n.drop_duplicates(k).set_index(k).doc_no
    d["orig"] = [first.get(tuple(x)) for x in d[k].values]
    d["s"] = 1.0
    d["x"] = "Same supplier, material, quantity and amount as document " + d.orig.astype(str) + "; later posting."
    return out(d, "erp_purchase_lines", "duplicate_record", "key", "s", "x")


def erp_material(raw, th):
    e = raw["erp2"]
    m = raw["materials"].set_index("material_id").erp_name
    d = e[e.material_text != e.material_id.map(m)].copy()
    txt = {v: k for k, v in m.items()}
    d["s"] = 1.0
    d["x"] = ("Material " + d.material_id + " but document text '" + d.material_text + "' belongs to "
              + d.material_text.map(txt).fillna("another material") + ".")
    return out(d, "erp_purchase_lines", "material_mismatch", "key", "s", "x")


def erp_currency_native(raw, th):
    """Supplier-material billed in USD or SEK, yet this receipt is tagged EUR."""
    e = raw["erp2"]
    g = e[(e.uom != "EUR") & (e.movement_type == 101)].copy()
    g["non_eur"] = (g.currency != "EUR").astype(float)
    g["share"] = g.groupby(["supplier_id", "material_id"]).non_eur.transform("mean")
    native = g[g.currency != "EUR"].groupby(["supplier_id", "material_id"]).currency.agg(lambda s: s.mode().iat[0])
    d = g[(g.currency == "EUR") & (g.share >= th["cur_native_share"])].copy()
    d["nat"] = [native.get((a, b), "?") for a, b in zip(d.supplier_id, d.material_id)]
    d["x"] = ("Tagged EUR, but " + (100 * d.share).round(0).astype(int).astype(str) + " % of this supplier-material's receipts are in "
              + d.nat + ".")
    return out(d, "erp_purchase_lines", "currency_error", "key", "share", "x")


def erp_currency_spend(raw, th):
    """SEK amounts booked as EUR on opex spend lines (M900-M903), which have stable monthly amounts."""
    e = raw["erp2"]
    s = e[(e.uom == "EUR") & e.material_id.isin(["M900", "M901", "M902", "M903"])].copy()
    s["r"] = s.net_amount / s.groupby("material_id").net_amount.transform("median")
    d = s[s.r >= th["spend_ratio"]].copy()
    d["x"] = ("Spend line is " + d.r.round(1).astype(str) + "x the material median; about the SEK/EUR rate of "
              + str(F.FX_PER_EUR["SEK"]) + ".")
    return out(d, "erp_purchase_lines", "currency_error", "key", "r", "x")


def erp_currency_capex(raw, th):
    """Capex lines vary too much for a median, so reconcile each project-year with the capex register."""
    e = raw["erp2"]
    c = e[(e.uom == "EUR") & e.material_id.isin(["M950", "M951"]) & e.wbs_element.notna()].copy()
    reg = raw["capex"].groupby(["year", "project"]).capex_eur.sum()
    tot = c.groupby(["year", "wbs_element"]).net_amount.sum()
    rows = []
    fx = F.FX_PER_EUR["SEK"]
    for (y, p), t in tot.items():
        r = reg.get((y, p), np.nan)
        if not np.isfinite(r) or r <= 0 or t / r < th["capex_excess"]:
            continue
        g = c[(c.year == y) & (c.wbs_element == p)]
        # The one line whose conversion from SEK brings the project closest to the register.
        fixed = {i: abs(t - a + a / fx - r) for i, a in zip(g.index, g.net_amount)}
        i = min(fixed, key=fixed.get)
        row = g.loc[i].copy()
        row["r"] = t / r
        row["x"] = (f"Project-year total is {t / r:.1f}x the capex register; converting this line from SEK "
                    f"leaves a gap of {fixed[i] / r:.1%}.")
        rows.append(row)
    return out(pd.DataFrame(rows), "erp_purchase_lines", "currency_error", "key", "r", "x") if rows else out(None, "", "", "", "", "")


def erp_unit(raw, th):
    g = erp_goods(raw)
    d = g[(g.uom == "KG") & (g.ratio >= th["erp_unit_ratio"])].copy()
    d["x"] = "Price per kg is " + d.ratio.round(0).astype(int).astype(str) + "x the material median: tonnes keyed with uom KG."
    return out(d, "erp_purchase_lines", "unit_error", "key", "ratio", "x")


def erp_decimal(raw, th):
    g = erp_goods(raw)
    d = g[((g.ratio >= th["erp_dec_hi"]) & (g.ratio < th["erp_unit_ratio"])) | (g.ratio <= th["erp_dec_lo"])].copy()
    d["x"] = "Price per kg is " + d.ratio.round(3).astype(str) + "x the material median: quantity shifted one decimal place."
    return out(d, "erp_purchase_lines", "decimal_shift", "key", "ratio", "x")


# ---------------------------------------------------------------- energy
def energy_frame(raw):
    em = raw["energy_meter"].copy()
    em["key"] = "energy:" + em.site_id + ":" + em.year.astype(str) + "-" + em.month.map("{:02d}".format) + ":" + em.carrier
    parts = []
    for _, g in em.groupby(["site_id", "carrier"]):
        g = g.sort_values(["year", "month"]).copy()
        pos = g[g.value > 0]
        # Readings far from their +-2 month neighbours stay out of the profile fit. Without this, a calendar month
        # hit in most years learns the error as its seasonal norm (FIXLOG 1).
        vals = pos.value.to_numpy()
        nb = np.array([np.median(np.r_[vals[max(0, i - 2):i], vals[i + 1:i + 3]]) if len(vals) > 1 else vals[i] for i in range(len(vals))])
        rel = vals / nb
        v = pos[(rel < PROFILE_CLEAN) & (rel > 1 / PROFILE_CLEAN)]
        if v.empty:
            v = pos
        months = pd.Index(range(1, 13))
        lvl = v.groupby("year").value.transform("median")
        prof = (v.value / lvl).groupby(v.month).median().reindex(months).fillna(1.0)
        for _ in range(2):   # seasonal profile and yearly level, refined in turn
            lvl_y = (v.value / v.month.map(prof)).groupby(v.year).median()
            prof = (v.value / v.year.map(lvl_y)).groupby(v.month).median().reindex(months).fillna(1.0)
        # A year with no clean reading falls back on its own raw median.
        level = g.year.map(lvl_y).fillna(g.year.map(pos.groupby("year").value.median()))
        g["expected"] = level * g.month.map(prof)
        g["ratio"] = g.value / g.expected
        parts.append(g)
    return pd.concat(parts)


def energy_unit(raw, th):
    f = energy_frame(raw)
    d = f[f.ratio >= th["energy_unit_ratio"]].copy()
    d["x"] = "Reading is " + d.ratio.round(0).astype(int).astype(str) + "x the seasonal expectation: kWh in the MWh column."
    return out(d, "energy_meter_readings", "unit_error", "key", "ratio", "x")


def energy_spike(raw, th):
    f = energy_frame(raw)
    d = f[(f.ratio >= th["energy_spike_ratio"]) & (f.ratio < th["energy_unit_ratio"])].copy()
    d["x"] = "Reading is " + d.ratio.round(2).astype(str) + "x the same month's seasonal expectation."
    return out(d, "energy_meter_readings", "meter_spike", "key", "ratio", "x")


def energy_missing(raw, th):
    em = raw["energy_meter"]
    rows = []
    for (s, c), g in em.groupby(["site_id", "carrier"]):
        t = (g.year * 12 + g.month - 1).astype(int)
        have = set(t)
        for i in range(t.min(), t.max() + 1):   # gaps inside the carrier's active window only
            if i not in have:
                y, m = divmod(i, 12)
                rows.append(dict(key=f"energy:{s}:{y}-{m + 1:02d}:{c}", year=y, s=1.0, x="No reading for this month, inside the carrier's active period."))
    return out(pd.DataFrame(rows), "energy_meter_readings", "missing_record", "key", "s", "x")


# ---------------------------------------------------------------- small feeds
def fuel_unit(raw, th):
    f = raw["fuel_deliveries"].copy()
    f = f[f.unit == "l"]
    f["key"] = "fuel:" + f.delivery_id
    f["r"] = f.quantity / f.groupby(["site_id", "carrier"]).quantity.transform("median")
    d = f[f.r <= th["fuel_ratio"]].copy()
    d["x"] = d.quantity.round(3).astype(str) + " l is " + d.r.round(4).astype(str) + "x the usual delivery: m3 keyed as litres."
    return out(d, "fuel_deliveries", "unit_error", "key", "r", "x")


def system_gas(raw):
    r = raw["refrigerants"].copy()
    r["key"] = "refrigerant:" + r.event_id
    r["sys_gas"] = r.groupby(["site_id", "system"]).refrigerant.transform(lambda s: s.mode().iat[0])
    return r


def ref_unit(raw, th):
    r = system_gas(raw)
    d = r[(r.sys_gas != "R717_ammonia") & (r.kg_added >= th["ref_kg"])].copy()
    d["x"] = d.kg_added.astype(str) + " kg on a " + d.sys_gas + " system: grams in the kg column."
    return out(d, "refrigerant_service_log", "unit_error", "key", "kg_added", "x")


def ref_gas(raw, th):
    r = system_gas(raw)
    d = r[(r.refrigerant == "R717_ammonia") & (r.sys_gas != "R717_ammonia")].copy()
    d["s"] = 1.0
    d["x"] = "Coded ammonia on a system that otherwise runs " + d.sys_gas + "; ammonia has GWP 0, so this hides emissions."
    return out(d, "refrigerant_service_log", "wrong_gas_code", "key", "s", "x")


def goo_mismatch(raw, th):
    g = raw["goo"].copy()
    r = raw["goo_registry"].copy()
    r["vint"] = r.production_period_start.str[:4].astype(int)
    a = r.groupby(["consumption_year", "beneficiary_site"]).agg(reg_mwh=("mwh", "sum"), reg_vint=("vint", "max")).reset_index()
    m = g.merge(a, left_on=["year", "site_id"], right_on=["consumption_year", "beneficiary_site"], how="left")
    m["key"] = "goo:" + m.site_id + ":" + m.year.astype(str)
    bad_v = m.vintage_year != m.reg_vint
    bad_q = (m.mwh_cancelled - m.reg_mwh).abs() > 1.0
    d = m[bad_v | bad_q | m.reg_mwh.isna()].copy()
    d["s"] = 1.0
    d["x"] = ("Internal log: " + d.mwh_cancelled.astype(str) + " MWh, vintage " + d.vintage_year.astype(str)
              + ". Registry: " + d.reg_mwh.round(1).astype(str) + " MWh, vintage " + d.reg_vint.astype("Int64").astype(str) + ".")
    return out(d, "goo_cancellations", "certificate_mismatch", "key", "s", "x")


def waste_unit(raw, th):
    w = raw["waste"].copy()
    w["key"] = "waste:" + w.transfer_note
    w["r"] = w.quantity / w.groupby(["site_id", "waste_stream", "treatment"]).quantity.transform("median")
    d = w[w.r <= th["waste_ratio"]].copy()
    d["x"] = d.quantity.round(1).astype(str) + " kg is " + d.r.round(4).astype(str) + "x the stream median: tonnes keyed as kg."
    return out(d, "waste_transfer_notes", "unit_error", "key", "r", "x")


def travel_dup(raw, th):
    t = raw["travel"].copy()
    t["key"] = "travel:" + t.booking_id
    k = ["traveller_id", "travel_date", "route", "pkm", "nights"]
    d = t[t.duplicated(k, keep="first")].copy()    # file order, as the task defines it
    first = t.drop_duplicates(k).set_index(k).booking_id
    d["orig"] = [first.get(tuple(x)) for x in d[k].values]
    d["s"] = 1.0
    d["x"] = "Same traveller, date, route, distance and nights as booking " + d.orig.astype(str) + ", earlier in the file."
    return out(d, "travel_bookings", "duplicate_record", "key", "s", "x")


def ship_leg(raw, th):
    s = raw["shipments"]
    s = s[s.direction == "inbound"].copy()
    s["ref_doc"] = s.ref_doc.astype(str)
    road = {"EF-TKM-TRUCK", "EF-TKM-TRUCK-REEFER"}
    legs = s.groupby("ref_doc").ef_id.apply(set)
    yr = s.groupby("ref_doc").year.first()
    e = raw["erp2"]
    e = e[e.doc_no.isin(legs.index)].drop_duplicates("doc_no").copy()
    e["legs"] = e.doc_no.map(legs)
    e["sea"] = e.legs.map(lambda v: next(iter(v - road), None))
    e["has_sea"] = e.sea.notna().astype(float)
    e["share"] = e.groupby(["material_id", "origin_country"]).has_sea.transform("mean")
    exp = e[e.sea.notna()].groupby(["material_id", "origin_country"]).sea.agg(lambda v: v.mode().iat[0])
    d = e[e.sea.isna() & (e.share >= th["leg_share"])].copy()
    d["ef"] = [exp.get((a, b)) for a, b in zip(d.material_id, d.origin_country)]
    d["key"] = "ship:" + d.doc_no + ":" + d.ef
    d["yr"] = d.doc_no.map(yr)
    d["x"] = ("Road leg only, but " + (100 * d.share).round(1).astype(str) + " % of " + d.material_id + " lots from "
              + d.origin_country + " also carry " + d.ef + ".")
    return out(d, "shipments", "missing_leg", "key", "share", "x", year="yr")


# ---------------------------------------------------------------- farm survey
def survey_frame(raw):
    sv = raw["farm_survey"].copy()
    sv["key"] = "farm_survey:" + sv.survey_id
    par = raw["parcels"].set_index("parcel_id")
    ch = raw["crop_history"]
    ch = ch[ch.status == "declared"].join(par[["area_ha"]], on="parcel_id")
    g = ch.groupby(["farm_id", "crop", "year"]).area_ha.sum().rename("parcel_ha").reset_index()
    return sv.merge(g, on=["farm_id", "crop", "year"], how="left")


def survey_area(raw, th):
    s = survey_frame(raw)
    s["d"] = np.log(s.area_ha / s.parcel_ha).abs()
    d = s[s.d >= th["area_tol"]].copy()
    d["x"] = ("Survey says " + d.area_ha.astype(str) + " ha; declared parcels for this crop and year sum to "
              + d.parcel_ha.round(2).astype(str) + " ha.")
    return out(d, "farm_survey", "area_mismatch", "key", "d", "x")


def survey_n(raw, th):
    s = survey_frame(raw)
    med = s[s.n_mineral_kg_ha > 0].groupby("crop").n_mineral_kg_ha.median()
    s["r"] = s.n_mineral_kg_ha / s.crop.map(med)
    d = s[(s.n_mineral_kg_ha > 0) & ((s.r <= th["n_lo"]) | (s.r >= th["n_hi"]))].copy()   # N = 0 is legitimate
    d["x"] = "Mineral N " + d.n_mineral_kg_ha.astype(str) + " kg/ha is " + d.r.round(2).astype(str) + "x the crop median: decimal shift."
    return out(d, "farm_survey", "decimal_shift", "key", "r", "x")


def survey_yield(raw, th):
    s = survey_frame(raw)
    s["r"] = s.yield_t_ha / s.groupby("crop").yield_t_ha.transform("median")
    d = s[s.r >= th["yield_ratio"]].copy()
    d["x"] = "Yield " + d.yield_t_ha.astype(str) + " t/ha is " + d.r.round(1).astype(str) + "x the crop median."
    return out(d, "farm_survey", "outlier_implausible", "key", "r", "x")


# ---------------------------------------------------------------- 2025-only tables: no dev labels, so no tuning
def pcf_checks(raw, th=None):
    p = raw["pcfs"].copy()
    p["key"] = "pcf:" + p.supplier_id + ":" + p.material_id + ":" + p.year.astype(str)
    m = raw["materials"].set_index("material_id").default_ef_id
    ef = raw["ef_library"].set_index("ef_id").kgco2e_per_unit
    p["lib"] = p.material_id.map(m).map(ef)
    p["r"] = p.value / p.lib
    u = p[p.r >= 100].copy()
    u["x"] = u.value.astype(str) + " per kilogram is " + u.r.round(0).astype(int).astype(str) + "x the library factor: per-tonne value declared per kg."
    # Valid for year Y only if the reference period covers all of Y (METHODOLOGY section 4).
    y0 = pd.to_datetime(p.year.astype(str) + "-01-01")
    y1 = pd.to_datetime((p.year + 1).astype(str) + "-01-01")
    st = p[(pd.to_datetime(p.ref_start) > y0) | (pd.to_datetime(p.ref_end) < y1)].copy()
    st["x"] = "Reference period " + st.ref_start + " to " + st.ref_end + " does not cover " + st.year.astype(str) + "."
    return pd.concat([out(u, "supplier_pcfs", "pcf_unit_error", "key", "r", "x"),
                      out(st, "supplier_pcfs", "pcf_stale_period", "key", "year", "x")], ignore_index=True)


def farm_coords(raw, th=None):
    f = raw["farm_registry"].copy()
    c = raw["parcels"].groupby("farm_id")[["lat", "lon"]].mean().rename(columns=dict(lat="plat", lon="plon"))
    f = f.join(c, on="farm_id")
    straight = np.hypot(f.lat - f.plat, f.lon - f.plon)
    swapped = np.hypot(f.lon - f.plat, f.lat - f.plon)
    d = f[(straight > 1) & (swapped < 0.1)].copy()
    d["key"] = "farm:" + d.farm_id
    d["year"] = 2025
    d["s"] = 1.0
    d["x"] = "Registry lat/lon " + d.lat.astype(str) + "/" + d.lon.astype(str) + " match the farm's parcels only when swapped."
    return out(d, "farm_registry", "coordinate_swap", "key", "s", "x")


def commute_checks(raw, th=None):
    c = raw["commuting"].copy()
    c["key"] = "commute:" + c.response_id
    c["year"] = 2025
    u = c[c.one_way_km >= 1000].copy()
    u["x"] = u.one_way_km.astype(str) + " km one way: metres in the km column."
    ok = {"car", "carpool", "bus", "train", "bike_walk", "ev_car"}
    v = c[~c["mode"].isin(ok)].copy()
    v["s"] = 1.0
    v["x"] = "Mode '" + v["mode"] + "' is not a survey category, so the factor lookup misses it."
    return pd.concat([out(u, "commuting_survey", "unit_error", "key", "one_way_km", "x"),
                      out(v, "commuting_survey", "mode_mislabel", "key", "s", "x")], ignore_index=True)


def report_check(raw, th=None):
    d = raw["draft"].set_index("line").tco2e
    parts = int(d["scope1"] + d["scope2_market"] + d["scope3"])
    total = int(d["total_market_based"])
    if parts == total:
        return out(None, "", "", "", "", "")
    implied = total - int(d["scope1"]) - int(d["scope2_market"])
    s3 = str(int(d["scope3"]))
    swap = len(s3) == len(str(implied)) and sorted(s3) == sorted(str(implied))
    line = "scope3" if swap else "total_market_based"
    x = (f"Lines sum to {parts:,} but the total says {total:,}. Scope 3 of {implied:,} would reconcile it"
         + (", and that is the printed value with two digits transposed." if swap else "."))
    df = pd.DataFrame([dict(key=f"report:2025:{line}", year=2025, s=1.0, x=x)])
    return out(df, "draft_report_summary", "total_mismatch", "key", "s", "x")


# ---------------------------------------------------------------- soil
SOIL_FEATURES = ["row_map", "row_lowclay", "farm_map", "row_report"]   # ge30 and parcel facts failed in CV: see FIXLOG
LOW_CLAY = 30.0   # parcels mapped 'clay' under this clay % contradict their own class
SOIL_STEP = 0.30  # the task's own labelling rule: at least 30 % of the crop area on organic soil


def soil_frame(raw):
    """One row per survey row, with public soil evidence. No labels."""
    par = raw["parcels"].copy()
    par["is_org"] = par.soil_class_soilmap == "organic"
    par["is_lowclay"] = (par.soil_class_soilmap == "clay") & (par.clay_pct_soilmap < LOW_CLAY)
    fa = par.assign(o=par.area_ha * par.is_org).groupby("farm_id")[["o", "area_ha"]].sum()
    farm_map = fa.o / fa.area_ha
    ch = raw["crop_history"]
    ch = ch[ch.status == "declared"].merge(par[["parcel_id", "area_ha", "is_org", "is_lowclay"]], on="parcel_id")
    sv = raw["farm_survey"][["survey_id", "farm_id", "crop", "year", "soil_type_reported"]].copy()
    sv["key"] = "farm_survey:" + sv.survey_id
    pr = ch.merge(sv, on=["farm_id", "crop", "year"])
    rep_parcels = set(pr[pr.soil_type_reported == "Organic soil"].parcel_id)
    pr["on_rep"] = pr.parcel_id.isin(rep_parcels)
    pr["ha"] = pr.area_ha
    pr["ha_org"] = pr.ha * pr.is_org
    pr["ha_low"] = pr.ha * pr.is_lowclay
    pr["ha_rep"] = pr.ha * pr.on_rep
    a = pr.groupby("key")[["ha", "ha_org", "ha_low", "ha_rep"]].sum()
    f = sv.join(a, on="key")
    f["row_map"] = f.ha_org / f.ha
    f["row_lowclay"] = f.ha_low / f.ha
    f["row_report"] = f.ha_rep / f.ha
    f["farm_map"] = f.farm_id.map(farm_map)
    f["ge30"] = ((f.row_map + f.row_lowclay) >= SOIL_STEP).astype(float)
    return f, pr


def parcel_truth(pr, soil_labels, dev_years):
    """Parcel-level soil facts implied by labels of the given years only.

    A labelled row's share equals the area share of some subset of its parcels; a unique subset fixes them.
    An unlabelled 'Mineral soil' row in a labelled year has share < 0.3, so any parcel above 30 % of it is mineral.
    """
    from itertools import combinations
    known = {}
    pos = dict(zip(soil_labels.record_key, soil_labels.share))
    rows = pr[pr.year.isin(dev_years)]
    for k, g in rows.groupby("key"):
        tot = g.ha.sum()
        if g.soil_type_reported.iat[0] != "Mineral soil":
            continue
        if k in pos:
            ids, ar = list(g.parcel_id), list(g.ha / tot)
            hits = []
            for n in range(1, len(ids) + 1):
                for c in combinations(range(len(ids)), n):
                    if abs(sum(ar[i] for i in c) - pos[k]) <= 0.0051:
                        hits.append(c)
            if len(hits) == 1:
                for i, p in enumerate(ids):
                    known[p] = i in hits[0]
        else:
            for p, a in zip(g.parcel_id, g.ha / tot):
                if a >= 0.3 + 1e-9:
                    known.setdefault(p, False)
    return known


def add_known(f, pr, known):
    """Known organic and known mineral area shares per survey row."""
    z = pr.assign(kn=pr.parcel_id.map(known))
    z["ko"] = np.where(z.kn == True, z.ha, 0.0)    # noqa: E712
    z["km"] = np.where(z.kn == False, z.ha, 0.0)   # noqa: E712
    a = z.groupby("key")[["ko", "km", "ha"]].sum()
    f = f.copy()
    f["known_org"] = f.key.map(a.ko / a.ha).fillna(0.0)
    f["known_min"] = f.key.map(a.km / a.ha).fillna(0.0)
    return f


def fit_logit(X, y, ridge=1.0, iters=50):
    """Ridge logistic regression by Newton steps; the intercept is not penalised."""
    A = np.c_[np.ones(len(X)), X]
    assert np.isfinite(A).all()
    w = np.zeros(A.shape[1])
    P = np.eye(A.shape[1]) * ridge
    P[0, 0] = 0
    # numpy on Apple Accelerate raises false matmul warnings on finite input; the asserts carry the real check.
    with np.errstate(all="ignore"):
        for _ in range(iters):
            p = 1 / (1 + np.exp(-A @ w))
            g = A.T @ (p - y) + P @ w
            H = (A * (p * (1 - p))[:, None]).T @ A + P
            w = w - np.linalg.solve(H + 1e-9 * np.eye(len(w)), g)
    assert np.isfinite(w).all()
    return w


def soil_score(f, w, feats=SOIL_FEATURES):
    A = np.c_[np.ones(len(f)), f[feats].values]
    with np.errstate(all="ignore"):
        p = 1 / (1 + np.exp(-A @ w))
    assert np.isfinite(p).all()
    return p


def soil_flags(f, w, t, feats=SOIL_FEATURES, use_known=True):
    """Mineral-reported rows above t. Other-year parcel facts override the score when they settle the row."""
    m = f[f.soil_type_reported == "Mineral soil"].copy()
    m["p"] = soil_score(m, w, feats)
    flag = m.p >= t
    if use_known:
        flag = (flag & ~(m.known_min > 0.7)) | (m.known_org >= 0.3)
    d = m[flag].copy()
    d["p"] = np.where(d.known_org >= 0.3, np.maximum(d.p, 0.95), d.p)
    d["x"] = ("Reported mineral soil. Soil-map organic share " + d.row_map.round(2).astype(str) + ", low-clay 'clay' parcels "
              + d.row_lowclay.round(2).astype(str) + ", farm organic share " + d.farm_map.round(2).astype(str)
              + ", area on parcels reported organic in other rows " + d.row_report.round(2).astype(str) + ".")
    return out(d, "farm_survey", "soil_misreport", "key", "p", "x")


# Everything tuned or tested on dev labels. Soil is handled separately because it has a fitted score.
TUNED = [erp_material, erp_currency_native, erp_currency_spend, erp_currency_capex, erp_unit, erp_decimal,
         energy_unit, energy_spike, energy_missing, fuel_unit, ref_unit, ref_gas, goo_mismatch, waste_unit,
         travel_dup, ship_leg, survey_area, survey_n, survey_yield]
UNLABELLED = [pcf_checks, farm_coords, commute_checks, report_check]
PRIORITY = {"duplicate_record": 0, "currency_error": 1, "material_mismatch": 2, "unit_error": 3, "decimal_shift": 4}


def run_rules(raw, th):
    parts = [erp_duplicates(raw)] + [d(raw, th) for d in TUNED]
    r = pd.concat([p for p in parts if len(p)], ignore_index=True)
    r["pri"] = r.issue_type.map(PRIORITY).fillna(9)
    return r.sort_values("pri", kind="stable").drop_duplicates("record_key").drop(columns="pri").reset_index(drop=True)


def labels():
    k = pd.read_csv(ROOT / "tasks/dev/A1_dev_issue_labels_2023_2024.csv")
    s = k[k.issue_type == "soil_misreport"].copy()
    s["share"] = s.true_value.str.extract(r"([\d.]+)")[0].astype(float)
    return k, s

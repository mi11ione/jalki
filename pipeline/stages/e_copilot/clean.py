"""Cleaning layer: raw feeds -> canonical tables for the reference calculator.
Every change is appended to LOG as (table, record_key, year, issue, field, old, new, reason) so the audit trail is data.
Rules use only raw data, master data and the documented method. Dev labels are never read here."""
from __future__ import annotations
from ccn_paths import PACKAGE, stage_dir
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = PACKAGE
sys.path.insert(0, str(ROOT / "tools"))
from ccn_tools import io as IO, factors as F  # noqa: E402

LOG: list = []


def log(table, key, year, issue, field, old, new, reason):
    LOG.append(dict(table=table, record_key=key, year=int(year), issue_type=issue, field=field, old=old, new=new, reason=reason))


# ---------------------------------------------------------------- energy
def clean_energy(em: pd.DataFrame) -> pd.DataFrame:
    em = em.copy()
    em["v"] = em.value.astype(float)
    # pass 1: kWh in MWh column
    for (s, c, y), g in em.groupby(["site_id", "carrier", "year"]):
        med = g.v[g.v > 0].median()
        for i, r in g.iterrows():
            if med > 0 and r.v > 200 * med:
                em.loc[i, "v"] = r.v / 1000
                log("energy_meter_readings", f"energy:{s}:{y}-{int(r.month):02d}:{c}", y, "unit_error", "value", r.v, r.v / 1000, "kWh reported in MWh column (>200x series median)")
    # pass 2: spikes -> blank, then gap fill together with missing months
    for (s, c, y), g in em.groupby(["site_id", "carrier", "year"]):
        med = g.v[g.v > 0].median()
        for i, r in g.iterrows():
            if med > 0 and len(g) >= 8 and r.v > 2.4 * med:
                log("energy_meter_readings", f"energy:{s}:{y}-{int(r.month):02d}:{c}", y, "meter_spike", "value", r.v, None, ">2.4x series median; replaced by seasonal estimate")
                em.loc[i, "v"] = np.nan
    pv = em.dropna(subset=["v"]).set_index(["site_id", "carrier", "year", "month"]).v.unstack("month")
    pv = pv.reindex(columns=range(1, 13))
    pv = pv.reindex(em.groupby(["site_id", "carrier", "year"]).size().index)
    rows = []
    for (s, c, y), r in pv.iterrows():
        n_obs = int(em[(em.site_id == s) & (em.carrier == c) & (em.year == y)].shape[0])
        if n_obs < 8 and r.notna().sum() < 8:
            continue            # partial-year series (S-BJU gas, biogas start-up, steam end): no fill
        for m in range(1, 13):
            if m in r.index and pd.notna(r[m]):
                continue
            est = None
            for y2 in (y - 1, y + 1, y - 2):
                if (s, c, y2) in pv.index:
                    o = pv.loc[(s, c, y2)]
                    common = [k for k in pv.columns if pd.notna(o.get(k)) and pd.notna(r.get(k))]
                    if pd.notna(o.get(m)) and len(common) >= 6:
                        est = o[m] * r[common].sum() / o[common].sum()
                        break
            if est is None:
                est = r.median()
            rows.append(dict(site_id=s, year=y, month=m, carrier=c, v=est))
            log("energy_meter_readings", f"energy:{s}:{y}-{m:02d}:{c}", y, "missing_record", "value", None, round(float(est), 3), "gap filled: same month of adjacent year x level ratio")
    em = em.dropna(subset=["v"])
    out = pd.concat([em[["site_id", "year", "month", "carrier", "v"]], pd.DataFrame(rows)], ignore_index=True)
    return out.rename(columns={"v": "mwh"})


# ---------------------------------------------------------------- fuels
def clean_fuels(fd: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    fd = fd.copy()
    for i, r in fd[(fd.unit == "l") & (fd.quantity < 1000)].iterrows():
        fd.loc[i, "quantity"] = r.quantity * 1000
        log("fuel_deliveries", f"fuel:{r.delivery_id}", r.year, "unit_error", "quantity", r.quantity, r.quantity * 1000, "m3 keyed as litres (<1000 l against 10,000+ l lots)")
    ncv = {"lng": F.NCV["lng_t"], "lpg": F.NCV["lpg_t"], "light_fuel_oil": F.NCV["lfo_l"], "diesel": F.NCV["diesel_l"]}
    y = fd.groupby(["site_id", "carrier", "year"]).quantity.sum().reset_index()
    y = y.merge(st[["site_id", "carrier", "year", "stock_change"]], on=["site_id", "carrier", "year"], how="left").fillna({"stock_change": 0})
    y["native_consumed"] = y.quantity - y.stock_change
    y["mwh"] = y.native_consumed * y.carrier.map(ncv)
    y["month"] = 0
    return y


# ---------------------------------------------------------------- GoO
def clean_goo(reg: pd.DataFrame, internal: pd.DataFrame) -> pd.DataFrame:
    r = reg.copy()
    r["vintage_year"] = r.production_period_start.str[:4].astype(int)
    g = r.groupby(["consumption_year", "beneficiary_site", "vintage_year"]).mwh.sum().reset_index()
    g.columns = ["year", "site_id", "vintage_year", "mwh_cancelled"]
    m = internal.merge(g, on=["year", "site_id"], how="outer", suffixes=("_log", ""))
    for _, x in m.iterrows():
        if pd.isna(x.mwh_cancelled_log) or pd.isna(x.mwh_cancelled):
            log("goo_cancellations", f"goo:{x.site_id}:{int(x.year)}", x.year, "certificate_mismatch", "mwh", x.mwh_cancelled_log, x.mwh_cancelled, "present in only one of log/registry; registry is authoritative")
        elif abs(x.mwh_cancelled_log - x.mwh_cancelled) > 1 or x.vintage_year_log != x.vintage_year:
            log("goo_cancellations", f"goo:{x.site_id}:{int(x.year)}", x.year, "certificate_mismatch", "mwh/vintage", f"{x.mwh_cancelled_log}/{x.vintage_year_log}", f"{x.mwh_cancelled}/{x.vintage_year}", "log differs from registry; registry is authoritative")
    return g


# ---------------------------------------------------------------- refrigerants
def clean_refrigerants(rf: pd.DataFrame) -> pd.DataFrame:
    rf = rf.copy()
    gases = rf[rf.refrigerant != "R717_ammonia"].groupby(["site_id", "system"]).refrigerant.agg(lambda s: s.mode().iloc[0])
    amm_sys = rf.groupby(["site_id", "system"]).refrigerant.apply(lambda s: (s == "R717_ammonia").mean())
    for i, r in rf.iterrows():
        if r.refrigerant == "R717_ammonia" and (r.site_id, r.system) in gases.index and amm_sys[(r.site_id, r.system)] < 0.5:
            new = gases[(r.site_id, r.system)]
            rf.loc[i, "refrigerant"] = new
            log("refrigerant_service_log", f"refrigerant:{r.event_id}", r.year, "wrong_gas_code", "refrigerant", r.refrigerant, new, "ammonia code on an HFC system; system's own gas used")
        if r.refrigerant != "R717_ammonia" and r.kg_added >= 1000:
            rf.loc[i, "kg_added"] = r.kg_added / 1000
            log("refrigerant_service_log", f"refrigerant:{r.event_id}", r.year, "unit_error", "kg_added", r.kg_added, r.kg_added / 1000, "grams keyed as kg (HFC charge of tonnes is impossible on these systems)")
    return rf


# ---------------------------------------------------------------- ERP
def clean_erp(erp: pd.DataFrame, sup: pd.DataFrame, ship: pd.DataFrame, capex: pd.DataFrame | None = None) -> pd.DataFrame:
    e = erp.copy()
    e["year"] = e.posting_date.str[:4].astype(int)
    e["key"] = "erp:" + e.doc_no + ":" + e.line_no.astype(str)
    e["qty_kg"] = np.where(e.uom == "TO", e.quantity * 1000, np.where(e.uom == "KG", e.quantity, 0.0))
    e["cur"] = e.currency
    e["drop"] = False
    # duplicates: same supplier/material/qty/amount/lot on a later document among receipts
    rec = e[(e.movement_type == 101)].sort_values(["posting_date", "doc_no"])
    goods = rec[rec.uom != "EUR"]
    dcols = ["supplier_id", "material_id", "quantity", "net_amount", "plant"]
    d = goods[goods.duplicated(dcols, keep=False)]
    for _, g in d.groupby(dcols):
        g = g.sort_values("doc_no")          # 45... original first, 51... repost later
        for i, r in g.iloc[1:].iterrows():
            e.loc[i, "drop"] = True
            log("erp_purchase_lines", r.key, r.year, "duplicate_record", "*", r.quantity, 0, f"same supplier/material/qty/amount as {g.iloc[0].key}")
    # material mismatch: supplier master says one material, line says another
    sm = sup.groupby("supplier_id").material_id.agg(lambda s: set(s))
    for i, r in e[(~e.supplier_id.str.startswith(("F", "S0"))) & (e.uom != "EUR")].iterrows():
        allowed = sm.get(r.supplier_id, None)
        if allowed and r.material_id not in allowed and len(allowed) == 1:
            new = next(iter(allowed))
            log("erp_purchase_lines", r.key, r.year, "material_mismatch", "material_id", r.material_id, new, "line material differs from the supplier's only material in supplier master")
            e.loc[i, "material_id"] = new
    # quantity check against the independent logistics record: the leg tonnes of the same document
    tship = ship[ship.direction == "inbound"].groupby("ref_doc").t.max()
    e["t_ship"] = e.doc_no.map(tship)
    x = e[(e.uom != "EUR") & e.t_ship.notna() & (e.movement_type == 101) & (~e["drop"])]
    shipfixed = set()
    for i, r in x.iterrows():
        q = r.qty_kg / 1000 / r.t_ship
        if abs(q - 1) > 0.02:
            issue = "unit_error" if q < 0.01 else "decimal_shift"
            log("erp_purchase_lines", r.key, r.year, issue, "quantity", r.quantity, r.t_ship * 1000, f"ERP quantity is {q:.3g}x the shipment tonnes of the same document")
            e.loc[i, "qty_kg"] = r.t_ship * 1000
            shipfixed.add(i)
    # unit price tests, on non-dropped goods lines not already fixed from shipments
    g = e[(e.uom != "EUR") & (e.qty_kg != 0) & (~e["drop"])].copy()
    fx = g.currency.map(F.FX_PER_EUR).fillna(1.0)
    g["up"] = g.net_amount / fx / g.qty_kg
    base = g[(g.movement_type == 101)]
    med = base.groupby("material_id").up.median()
    g["ratio"] = g.up / g.material_id.map(med)
    for i, r in g.iterrows():
        q = r.ratio
        if i in shipfixed:
            continue
        if q > 300:
            e.loc[i, "qty_kg"] = r.qty_kg * 1000
            log("erp_purchase_lines", r.key, r.year, "unit_error", "quantity", r.quantity, r.quantity * 1000, "tonnes keyed with uom KG (unit price ~1000x material median)")
        elif q < 0.13 and q > 0.06:
            e.loc[i, "qty_kg"] = r.qty_kg / 10
            log("erp_purchase_lines", r.key, r.year, "decimal_shift", "quantity", r.quantity, r.quantity / 10, "quantity 10x too large (unit price ~0.1x material median)")
        elif 6 < q < 16 and r.currency == "EUR":
            e.loc[i, "cur"] = "SEK"
            log("erp_purchase_lines", r.key, r.year, "currency_error", "currency", "EUR", "SEK", "SEK amount booked as EUR (unit price ~11x material median)")
    # spend lines (uom EUR): duplicates, then SEK booked as EUR
    sp = e[(e.uom == "EUR") & (~e["drop"])].sort_values(["posting_date", "doc_no"])
    for _, g in sp[sp.duplicated(["supplier_id", "material_id", "net_amount"], keep=False)].groupby(["supplier_id", "material_id", "net_amount"]):
        for i, r in g.iloc[1:].iterrows():
            e.loc[i, "drop"] = True
            log("erp_purchase_lines", r.key, r.year, "duplicate_record", "*", r.net_amount, 0, f"same supplier/material/amount as {g.iloc[0].key}")
    sv = e[(e.uom == "EUR") & (~e["drop"]) & e.material_id.isin(["M900", "M901", "M902", "M903"])]
    medy = sv.groupby(["material_id", "year"]).net_amount.transform("median")
    for i, r in sv[sv.net_amount > 4 * medy].iterrows():
        e.loc[i, "cur"] = "SEK"
        log("erp_purchase_lines", r.key, r.year, "currency_error", "currency", "EUR", "SEK", "monthly service invoice ~11x the material's median month: SEK booked as EUR")
    if capex is not None:
        cx = e[(e.uom == "EUR") & (~e["drop"]) & e.material_id.isin(["M950", "M951"])]
        plan = capex.groupby(["year", "project"]).capex_eur.sum()
        for (y, w), g in cx.groupby(["year", "wbs_element"]):
            if (y, w) in plan.index and g.net_amount.sum() > 1.5 * plan[(y, w)]:
                i = g.net_amount.idxmax()
                r = e.loc[i]
                e.loc[i, "cur"] = "SEK"
                log("erp_purchase_lines", r.key, r.year, "currency_error", "currency", "EUR", "SEK", f"WBS total {g.net_amount.sum():.0f} exceeds capex_projects {plan[(y, w)]:.0f}; largest line is SEK booked as EUR")
    e["amount_eur"] = e.net_amount / e.cur.map(F.FX_PER_EUR).fillna(1.0)
    return e[~e["drop"]].copy()


# ---------------------------------------------------------------- waste / travel
def clean_waste(w: pd.DataFrame) -> pd.DataFrame:
    w = w.copy()
    med = w.groupby(["site_id", "waste_stream"]).quantity.transform("median")
    for i, r in w[w.quantity < med / 100].iterrows():
        w.loc[i, "quantity"] = r.quantity * 1000
        log("waste_transfer_notes", f"waste:{r.transfer_note}", r.year, "unit_error", "quantity", r.quantity, r.quantity * 1000, "tonnes keyed as kg (<1% of stream median)")
    w["t"] = w.quantity / 1000
    efmap = {"anaerobic_digestion": "EF-WASTE-BIO-AD", "composting": "EF-WASTE-BIO-COMPOST", "incineration": "EF-WASTE-MIXED-INC",
             "recycling": "EF-WASTE-RECYCLE", "landfill_codigestion": "EF-WASTE-SPENTEARTH"}
    w["ef_id"] = w.treatment.map(efmap)
    w.loc[w.waste_stream == "plastic_waste", "ef_id"] = "EF-WASTE-PLASTIC-INC"
    return w


def clean_travel(t: pd.DataFrame) -> pd.DataFrame:
    cols = ["traveller_id", "travel_date", "route", "pkm", "nights"]
    d = t[t.duplicated(cols, keep="first")]
    for _, r in d.iterrows():
        log("travel_bookings", f"travel:{r.booking_id}", r.year, "duplicate_record", "*", r.pkm, 0, "same traveller, date, route, distance, nights as an earlier row")
    return t[~t.duplicated(cols, keep="first")].copy()


# ---------------------------------------------------------------- PCF
def valid_pcfs(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    p["ok_period"] = (p.ref_start.str[:4].astype(int) <= p.year) & (p.ref_end > p.year.astype(str) + "-12-31")
    p["ok_unit"] = (p.value < 50) & (p.declared_unit == "kilogram")
    for _, r in p[~p.ok_period].iterrows():
        log("supplier_pcfs", f"pcf:{r.supplier_id}:{r.material_id}:{r.year}", r.year, "pcf_stale_period", "referencePeriod", f"{r.ref_start}..{r.ref_end}", "library default", "reference period does not cover the year; METHODOLOGY s4 falls back to material default")
    for _, r in p[~p.ok_unit].iterrows():
        log("supplier_pcfs", f"pcf:{r.supplier_id}:{r.material_id}:{r.year}", r.year, "pcf_unit_error", "pCfExcludingBiogenic", r.value, "library default", "value is per tonne, not per declared kg; METHODOLOGY s4 falls back to material default")
    return p[p.ok_period & p.ok_unit].rename(columns={"value": "kgco2e_per_kg"})[["year", "supplier_id", "material_id", "kgco2e_per_kg"]]

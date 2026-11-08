"""Label-free cleaning rules (raw -> clean). Every correction is appended to a log with
table, record_key, field, old, new, rule and reason. Rules were designed by inspecting the raw
feeds and are checked against the public 2023/2024 A1 labels in rule_check.py (precision/recall);
the labels are never read here."""
import copy
from collections import defaultdict
import lib
from ccn_tools import factors as F

MODE_MAP = {"Car": "car", "henkilöauto": "car", "auto": "car", "linja-auto": "bus"}
SEA_KM = None  # filled from data: fixed sea/ro-pax distance per (material, origin, ef_id)


def clean(raw0):
    raw = copy.deepcopy(raw0)
    log = []

    def note(table, key, field, old, new, rule, reason):
        log.append(dict(table=table, record_key=key, field=field, old=old, new=new, rule=rule, reason=reason))

    mm = {m["material_id"]: m for m in raw["materials"]}
    name2id = {m["erp_name"]: m["material_id"] for m in raw["materials"]}

    # ---------------- ERP
    erp = raw["erp"]
    for e in erp:
        e["key"] = f"erp:{e['doc_no']}:{int(e['line_no'])}"
    # R-ERP-1 material_mismatch: material text on the document names another master material
    for e in erp:
        t = name2id.get(e["material_text"])
        if t and t != e["material_id"]:
            note("erp", e["key"], "material_id", e["material_id"], t, "R-ERP-1",
                 f"material text '{e['material_text']}' is the master text of {t}")
            e["material_id"] = t
    # R-ERP-2 duplicate posting: same supplier, material, quantity, amount, currency as an earlier receipt
    seen, keep = set(), []
    for e in erp:
        k = (e["supplier_id"], e["material_id"], e["quantity"], e["uom"], e["net_amount"], e["currency"], int(e["movement_type"]))
        if int(e["movement_type"]) == 101 and k in seen:
            note("erp", e["key"], "*", "row", "dropped", "R-ERP-2", "duplicate posting of an earlier receipt (same supplier, material, qty, amount)")
            continue
        seen.add(k)
        keep.append(e)
    erp = keep
    # unit price per kg vs material median (receipts in KG/TO)
    def qkg(e):
        return e["quantity"] * 1000 if e["uom"] == "TO" else e["quantity"]
    def eur(e):
        return e["net_amount"] / F.FX_PER_EUR.get(e["currency"], 1.0)
    prices = defaultdict(list)
    for e in erp:
        if e["uom"] in ("KG", "TO") and int(e["movement_type"]) == 101 and qkg(e) > 0:
            prices[e["material_id"]].append(eur(e) / qkg(e))
    med = {m: lib.median(v) for m, v in prices.items()}
    # R-ERP-0 currency label error: line currency differs from the supplier's usual currency and the price
    # is normal once read in the usual currency (must run before the decimal-shift rule: SEK/EUR = 11.4 ~ x10)
    curs = defaultdict(lambda: defaultdict(int))
    for e in erp:
        curs[e["supplier_id"]][e["currency"]] += 1
    for e in erp:
        if e["uom"] not in ("KG", "TO") or int(e["movement_type"]) != 101 or e["quantity"] <= 0:
            continue
        usual = max(curs[e["supplier_id"]], key=curs[e["supplier_id"]].get)
        if e["currency"] != usual:
            r_now = eur(e) / qkg(e) / med[e["material_id"]]
            r_usual = e["net_amount"] / F.FX_PER_EUR[usual] / qkg(e) / med[e["material_id"]]
            if abs(r_usual - 1) < abs(r_now - 1) and 0.5 < r_usual < 2:
                note("erp", e["key"], "currency", e["currency"], usual, "R-ERP-0",
                     f"supplier invoices in {usual}; price is {r_now:.2f}x median as {e['currency']} but {r_usual:.2f}x as {usual}: currency label error")
                e["currency"] = usual
    for e in erp:
        if e["uom"] != "KG" or int(e["movement_type"]) != 101 or e["quantity"] <= 0:
            continue
        r = eur(e) / qkg(e) / med[e["material_id"]]
        if r > 300:   # R-ERP-3 tonnes keyed with uom KG
            note("erp", e["key"], "quantity", e["quantity"], e["quantity"] * 1000, "R-ERP-3", f"unit price {r:.0f}x material median: tonnes keyed as KG")
            e["quantity"] *= 1000
        elif 6.5 < r < 15:   # R-ERP-4 decimal shift (quantity /10)
            note("erp", e["key"], "quantity", e["quantity"], e["quantity"] * 10, "R-ERP-4", f"unit price {r:.1f}x material median: decimal shift")
            e["quantity"] *= 10
        elif 1 / 15 < r < 1 / 6.5:   # quantity x10
            note("erp", e["key"], "quantity", e["quantity"], e["quantity"] / 10, "R-ERP-4", f"unit price {r:.2f}x material median: decimal shift")
            e["quantity"] /= 10
    # R-ERP-5 SEK amount booked as EUR on spend lines (services/capex): amount > 5x material median
    spend = defaultdict(list)
    for e in erp:
        if e["uom"] == "EUR":
            spend[(e["material_id"], e["posting_date"][:4])].append(e["net_amount"])
    for e in erp:
        if e["uom"] == "EUR" and e["currency"] == "EUR":
            m = lib.median(spend[(e["material_id"], e["posting_date"][:4])])
            if e["net_amount"] > 5 * m:
                new = round(e["net_amount"] / F.FX_PER_EUR["SEK"], 2)
                note("erp", e["key"], "net_amount", e["net_amount"], new, "R-ERP-5",
                     f"spend line {e['net_amount']/m:.1f}x the material-year median, ~SEK/EUR rate {F.FX_PER_EUR['SEK']}: SEK amount booked as EUR")
                e["net_amount"] = new
    raw["erp"] = erp

    # ---------------- energy meters
    em = raw["energy_meter"]
    series = defaultdict(dict)
    for m in em:
        m["key"] = f"energy:{m['site_id']}:{int(m['year'])}-{int(m['month']):02d}:{m['carrier']}"
        if m["unit"] == "kWh":
            m["value"] /= 1000; m["unit"] = "MWh"
        series[(m["site_id"], m["carrier"], int(m["year"]))][int(m["month"])] = m
    def smed(s):
        v = [x["value"] for x in s.values() if x["value"] > 0]
        return lib.median(v) if v else 0
    for k, s in series.items():   # R-EN-1 kWh in MWh column
        md = smed(s)
        for mo, m in s.items():
            if md > 0 and m["value"] > 200 * md:
                note("energy", m["key"], "value", m["value"], m["value"] / 1000, "R-EN-1", f"{m['value']/md:.0f}x series median: kWh reported in MWh column")
                m["value"] /= 1000
    def other_years(site, carrier, year, mo):
        v = [series[(site, carrier, y)][mo]["value"] for y in range(year - 2, year + 3)
             if y != year and (site, carrier, y) in series and mo in series[(site, carrier, y)]
             and not series[(site, carrier, y)][mo].get("suspect")]
        return v
    def impute(site, carrier, year, mo):
        s = series[(site, carrier, year)]
        # seasonal profile from other years scaled to this year's level; fallback neighbour mean
        num_, den = 0.0, 0.0
        ests = []
        for y in range(year - 2, year + 3):
            o = series.get((site, carrier, y))
            if y == year or not o or mo not in o:
                continue
            common = [m_ for m_ in s if m_ in o and m_ != mo and not s[m_].get("suspect") and not o[m_].get("suspect")]
            if len(common) < 6:
                continue
            a = sum(s[m_]["value"] for m_ in common); b = sum(o[m_]["value"] for m_ in common)
            if b > 0:
                ests.append(o[mo]["value"] * a / b)
        if ests:
            return sum(ests) / len(ests), "seasonal profile of adjacent years scaled to this year's level"
        nb = [s[m_]["value"] for m_ in (mo - 1, mo + 1) if m_ in s and not s[m_].get("suspect")]
        return (sum(nb) / len(nb) if nb else smed(s)), "mean of neighbouring months"
    # R-EN-2 meter spike: > 2.4x series median AND > 2x same month in adjacent years
    for (site, carrier, year), s in series.items():
        md = smed(s)
        for mo, m in s.items():
            oy = other_years(site, carrier, year, mo)
            if md > 0 and m["value"] > 2.4 * md and (not oy or m["value"] > 2 * max(oy)):
                m["suspect"] = True
            elif len(oy) >= 1 and m["value"] > 2.5 * max(oy):   # seasonal series: compare with the same month in other years
                m["suspect"] = True
    for (site, carrier, year), s in series.items():
        for mo, m in s.items():
            if m.get("suspect"):
                v, how = impute(site, carrier, year, mo)
                note("energy", m["key"], "value", m["value"], round(v, 3), "R-EN-2", f"meter spike (>2.4x series median, >2x same month other years); replaced by {how}")
                m["value"] = v
    # R-EN-3 missing months: series with >= 8 of 12 readings are filled to 12; shorter series are a
    # carrier starting/stopping mid-year (e.g. Säkylä steam ends 6/2023, biogas starts 7/2023) and are not filled
    added = []
    for (site, carrier, year), s in list(series.items()):
        if len(s) < 8 or len(s) == 12:
            continue
        for mo in range(1, 13):
            if mo not in s:
                v, how = impute(site, carrier, year, mo)
                key = f"energy:{site}:{year}-{mo:02d}:{carrier}"
                note("energy", key, "value", None, round(v, 3), "R-EN-3", f"missing meter month inside reporting period; filled by {how}")
                r = dict(site_id=site, year=float(year), month=float(mo), carrier=carrier, value=v, unit="MWh", key=key)
                added.append(r); s[mo] = r
    raw["energy_meter"] = em + added
    # R-EN-4 registry anchor (a-final): GoO registry volume equals metered electricity at every covered site-year in
    # 2023-2025 (s04_pcf_goo.py), so a filled electricity month is registry total minus the months that need no fill.
    # Two fills in one site-year share the remainder in proportion to their seasonal estimates. The guard skips
    # site-years where the registry cannot be consumption (for example S-KAN 2021, partly covered).
    regv = defaultdict(float)
    for g in raw["goo_registry"]:
        if g["production_period_start"][:4] == str(int(g["consumption_year"])):
            regv[(g["beneficiary_site"], int(g["consumption_year"]))] += g["mwh"]
    filled = {l["record_key"] for l in log if l["rule"] in ("R-EN-2", "R-EN-3")}
    for (site, carrier, year), s in series.items():
        if carrier != "electricity" or (site, year) not in regv:
            continue
        months = [m for m in s.values() if m["key"] in filled]
        est = sum(m["value"] for m in months)
        if not months or est <= 0:
            continue
        implied = regv[(site, year)] - sum(m["value"] for m in s.values() if m["key"] not in filled)
        if abs(implied - est) > 0.1 * est:
            continue
        for m in months:
            new = m["value"] * implied / est
            note("energy", m["key"], "value", round(m["value"], 3), round(new, 3), "R-EN-4",
                 f"registry {regv[(site, year)]:.3f} MWh less the {12 - len(months)} months needing no fill leaves {implied:.3f} MWh for {len(months)} filled month(s)")
            m["value"] = new

    # ---------------- fuel deliveries: R-FUEL-1 m3 keyed as litres (litre deliveries < 100)
    for d in raw["fuel_deliveries"]:
        if d["unit"] == "l" and d["quantity"] < 100:
            note("fuel", f"fuel:{d['delivery_id']}", "quantity", d["quantity"], d["quantity"] * 1000, "R-FUEL-1",
                 "litre delivery < 100 l among tanker loads of 10-70 m3: m3 keyed as litres")
            d["quantity"] *= 1000

    # ---------------- GoO: R-GOO-1 registry statement is authoritative
    reg = defaultdict(float)
    for g in raw["goo_registry"]:
        if g["production_period_start"][:4] == str(int(g["consumption_year"])):
            reg[(g["beneficiary_site"], int(g["consumption_year"]))] += g["mwh"]
    newgoo = []
    for (site, y), mwh in sorted(reg.items()):
        newgoo.append(dict(site_id=site, year=y, vintage_year=y, mwh_cancelled=mwh))
    logm = {(g["site_id"], int(g["year"])): g for g in raw["goo"]}
    for (site, y), g in logm.items():
        r = reg.get((site, y), 0.0)
        if int(g["vintage_year"]) != y or abs(g["mwh_cancelled"] - r) > 1:
            note("goo", f"goo:{site}:{y}", "mwh_cancelled/vintage", f"{g['mwh_cancelled']} (vintage {int(g['vintage_year'])})", f"{r:.3f} (vintage {y})",
                 "R-GOO-1", "internal log differs from the national registry statement, which is authoritative")
    raw["goo"] = newgoo

    # ---------------- refrigerants
    sysgas = defaultdict(lambda: defaultdict(int))
    for r in raw["refrigerants"]:
        sysgas[(r["site_id"], r["system"])][r["refrigerant"]] += 1
    for r in raw["refrigerants"]:
        key = f"refrigerant:{r['event_id']}"
        g = sysgas[(r["site_id"], r["system"])]
        dom = max(g, key=g.get)
        # R-REF-1 wrong gas code: ammonia logged on a system whose majority of events (2019-2025) is a non-ammonia gas
        if r["refrigerant"] == "R717_ammonia" and dom != "R717_ammonia" and g[dom] > g["R717_ammonia"]:
            note("refrigerant", key, "refrigerant", r["refrigerant"], dom, "R-REF-1", f"system '{r['system']}' runs on {dom} in other events: ammonia code is a wrong gas code")
            r["refrigerant"] = dom
    kgs = defaultdict(list)
    for r in raw["refrigerants"]:
        kgs[(r["site_id"], r["system"])].append(r["kg_added"])
    for r in raw["refrigerants"]:
        md = lib.median(kgs[(r["site_id"], r["system"])])
        if r["refrigerant"] != "R717_ammonia" and r["kg_added"] > 1000 and r["kg_added"] > 20 * max(md, 1):
            note("refrigerant", f"refrigerant:{r['event_id']}", "kg_added", r["kg_added"], r["kg_added"] / 1000, "R-REF-2",
                 f"{r['kg_added']} kg of HFC in one top-up ({r['kg_added']/max(md,1):.0f}x system median): grams in kg column")
            r["kg_added"] /= 1000

    # ---------------- waste: R-WASTE-1 tonnes keyed as kg (< 2% of stream median)
    ws = defaultdict(list)
    for w in raw["waste"]:
        ws[(w["site_id"], w["waste_stream"])].append(w["quantity"])
    for w in raw["waste"]:
        md = lib.median(ws[(w["site_id"], w["waste_stream"])])
        if w["quantity"] < 0.02 * md:
            note("waste", f"waste:{w['transfer_note']}", "quantity", w["quantity"], w["quantity"] * 1000, "R-WASTE-1",
                 f"monthly quantity {w['quantity']} kg vs stream median {md:.0f} kg: tonnes keyed as kg")
            w["quantity"] *= 1000

    # ---------------- travel: R-TRAVEL-1 re-imported duplicates
    seen, keep = set(), []
    for t in raw["travel"]:
        k = (t["traveller_id"], t["travel_date"], t["route"], t["pkm"], t["nights"])
        if k in seen:
            note("travel", f"travel:{t['booking_id']}", "*", "row", "dropped", "R-TRAVEL-1", "same traveller, date, route, distance and nights as an earlier booking")
            continue
        seen.add(k); keep.append(t)
    raw["travel"] = keep

    # ---------------- commuting: R-COMM-1 metres in km field, R-COMM-2 mode labels
    for c in raw["commuting"]:
        if c["one_way_km"] > 1000:
            note("commuting", f"commute:{c['response_id']}", "one_way_km", c["one_way_km"], c["one_way_km"] / 1000, "R-COMM-1", "one-way distance > 1000 km: metres entered as km")
            c["one_way_km"] /= 1000
        if c["mode"] in MODE_MAP:
            note("commuting", f"commute:{c['response_id']}", "mode", c["mode"], MODE_MAP[c["mode"]], "R-COMM-2", "free-text / Finnish mode label mapped to survey code")
            c["mode"] = MODE_MAP[c["mode"]]

    # ---------------- shipments: R-SHIP-1 missing sea / ro-pax leg
    erpd = {e["doc_no"]: e for e in raw["erp"]}
    legs = defaultdict(list)
    for s in raw["shipments"]:
        if s["direction"] == "inbound":
            legs[s["ref_doc"]].append(s)
    pat = defaultdict(lambda: defaultdict(int)); seakm = defaultdict(list)
    for doc, ls in legs.items():
        e = erpd.get(doc)
        if not e:
            continue
        pat[(e["material_id"], e["origin_country"])][tuple(sorted(l["ef_id"] for l in ls))] += 1
        for l in ls:
            if l["mode"] in ("ship-bulk", "ship-reefer", "ropax"):
                seakm[(e["material_id"], e["origin_country"], l["ef_id"])].append(l["km"])
    added = []
    for doc, ls in legs.items():
        e = erpd.get(doc)
        if not e:
            continue
        p = pat[(e["material_id"], e["origin_country"])]
        full = max(p, key=p.get)
        have = tuple(sorted(l["ef_id"] for l in ls))
        if len(full) > len(have) and set(have) < set(full):
            for ef in set(full) - set(have):
                km = lib.median(seakm[(e["material_id"], e["origin_country"], ef)])
                t = ls[0]["t"]
                r = dict(shipment_id="IMPUTED", year=ls[0]["year"], direction="inbound", ref_doc=doc, ef_id=ef, mode=ef, t=t, km=km, tkm=t * km)
                note("shipments", f"ship:{doc}:{ef}", "tkm", None, round(t * km, 2), "R-SHIP-1",
                     f"import lot has only {have}; {p[full]} of {sum(p.values())} lots of {e['material_id']} from {e['origin_country']} also have {ef} at {km} km")
                added.append(r)
    raw["shipments"] = raw["shipments"] + added

    # ---------------- supplier PCFs: R-PCF-1 reference period must cover the year; R-PCF-2 per-kg values
    used = []
    for p in raw["pcfs"]:
        key = f"pcf:{p['supplier_id']}:{p['material_id']}:{p['year']}"
        if not (p["ref_start"][:4] <= str(p["year"]) < p["ref_end"][:4] or p["ref_start"][:4] == str(p["year"])):
            note("pcf", key, "pcf", p["value"], "default EF", "R-PCF-1", f"reference period {p['ref_start']}..{p['ref_end']} does not cover {p['year']}: stale PCF, use material default factor")
            continue
        dflt = {e["ef_id"]: e["kgco2e_per_unit"] for e in raw["ef_library"]}[mm[p["material_id"]]["default_ef_id"]]
        if p["value"] > 50 * dflt:
            note("pcf", key, "pcf", p["value"], "default EF", "R-PCF-2", f"value {p['value']} is ~1000x the {dflt} kg/kg default: per-tonne value declared per kg; invalid, use default factor")
            continue
        used.append(dict(year=p["year"], supplier_id=p["supplier_id"], material_id=p["material_id"], kgco2e_per_kg=p["value"]))
    raw["pcf_used"] = used
    return raw, log

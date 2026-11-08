"""Final build: all E answers with evidence, soil and PCF sensitivity, official dev score, corrections log, results.json."""
from ccn_paths import PACKAGE, stage_dir
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import pipeline as P
import farm as FM
from clean import ROOT, F
from ccn_tools import reference_calculator as RC, score as SC
HERE = stage_dir("e_copilot")
D = ROOT / "data"
soil = json.loads((HERE / "soil.json").read_text())
KEY1 = "cat01_purchased_goods_services"
RAPE = ["M101", "M102", "M103", "M104", "M105", "M106", "M107"]
IMP = RAPE[1:]


def flag_total(b, y=2025):
    inv = b["inv"][y]; T = b["T"]
    ef = T["ef_library"].set_index("ef_id").flag_share
    mm = T["materials"].set_index("material_id").default_ef_id
    g = inv[(inv.category == "cat01_purchased_goods") & ~inv.line_item.str.startswith("contract_farming")].copy()
    g["fs"] = g.line_item.str.split(":").str[0].map(mm).map(ef)
    f = b["farms"][b["farms"].year == y]
    return float((g.tco2e * g.fs).sum()), float(f.t_flag_min.sum() + f.t_org.sum())


def numeric(b):
    inv = b["inv"][2025]; T = b["T"]; A = {}
    s = RC.summarise(inv).set_index("category").tco2e
    en = T["energy"]; e25 = en[en.year == 2025]
    item = lambda sc, it: float(inv[(inv.scope == sc) & inv.line_item.isin(it)].tco2e.sum())
    A["E01"] = item("scope1", ["S-SAK:lng", "S-SAK:lpg"])
    A["E02"] = float(s["scope2_market_total"])
    A["E03"] = float(inv[(inv.scope == "scope2_location") & (inv.line_item == "S-KAN")].tco2e.sum())
    c1 = inv[inv.category == "cat01_purchased_goods"]
    mat = c1.line_item.str.split(":").str[0]
    A["E04"] = float(c1[mat.isin(IMP)].tco2e.sum())
    f = b["farms"][b["farms"].year == 2025]
    tr = f[f.crop == "turnip_rape"]; pea = f[f.crop == "pea"]
    A["E05"] = 100 * (float(c1[mat.isin(RAPE)].tco2e.sum()) + float(tr.tco2e.sum())) / float(s[KEY1])
    total = float(s["scope1_total"] + s["scope2_market_total"] + s["scope3_total"])
    fp, ff = flag_total(b)
    flag = fp + ff
    A["E06"] = 100 * flag / total
    A["E07"] = 100 * float(f.t_org.sum() / f.tco2e.sum())
    tot, hard, _ = FM.count_ge30(b["raw"], b["post"], 2025)
    A["E08"] = float(tot)
    k = e25[e25.site_id == "S-KAN"].groupby("carrier").mwh.sum()
    A["E09"] = float(sum(k.get(c, 0) * F.FUEL_BIOGENIC_T_PER_MWH.get(c, 0) for c in k.index))
    sk = e25[e25.site_id == "S-SAK"].groupby("carrier").mwh.sum()
    A["E10"] = float(sk["electricity"])
    goo = T["goo"]; g = float(goo[(goo.year == 2025) & (goo.site_id == "S-SAK") & (goo.vintage_year == 2025)].mwh_cancelled.sum())
    cov = min(g, sk["electricity"])
    A["E11"] = 100 * float((sk.get("biogas", 0) + cov) / sk.sum())
    w = b["raw"]["water"]; w = w[w.year == 2024]
    wd = w[(w.flow == "withdrawal") & (w.source_or_destination != "reused_water")].m3.sum(); dc = w[w.flow == "discharge"].m3.sum()
    A["E12"] = float(wd - dc)
    A["E13"] = float(inv[(inv.category == "fugitive_refrigerants") & inv.line_item.str.startswith("S-SAK:")].tco2e.sum())
    A["E14"] = float(inv[inv.line_item.isin(["inbound:EF-TKM-SHIP-BULK", "inbound:EF-TKM-SHIP-REEFER"])].tco2e.sum())
    e = b["erp"]; A["E15"] = float(e[(e.year == 2025) & (e.material_id == "M130")].qty_kg.sum() / 1000)
    A["E16"] = float(pea.tco2e.sum() * 1000 / pea.kg.sum())
    A["E17"] = float(tr.tco2e.sum() * 1000 / tr.kg.sum())
    A["E18"], A["E19"] = deliveries(b)
    s12 = float(s["scope1_total"] + s["scope2_market_total"])
    A["E20"] = s12 * (1 - 0.042 * 7)
    A["E21"] = flag * (1 - 0.0303 * 7)
    s24 = RC.summarise(b["inv"][2024]).set_index("category").tco2e
    A["E90"], A["E91"], A["E92"] = float(s24["scope1_total"]), float(s24["scope2_market_total"]), float(s24[KEY1])
    X = dict(flag_t=flag, flag_purchased=fp, flag_farm=ff, total_t=total, s1=float(s["scope1_total"]), s2m=float(s["scope2_market_total"]), s2l=float(s["scope2_location_total"]), s3=float(s["scope3_total"]), cat1=float(s[KEY1]),
             farm_t=float(f.tco2e.sum()), farm_org_t=float(f.t_org.sum()), org_ha=float(f.org_area.sum()), crop_ha=float(f.area.sum()), e08_hard=int(hard), goo_saks=g, sak_mwh={k_: float(v) for k_, v in sk.items()}, wd=float(wd), dc=float(dc))
    return A, X


def deliveries(b):
    raw, sv, erp = b["raw"], b["sv"], b["erp"]
    m = FM.contract_parcels(raw); pea = m[m.crop == "pea"].groupby(["farm_id", "year"]).area_ha.sum().rename("area").reset_index()
    s = sv[sv.crop == "pea"][["farm_id", "year", "yield_t_ha"]]
    prod, act = {}, {}
    for y in range(2021, 2027):
        a = pea[pea.year == y].merge(s[s.year == y], on=["farm_id", "year"], how="left")
        r = a[a.yield_t_ha.notna()]
        yw = (r.yield_t_ha * r.area).sum() / r.area.sum()
        prod[y] = (a.yield_t_ha.fillna(yw) * a.area).sum()
        if y < 2026:
            act[y] = erp[(erp.material_id == "M110") & (erp.year == y)].qty_kg.sum() / 1000
    ratio = np.mean([act[y] / prod[y] for y in act])
    fi = 100 * (prod[2026] * ratio / act[2025] - 1)
    fh = pd.read_csv(D / "03_farming" / "foodhills_odlingsdata_se.csv", sep=";", decimal=",")
    t = fh.groupby("skördeår")["levererad_mängd_ton"].sum()
    return float(fi), float(100 * (t[2026] / t[2025] - 1))


base = P.build(mode="rate", b_low=soil["b_low"])
A, X = numeric(base)
L = base["log"]
L.to_csv(HERE / "corrections_log.csv", index=False)

# soil sensitivity
sens = {}
for name, (pm, pc, bl) in dict(low=(0.8, 0.2, 0.0), high=(1.0, 0.6, 0.002)).items():
    FM.P_MAP_ORG, FM.P_CLUSTER = pm, pc
    sens[name] = numeric(P.build(mode="rate", b_low=bl))[0]
FM.P_MAP_ORG, FM.P_CLUSTER = 0.90, 0.40
base2 = P.build(mode="rate", b_low=soil["b_low"])     # restores the log and tables for everything below
# PCF reading: unit-error PCF divided by 1000 instead of library default
pcf_alt = 0.0
raw = base2["raw"]; pc = raw["pcfs"]; p25 = pc[(pc.year == 2025) & (pc.value > 50)]
mm = raw["materials"].set_index("material_id").default_ef_id; ef = raw["ef_library"].set_index("ef_id").kgco2e_per_unit
e = base2["erp"]; rows = {}
for _, r in p25.iterrows():
    kg = e[(e.year == 2025) & (e.supplier_id == r.supplier_id) & (e.material_id == r.material_id)].qty_kg.sum()
    rows[r.material_id] = kg * (r.value / 1000 - ef[mm[r.material_id]]) / 1000
print("PCF /1000 reading, t change by material", {k: round(v, 1) for k, v in rows.items()})

# internal-log GoO comparator for E02
T2 = dict(base2["T"]); g = raw["goo"]; T2["goo"] = g
s2_log = float(RC.summarise(RC.compute_inventory(T2, 2025)).set_index("category").tco2e["scope2_market_total"])
# naive market-based 2025 from raw package
from ccn_tools import io as IO
N = IO.naive_canonical(raw); s_naive = RC.summarise(RC.compute_inventory(N, 2025)).set_index("category").tco2e

# current calculator comparator on the same farm set
cf = pd.read_csv(D / "03_farming" / "current_calculator_footprints.csv")
f25 = base2["farms"][base2["farms"].year == 2025]
cmp_ = {}
for crop in ("pea", "turnip_rape"):
    q = f25[f25.crop == crop].merge(cf[(cf.year == 2025) & (cf.crop == crop)], on=["farm_id", "crop", "year"])
    cmp_[crop] = dict(n=len(q), current=float((q.carbon_footprint_kgco2e_per_kg * q.kg).sum() / q.kg.sum()), ours=float(q.tco2e.sum() * 1000 / q.kg.sum()))

# label recall on the public years (audit metric) and A2 dev scores
lab = base2["lab"]; dv = base2["log"]; dv = dv[dv.year.isin([2023, 2024])]
rec = {}
for t in ["erp_purchase_lines", "energy_meter_readings", "fuel_deliveries", "goo_cancellations", "refrigerant_service_log", "shipments", "travel_bookings", "waste_transfer_notes"]:
    a = set(lab[lab.table == t].record_key); c = set(dv[dv.table == t].record_key)
    rec[t] = dict(labels=len(a), found=len(c), tp=len(a & c))
q = lab[(lab.table == "erp_purchase_lines") & lab.issue_type.isin(["unit_error", "decimal_shift"])]
rec["erp_quantity"] = dict(labels=len(q), tp=int(q.record_key.isin(dv.record_key).sum()))
a2 = {}
for y in (2023, 2024):
    key = pd.read_csv(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{y}.csv")
    a2[y] = SC.score_a2(RC.summarise(base2["inv"][y]).reset_index(), key)["score"]
ho = {}
for lab_y, te in ((2023, 2024), (2024, 2023)):
    h = P.build(label_years=(lab_y,), mode="rate", b_low=soil["b_low"])
    c = RC.summarise(h["inv"][te]).set_index("category").tco2e[KEY1]
    k = pd.read_csv(ROOT / "tasks" / "dev" / f"A2_dev_inventory_{te}.csv").set_index("category").tco2e[KEY1]
    ho[te] = dict(mine=float(c), key=float(k), err_pct=float(100 * (c / k - 1)))
base2 = P.build(mode="rate", b_low=soil["b_low"]); L = base2["log"]

def ks(table, issue=None, year=2025, n=8):
    d = L[(L.table == table) & (L.year == year)]
    if issue:
        d = d[d.issue_type == issue]
    return " ".join(d.record_key.head(n))

mix = lambda *a: "; ".join(x for x in a if x)
R_ = "data/02_raw_feeds/"
EV = {
 "E01": mix(f"{R_}fuel_deliveries.csv site S-SAK lng+lpg 2025 less {R_}fuel_stock_changes.csv", "METHODOLOGY s2 (NCV LNG 13.5, LPG 12.8), s3 (LNG 0.1991, LPG 0.2336 t/MWh)"),
 "E02": mix(f"{R_}energy_meter_readings.csv, {R_}goo_registry_statement.csv (authoritative, METHODOLOGY s2)", "corrected: " + ks("goo_cancellations") + " " + ks("energy_meter_readings", "unit_error"), "residual mix FI 0.406 / SE 0.035, ccn_tools/factors.py; S-HQ has no GoO"),
 "E03": mix(f"{R_}energy_meter_readings.csv S-KAN electricity 2025 x 0.026 (METHODOLOGY s3)", "corrected: energy:S-KAN:2025-06:electricity kWh in MWh column"),
 "E04": mix(f"{R_}erp_purchase_lines_2021_2025.csv M102-M107 2025, net of movement 122", f"{R_}supplier_pcfs valid only, else library default (METHODOLOGY s4)", "excluded: pcf:SUP022:M107:2025 pcf:SUP023:M107:2025 (stale), pcf:SUP011:M104:2025 (per t)"),
 "E05": mix("E04 lines + M101 + contract_farming:FI_SW:turnip_rape over cat 1 goods and services", "e_copilot/corrections_log.csv", "METHODOLOGY s4, s5"),
 "E06": mix("FLAG = farm N2O, organic soils, liming (METHODOLOGY s5) + purchased kg x factor x flag_share (01_master/emission_factor_library.csv)", "denominator S1 + S2 market + S3 from reference_calculator.py"),
 "E07": mix("data/03_farming/farm_survey_fi.csv, parcel_crop_history_and_plan.csv, 01_master/parcels.csv", "ESTIMATE: true soil is hidden; three-cell soil table, ASSUMPTIONS 'Organic soils', METHODOLOGY s5"),
 "E08": mix("01_master/parcels.csv soil map, farm_survey_fi.csv reports, public soil_misreport labels 2023-24", "ESTIMATE: expected count, sum of P(share>=30 %) over farms; TASKS_AND_SCORING A1 definition"),
 "E09": mix(f"{R_}energy_meter_readings.csv S-KAN wood_chips x 0.4032 + oilseed_sidestream x 0.45 (METHODOLOGY s3)", "corrected: energy:S-KAN:2025-04:oilseed_sidestream energy:S-KAN:2025-12:wood_chips (spikes), energy:S-KAN:2025-06:oilseed_sidestream energy:S-KAN:2025-07:wood_chips (gaps, estimated)"),
 "E10": mix(f"{R_}energy_meter_readings.csv S-SAK electricity 2025", "corrected: energy:S-SAK:2025-06:electricity 1708632 -> 1708.632, kWh in MWh column"),
 "E11": mix(f"{R_}energy_meter_readings.csv, fuel_deliveries.csv, fuel_stock_changes.csv, goo_registry_statement.csv GO-2025-SAK-01..04", "numerator biogas + GoO-covered electricity; corrected energy:S-SAK:2025-10:biogas (gap, estimated) energy:S-SAK:2025-06:electricity"),
 "E12": mix(f"{R_}water_balance.csv 2024: withdrawals excl. reused_water less discharges", "APETIT_DATA_RECONCILIATION.md water note; GRI 303"),
 "E13": mix(f"{R_}refrigerant_service_log.csv S-SAK 2025 RS00074-RS00079", "corrected: refrigerant:RS00078 R717 on R449A system", "METHODOLOGY s3 GWP100 R404A 4,728, R449A 1,504, ammonia 0"),
 "E14": mix(f"{R_}shipments.csv inbound EF-TKM-SHIP-BULK and EF-TKM-SHIP-REEFER 2025", "missing legs added: " + ks("shipments", "missing_leg"), "01_master/emission_factor_library.csv 0.013 and 0.021"),
 "E15": mix(f"{R_}erp_purchase_lines_2021_2025.csv M130 2025, net of movement 122", "quantities checked against shipments.csv tonnes; 01_master/materials.csv sbtn_high_impact_commodity True"),
 "E16": mix("M110 deliveries, farm_survey_fi.csv, parcels; METHODOLOGY s5", "ESTIMATE: includes modelled organic soil"),
 "E17": mix("M100 deliveries, farm_survey_fi.csv, parcels; METHODOLOGY s5", "ESTIMATE: includes modelled organic soil"),
 "E18": mix("2025 = ERP M110; 2026 = crop history area x survey yield x mean 2021-25 delivered/production ratio", "ESTIMATE: ERP ends 2025, no 2026 delivery record exists for Finland"),
 "E19": "data/03_farming/foodhills_odlingsdata_se.csv levererad_mängd_ton summed by skördeår, 2026 vs 2025 (298 and 296 growers)",
 "E20": "S1 + S2 market 2025 x (1 - 0.042 x 7); framework_digest.md SBTi; illustrative, 2025 not Foodhills-adjusted",
 "E21": "E06 FLAG t x (1 - 0.0303 x 7); framework_digest.md SBTi; illustrative",
 "E90": "reference_calculator.py on cleaned feeds; corrected: " + ks("refrigerant_service_log", year=2024) + " " + ks("fuel_deliveries", year=2024),
 "E91": f"{R_}goo_registry_statement.csv, energy meters; corrected " + ks("goo_cancellations", year=2024),
 "E92": "cleaned ERP + valid PCFs + farm model; see corrections_log.csv; held-out check in results.json",
}
RUB = {
 "E30": (f"Yes. SBTi requires a FLAG target of food production and food and beverage processing companies, and of any company whose FLAG emissions exceed 20 % of its total. Apetit is a food processor, so it applies regardless of share. In this synthetic dataset FLAG is also {A['E06']:.0f} % of the total (estimate), above 20 %. A no-deforestation commitment with a cut-off no later than 2020 comes with it.", "data/07_frameworks/framework_digest.md 'FLAG'; docs/SCENARIOS_AND_RISK.md Track B item 2; SBTi FLAG in source_registry.csv; share from E06"),
 "E31": ("(a) Scope 1+2: 4.2 %/yr linear (1.5 C). (b) Scope 3 well-below 2 C: 2.5 %/yr. (c) FLAG: 3.03 %/yr.", "framework_digest.md 'Minimum ambition (V1.3.1 method appendix)'; TASKS_AND_SCORING B1; SBTi CNZS V1.3.1 Method Appendix in source_registry.csv"),
 "E32": ("A 2019 base year cannot be used as published. It includes the grain trade, sold 2022, and excludes Foodhills, bought 27 Nov 2025. Both are structural changes, so the base year must be recalculated: remove the grain trade and add Foodhills, if the change passes the significance threshold (5 % in the Apetit brief). Scope 3 is most affected. Activity data starts in 2021, so 2019 needs estimates. Show a recalculated 2019 next to a 2025 base; 2025 also needs adjusting because only December of Foodhills is in scope and Swedish growers enter from 2026.", "docs/METHODOLOGY.md s1; data/05_scenarios/structural_events.csv rows 2022-03-10, 2022-05-31, 2025-11-27; published_inventory_history.csv; SCENARIOS_AND_RISK.md Track B item 1; framework_digest.md 'Accounting'; run/brief.md"),
 "E33": (f"No. Location-based Scope 2 uses the grid-average factor whatever certificates are held. GoOs only change market-based Scope 2. Here 2025 location-based is {X['s2l']:.0f} t and market-based {X['s2m']:.0f} t, and cancelling GoOs moves only the second (synthetic data).", "framework_digest.md 'Scope 2'; METHODOLOGY s3; GLOSSARY 'Location- vs market-based'; ccn_tools/reference_calculator.py"),
 "E34": ("FLAG: direct and indirect N2O, drained organic soils, liming (plus land-use change and soil carbon where accounted). Non-FLAG: fertiliser manufacture, diesel, electricity, pesticides.", "docs/METHODOLOGY.md s5 'FLAG (SBTi) part'; framework_digest.md 'FLAG'"),
 "E35": ("Rapeseed: no, it is not a relevant EUDR commodity. Soy protein isolate: no, HS 3504 is not listed in Annex I, although soybeans (1201), soy oil (1507) and soy meal (2304) are. Scope follows HS codes, and Annex I can be amended, so screen per product. It remains an SBTN high-impact commodity.", "framework_digest.md 'EU Deforestation Regulation'; structural_events.csv 2026-12-30; 01_master/materials.csv M102-M107, M130 (eudr_commodity False); APETIT_DATA_RECONCILIATION.md; EUDR overview in source_registry.csv"),
 "E36": ("An area where Aqueduct baseline water stress is 'high' or above, or where WEI+ is at least 40 %.", "framework_digest.md 'ESRS (revised, 2026)'; EFRAG simplified ESRS E3 in source_registry.csv"),
 "E37": ("Yes, reporting removals is optional under the LSR Standard (v1.1 June 2026, effective 1 Jan 2027). They must be monitored and traceable, and reversals must be accounted for. This dataset does not model catch-crop removals, so none can be claimed from it.", "framework_digest.md 'Land Sector and Removals Standard'; docs/ASSUMPTIONS_AND_LIMITATIONS.md 'Not modelled'; GHG Protocol LSR in source_registry.csv"),
 "E38": ("Step 1a, materiality screening within Step 1 Assess. In this package's mapping the pressures are land use, water use, nutrient pollution, GHG and pesticides.", "framework_digest.md 'SBTN'; docs/NATURE_SBTN.md 'Mapping to SBTN steps'; SBTN Step 1a in source_registry.csv. Pressure list is the package's; check wording against SBTN's own guidance"),
 "E39": ("Because nothing physical changed: the same activity is measured with a better factor. It is a measurement improvement, so the difference is a method change, not abatement. Keep it out of reduction claims, and restate the base year if it is significant.", "data/05_scenarios/decarbonisation_levers.csv L27 (abatement 0, 'reported change is not a real reduction'); TASKS_AND_SCORING B1/B2; SCENARIOS_AND_RISK.md item 5; framework_digest.md 'Accounting'"),
}
# full record-key lists per question, using the key formats in TASKS_AND_SCORING A1
rw = base2["raw"]; er = base2["erp"]; e25 = er[er.year == 2025]
fd = rw["fuel_deliveries"]; fd = fd[fd.year == 2025]
em = rw["energy_meter"]; em = em[em.year == 2025]
ekeys = lambda site, carriers: [f"energy:{site}:2025-{m:02d}:{c}" for c in carriers for m in range(1, 13)]
fkeys = lambda site, carriers: ["fuel:" + i for i in fd[(fd.site_id == site) & fd.carrier.isin(carriers)].delivery_id]
mkeys = lambda mats: e25[e25.material_id.isin(mats)].key.tolist()
shp = base2["T"]["shipments"]; shp = shp[(shp.year == 2025) & (shp.direction == "inbound") & shp.ef_id.isin(["EF-TKM-SHIP-BULK", "EF-TKM-SHIP-REEFER"])]
rg = pd.read_csv(D / "02_raw_feeds" / "goo_registry_statement.csv"); rg = rg[rg.consumption_year == 2025]
rfl = rw["refrigerants"]; rfl = rfl[(rfl.year == 2025) & (rfl.site_id == "S-SAK")]
wb = rw["water"]; wb = wb[wb.year == 2024]
KEYS = {"E01": fkeys("S-SAK", ["lng", "lpg"]), "E02": rg.cancellation_id.tolist(), "E03": ekeys("S-KAN", ["electricity"]), "E04": mkeys(IMP),
        "E05": mkeys(RAPE + ["M100"]), "E09": ekeys("S-KAN", ["wood_chips", "oilseed_sidestream"]), "E10": ekeys("S-SAK", ["electricity"]),
        "E11": ekeys("S-SAK", ["electricity", "biogas"]) + fkeys("S-SAK", ["lng", "lpg"]) + rg[rg.beneficiary_site == "S-SAK"].cancellation_id.tolist(),
        "E12": [f"water:{a}:2024:{b_}:{c}" for a, b_, c in zip(wb.site_id, wb.flow, wb.source_or_destination)],
        "E13": ["refrigerant:" + i for i in rfl.event_id], "E14": [f"ship:{a}:{b_}" for a, b_ in zip(shp.ref_doc, shp.ef_id)],
        "E15": mkeys(["M130"]), "E16": mkeys(["M110"]), "E17": mkeys(["M100"])}
pd.DataFrame([(q_, k_) for q_, v in KEYS.items() for k_ in v], columns=["question_id", "record_key"]).to_csv(HERE / "evidence_keys.csv", index=False)
for q_, v in KEYS.items():
    EV[q_] = f"{EV[q_]}; records ({len(v)}, full list in evidence_keys.csv): {' '.join(v[:4])}"
# what the ERP rules missed on the public labels
lb = lab[lab.table == "erp_purchase_lines"]; miss = lb[~lb.record_key.isin(dv.record_key)]
rawe = rw["erp"].assign(key=lambda d_: "erp:" + d_.doc_no + ":" + d_.line_no.astype(str))
mm_ = rawe[rawe.key.isin(miss.record_key)]
erp_missed = dict(n=len(miss), types=miss.issue_type.value_counts().to_dict(), true_values=miss.true_value.value_counts().to_dict(), uoms=mm_.uom.value_counts().to_dict())
print("ERP labels missed", erp_missed)
ROUND = dict(E08=0, E12=0, E15=1, E16=3, E17=3, E05=2, E06=2, E07=2, E11=2, E18=1, E19=2)
sub = pd.read_csv(ROOT / "tasks" / "templates" / "E_answers_submission.csv", dtype=str)
sub["answer"] = [round(A[q], ROUND.get(q, 1)) if q in A else RUB[q][0] for q in sub.question_id]
sub["evidence"] = [EV[q] if q in A else RUB[q][1] for q in sub.question_id]
sub.loc[sub.question_id == "E08", "answer"] = int(round(A["E08"]))
sub.to_csv(HERE / "E_answers_submission.csv", index=False)
chk = pd.read_csv(HERE / "E_answers_submission.csv")
key = pd.read_csv(ROOT / "tasks" / "dev" / "E_dev_answers.csv")
final = SC.score_e(chk, key)
base_sc = json.loads((HERE / "baseline_score.json").read_text())
res = dict(task="E", synthetic_data_note="Synthetic twin; not Apetit's actual emissions.", baseline_dev=dict(score=base_sc["score"], correct=base_sc["correct"], n=base_sc["n"]), final_dev=final,
           a2_dev_naive=base_sc["a2_naive"], erp_missed=erp_missed,
           dev_values={q: A[q] for q in ("E90", "E91", "E92")}, dev_keys=dict(zip(key.question_id, key.answer)),
           a2_dev_final=a2, heldout_cat1=ho, label_recall_2023_24=rec, answers=A, soil_low=sens["low"], soil_high=sens["high"], extras=X, e02_internal_log=s2_log, naive_2025=dict(s1=float(s_naive["scope1_total"]), s2m=float(s_naive["scope2_market_total"]), s3=float(s_naive["scope3_total"])),
           current_calculator_2025=cmp_, pcf_div1000_change_t=rows, n_corrections=int(len(L)), corrections_by_issue=L.groupby("issue_type").size().to_dict(), corrections_2025=int((L.year == 2025).sum()))
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float, ensure_ascii=False))
print("BASELINE dev", res["baseline_dev"]); print("FINAL dev", final)
print("dev values", {q: round(A[q], 1) for q in ("E90", "E91", "E92")})
print("A2 dev final (in-sample)", a2); print("held-out cat1", {k: round(v["err_pct"], 2) for k, v in ho.items()})
print("label recall", rec)
print(pd.DataFrame(dict(answer=pd.Series(A), low=pd.Series(sens["low"]), high=pd.Series(sens["high"]))).round(3).to_string())
print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in X.items()})
print("S2 market with internal GoO log", round(s2_log, 1), "registry", round(A["E02"], 1), "naive", res["naive_2025"])
print("current calculator", cmp_); print("corrections", res["n_corrections"], res["corrections_by_issue"], "2025:", res["corrections_2025"])

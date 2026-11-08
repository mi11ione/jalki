"""Jälki v5 data layer. Called by build.py on the frozen trunk data (base/app/data.js); returns a log.

Each step names the ticket or reviewer finding it applies and asserts its input before changing anything.
Synthetic pack only: no figure here is Apetit's real emissions.
"""
import csv, json, re
from pathlib import Path

import v5route
import whose

S5 = 'python3 stages/pj-v5/build.py'


def num(D, k, v, unit, dp, en, fi, source, label='derivation'):
    D['v3']['numbers'][k] = {'v': v, 'unit': unit, 'dp': dp, 'en': en, 'fi': fi, 'source': source, 'script': source.split(' → ')[0], 'label': 'generated'}
    D.setdefault('prov', {})['v3.' + k] = {'l': label, 's': source}


def vendored(HERE, name):
    """Sibling-ticket inputs are vendored in stages/pj-v5/vendored/ (vendor.py) and checked by hash, so a clean clone rebuilds."""
    import hashlib
    p = Path(HERE) / 'vendored' / name
    rec = json.loads((Path(HERE) / 'vendored/SHA256.json').read_text())[name]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == rec['sha256'], name
    return p


def apply(D, ROOT, HERE):
    L = []
    ROOT, HERE = Path(ROOT), Path(HERE)

    # 1. route without L07 (pj-review4 R5: same missing-capacity rule that took L01 out)
    s12_v4 = (D['v4']['route2032_s12_lo'], D['v4']['route2032_s12_hi'])
    D['v4'] = v5route.compute(D, ROOT)
    L.append('route: L07 out (needs ~7,300 MWh biogas the pack does not show); cost %.0f -> %.0f EUR/yr; capex %.0f -> %.0f; '
             'Scope 1+2 2032 %.0f..%.0f -> %.0f..%.0f t; FLAG gap unchanged %.1f..%.1f t' % (
                 D['v4']['v4_rec_eur'], D['v4']['rec_eur'], D['v4']['v4_rec_capex'], D['v4']['rec_capex'], s12_v4[0], s12_v4[1],
                 D['v4']['route2032_s12_lo'], D['v4']['route2032_s12_hi'], D['v4']['route2032_flag_lo'], D['v4']['route2032_flag_hi']))
    lo16, hi16 = v5route.rng(D, [i for i in D['route']['rec'] if i != 'L16'], 2032, 'flag')
    D['v4']['nol16_2032_lo'], D['v4']['nol16_2032_hi'] = lo16, hi16
    num(D, 'w_nol16_lo', lo16, 't', 0, 'FLAG gap 2032 with L16 (uncited constant) at zero, low', 'FLAG-vaje 2032, L16 (lähteetön vakio) nollassa, alaraja', S5 + ' → v5.json#v4.nol16_2032_lo')
    num(D, 'w_nol16_hi', hi16, 't', 0, 'FLAG gap 2032 with L16 (uncited constant) at zero, high', 'FLAG-vaje 2032, L16 (lähteetön vakio) nollassa, yläraja', S5 + ' → v5.json#v4.nol16_2032_hi')
    L.append('pessimistic re-run, L16 at zero: 2032 FLAG gap %.0f..%.0f t (headline %.0f..%.0f)' % (lo16, hi16, D['v4']['route2032_flag_lo'], D['v4']['route2032_flag_hi']))
    for k in ('s12', 's3nf'):
        D['prov'].setdefault('d.tg_%s_lo' % k, {'l': 'derivation', 's': 'app.js tgap on the recommended route (v5route.py lever set) ← data.js route, rlev'})
        D['prov'].setdefault('d.tg_%s_hi' % k, {'l': 'derivation', 's': 'app.js tgap on the recommended route (v5route.py lever set) ← data.js route, rlev'})

    # 2. whose numbers (graft from the authorship idea; recomputed here from the shipped trail and raw PCF files)
    W = whose.compute(D, HERE / 'base/app')
    A = W['authors']
    sw, sa, y1, t, s5 = W['swing'], W['swing_all_valid'], W['year1'], W['top'], W['sup005']
    assert 10.95 <= sw['min_pct'] < 11.05 and 48.4 < sw['max_pct'] < 48.6 and 7.7 < y1['lo_pct'] < 7.72 and 9.0 < y1['hi_pct'] < 9.04, (sw, y1)
    WS = 'python3 stages/pj-v5/whose.py → whose.json'
    V5 = {'script': WS, 'synthetic_only': True}
    for g in ('library', 'supplier', 'farms', 'ops', 'product'):
        V5['a_%s_share' % g], V5['a_%s_break' % g], V5['a_%s_t' % g] = A[g]['share_pct'], A[g]['break_pct'], A[g]['t']
    V5.update(top_share=t['share_pct'], top_break=t['break_pct'], top_n=t['n'], top_source=t['source'], ghost_flag=t['ghost_flag_t'], ghost_years=t['ghost_years'],
              pcf_share=W['pcf']['share_pct'], pcf_unassured=W['pcf']['unassured_share_pct'], pcf_n=W['pcf']['n_used'],
              sw_lo=sw['min_pct'], sw_hi=sw['max_pct'], sw_med=sw['median_pct'], sw_n=sw['n'], sw_over=W['swing_over_cut_n'],
              swa_lo=sa['min_pct'], swa_hi=sa['max_pct'], swa_med=sa['median_pct'], swa_n=sa['n'],
              y1_lo=y1['lo_pct'], y1_hi=y1['hi_pct'], ramp=y1['ramp_years'],
              s5_share=s5['share_pct'], s5_t=s5['t'], s5_yoy=s5['signed_pct'], s5_p24=s5['primary24'], s5_p25=s5['primary25'], s5_fb=s5['fallback_t'],
              reg_n=W['register']['n'], reg_sha=W['register']['sha256'], reg_live=W['register']['n_carrying_t'], edges=W['edges'],
              swing_rows=[{'supplier': r['supplier'], 'material': r['material'], 'swing_pct': r['swing_pct'], 'signed_pct': r['signed_pct'],
                           'file24': r['file24'], 'file25': r['file25']} for r in W['pcf']['rows'] if r['rapeseed'] and r['swing_pct'] is not None])
    # review queue size explained: the ceiling covers judgement corrections only; validated unit and duplicate fixes are not undoable
    pc = D['bundle']['meter']['chips']['pending_corrections']
    V5['validated_fix_t'] = -pc['clean_minus_raw_by_evidence_level']['rule_validated_on_dev_labels']
    V5['n_judgement'], V5['n_corrections'] = pc['n_judgement_corrections'], pc['n_corrections']
    D['v5'] = V5
    (HERE / 'whose.json').write_text(json.dumps(W, indent=1, ensure_ascii=False))
    G = {'library': ('External factor library', 'Ulkoinen kerroinkirjasto'), 'supplier': ("Suppliers' own footprints (PCF)", 'Toimittajien omat jalanjäljet (PCF)'),
         'farms': ('Our contract farms, our method', 'Omat sopimustilat, oma menetelmä'), 'ops': ('Fuel, power and refrigerant constants', 'Polttoaine-, sähkö- ja kylmäainevakiot'),
         'product': ('Use and end-of-life constants', 'Käytön ja elinkaaren lopun vakiot')}
    for g, (en, fi) in G.items():
        num(D, 'w_%s_share' % g, A[g]['share_pct'], 'pct', 1, en + ': share of the 2025 base', fi + ': osuus perusvuodesta 2025', WS + '#authors.%s.share_pct' % g)
        num(D, 'w_%s_break' % g, A[g]['break_pct'], 'pct', 1, en + ': uniform revision that moves the base 5%', fi + ': tasainen muutos, joka siirtää perusvuotta 5 %', WS + '#authors.%s.break_pct' % g)
    W5 = [('top_share', 'pct', 1, 'One library source (Agri-footprint / national LCA studies): share of the base', 'Yksi kirjaston lähde (Agri-footprint / kansalliset LCA-tutkimukset): osuus perusvuodesta'),
          ('top_break', 'pct', 2, 'Revision of that one source that lands on the 5% line', 'Saman lähteen muutos, joka osuu 5 %:n rajalle'),
          ('top_n', 'n', 0, 'Factors from that source carrying 2025 tonnes', 'Lähteen kertoimet, joilla on vuoden 2025 tonneja'),
          ('ghost_flag', 't', 0, 'FLAG tonnes that move at that revision, with no recalculation forced', 'FLAG-tonnit, jotka liikkuvat tällä muutoksella ilman pakotettua uudelleenlaskentaa'),
          ('ghost_years', 'n', 2, 'Those tonnes in years of the required FLAG cut', 'Nämä tonnit vaaditun FLAG-leikkauksen vuosina'),
          ('pcf_unassured', 'pct', 1, 'Base resting on supplier PCFs with no assurance on the 2025 file', 'Perusvuoden osa, joka nojaa vahvistamattomiin vuoden 2025 PCF:iin'),
          ('pcf_n', 'n', 0, 'Supplier PCFs used in the 2025 base', 'Perusvuodessa 2025 käytetyt toimittaja-PCF:t'),
          ('sw_lo', 'pct', 1, "Rapeseed suppliers' own PCF, 2024 to 2025 move: smallest", 'Rapsitoimittajien oma PCF, muutos 2024–2025: pienin'),
          ('sw_hi', 'pct', 1, "Rapeseed suppliers' own PCF, 2024 to 2025 move: largest", 'Rapsitoimittajien oma PCF, muutos 2024–2025: suurin'),
          ('sw_med', 'pct', 1, "Rapeseed suppliers' own PCF, 2024 to 2025 move: median", 'Rapsitoimittajien oma PCF, muutos 2024–2025: mediaani'),
          ('sw_n', 'n', 0, 'Rapeseed PCFs in the base with a valid 2024 file', 'Perusvuoden rapsi-PCF:t, joilla on voimassa oleva vuoden 2024 tiedosto'),
          ('swa_lo', 'pct', 1, 'Every valid 2024/25 rapeseed PCF pair in the pack: smallest move', 'Kaikki voimassa olevat rapsi-PCF-parit 2024/25: pienin muutos'),
          ('swa_med', 'pct', 1, 'Every valid 2024/25 rapeseed PCF pair in the pack: median move', 'Kaikki voimassa olevat rapsi-PCF-parit 2024/25: mediaani'),
          ('swa_n', 'n', 0, 'Valid 2024/25 rapeseed PCF pairs in the pack', 'Voimassa olevat rapsi-PCF-parit 2024/25'),
          ('y1_lo', 'pct', 1, 'Year-one supplier cut the 2032 route asks, low', 'Reitin vuodelle 2032 vaatima ensimmäisen vuoden toimittajaleikkaus, alaraja'),
          ('y1_hi', 'pct', 1, 'Year-one supplier cut the 2032 route asks, high', 'Reitin vuodelle 2032 vaatima ensimmäisen vuoden toimittajaleikkaus, yläraja'),
          ('s5_share', 'pct', 1, "SUP005's rapeseed PCF: share of the base", 'SUP005:n rapsi-PCF: osuus perusvuodesta'),
          ('s5_p24', 'pct', 0, "SUP005's primary-data share, 2024 file", 'SUP005:n primääridatan osuus, vuoden 2024 tiedosto'),
          ('s5_p25', 'pct', 0, "SUP005's primary-data share, 2025 file", 'SUP005:n primääridatan osuus, vuoden 2025 tiedosto'),
          ('s5_fb', 't', 0, 'Base change if SUP005 falls back to the library default', 'Perusvuoden muutos, jos SUP005 palaa kirjaston oletukseen'),
          ('reg_n', 'n', 0, 'Factors in the sealed register', 'Sinetöidyn rekisterin kertoimet'),
          ('reg_live', 'n', 0, 'Of those, factors carrying 2025 tonnes', 'Niistä kertoimet, joilla on vuoden 2025 tonneja'),
          ('validated_fix_t', 't', 0, 'Validated unit and duplicate fixes already removed from the raw records', 'Raakatiedoista jo poistetut todennetut yksikkö- ja kaksoiskorjaukset'),
          ('bjuv_gas_mwh', 'n', 0, "Bjuv natural gas a year, MWh (12 × the December meter)", 'Bjuvin maakaasu vuodessa, MWh (12 × joulukuun mittari)')]
    for k, u, dp, en, fi in W5:
        src = WS + '#' + k if k not in ('validated_fix_t', 'bjuv_gas_mwh') else ('bundle meter.chips.pending_corrections.clean_minus_raw_by_evidence_level' if k == 'validated_fix_t' else 'bundle meter.chips.foodhills.gas12_mwh')
        num(D, 'w_' + k, V5[k] if k in V5 else D['bundle']['meter']['chips']['foodhills']['gas12_mwh'], u, dp, en, fi, src, 'data' if k.startswith(('sw', 'swa', 's5', 'reg', 'pcf', 'validated', 'bjuv')) else 'derivation')
    L.append('whose: library %.1f%% (break %.1f%%), suppliers %.1f%% (%.1f%%), farms %.1f%% (%.1f%%); top source %.1f%% break %.2f%% ghost FLAG %.0f t = %.2f yr; '
             'swing %.1f-%.1f%% median %.1f%% n=%d (all valid pairs %.1f-%.1f%% median %.1f%% n=%d); year-one cut %.2f-%.2f%%; register %d factors %s' % (
                 A['library']['share_pct'], A['library']['break_pct'], A['supplier']['share_pct'], A['supplier']['break_pct'], A['farms']['share_pct'], A['farms']['break_pct'],
                 t['share_pct'], t['break_pct'], t['ghost_flag_t'], t['ghost_years'], sw['min_pct'], sw['max_pct'], sw['median_pct'], sw['n'],
                 sa['min_pct'], sa['max_pct'], sa['median_pct'], sa['n'], y1['lo_pct'], y1['hi_pct'], W['register']['n'], W['register']['sha256'][:16]))

    # 3. one PCF-noise number everywhere (step-12417-3 mismatch 3: the plan's 14% counted two stale 2022-period files)
    old = D['v4']['rape']['pcf_noise_median_pct']
    D['v4']['rape']['pcf_noise_median_pct'] = sw['median_pct']
    D['v4']['rape']['pcf_noise_rule'] = sw['rule'] + ' (whose.py); the trunk median counted SUP022/SUP023 files whose reference period is 2022'
    L.append('pcf noise: %.2f%% (stale files counted) -> %.2f%% (valid in-base files, n=%d); review, all valid pairs: %.2f%% (n=%d)' % (old, sw['median_pct'], sw['n'], sa['median_pct'], sa['n']))

    # 4. review impacts that used the 0.3 kg/kg placeholder: replace by the record route (step-11875-1, step-12414-2, step-12420-7)
    rv = {r['id']: r for r in D['v3']['review']}
    fixed = []
    for r in csv.DictReader(open(vendored(HERE, 'routes_c2.csv'), encoding='utf-8')):
        m = re.match(r'v3\.review_(\d+)_impact$', r['figure_id'])
        if not m or r['status'] != 'mismatch':
            continue
        i = int(m.group(1))
        new = round(float(r['route_value']), 1)
        assert abs(rv[i]['impact'] - D['v3']['numbers']['review_%d_impact' % i]['v']) < 0.05
        rv[i]['impact'] = new
        q = D['v3']['numbers']['review_%d_impact' % i]
        q['v'] = new
        q['source'] = 'record route: ' + r['note'] + ' [python3 stages/step-09815-7/route_review.py]'
        D['prov']['v3.review_%d_impact' % i] = {'l': 'data', 's': q['source']}
        fixed.append((i, new))
    assert sorted(i for i, _ in fixed) == [12, 15, 45, 47, 51, 57, 70], fixed
    thr = D['v3']['numbers']['review_threshold']['v']
    L.append('review impacts from the record route: %s; blocking now %d of %d (threshold %g t)' % (
        fixed, sum(1 for r in D['v3']['review'] if r['impact'] is None or abs(r['impact']) >= thr), len(D['v3']['review']), thr))

    # 5. peat floor across the bases tested (step-12141-1 forward-port C15-C21 from step-10447-1; step-12702-4 floor labels)
    fr = json.loads(vendored(HERE, 'floor_repair.json').read_text())['floor']
    b = {x['base']: x for x in fr['bases']}
    assert abs(b['cp_2025']['pct'] - D['bundle']['meter']['chips']['peat']['lo_pct']) < 1e-4
    FS = 'python3 stages/step-10447-1/floor_repair.py → floor_repair.json'
    num(D, 'floor_min', min(x['pct'] for x in fr['bases']), 'pct', 2, 'Peat floor, soil map only: lowest across the bases tested', 'Turpeen alaraja, pelkkä maaperäkartta: pienin testatuilla perusvuosilla', FS)
    num(D, 'floor_max', max(x['pct'] for x in fr['bases']), 'pct', 2, 'Peat floor, soil map only: highest across the bases tested', 'Turpeen alaraja, pelkkä maaperäkartta: suurin testatuilla perusvuosilla', FS)
    num(D, 'floor_inv', b['inventory_2025']['pct'], 'pct', 2, 'Peat floor as a share of the 2025 inventory', 'Turpeen alaraja osuutena vuoden 2025 inventaariosta', FS)
    num(D, 'floor_tgt', b['target_base']['pct'], 'pct', 2, 'Peat floor as a share of the target base', 'Turpeen alaraja osuutena tavoiteperusvuodesta', FS)
    num(D, 'floor_n_bases', float(fr['n']), 'n', 0, 'Bases and denominator recipes tested', 'Testatut perusvuodet ja nimittäjät', FS)
    num(D, 'farmer_mineral_ha', fr['farmer_mineral_ha_2025'], 'ha', 0, 'Mapped peat where growers answered mineral soil, 2025', 'Kartoitettu turve, jolla viljelijä vastasi kivennäismaa, 2025', FS)
    num(D, 'farmer_rule_pct', fr['farmer_rule_pct_2025'], 'pct', 2, 'Peat change if growers\' mineral answers were accepted', 'Turvemuutos, jos viljelijöiden kivennäismaavastaukset hyväksytään', FS)
    num(D, 'floor_margin_t', fr['worst_margin_t'], 't', 0, 'Tonnes above the 5% line on the lowest base', 'Tonnit 5 %:n rajan yläpuolella pienimmällä perusvuodella', FS)
    assert fr['verdict_survives_worst_base'] and min(x['pct'] for x in fr['bases']) > 5.0
    L.append('floor: %.2f-%.2f%% across %d bases (worst margin %.1f t); farmer answers %.0f ha -> %.2f%%' % (
        min(x['pct'] for x in fr['bases']), max(x['pct'] for x in fr['bases']), fr['n'], fr['worst_margin_t'], fr['farmer_mineral_ha_2025'], fr['farmer_rule_pct_2025']))
    for k, en, fi in (('ca12_peat_rank', "CA12's rank by Finnish contract peat hectares.", 'CA12:n sija suomalaisissa sopimusturvehehtaareissa.'),
                      ('ca12_n', 'Catchments with Finnish contract area.', 'Valuma-alueet, joilla on suomalaista sopimusalaa.')):
        D['v3']['numbers'][k]['en'], D['v3']['numbers'][k]['fi'] = en, fi

    # 6. Pudasjarvi chip on one base (pj-review4 R8, step-12420-7 claims_v4_01): band and trigger both on the reported 2025 total
    ch = D['bundle']['meter']['chips']['pudasjarvi']
    den = ch['denominator_t']
    slope = ch['t'] / (ch['copack_ef_kg_per_kg'] - ch['breakeven_copack_kg_per_kg'])
    assert abs(slope - ch['pizza_t']) < 0.01, (slope, ch['pizza_t'])
    lo_old, tr_old = ch['lo_pct'], ch['trigger_copack_kg_per_kg']
    ch['lo_pct'] = 100 * ch['lo_t'] / den
    ch['trigger_copack_kg_per_kg'] = ch['breakeven_copack_kg_per_kg'] + D['bundle']['meter']['line_pct'] / 100 * den / ch['pizza_t']
    ch['band_rule'] += '; v5: both ends and the trigger on the reported 2025 total (one base)'
    for k in ('chip.pudasjarvi.lo_pct', 'chip.pudasjarvi.tr'):
        D['prov'][k] = {'l': 'derivation', 's': 'bundle meter.chips.pudasjarvi re-based on the reported 2025 total (lo_t ÷ total; breakeven + 5%% × total ÷ pizza tonnes) [%s]' % S5}
    L.append('pudasjarvi: lo %.2f%% (pro forma) -> %.2f%% (reported); trigger %.3f -> %.3f kg/kg (reported base); placeholder %.2f kg/kg' % (
        lo_old, ch['lo_pct'], tr_old, ch['trigger_copack_kg_per_kg'], ch['copack_ef_kg_per_kg']))
    assert ch['lo_pct'] < 5 < ch['hi_pct'] and ch['trigger_copack_kg_per_kg'] < ch['copack_ef_kg_per_kg']

    # 6b. pj-review4 R10 (rotation on one perimeter, Finland) and R11 (retired is not rewetted): values printed by step-12696-2/fix.py
    td = vendored(HERE, 'review4_fix_trunk.diff').read_text(encoding='utf-8')
    m = re.search(r'^\+  var FX = (\{.*\});$', td, re.M)
    FX = json.loads(m.group(1))
    FS2 = 'python3 stages/step-12696-2/fix.py → FX.'
    P = D['promise']
    assert abs(FX['pace']['flag_cut_per_year_t'] - P['pace']) < 1e-6 and FX['rot']['t_r'] == P['rot_t_r'], (FX['pace'], P['rot_t_r'])
    old = (P['rot_t'], P['rot_years'], P['rot_pct_base'])
    P['rot_t'], P['rot_years'], P['rot_pct_base'] = FX['rot']['t'], FX['rot']['years'], FX['rot']['pct_base']
    for k in ('p.rot_t', 'p.rot_t_r', 'p.rot_years', 'p.rot_pct_base'):
        D['prov'][k] = {'l': 'derivation', 's': FS2 + 'rot (mean |move| of Finnish contract-crop peat hectares in declared years × CO₂e per hectare; one perimeter, Finland)'}
    L.append('rotation on the Finnish perimeter: %.0f t, %.2f yr, %.2f%% -> %.0f t, %.2f yr, %.2f%% (shown "about %d t")' % (old + (P['rot_t'], P['rot_years'], P['rot_pct_base'], P['rot_t_r'])))
    for k, v, u, dp, en, fi in (('grass_t_ha', FX['peat']['grass_t_ha'], 'tha', 1, 'Drained peat under grass, CO₂ per hectare (pack factor)', 'Ojitettu turve nurmella, CO₂ hehtaarilta (paketin kerroin)'),
                                ('crop_t_ha', FX['peat']['crop_t_ha'], 'tha', 1, 'Drained peat under crops, CO₂ per hectare (pack factor)', 'Ojitettu turve viljelyssä, CO₂ hehtaarilta (paketin kerroin)'),
                                ('retire_t', FX['peat']['retire_t'], 't', 0, 'L11 hectares retired to grass: tonnes saved', 'L11:n hehtaarit nurmelle: säästetyt tonnit'),
                                ('retire_pct', FX['peat']['retire_pct'], 'pct', 1, 'Share of the per-hectare credit a parcel retired to grass earns', 'Osuus hehtaarikohtaisesta hyvityksestä, jonka nurmelle poistettu lohko saa')):
        num(D, 'w_' + k, v, u, dp, en, fi, FS2 + 'peat.' + k, 'data' if k.endswith('t_ha') else 'derivation')
    L.append('retired vs rewetted: grass %.1f vs crop %.1f t CO2/ha; retiring L11 hectares saves %.0f t, %.1f%% of the credit' % (FX['peat']['grass_t_ha'], FX['peat']['crop_t_ha'], FX['peat']['retire_t'], FX['peat']['retire_pct']))

    # 7. first-screen hero labels (step-11875-1 trace_v4_02)
    hero = 'v4model.gaps on data.js route + rlev: recommended route, central bands, L11 credit zero, three demand scenarios; reproduced exactly by an independent route model (claim audit 1794012420-7) [%s]' % S5
    for k in ('v4.gap2032_lo', 'v4.gap2032_hi', 'v4.gap2035_lo', 'v4.gap2035_hi'):
        D['prov'][k] = {'l': 'derivation', 's': hero}
    for k in ('v4.r2032.cap', 'v4.r2035.cap', 'v4.r.price_hi', 'v4.r.price_lo'):
        D['prov'][k] = {'l': 'assumption', 's': 'catalogue field-lever price (L09 to L12 central) as the per-tonne ceiling; pilot cap = central year-one tonnes × ceiling. A term we set, not a quote [%s]' % S5}
    for k in ('v4.rec_eur', 'v4.rec_cap', 'v4.rec_opex', 'v4.rec_capex', 'd.rcost', 'd.rcapex'):
        D['prov'][k] = {'l': 'assumption', 's': 'catalogue capex and opex (05_scenarios/decarbonisation_levers.csv), capital at an assumed 8%% over each lever\'s lifetime; design estimates, not quotes [%s]' % S5}
    D['prov']['v4.r.noise'] = {'l': 'data', 's': WS + ' (rapeseed PCFs in the base with a valid 2024 file)'}
    return L


DISPLAY = [  # visible source names: the stage, not the development folder it was made in; the map is source_map.json
    ('step-09804-3/pj-v3', 'route'), ('a-final', 'inventory'), ('pj-data', 'bundle'), ('b-path', 'pathways'), ('pj-v2', 'promise'),
    ('pj-promise', 'promise'), ('pj-v3', 'route'), ('pj-v4', 'pipeline'), ('pj-v5', 'pipeline'), ('pj-future', 'climate'), ('c3-eur', 'climate-eur'),
    ('c2-risk-2', 'climate-risk'), ('c1-yield-b', 'yields'), ('d-final', 'catchments'), ('pj-rape', 'rapeseed'), ('model-c-c', 'second-pipeline'),
    ('model-b2', 'mandates'), ('model-b3', 'whose'), ('model-b', 'pillars'), ('pj-review', 'checks'),
]


def neutral(s, used):
    def path(m):
        f = m.group(1)
        for a, b in DISPLAY:
            if f == a or f.startswith(a + '/'):
                used[b] = 'stages/' + a
                return b + f[len(a):]
        mm = re.match(r'um-(\d{10}-\d+)$', f)
        if mm:
            used['audit-' + mm.group(1)] = 'stages/' + f
            return 'audit-' + mm.group(1)
        used[f] = 'stages/' + f
        return f
    s = re.sub(r'stages/((?:um-\d{10}-\d+/pj-v3)|[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*?)(?=/|\b|$)', path, s)
    s = re.sub(r'(?<![\w/.-])um-(\d{10}-\d+)(?=/)', lambda m: used.setdefault('audit-' + m.group(1), 'stages/um-' + m.group(1)) and 'audit-' + m.group(1), s)
    for a, b in (('pj-v3 data.js', 'route data.js'), ('pj-v3 ', 'route ')):
        s = s.replace(a, b)
    bare = {'model-b2': 'mandates', 'model-b3': 'whose', 'model-b': 'pillars', 'model-c-c': 'second-pipeline'}
    s = re.sub(r'(?<![\w/.-])(model-b2|model-b3|model-b|model-c-c)(?![\w-])', lambda m: used.setdefault(bare[m.group(1)], 'stages/' + m.group(1)) and bare[m.group(1)], s)
    if 'review' in s:
        used['stress (in file names)'] = 'review'
        s = s.replace('review', 'stress')
    if 'attack' in s:
        used['stress (in file names)'] = 'review / attack'
        s = s.replace('attack', 'stress')
    if 'decisions.md' in s:
        used['decision-log'] = 'decisions.md'
        s = s.replace('decisions.md', 'decision-log')
    return s


def neutralise(o, used):
    if isinstance(o, dict):
        return {k: neutralise(v, used) for k, v in o.items()}
    if isinstance(o, list):
        return [neutralise(v, used) for v in o]
    if isinstance(o, str) and ('stages/' in o or 'um-17' in o or 'pj-v3' in o or 'review' in o or 'ar-' in o or 'attack' in o or 'decisions.md' in o):
        return neutral(o, used)
    return o

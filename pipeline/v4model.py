"""v4 figures, computed from the merged data.js (a-final / pj-data outputs). Called by build.py; prints nothing itself.

Mirrors app.js routeGap: lever tonnes × ramp × demand index × FLAG fraction; L11 credit zero; L12 capped at the peat pool;
s12 levers and not-in-inventory levers do not touch FLAG. Extends it to the other two targets the same way.
"""
import json
from pathlib import Path

CAPACITY_OUT = {'L01': 'needs much more biogas than today', 'L14': 'central case needs the highest volume ever bought from lower-factor origins',
                'L22': 'needs an industry coalition; Apetit cannot do it alone'}


def ramp(L, y):
    return 0.0 if y < L['start'] else min(1.0, (y - L['start'] + 1) / max(L['ramp'], 1))


def gaps(D, on, y, s, band=None, cut=0.0):
    """Gaps for the three targets in year y, scenario s, levers `on` at `band` (default central)."""
    RT, P = D['route'], D['promise']
    j = y - 2025
    v = RT['v'][s][j]
    red = {'s12': 0.0, 's3nf': 0.0, 'flag': 0.0}
    for L in D['rlev']:
        if L['id'] not in on or L['cls'] == 'not_in_inventory':
            continue
        t = L['t'][band or 'central']
        r = ramp(L, y) * v
        if L['bucket'] == 's12':
            red['s12'] += t * r
            continue
        if L['id'] == 'L11':
            continue  # reallocation: zero physical credit
        tf = min(t, P['peat_t']) if L['id'] == 'L12' else t
        red['flag'] += tf * r * L['ff']
        red['s3nf'] += t * r * (1 - L['ff'])
    g = {k: RT['bau'][s][k][j] - RT['target'][k][j] - red[k] for k in red}
    g['flag'] -= cut / 100 * RT['seed'] * v
    return g, red


def rng(D, on, y, k, band=None):
    vals = [gaps(D, on, y, s, band)[0][k] for s in D['route']['main']]
    return min(vals), max(vals)


def compute(D, ROOT):
    RT, P = D['route'], D['promise']
    ids = [L['id'] for L in D['rlev']]
    lv = {L['id']: L for L in D['rlev']}
    out = {'script': 'python3 stages/pj-v4/build.py (v4model.py)', 'synthetic_only': True}

    # check: the model reproduces the bank's physical catalogue gaps (every lever on, L11 zero)
    for y in (2032, 2035):
        lo, hi = rng(D, ids, y, 'flag')
        assert abs(lo - P['gap%d_noL11_lo' % y]) < 0.5 and abs(hi - P['gap%d_noL11_hi' % y]) < 0.5, (y, lo, hi)
    out['model_check'] = 'reproduces promise.gap2032/2035_noL11 within 0.5 t'

    # capacity-clean route and saving set (L7: capacity the data shows)
    rec = [i for i in RT['rec'] if i not in CAPACITY_OUT]
    sav = [i for i in RT['sav'] if i not in CAPACITY_OUT]
    out['capacity_out'] = CAPACITY_OUT
    out['rec_before'], out['sav_before'] = RT['rec'], RT['sav']
    RT['rec'], RT['sav'] = rec, sav
    cost = sum(lv[i]['cost'] for i in rec)
    capex = sum(lv[i]['capex'] for i in rec)
    m = json.loads((Path(ROOT) / 'stages/model-b2/metrics.json').read_text())
    adj = (Path(ROOT) / 'stages/model-b2/app/data.js').read_text()
    MAN = json.loads(adj[adj.index('{'):adj.rindex('}') + 1])['MANDATE']
    assert sorted(MAN['presets']['route']) == sorted(rec), 'route differs from the mandate build'
    assert abs(m['route']['cost'] - cost) < 0.01 and abs(m['route']['capex'] - capex) < 0.01
    out.update(rec_eur=cost, rec_capex=capex, rec_annual_capital=m['route']['annual_capital'], rec_cash_opex=m['route']['cash_opex'],
               split_source='python3 stages/model-b2/build.py → metrics.json (same lever set, same cost, checked)')
    P['rec_eur'], P['rec_capex'] = cost, capex
    P['sav_n'] = len(sav)
    P['sav_t'] = sum(lv[i]['t']['central'] for i in sav)
    P['sav_eur'] = sum(lv[i]['cost'] for i in sav)
    out.update(sav_n=P['sav_n'], sav_t=P['sav_t'], sav_eur=P['sav_eur'], sav_capex=sum(lv[i]['capex'] for i in sav),
               sav_flag_t=sum(lv[i]['t']['central'] * lv[i]['ff'] for i in sav))

    # physical supplier cut: the recommended route's physical FLAG gap ÷ bought-rapeseed FLAG in that year, per scenario
    for y in (2032, 2035):
        j = y - 2025
        cuts = []
        for s in RT['main']:
            g = gaps(D, rec, y, s)[0]['flag']
            seed = RT['seed'] * RT['v'][s][j]
            cuts.append(100 * g / seed)
        out['cutphys%d_lo' % y], out['cutphys%d_hi' % y] = min(cuts), max(cuts)
        out['cutbooked%d_lo' % y], out['cutbooked%d_hi' % y] = P['cut%d_lo' % y], P['cut%d_hi' % y]
        # verdict worst case: every catalogue lever on at its HIGH band, physical cuts only, most favourable scenario
        out['worst%d_flag_lo' % y] = rng(D, ids, y, 'flag', 'high')[0]
        assert out['worst%d_flag_lo' % y] > 0, 'verdict "not on today\'s catalogue" fails its own worst case'

    # recommended route: three targets, and the HVO pause (L20 off)
    for y in (2032, 2035):
        for k in ('s12', 's3nf', 'flag'):
            out['route%d_%s_lo' % (y, k)], out['route%d_%s_hi' % (y, k)] = rng(D, rec, y, k)
            out['pause%d_%s_lo' % (y, k)], out['pause%d_%s_hi' % (y, k)] = rng(D, [i for i in rec if i != 'L20'], y, k)
        out['routelow%d_flag_hi' % y] = rng(D, rec, y, 'flag', 'low')[1]
        d = [gaps(D, [i for i in rec if i != 'L20'], y, s)[0]['s3nf'] - gaps(D, rec, y, s)[0]['s3nf'] for s in RT['main']]
        out['pausedelta%d_lo' % y], out['pausedelta%d_hi' % y] = min(d), max(d)
        assert abs(out['pause%d_flag_lo' % y] - out['route%d_flag_lo' % y]) < 1e-9  # pausing HVO leaves FLAG where it is
    out['hvo_cost'] = lv['L20']['cost']
    out['hvo_flag_t'] = lv['L20']['t']['central'] * lv['L20']['ff']
    out['hvo_share_pct'] = 100 * lv['L20']['cost'] / cost
    out['route_flag_cut_t'] = sum(lv[i]['t']['central'] * lv[i]['ff'] for i in rec if lv[i]['bucket'] == 'flag' and i != 'L11')
    # checks against the mandate build's own metrics (2035, current policies, central)
    g35, _ = gaps(D, rec, 2035, 'current_policies')
    out['route2035_cp'] = g35
    out['mandate_build_2035_cp'] = m['route']['gap']
    out['pause_s3nf_delta_2035_cp'] = gaps(D, [i for i in rec if i != 'L20'], 2035, 'current_policies')[0]['s3nf'] - g35['s3nf']

    # bought-rapeseed plan: pj-rape's method (stages/pj-rape/rape.py, plan.md) re-run on THIS route gap.
    # pj-rape priced 53,358 t / 65,336 t, a route gap that takes the crop plan's rotation credit (1,071 t in 2035);
    # Jälki holds contract peat at its 2025 area, so the plan is re-priced here on the same gap the page shows.
    plan = Path(ROOT) / 'stages/pj-rape/plan.md'
    sc = json.loads((Path(ROOT) / 'stages/pj-rape/scores.json').read_text())
    out['rape_plan_sha256'] = __import__('hashlib').sha256(plan.read_bytes()).hexdigest()
    assert abs(sc['facts']['seed_flag_t'] - RT['seed']) < 0.01
    assert abs(sc['facts']['physical_gap_2035_t']['current_policies'] - (out['route2035_cp']['flag'] - P['rotcredit2035_lo'])) < 0.5
    seed_t, seed_flag, paid = sc['seed']['seed_t'], RT['seed'], sc['seed']['eur_per_t']
    int0 = sc['seed']['flag_t_per_t']
    cb = sc['cost_band']
    pc_lo, pc_hi, pf_lo, pf_hi = cb['central_lo'], cb['central_hi'], cb['lo'], cb['hi']
    H = sc['review']
    R = {'source': 'method of python3 stages/pj-rape/rape.py (plan.md), re-run by python3 stages/pj-v4/build.py on the route gap shown',
         'price_central_lo': pc_lo, 'price_central_hi': pc_hi, 'price_full_lo': pf_lo, 'price_full_hi': pf_hi,
         'seed_t': seed_t, 'seed_flag_t': seed_flag, 'seed_share_pct': sc['facts']['seed_share_pct'], 'paid_eur_t': paid,
         'int_now': int0, 'int_min_origin': H['min_library_flag_int'], 'int_min_pcf': H['min_observed_pcf_flag_int'],
         'pcf_noise_median_pct': H['pcf_yoy_median_pct'], 'origin_feasible_t': sc['origin_switch'].get('feasible_t'),
         'ramp_years': sc['offer_gate']['ramp_years'], 'floor_frac': sc['offer_gate']['floor_frac_assumption'], 'pj_rape_gap_2035_cp': sc['facts']['physical_gap_2035_t']['current_policies']}
    for y in (2032, 2035):
        j = y - 2025
        rows = {}
        for s in ('current_policies', 'net_zero_2050'):
            g = gaps(D, rec, y, s)[0]['flag']
            v = RT['v'][s][j]
            cut = g / (seed_flag * v)
            rows[s] = {'gap_t': g, 'cut_pct': 100 * cut, 'cut_t_per_t_seed': g / (seed_t * v), 'target_int': int0 * (1 - cut),
                       'eur_central': [g * pc_lo, g * pc_hi], 'eur_full': [g * pf_lo, g * pf_hi],
                       'x_route': [g * pc_lo / cost, g * pc_hi / cost],
                       'premium_eur_t_seed': [g * pc_lo / (seed_t * v), g * pc_hi / (seed_t * v)],
                       'premium_pct_paid': [100 * g * pc_lo / (seed_t * v) / paid, 100 * g * pc_hi / (seed_t * v) / paid]}
        cp, nz = rows['current_policies'], rows['net_zero_2050']
        assert cp['target_int'] < R['int_min_origin'] and cp['target_int'] < 1.0
        # pilot gate: three suppliers with PCFs, sized on this year's cut (current policies), quarter-ramp year one
        offers = []
        for o in sc['offer_gate']['offers'][:3]:
            c = o['flag_t'] * cp['cut_pct'] / 100 / R['ramp_years']
            offers.append({'supplier': o['supplier'], 'country': o['country'], 'share_pct': o['share_pct'], 'central_t': c,
                           'floor_t': c * R['floor_frac'], 'cap_eur': c * o['price_ceiling_eur_t'], 'ceiling_eur_t': o['price_ceiling_eur_t']})
        pil = {'share_pct': sum(o['share_pct'] for o in offers), 'central_t': sum(o['central_t'] for o in offers),
               'floor_t': sum(o['floor_t'] for o in offers), 'cap_eur': sum(o['cap_eur'] for o in offers)}
        pil['floor_pct_gap'] = 100 * pil['floor_t'] / cp['gap_t']
        pil['cap_pct_route'] = 100 * pil['cap_eur'] / cost
        R[str(y)] = {'current_policies': cp, 'net_zero_2050': nz, 'offers': offers, 'pilot': pil,
                     'eur_lo': min(cp['eur_central'][0], nz['eur_central'][0]), 'eur_hi': max(cp['eur_central'][1], nz['eur_central'][1]),
                     'x_lo': min(cp['x_route'][0], nz['x_route'][0]), 'x_hi': max(cp['x_route'][1], nz['x_route'][1]),
                     'tpt_lo': min(cp['cut_t_per_t_seed'], nz['cut_t_per_t_seed']), 'tpt_hi': max(cp['cut_t_per_t_seed'], nz['cut_t_per_t_seed']),
                     'int_lo': min(cp['target_int'], nz['target_int']), 'int_hi': max(cp['target_int'], nz['target_int'])}
    out['rape'] = R
    return out


NEUTRAL = [  # visible source labels: name the script, not the internal build folder it was copied from
    (r'stages/model-c-c/app/data\.js#', 'second pipeline (analysis.py, built blind from the raw pack) · data.js#'),
    (r'run/lock\.md#pj-v3', 'review rule: a correction of 10 t or more blocks signing until decided'),
    (r'run/lock\.md#hard-rule', 'data rule: the non-CC-BY sample workbook is withheld from the pack'),
    (r'stages/pj-review/scores\.json#q2\.facts_hold', 'facts checker (s00_facts.py): brief facts that hold'),
    (r'stages/step-04760-6/attack_rc5\.json#board', 'peat sensitivity run (leave-one-farm-out), rc5.json#board'),
]


def clean_sources(D, ROOT):
    """Replace model-b data.js references by the script that made the number; neutral labels for the rest."""
    import re
    s = (Path(ROOT) / 'stages/model-b/app/data.js').read_text()
    NUM = json.loads(s[s.index('{'):s.rindex('}') + 1])['NUM']
    n = 0
    for k, q in D['v3']['numbers'].items():
        src = q.get('source', '')
        m = re.match(r'stages/model-b/app/data\.js#NUM\.(\w+)', src)
        if m and m.group(1) in NUM:
            q['source'] = NUM[m.group(1)]['s'] + ' → ' + m.group(1)
            n += 1
        m = re.match(r'stages/model-b/app/data\.js#CROPS\.(\w+)\.(\w+)', src)
        if m:
            q['source'] = 'python3 stages/pj-future/f10_join.py · C2-A/B · c3-eur → ' + m.group(1) + '.' + m.group(2)
            n += 1
        for pat, rep in NEUTRAL:
            if re.search(pat, q['source']):
                q['source'] = re.sub(pat, rep, q['source'])
                n += 1
    D['v3']['review_source'] = re.sub(r'stages/model-c-c/', 'second pipeline: ', D['v3']['review_source'])
    SCRIPTS = [(r'python3 stages/model-c-c/analysis\.py', 'second pipeline, built blind from the raw pack (analysis.py)'),
               (r'python3 stages/pj-review/review\.py', 'facts checker and probe-gate check (see source_map.json)'),
               (r'python3 stages/step-04760-6/attack_rc5\.py', 'peat sensitivity run, leave-one-farm-out (see source_map.json)')]
    smap = {}
    for q in D['v3']['numbers'].values():
        for pat, rep in SCRIPTS:
            if q.get('script') and re.search(pat, q['script']):
                smap[rep] = re.search(pat, q['script']).group(0)
                q['script'] = rep
                n += 1
    for k, v in list(D.get('promise_notes', {}).items()):
        if isinstance(v, str) and 'pj-review' in v:
            D['promise_notes'][k] = re.sub(r'\s*from pj-review R2', '', v).replace('pj-review', 'the gate check')
            n += 1
    (Path(ROOT) / 'stages/pj-v4/source_map.json').write_text(json.dumps(smap, indent=1))
    left = [q['source'] for q in D['v3']['numbers'].values() if re.search(r'model-b|model-c|lock\.md|attack|review|px-', q['source'])]
    assert not left, left[:3]
    return n

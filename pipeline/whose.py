"""Whose numbers is the 2025 base made of? Recomputed for Jälki v5 from the shipped trail and the raw pack.

Run: python3 stages/pj-v5/whose.py        (build.py imports compute() and writes whose.json)
Reads only:
  base/app/data.js         the trunk bundle (line FLAG fractions, totals, required FLAG cut, v4 physical cut and ramp)
  base/app/trail/*         the 2025 edge trail Jälki ships (every edge: record, factor, tonnes)
  twin/data/data/01_master/emission_factor_library.csv, materials.csv
  twin/data/data/02_raw_feeds/supplier_pcfs/*.json   (2024 and 2025 files, read raw)
Rules stated before computing (not tuned):
  author of a tonne = who writes its factor: library row, supplier PCF, our farm rows, standard constants, use/end-of-life constants.
  a PCF file is valid for year Y if declared per kilogram, value < 100 kg/kg and its reference period starts in Y (METHODOLOGY s4).
  swing = |2025 / 2024 - 1| for rapeseed materials M101-M107 whose 2025 PCF is in the base and whose 2024 file is valid.
  year-one cut = the recommended route's physical supplier cut for 2032 / the plan's ramp years (both from v4).
Synthetic pack only: no figure is Apetit's real emissions.
"""
import csv, hashlib, json, re, statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACK = ROOT / 'twin/data/data'
RAPE = ('M101', 'M102', 'M103', 'M104', 'M105', 'M106', 'M107')


def _js(p, start='{'):
    s = Path(p).read_text(encoding='utf-8')
    return json.loads(s[s.index(start):s.rindex('}') + 1])


def load_trail(app):
    meta = (app / 'trail/meta.js').read_text(encoding='utf-8')
    M = json.JSONDecoder().raw_decode(meta, meta.index('Object.assign(window.TRAIL,') + len('Object.assign(window.TRAIL,'))[0]
    k = 'window.TRAIL.factors_text='
    M['factors_text'] = json.JSONDecoder().raw_decode(meta, meta.index(k) + len(k))[0]
    shards = []
    for f in sorted((app / 'trail/l').glob('*.js')):
        s = f.read_text(encoding='utf-8')
        shards.append(json.loads(s[s.index('=') + 1:s.rindex(';')]))
    return M, shards


def group_of(f, lib):
    if f in lib:
        return 'library'
    p = f.split(':')[0]
    if p == 'PCF':
        return 'supplier'
    if p == 'FARMROW':
        return 'farms'
    if p in ('FUEL_EF', 'GWP', 'RESIDUAL_FI', 'RESIDUAL_SE', 'COMMUTE', 'GRID', 'FUEL_BIOGENIC'):
        return 'ops'
    if p in ('USE', 'EOL'):
        return 'product'
    raise SystemExit('unmapped factor ' + f)


def pcf_file(p):
    j = json.loads(p.read_text(encoding='utf-8'))
    q = j['pcf']
    s, m, y = p.stem.split('_')
    v = float(q['pCfExcludingBiogenic'])
    per = (q.get('referencePeriodStart') or '')[:4]
    return (s, m, y), {'value': v, 'unit': q.get('declaredUnit'), 'period': per, 'primary': q.get('primaryDataShare'),
                       'assured': bool((q.get('assurance') or {}).get('assurance')), 'file': 'data/02_raw_feeds/supplier_pcfs/' + p.name,
                       'valid': q.get('declaredUnit') == 'kilogram' and v < 100 and per == y}


def compute(D=None, app=None):
    app = app or HERE / 'base/app'
    D = D or _js(app / 'data.js')
    B = D['bundle']
    M, shards = load_trail(app)
    lib = {r['ef_id']: r for r in csv.DictReader(open(PACK / '01_master/emission_factor_library.csv', encoding='utf-8'))}
    mats = {r['material_id']: r for r in csv.DictReader(open(PACK / '01_master/materials.csv', encoding='utf-8'))}
    TOT = B['inventory_2025']['totals']['total_market']
    ff = {l['line_id']: ((l.get('flag_t') or 0.0) / l['tco2e'] if l['tco2e'] else 0.0) for l in B['inventory_2025']['lines']}
    byF, byFflag, nE, tot = defaultdict(float), defaultdict(float), 0, 0.0
    for s in shards:
        if s['scope'] not in ('scope1', 'scope2_market', 'scope3'):
            continue
        c = {k: i for i, k in enumerate(s['cols'])}
        for e in s['edges']:
            t = e[c['t']] or 0.0
            nE += 1
            tot += t
            f = e[c['factor']]
            if not f:
                assert abs(t) < 1e-9
                continue
            byF[f] += t
            byFflag[f] += t * ff.get(s['line_id'], 0.0)
    assert abs(tot - TOT) < 0.01, (tot, TOT)
    out = {'synthetic_only': True, 'script': 'python3 stages/pj-v5/whose.py', 'base_t': TOT, 'edges': nE}
    G = defaultdict(lambda: {'t': 0.0, 'flag_t': 0.0, 'n': 0})
    for f, t in byF.items():
        g = G[group_of(f, lib)]
        g['t'] += t
        g['flag_t'] += byFflag[f]
        g['n'] += abs(t) > 1e-9
    assert abs(sum(g['t'] for g in G.values()) - TOT) < 0.01
    out['authors'] = {k: {'t': v['t'], 'flag_t': v['flag_t'], 'n': v['n'], 'share_pct': 100 * v['t'] / TOT, 'break_pct': 5 / (100 * v['t'] / TOT) * 100}
                      for k, v in G.items()}
    # one library source
    fam = defaultdict(lambda: {'t': 0.0, 'flag_t': 0.0, 'n': 0})
    for f, t in byF.items():
        if f in lib and abs(t) > 1e-9:
            k = lib[f]['reference_source']
            fam[k]['t'] += t
            fam[k]['flag_t'] += byFflag[f]
            fam[k]['n'] += 1
    src, top = max(fam.items(), key=lambda kv: kv[1]['t'])
    r_star = 0.05 * TOT / top['t']
    req = D['promise']['pace']  # required FLAG cut a year on the recalculated base (2032 V2 linear path)
    out['top'] = {'source': src, 'n': top['n'], 't': top['t'], 'flag_t': top['flag_t'], 'share_pct': 100 * top['t'] / TOT,
                  'break_pct': 100 * r_star, 'ghost_flag_t': r_star * top['flag_t'], 'ghost_years': r_star * top['flag_t'] / req, 'req_cut_t': req}
    # supplier PCFs, raw files
    files = dict(pcf_file(p) for p in sorted((PACK / '02_raw_feeds/supplier_pcfs').glob('*.json')))
    sup = []
    for f, t in byF.items():
        if not f.startswith('PCF:') or abs(t) < 1e-9:
            continue
        _, s, m, y = f.split(':')
        b, a = files[(s, m, y)], files.get((s, m, '2024'))
        assert b['valid'], f  # a PCF that is in the base must be valid for 2025
        d = mats.get(m, {}).get('default_ef_id')
        dv = float(lib[d]['kgco2e_per_unit']) if d in lib else None
        sup.append({'supplier': s, 'material': m, 't': t, 'share_pct': 100 * t / TOT, 'v25': b['value'], 'v24': a['value'] if a else None,
                    'valid24': bool(a and a['valid']), 'swing_pct': abs(b['value'] / a['value'] - 1) * 100 if a and a['valid'] else None,
                    'signed_pct': (b['value'] / a['value'] - 1) * 100 if a and a['valid'] else None,
                    'primary24': a['primary'] if a else None, 'primary25': b['primary'], 'assured24': a['assured'] if a else None, 'assured25': b['assured'],
                    'fallback_t': t * (dv / b['value'] - 1) if dv else None, 'rapeseed': m in RAPE, 'file25': b['file'], 'file24': a['file'] if a else None})
    sup.sort(key=lambda r: -r['t'])
    out['pcf'] = {'share_pct': 100 * sum(r['t'] for r in sup) / TOT, 'n_used': len(sup),
                  'unassured_share_pct': 100 * sum(r['t'] for r in sup if not r['assured25']) / TOT, 'rows': sup}
    sw = sorted(r['swing_pct'] for r in sup if r['rapeseed'] and r['swing_pct'] is not None)
    out['swing'] = {'n': len(sw), 'min_pct': sw[0], 'max_pct': sw[-1], 'median_pct': statistics.median(sw), 'values_pct': sw,
                    'rule': 'rapeseed PCFs in the 2025 base with a valid 2024 file; |2025/2024 - 1|'}
    # review variant: every valid 2024/2025 rapeseed pair in the raw pack, used in the base or not
    allp = sorted(abs(files[(s, m, '2025')]['value'] / v['value'] - 1) * 100 for (s, m, y), v in files.items()
                  if y == '2024' and m in RAPE and v['valid'] and (s, m, '2025') in files and files[(s, m, '2025')]['valid'])
    out['swing_all_valid'] = {'n': len(allp), 'min_pct': allp[0], 'max_pct': allp[-1], 'median_pct': statistics.median(allp)}
    ramp = D['v4']['rape']['ramp_years']
    out['year1'] = {'lo_pct': D['v4']['cutphys2032_lo'] / ramp, 'hi_pct': D['v4']['cutphys2032_hi'] / ramp, 'ramp_years': ramp,
                    'rule': 'recommended-route physical supplier cut 2032 / ramp years'}
    out['swing_over_cut_n'] = sum(1 for w in sw if w > out['year1']['hi_pct'])
    s5 = sup[0]
    assert s5['supplier'] == 'SUP005'
    out['sup005'] = s5
    # the register Jälki already seals: TRAIL.factors_text, hashed into every signed record
    ft = M['factors_text']
    fp = hashlib.sha256(ft.encode('utf-8')).hexdigest()
    assert fp.startswith(D['seal']['factors'][:16]), (fp, D['seal']['factors'])
    out['register'] = {'n': D['seal']['n_factors'], 'sha256': fp, 'n_carrying_t': sum(1 for v in byF.values() if abs(v) > 1e-9)}
    return out


if __name__ == '__main__':
    W = compute()
    for k, a in sorted(W['authors'].items(), key=lambda kv: -kv[1]['t']):
        print('%-9s %10.1f t %6.2f%%  break %6.1f%%  n=%d' % (k, a['t'], a['share_pct'], a['break_pct'], a['n']))
    t = W['top']
    print('top source %s: %.2f%% of base, break %.2f%%, ghost FLAG %.0f t = %.2f years of %.0f t/yr' % (t['source'], t['share_pct'], t['break_pct'], t['ghost_flag_t'], t['ghost_years'], t['req_cut_t']))
    print('PCFs used %d, %.2f%% of base, unassured %.2f%%' % (W['pcf']['n_used'], W['pcf']['share_pct'], W['pcf']['unassured_share_pct']))
    for r in W['pcf']['rows']:
        print('  %s %s %8.0f t %5.2f%% 24=%s 25=%.4f swing=%s prim %s->%s assured %s->%s fallback %s' % (
            r['supplier'], r['material'], r['t'], r['share_pct'], r['v24'], r['v25'], None if r['swing_pct'] is None else round(r['swing_pct'], 1),
            r['primary24'], r['primary25'], r['assured24'], r['assured25'], None if r['fallback_t'] is None else round(r['fallback_t'])))
    s = W['swing']
    print('rapeseed swing n=%d %.1f-%.1f%% median %.1f%%; all valid pairs n=%d %.1f-%.1f%% median %.1f%%' % (
        s['n'], s['min_pct'], s['max_pct'], s['median_pct'], W['swing_all_valid']['n'], W['swing_all_valid']['min_pct'], W['swing_all_valid']['max_pct'], W['swing_all_valid']['median_pct']))
    print('year-one cut %.2f-%.2f%% (ramp %d); suppliers swinging more than the cut: %d of %d' % (W['year1']['lo_pct'], W['year1']['hi_pct'], W['year1']['ramp_years'], W['swing_over_cut_n'], s['n']))
    print('register', W['register'])
    (HERE / 'whose.json').write_text(json.dumps(W, indent=1, ensure_ascii=False))

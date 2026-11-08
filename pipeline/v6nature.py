"""Jälki v6 nature fold: eutrophication by location and yield, not land area.

Graft of model-b4's parcel join (stages/model-b4/build.py sections 1-3), recomputed here from the pack:
  stages/pj-data/trail (a-final 2025 contract-farm lines: parcels, delivered kg, farm CO2e per farm-crop)
  stages/d-final/repro_a/parcels_2025_primary.csv (shipped D1 model A: P delivered to water per parcel, 2025)
  twin/data/data/01_master/parcels.csv, twin/data/data/06_nature/catchments.csv
Metric: phosphorus to water per tonne harvested, compared crop by crop. For each farm-crop, expected P is
delivered tonnes x the crop's median P per tonne across all Finnish contract farm-crops; the index is actual P / expected P.
1.0 = a typical tonne of the same crop; 2.0 = twice the P per tonne. Catchments are ranked on the same index
(sum of actual P / sum of expected P), only where at least MIN_FARMS farms deliver.
Run: python3 stages/pj-v8/v6nature.py      Writes stages/pj-v8/nature6.json. Stdlib only. Synthetic pack only.
"""
import collections, csv, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[1]
DATA = R / 'twin/data/data'
MIN_FARMS = 3
TOP = 10


def rd(p):
    with open(p, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def med(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


par = {r['parcel_id']: r for r in rd(DATA / '01_master/parcels.csv')}
cat = {r['catchment_id']: r for r in rd(DATA / '06_nature/catchments.csv')}
pA = {r['parcel_id']: float(r['p_to_water_kg']) for r in rd(R / 'stages/d-final/repro_a/parcels_2025_primary.csv')}
idx = json.load(open(R / 'stages/pj-data/trail/index.json'))
lines = [l for l in idx['lines'] if 'contract_farming' in l['item']]
assert len(lines) == 5, lines

# farm-crop units from the trail: CO2e, delivered tonnes, parcels
FC = {}
miss = 0
line_t = 0.0
for l in lines:
    s = json.load(open(R / 'stages/pj-data/trail' / l['shard']))
    line_t += s['t']
    for k, v in s['parties'].items():
        FC[k] = dict(key=k, farm=k.split(':')[1], crop=k.split(':')[2], t=v['t'], t_flag=v.get('t_flag', 0.0), tons=v.get('kg', 0.0) / 1000.0, ha=v.get('ha', 0.0), has_kg='kg' in v, p=0.0, catch=collections.Counter())
    for e in s['edges']:
        e = dict(zip(s['cols'], e))
        if not str(e['record']).startswith('parcel:'):
            continue
        pid = e['record'][7:]
        u = FC[e['party']]
        if pid in pA:
            u['p'] += pA[pid]
        else:
            miss += 1
        u['catch'][par[pid]['catchment_id']] += float(e['clean'])

# crop median P per delivered tonne (farm-crop units with delivery)
units = [u for u in FC.values() if u['tons'] > 0]
crop_med = {c: med([u['p'] / u['tons'] for u in units if u['crop'] == c]) for c in sorted(set(u['crop'] for u in units))}
for u in units:
    u['exp'] = u['tons'] * crop_med[u['crop']]

# farms
F = collections.OrderedDict()
for u in sorted(units, key=lambda x: x['key']):
    f = F.setdefault(u['farm'], dict(farm=u['farm'], t=0.0, p=0.0, exp=0.0, tons=0.0, ha=0.0, catch=collections.Counter()))
    f['t'] += u['t']; f['p'] += u['p']; f['exp'] += u['exp']; f['tons'] += u['tons']; f['ha'] += u['ha']; f['catch'].update(u['catch'])
for f in F.values():
    f['idx'] = f['p'] / f['exp'] if f['exp'] else 0.0
    f['main'] = f['catch'].most_common(1)[0][0]
p_tot = sum(f['p'] for f in F.values())
t_tot = sum(f['t'] for f in F.values())
ha_tot = sum(f['ha'] for f in F.values())

top_t = [f['farm'] for f in sorted(F.values(), key=lambda f: -f['t'])[:TOP]]
top_p = [f['farm'] for f in sorted(F.values(), key=lambda f: -f['p'])[:TOP]]
top_ha = [f['farm'] for f in sorted(F.values(), key=lambda f: -f['ha'])[:TOP]]
both = sorted(set(top_t) & set(top_p))
share = lambda fs, k, tot: 100.0 * sum(F[x][k] for x in fs) / tot
top20_t = [f['farm'] for f in sorted(F.values(), key=lambda f: -f['t'])[:20]]
top20_p = [f['farm'] for f in sorted(F.values(), key=lambda f: -f['p'])[:20]]


def cover(key, frac):
    fs = sorted(F.values(), key=lambda f: -f[key])
    tot = sum(f[key] for f in fs); acc = 0.0; o = []
    for f in fs:
        if acc >= frac * tot:
            break
        o.append(f['farm']); acc += f[key]
    return o


half_t, half_p = cover('t', 0.5), cover('p', 0.5)
ROB = dict(overlap_top20=len(set(top20_t) & set(top20_p)), half_t_farms=len(half_t), half_p_farms=len(half_p),
           half_overlap=len(set(half_t) & set(half_p)), half_t_p_pct=round(share(half_t, 'p', sum(f['p'] for f in F.values())), 1))

# catchments: units split by parcel hectares across catchments
C = collections.defaultdict(lambda: dict(p=0.0, exp=0.0, tons=0.0, t=0.0, ha=0.0, farms=set()))
for u in units:
    tot_ha = sum(u['catch'].values())
    for c, ha in u['catch'].items():
        w = ha / tot_ha if tot_ha else 0.0
        x = C[c]
        x['p'] += u['p'] * w; x['exp'] += u['exp'] * w; x['tons'] += u['tons'] * w; x['t'] += u['t'] * w; x['ha'] += ha; x['farms'].add(u['farm'])
rows = []
for c, x in C.items():
    if len(x['farms']) < MIN_FARMS:
        continue
    rows.append(dict(id=c, idx=round(x['p'] / x['exp'], 3), p_kg=round(x['p'], 1), p_per_t=round(x['p'] / x['tons'], 4), tons=round(x['tons'], 1),
                     t=round(x['t'], 1), ha=round(x['ha'], 1), farms=len(x['farms']), status=cat[c]['ecological_status_class'], water=cat[c]['receiving_water_type']))
rows.sort(key=lambda r: -r['idx'])
for i, r in enumerate(rows):
    r['rank_idx'] = i + 1
for i, r in enumerate(sorted(rows, key=lambda r: -r['t'])):
    r['rank_t'] = i + 1
for i, r in enumerate(sorted(rows, key=lambda r: -r['ha'])):
    r['rank_ha'] = i + 1
ca12 = [r for r in rows if r['id'] == 'CA12']
top3_idx = rows[:3]
top3_t_ids = [r['id'] for r in sorted(rows, key=lambda r: -r['t'])[:3]]

out = dict(
    synthetic_only=True, script='python3 stages/pj-v8/v6nature.py',
    inputs=['stages/pj-data/trail/l/104-108.json', 'stages/d-final/repro_a/parcels_2025_primary.csv', 'twin/data/data/01_master/parcels.csv', 'twin/data/data/06_nature/catchments.csv'],
    farms=len(F), units=len(units), units_all=len(FC), units_no_kg=sum(1 for u in FC.values() if not u['has_kg']),
    units_no_kg_t=round(sum(u['t'] for u in FC.values() if u['tons'] <= 0), 1), units_no_kg_p=round(sum(u['p'] for u in FC.values() if u['tons'] <= 0), 1), parcels_without_p=miss, line_t=round(line_t, 1), farm_t=round(t_tot, 1), p_kg=round(p_tot, 1), ha=round(ha_tot, 1),
    crop_med_p_per_t={k: round(v, 4) for k, v in crop_med.items()},
    top_n=TOP, overlap_top_t_top_p=len(both), overlap_farms=both,
    top_t_p_pct=round(share(top_t, 'p', p_tot), 1), top_t_t_pct=round(share(top_t, 't', t_tot), 1),
    top_p_p_pct=round(share(top_p, 'p', p_tot), 1), top_p_t_pct=round(share(top_p, 't', t_tot), 1),
    top_ha_p_pct=round(share(top_ha, 'p', p_tot), 1),
    idx_max_farm=round(max(f['idx'] for f in F.values()), 2),
    farms_idx_ge2=sum(1 for f in F.values() if f['idx'] >= 2.0),
    farms_idx_ge2_p_pct=round(100.0 * sum(f['p'] for f in F.values() if f['idx'] >= 2.0) / p_tot, 1),
    farms_idx_ge2_tons_pct=round(100.0 * sum(f['tons'] for f in F.values() if f['idx'] >= 2.0) / sum(f['tons'] for f in F.values()), 1),
    robust=ROB, min_farms=MIN_FARMS, n_catch=len(rows), catchments=rows,
    ca12=ca12[0] if ca12 else None,
    top3_idx_in_top3_t=sum(1 for r in top3_idx if r['id'] in top3_t_ids),
    idx_spread=[rows[-1]['idx'], rows[0]['idx']],
)
(HERE / 'nature6.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
if __name__ == '__main__':
    print(json.dumps({k: v for k, v in out.items() if k != 'catchments'}, indent=1))
    for r in rows:
        print(r)
else:
    print('NATURE: %d farms, %d catchments; top-10 emitters send %.1f%% of P; overlap %d' % (out['farms'], out['n_catch'], out['top_t_p_pct'], out['overlap_top_t_top_p']))

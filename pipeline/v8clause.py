"""Jälki v8: the phosphorus contract clause for lake catchments, recomputed from the pack.

Clause (first proposed by an alternative build): a buffer strip on every contract parcel that has none, lies within
DMAX m of water, and drains to a catchment whose ecological status is below good (moderate, poor, bad).
Join, as v6nature.py: the inventory trail's 2025 contract-farm lines (one parcel edge each), the shipped catchment
P model A (P delivered to water per parcel, 2025), the pack's parcel register (buffer strip, distance to water,
catchment) and catchment table (ecological status).
Effect: model A multiplies field P by 0.75 when a parcel has a buffer strip (d-final/repro_a/model.py line 125), and
delivered P is field P times distance and retention factors, so a new strip cuts that parcel's delivered P by 25%.
Denominator: all contract P to water on the trail parcels (the same 4,272 kg as the nature card).
Pessimistic re-run: half the model's strip effect (x0.875 instead of x0.75).
Run: python3 stages/pj-v8/v8clause.py      Writes stages/pj-v8/clause8.json. Stdlib only. Synthetic pack only.
"""
import csv, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[1]
DATA = R / 'twin/data/data'
DMAX = 100.0
BELOW_GOOD = ('moderate', 'poor', 'bad')
CUT = 0.25


def rd(p):
    with open(p, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


par = {r['parcel_id']: r for r in rd(DATA / '01_master/parcels.csv')}
cat = {r['catchment_id']: r for r in rd(DATA / '06_nature/catchments.csv')}
pA = {r['parcel_id']: float(r['p_to_water_kg']) for r in rd(R / 'stages/d-final/repro_a/parcels_2025_primary.csv')}
src = (R / 'stages/d-final/repro_a/model.py').read_text(encoding='utf-8').splitlines()
assert 'fp *= 0.75 if p["buffer_strip"] == "True" else 1.0' in src[124], 'model A buffer coefficient moved'
idx = json.load(open(R / 'stages/pj-data/trail/index.json'))
lines = [l for l in idx['lines'] if 'contract_farming' in l['item']]
assert len(lines) == 5, lines

P = {}
for l in lines:
    s = json.load(open(R / 'stages/pj-data/trail' / l['shard']))
    for e in s['edges']:
        e = dict(zip(s['cols'], e))
        if not str(e['record']).startswith('parcel:'):
            continue
        pid = e['record'][7:]
        assert pid not in P, pid
        m = par[pid]
        P[pid] = dict(pid=pid, farm=m['farm_id'], ha=float(m['area_ha']), catch=m['catchment_id'], status=cat[m['catchment_id']]['ecological_status_class'],
                      buf=m['buffer_strip'] == 'True', dist=float(m['dist_to_water_m']), p=pA.get(pid, 0.0))
p_tot = sum(x['p'] for x in P.values())
nobuf = [x for x in P.values() if not x['buf'] and x['p'] > 0]
sel = [x for x in nobuf if x['dist'] <= DMAX and x['status'] in BELOW_GOOD]
kg = CUT * sum(x['p'] for x in sel)
ca12 = [x for x in sel if x['catch'] == 'CA12']
out = dict(
    synthetic_only=True, script='python3 stages/pj-v8/v8clause.py', dmax_m=DMAX, below_good=list(BELOW_GOOD), cut=CUT,
    contract_parcels=len(P), p_total_kg=round(p_tot, 1), nobuf_parcels=len(nobuf),
    parcels=len(sel), farms=len(set(x['farm'] for x in sel)), ha=round(sum(x['ha'] for x in sel), 1),
    kg=round(kg, 1), pct=round(100 * kg / p_tot, 1),
    ca12_parcels=len(ca12), ca12_kg=round(CUT * sum(x['p'] for x in ca12), 1), ca12_status=cat['CA12']['ecological_status_class'],
    half_effect_kg=round(kg / 2, 1), half_effect_pct=round(50 * kg / p_tot, 1),
    catchments=len(set(x['catch'] for x in sel)),
)
# cross-check against the alternative build that first proposed the clause (same join, written independently)
ex = {r['key']: r['value'] for r in json.load(open(R / 'stages/model-b4/numbers.json'))['numbers']} if (R / 'stages/model-b4/numbers.json').exists() else {}
if ex:
    for a, b in (('parcels', 'water_default_parcels'), ('farms', 'water_default_farms'), ('kg', 'water_default_kg'), ('pct', 'water_default_pct'), ('ha', 'water_default_ha')):
        assert abs(out[a] - ex[b]) < 0.051, (a, out[a], ex[b])
    out['cross_check'] = 'matches the Pelto build on parcels, farms, hectares, kg and share'
(HERE / 'clause8.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print('CLAUSE8: %d parcels on %d farms (%.1f ha), about %.1f kg P a year = %.1f%% of %.1f kg contract P; CA12 %d parcels %.1f kg (%s); half effect %.1f kg; %s' % (
    out['parcels'], out['farms'], out['ha'], out['kg'], out['pct'], out['p_total_kg'], out['ca12_parcels'], out['ca12_kg'], out['ca12_status'], out['half_effect_kg'], out.get('cross_check', 'no cross-check')))

"""Jälki v8 (from v7): one rebuild command.

Run: python3 stages/pj-v8/build.py
v8 adds, after blind round R7 (narrow pass): v8model.py (the phosphorus contract clause for lake catchments, v8clause.py)
and v8_layer.js (the promise and its price in the headline, the nature card reworded, the clause line in the nature fold,
no internal paths or development names on screen). Everything below is otherwise v7.
v7 adds, after the stand's ending: v7model.py (the rapeseed decision measured from field records, v7rape.py) and
v7_layer.js (rapeseed framed as the measurement that shows the decision pays, peat in one plain sentence, "Where every
number comes from" on the first screen, one euro format, a tighter first screen). Everything below is otherwise v6.
v6 added, after the stand: v6model.py (Ask the frameworks bank from v6ask.py with its citation check; nature figures from
v6nature.py) and v6_layer.js (framework answers inside the decision flow, eutrophication fold, rapeseed plan framed as what
it should measure, the base-year replay line, the fit note). Everything below is otherwise the v5c build unchanged.

1. Fresh copy of the frozen trunk app (base/app = stages/pj-v4/app as run/trunk.txt named it, hash in base/TRUNK.json).
2. Data layer (v5model.py): route without L07 (v5route.py), whose-numbers figures (whose.py), one PCF-noise number,
   review impacts from the record route, peat floor across the bases tested, Pudasjarvi chip on one base, provenance labels.
3. Visible source names: development folders become stage names (map in source_map.json).
4. Screen layer: checked surgical edits to app.js, then v5_layer.js inserted before the exports, then the code seal.
Writes only inside stages/pj-v5. Synthetic pack only.
"""
import hashlib, json, re, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'base/app'
APP = HERE / 'app'
BUILD = HERE / 'build'
LOG = []
sys.path.insert(0, str(HERE))
import v5model  # noqa: E402
import v6model  # noqa: E402
import v7model  # noqa: E402
import v8model  # noqa: E402
v5model.DISPLAY.insert(0, ('pj-v8', 'pipeline'))


def log(*a):
    s = ' '.join(str(x) for x in a)
    LOG.append(s)
    print(s)


def readjs(p):
    s = Path(p).read_text(encoding='utf-8')
    return json.loads(s[s.index('{'):s.rindex('}') + 1])


def tree_hash(d):
    h = hashlib.sha256()
    for p in sorted(x for x in Path(d).rglob('*') if x.is_file()):
        h.update(str(p.relative_to(d)).encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def sub(text, old, new, label, n=1):
    c = text.count(old)
    if c != n:
        raise SystemExit('EDIT FAILED ' + label + ': found ' + str(c) + ' times, expected ' + str(n) + ': ' + old[:160])
    log('  edit:', label, '(' + str(c) + ')')
    return text.replace(old, new)


# ------------------------------------------------------------------ 1. fresh copy of the frozen trunk
trunk = json.loads((HERE / 'base/TRUNK.json').read_text())
assert tree_hash(BASE) == trunk['tree_sha256'], 'base/app no longer matches the frozen trunk'
log('1. base/app = frozen trunk', trunk['trunk'], trunk['tree_sha256'][:16], '(app.js', trunk['app_js_sha256'][:8] + ')')
for d in [APP]:
    if d.exists():
        shutil.rmtree(d)
shutil.copytree(BASE, APP)
BUILD.mkdir(exist_ok=True)
D = readjs(APP / 'data.js')
D0 = json.loads(json.dumps(D))

# ------------------------------------------------------------------ 2. data layer
log('2. data layer (v5model.py)')
for line in v5model.apply(D, ROOT, HERE):
    log('  ' + line)
log('2b. v6 data layer (v6model.py)')
for line in v6model.apply(D, ROOT, HERE):
    log('  ' + line)
log('2c. v7 data layer (v7model.py)')
for line in v7model.apply(D, ROOT, HERE):
    log('  ' + line)
log('2d. v8 data layer (v8model.py)')
for line in v8model.apply(D, ROOT, HERE):
    log('  ' + line)

# ------------------------------------------------------------------ 3. visible source names
used = {}
D = v5model.neutralise(D, used)
left = []


def scan(o):
    if isinstance(o, dict):
        for v in o.values():
            scan(v)
    elif isinstance(o, list):
        for v in o:
            scan(v)
    elif isinstance(o, str) and re.search(r'stages/|model-b|model-c|review|attack|lock\.md|pj-v3(?![\w-])', o):
        m = re.search(r'stages/|model-b|model-c|review|attack|lock\.md|pj-v3(?![\w-])', o)
        left.append(o[max(0, m.start() - 80):m.end() + 60])


scan(D)
assert not left, left[:5]
# v5a (MANIFEST item 7): the review-threshold drawer named an internal file ("the lock"); the deck drawer's neutral wording
_rt = D['prov']['v3.review_threshold']
assert _rt['s'].count('review-materiality threshold declared in the lock') == 1, _rt['s']
_rt['s'] = _rt['s'].replace('review-materiality threshold declared in the lock', 'review-materiality threshold set for expert review')
log('  edit: review-threshold drawer source worded as the deck (v5a, MANIFEST item 7)')
log('3. visible source names neutralised in data.js:', len(used), 'folders mapped (source_map.json)')

# ------------------------------------------------------------------ 4. screen layer
log('4. screen layer')
app = (APP / 'app.js').read_text(encoding='utf-8')
app = sub(app, "vd += rng('chip.' + c.id + '.lo_pct', 'chip.' + c.id + '.hi_pct') + ' <span class=\"small\">· ' + esc(L2(T.central)) + ' ' + nb('chip.' + c.id + '.pct') + '</span>';",
          "vd += rng('chip.' + c.id + '.lo_pct', 'chip.' + c.id + '.hi_pct') + (Math.abs(CH[c.id].pct - CH[c.id].hi_pct) < 1e-9 && CH[c.id].hi_pct !== CH[c.id].lo_pct ? ' <span class=\"small\">· ' + esc(L2(['estimate at the upper end', 'arvio yläpäässä'])) + '</span>' : ' <span class=\"small\">· ' + esc(L2(T.central)) + ' ' + nb('chip.' + c.id + '.pct') + '</span>') + (c.id === 'peat' ? ' <span class=\"small\">· ' + fx(['floor {r:v3.floor_min,v3.floor_max} across the bases tested', 'alaraja {r:v3.floor_min,v3.floor_max} testatuilla perusvuosilla']) + '</span>' : '');",
          'meter: "central" only inside the band; peat floor across bases (forward-port C04; b4 chair "mean = range max")')
app = sub(app, "<th>Shortfall €/yr</th>", "<th>Shortfall €/yr (model B)</th>", 'crop table: euros come from model B (pj-review4 R9)')
app = sub(app, "<td class=\"src\">stages/pj-future/f10_join.py · C2-A/B · c3-eur</td>", "<td class=\"src\">climate join (f10_join.py): yields A and B, euros on B</td>", 'crop table: raw dev label (b4 spec)')
app = sub(app, "<td>generated", "<td>synthetic", 'visible table labels: "generated" -> "synthetic"', n=5)
app = sub(app, "'CA12 is {n:v3.ca12_peat_rank} of {n:v3.ca12_n} by peat area, holding {k:v3.ca12_peat_pct}.','CA12 on turvealassa {n:v3.ca12_peat_rank}/{n:v3.ca12_n}, osuus {k:v3.ca12_peat_pct}.'",
          "'CA12 is {n:v3.ca12_peat_rank} of {n:v3.ca12_n} by Finnish contract peat area, holding {k:v3.ca12_peat_pct} of it.','CA12 on suomalaisessa sopimusturvealassa {n:v3.ca12_peat_rank}/{n:v3.ca12_n}, osuus {k:v3.ca12_peat_pct}.'",
          'CA12 Finnish boundary (forward-port C14)')
app = sub(app, "L2(['changed on the ground on the route; moving a contract does not restore drained land.', 'muuttuu maastossa reitillä; sopimuksen siirto ei palauta ojitettua maata.'])",
          "L2(['model hectares (tonnes ÷ 34.6 t/ha) rewetted on the route; moving a contract does not restore drained land.', 'mallihehtaaria (tonnit ÷ 34,6 t/ha) soistetaan reitillä; sopimuksen siirto ei palauta ojitettua maata.'])",
          'nature card: model hectares (pj-review4 R6)')
app = sub(app, "each tonne of seed must carry {r:v4.r{Y}.tpt_lo,v4.r{Y}.tpt_hi} less CO₂e: from {k:v4.r.int_now} today to {r:v4.r{Y}.int_lo,v4.r{Y}.int_hi}. The cleanest origin in the factor library is {k:v4.r.int_origin}; the cleanest footprint any supplier has filed is {k:v4.r.int_pcf}.",
          "each tonne of seed must carry {r:v4.r{Y}.tpt_lo,v4.r{Y}.tpt_hi} less FLAG CO₂e: from {k:v4.r.int_now} today to {r:v4.r{Y}.int_lo,v4.r{Y}.int_hi} (FLAG part only, t CO₂e per t of seed). The cleanest origin in the factor library is {k:v4.r.int_origin} on the same FLAG basis; the cleanest footprint any supplier has filed is {k:v4.r.int_pcf}.",
          'rapeseed intensities labelled FLAG-only (b4 agro)')
app = sub(app, "vähemmän CO₂e:tä: nykyisestä {k:v4.r.int_now} tasolle {r:v4.r{Y}.int_lo,v4.r{Y}.int_hi}. Kerroinkirjaston puhtain alkuperä on {k:v4.r.int_origin};",
          "vähemmän FLAG-CO₂e:tä: nykyisestä {k:v4.r.int_now} tasolle {r:v4.r{Y}.int_lo,v4.r{Y}.int_hi} (vain FLAG-osuus, t CO₂e siementonnia kohden). Kerroinkirjaston puhtain alkuperä samalla FLAG-perusteella on {k:v4.r.int_origin};",
          'rapeseed intensities FLAG-only, FI')
app = sub(app, "'The cut cannot be seen in footprints: supplier PCF totals already move by a median {k:v4.r.noise} a year with no programme. Offers must carry field activity data, not just a new PCF.', 'Leikkaus ei näy jalanjäljissä: toimittajien PCF-summat liikkuvat jo {k:v4.r.noise} vuodessa (mediaani) ilman ohjelmaa. Tarjouksissa on oltava peltotiedot, ei pelkkä uusi PCF.'",
          "'The cut cannot be seen in footprints: rapeseed suppliers\\' own footprints moved {r:v3.w_sw_lo,v3.w_sw_hi} in a year (median {k:v4.r.noise}) with no programme, against a year-one cut of {r:v3.w_y1_lo,v3.w_y1_hi}. Offers must carry field activity data, not just a new PCF.', 'Leikkaus ei näy jalanjäljissä: rapsitoimittajien omat jalanjäljet muuttuivat vuodessa {r:v3.w_sw_lo,v3.w_sw_hi} (mediaani {k:v4.r.noise}) ilman ohjelmaa, kun ensimmäisen vuoden leikkaus on {r:v3.w_y1_lo,v3.w_y1_hi}. Tarjouksissa on oltava peltotiedot, ei pelkkä uusi PCF.'",
          'plan: one swing figure everywhere (step-12417-3 mismatch 3; graft)')
app = sub(app, "SUP011\\'s 2025 footprint was filed in the wrong unit and rejected; its first ask is a corrected filing.",
          "SUP011\\'s 2025 footprint was filed in the wrong unit and rejected, so it has no usable footprint yet; its first ask is a corrected filing.",
          'SUP011 readiness (b4 ctrl-codex)')
app = sub(app, 'L01, L14 and L22', 'L01, L07, L14 and L22', 'route exclusions name L07 (EN)', n=app.count('L01, L14 and L22') or 1)
app = sub(app, 'L01, L14 ja L22', 'L01, L07, L14 ja L22', 'route exclusions name L07 (FI)', n=app.count('L01, L14 ja L22') or 1)
app = sub(app, "OFFER.central = Math.round(pl.central_t); OFFER.price = 250; OFFER.cap = Math.round(pl.cap_eur);",
          "OFFER.price = 250; OFFER.central = Math.min(Math.round(pl.central_t), Math.floor(pl.cap_eur / OFFER.price)); OFFER.cap = Math.round(pl.cap_eur);",
          'pilot button: whole tonnes the cap pays for, so its own terms sit inside the cap (v5a, MANIFEST item 6)')
app = sub(app, "the answer is decision 0, not a bigger budget.', 'Jos kukaan toimittaja ei pysty tarjoamaan alarajaansa katon sisällä, vastaus on päätös 0, ei suurempi budjetti.'",
          "the target year comes back to the board, not a bigger budget.', 'Jos kukaan toimittaja ei pysty tarjoamaan alarajaansa katon sisällä, tavoitevuosi palaa hallitukselle, ei suurempi budjetti.'",
          'offer gate: "decision 0" -> "the target year" (pj-v5c, 3 of 3 judges)')
app = sub(app, "T.h_d0 = ['Decision 0 · target year', 'Päätös 0 · tavoitevuosi'];", "T.h_d0 = ['Target year', 'Tavoitevuosi'];",
          'first-screen label: "Decision 0" -> "Target year" (pj-v5c)')
app = sub(app, "decision 0 comes back to the board before any budget.", "the target year comes back to the board before any budget.", 'next week: "the target year comes back to the board" (pj-v5c)')
app = sub(app, "päätös 0 palaa hallitukselle ennen budjettia.", "tavoitevuosi palaa hallitukselle ennen budjettia.", 'next week, FI (pj-v5c)')
app = sub(app, "d('P').title = ['Decision 0 · the target year', 'Päätös 0 · tavoitevuosi'];", "d('P').title = ['Target year', 'Tavoitevuosi'];",
          'decision P title: "Decision 0" -> "Target year" (pj-v5c)')
ANCHOR = '  /* exports for the headless check'
layer = (HERE / 'v5_layer.js').read_text(encoding='utf-8')
m6 = ("  T.m6 = [T.m6[0].replace('is {r:v3.soil_map25_lo,v3.soil_map25_hi} across those bases', 'is {r:v3.floor_min,v3.floor_max} across all {n:v3.floor_n_bases} bases and denominator recipes tested ({k:chip.peat.lo_pct} of the current-practice total, {k:v3.floor_inv} of the 2025 inventory, {k:v3.floor_tgt} of the target base, {k:v3.floor_margin_t} above the line there)'),\n"
      "    T.m6[1].replace('on {r:v3.soil_map25_lo,v3.soil_map25_hi};', 'on {r:v3.floor_min,v3.floor_max} kaikilla {n:v3.floor_n_bases} testatulla perusvuodella ja nimittäjällä ({k:chip.peat.lo_pct} nykykäytännön kokonaispäästöstä, {k:v3.floor_inv} vuoden 2025 inventaariosta, {k:v3.floor_tgt} tavoiteperusvuodesta, siinäkin {k:v3.floor_margin_t} rajan yläpuolella);')];\n"
      "  if (T.m6[0].indexOf('soil_map25') >= 0 || T.m6[1].indexOf('soil_map25') >= 0) throw new Error('m6 floor range not replaced');\n")
layer6 = (HERE / 'v6_layer.js').read_text(encoding='utf-8')
layer7 = (HERE / 'v7_layer.js').read_text(encoding='utf-8')
layer8 = (HERE / 'v8_layer.js').read_text(encoding='utf-8')
app = sub(app, ANCHOR, layer + m6 + '\n' + layer6 + '\n' + layer7 + '\n' + layer8 + '\n' + ANCHOR, 'insert v5_layer.js, v6_layer.js, v7_layer.js, then v8_layer.js, before the exports')
smap = {}
app = re.sub(r'stages/(?:um-\d{10}-\d+/pj-v3|[A-Za-z0-9_\-]+)', lambda m: v5model.neutral(m.group(0), smap), app)
for a, b in (("'pj-v3 data.js", "'route data.js"), ('; pj-v3 data.js#promise', '; route data.js#promise')):
    app = app.replace(a, b)
used.update(smap)
vis = re.findall(r"'[^'\n]*(?:stages/|model-b|model-c)[^'\n]*'", app)
assert not vis, vis[:3]
log('  app.js: development folder names neutralised;', len(smap), 'folders mapped')
(APP / 'app.js').write_text(app, encoding='utf-8')
css = (APP / 'style.css').read_text(encoding='utf-8')
css += ('\n/* v5: whose numbers */\ntable.whose td:nth-child(2),table.whose td:nth-child(3){white-space:nowrap}\nsvg.swing{max-width:560px;margin:10px 0 4px}\n'
        'svg.swing .tick{font-size:11px;fill:#333}\n.mono{font-family:ui-monospace,Menlo,monospace;font-size:.9em}\n'
        '\n/* v5b: first screen. Synthetic tag small in the corner; verdict and floor lead; swing line; decision; decision 0 smaller; pillars quieter */\n'
        '.rail .rr{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}\n'
        '.rail .synth.tagc{border:1px solid var(--hair);color:var(--mid);font-size:.66rem;padding:2px 6px;letter-spacing:.03em;text-transform:none}\n'
        '.hv .hv2{display:block;color:var(--ink);margin-top:6px}.hv .n{font:inherit;color:inherit;letter-spacing:inherit;border-bottom-width:3px}\n'
        '.hsw{font-size:1.3rem;line-height:1.4;max-width:36em;margin:0 0 26px}.hsw b{display:block;margin-top:4px}\n'
        '.hown{font-size:.86rem;color:var(--mid);margin:-4px 0 10px}\n'
        '.d0.d0s{margin:20px 0 0;padding-top:12px;border-top:1px solid var(--hair)}.d0s .d0b{font-size:.85rem;padding:5px 10px}.d0s p.small{margin:2px 0 0}\n'
        '.simnote{margin:4px 0 14px}\n'
        '.pillars.quiet{margin:12px 0 18px;opacity:.85}.pillars.quiet .pillar{border-top:1px solid var(--hair);padding:10px 12px}.pillars.quiet .pillar-value{font-size:.95rem;font-weight:600}\n'
        '@media(max-width:820px){.hsw{font-size:1.1rem}.hv .hv2{margin-top:4px}}\n'
        '\n/* v5c: the shortfall is the big red line; the lever-list line under it is short and plain */\n'
        '.hv .hv2{font-size:.4em;font-weight:500;letter-spacing:-.005em;line-height:1.25;margin-top:10px}\n'
        '@media(max-width:820px){.hv .hv2{font-size:.5em}}\n'
        '\n/* v6: ask the frameworks; nature by yield and location */\n'
        '.ask6p{border:1px solid var(--hair);padding:14px 16px;margin:0 0 22px;background:#fafaf8}.ask6p h3{margin-top:0}\n'
        '.ask6f{display:flex;gap:8px;margin:8px 0}.ask6f input{flex:1;min-width:0;font:inherit;padding:7px 9px;border:1px solid #bbb}.ask6f button{font:inherit;padding:7px 14px}\n'
        'details.ask6{margin:10px 0 12px;border-left:3px solid var(--hair);padding-left:10px}details.ask6>summary{cursor:pointer;font-size:.88rem;font-weight:600}\n'
        '.ask6c{margin:10px 0 14px;padding:10px 0 4px;border-top:1px solid var(--hair)}.ask6c p{margin:4px 0}.ask6q{line-height:1.45}\n'
        '.ask6s{display:inline-block;font-size:.72rem;font-weight:600;padding:1px 6px;border:1px solid var(--hair);color:var(--mid);white-space:nowrap}\n'
        '.ask6s.s-approved{border-color:#1a7f37;color:#1a7f37}.ask6s.s-revise{border-color:#c8102e;color:#c8102e}\n'
        '.ask6l{margin:6px 0;padding-left:18px;font-size:.8rem;color:var(--mid)}.ask6l li{margin:2px 0}.ask6l q{color:var(--ink)}\n'
        '.ask6b{margin:6px 0 2px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}.ask6b button.on{background:#111;color:#fff}\n'
        '.ask6how{margin-top:10px}\n'
        'svg.nat6{max-width:640px;margin:8px 0 2px}svg.nat6 .tick{font-size:11px;fill:#333}svg.nat6 text.n{cursor:pointer;fill:#111}\n'
        '.nat6leg i.sw{display:inline-block;width:10px;height:10px;margin:0 4px 0 8px;vertical-align:-1px}\n'
        '\n/* v7: visual pass. One 12-column grid, one accent (signal red), status in ink, more white space */\n'
        '.ok{color:var(--ink);font-weight:700}.ask6s.s-approved{border-color:var(--ink);color:var(--ink)}.b-rew{fill:var(--ink)}i.b-rew{background:var(--ink)}\n'
        '.hero.h7{padding:40px 0 30px;display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:24px}.h7>*{grid-column:1/-1}\n'
        '.h7 .hq{margin:0 0 18px}.h7 .hq2{color:var(--ink);margin-left:4px}\n'
        '.h7 .hv{font-size:3.6rem;margin:0 0 18px;grid-column:1/11}\n'
        '.h7 .hsw{grid-column:1/10;font-size:1.2rem;line-height:1.45;margin:0 0 18px}\n'
        '.h7 .trust7{font-size:.92rem;margin:0 0 28px;padding:9px 0 9px 14px;border-left:4px solid var(--ink);max-width:none}\n'
        '.trust7 .trl{white-space:nowrap;margin-left:8px}.trust7 .trl a{margin-right:16px;font-weight:600}\n'
        '.h7 .hrow{grid-template-columns:repeat(12,minmax(0,1fr));column-gap:24px;padding-top:22px}.h7 .hrec{grid-column:1/8}.h7 .hnext{grid-column:8/-1}\n'
        '.h7 .hlead{font-size:1.35rem;font-weight:700;line-height:1.25;margin:2px 0 8px}.h7 .hrec p:not(.hlead):not(.hown),.h7 .hnext p{font-size:1rem}\n'
        '.h7 .d0s{margin-top:26px}\n'
        '.pillars.p7{grid-template-columns:repeat(4,minmax(0,1fr));gap:24px;margin:30px 0 40px}\n'
        '.pillars.p7 .pillar{border:0;border-top:2px solid var(--ink);padding:12px 0 0}.pillars.p7 .pillar:hover{background:none}\n'
        '.pillars.p7 .pillar-value{font-size:1.5rem;font-weight:700;letter-spacing:-.01em;margin:8px 0 6px;line-height:1.2}.pillars.p7 .pillar-value .w{border-bottom:2px solid var(--acc)}\n'
        '.pillars.p7 .pillar p{font-size:.84rem;color:var(--mid);line-height:1.45}\n'
        '.sources>summary{cursor:pointer;padding:16px 0;border-top:1px solid var(--ink)}\n'
        '@media(max-width:820px){.hero.h7{display:block;padding:24px 0 22px}.h7 .hv{font-size:2.2rem}.h7 .hsw{font-size:1.02rem}.h7 .hlead{font-size:1.15rem}'
        '.h7 .hrow{display:block}.h7 .hnext{margin-top:18px}.trust7 .trl{display:block;margin:6px 0 0;white-space:normal}.pillars.p7{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}\n'
        '@media(max-width:480px){.pillars.p7{grid-template-columns:1fr}}\n'
        '\n/* v8: the promise and its price in one headline; the nature card states its sentence; the clause line */\n'
        '.h7 .hv{font-size:2.8rem;line-height:1.12;grid-column:1/12}\n'
        '.pillars.p7 .pillar-value.pv8{font-size:1.08rem;line-height:1.35;letter-spacing:0}\n'
        'p.cl8{border-left:3px solid var(--ink);padding-left:10px}\n'
        '@media(max-width:820px){.h7 .hv{font-size:1.9rem}}\n')
(APP / 'style.css').write_text(css, encoding='utf-8')

# ------------------------------------------------------------------ 5. seal and write
seal_files = [HERE / 'build.py', HERE / 'v5model.py', HERE / 'v5route.py', HERE / 'whose.py', HERE / 'v5_layer.js',
              HERE / 'v6model.py', HERE / 'v6ask.py', HERE / 'v6nature.py', HERE / 'v6_layer.js',
              HERE / 'v7model.py', HERE / 'v7rape.py', HERE / 'v7_layer.js',
              HERE / 'v8model.py', HERE / 'v8clause.py', HERE / 'v8_layer.js', APP / 'app.js', APP / 'index.html', APP / 'style.css']
h = hashlib.sha256()
for p in seal_files:
    h.update(str(p.relative_to(HERE)).encode() + b'\0' + p.read_bytes())
D['seal']['code'] = h.hexdigest()
D['seal']['code_files'] = [str(p.relative_to(HERE)) for p in seal_files]
D['seal']['pipeline'] = 'a-final inventory; Jälki v5 route and whose-numbers layer; v6 framework answers and nature by yield; v7 rapeseed measured from field records'
(APP / 'data.js').write_text('window.D = ' + json.dumps(D, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
(HERE / 'v5.json').write_text(json.dumps({'v4': D['v4'], 'v5': D['v5'], 'synthetic_only': True, 'script': 'python3 stages/pj-v8/build.py'}, indent=1, ensure_ascii=False))
(HERE / 'v6.json').write_text(json.dumps({'v6': D['v6'], 'numbers': {k: v for k, v in D['v3']['numbers'].items() if k.startswith('n6_')}, 'synthetic_only': True, 'script': 'python3 stages/pj-v8/build.py'}, indent=1, ensure_ascii=False))
(HERE / 'v7.json').write_text(json.dumps({'v7': D['v7'], 'numbers': {k: v for k, v in D['v3']['numbers'].items() if k.startswith('n7_')}, 'synthetic_only': True, 'script': 'python3 stages/pj-v8/build.py'}, indent=1, ensure_ascii=False))
(HERE / 'v8.json').write_text(json.dumps({'v8': D['v8'], 'numbers': {k: v for k, v in D['v3']['numbers'].items() if k.startswith('n8_')}, 'headline': {'rec_eur': D['v4']['rec_eur'], 'gap2032_lo': D['v4']['route2032_flag_lo']}, 'synthetic_only': True, 'script': 'python3 stages/pj-v8/build.py'}, indent=1, ensure_ascii=False))
used['pipeline'] = 'stages/pj-v8 (this build; strings first written in stages/pj-v4, stages/pj-v5, stages/pj-v6 and stages/pj-v7 name earlier stages of the same app, all carried here)'
(HERE / 'source_map.json').write_text(json.dumps({'note': 'visible stage name -> development folder in the checkout (stages/...); audit-<id> = check run um-<id>',
                                                  'map': dict(sorted(used.items()))}, indent=1))
changed = sorted(k for k in D if k != 'seal' and D.get(k) != D0.get(k))
log('5. data.js top-level keys changed:', changed)
log('  code seal', D['seal']['code'][:16], 'app tree', tree_hash(APP)[:16])
(HERE / 'build.log').write_text('\n'.join(LOG) + '\n')
print('BUILD OK')

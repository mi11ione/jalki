"""pj-v6 headless check of "Ask the frameworks" (Node, no browser; one temp file under /tmp, removed).
- the four questions from the ticket, in EN and FI, reach the right answer; an off-topic question reaches none;
- the page carries 7 answer cards, each with a quoted passage and a source document, inside the decision flow and the nature fold;
- an expert approval shows on the page and lands in the signed record; the record still replays green.
Run: python3 stages/pj-v6/ask_check.py
"""
import json, os, shutil, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / 'app'
JS = r'''
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const APP = __APP__;
globalThis.window = globalThis;
const store = {};
globalThis.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
function load(f) { vm.runInThisContext(fs.readFileSync(f, 'utf8'), { filename: f }); }
load(path.join(APP, 'data.js')); load(path.join(APP, 'trail', 'meta.js'));
for (const f of fs.readdirSync(path.join(APP, 'trail', 'l')).sort()) load(path.join(APP, 'trail', 'l', f));
load(path.join(APP, 'app.js'));
const PJ = globalThis.PJ, P6 = globalThis.PJ6, AT = '2026-11-07T09:00:00.000Z', out = {};
const Q = [['Does a supplier PCF change count as a reduction?', 'A1'], ['When must the base year be recalculated?', 'A2'],
  ['Does moving crops off peat count under FLAG?', 'A3'], ['What counts as a removal?', 'A4'],
  ['Lasketaanko toimittajan PCF-muutos vähennykseksi?', 'A1'], ['Milloin perusvuosi pitää laskea uudelleen?', 'A2'],
  ['Lasketaanko viljelyn siirto pois turpeelta FLAG-vähennykseksi?', 'A3'], ['Mikä lasketaan poistumaksi?', 'A4'],
  ['Which SBTN step ranks catchments?', 'A7'], ['What is the price of coffee in Helsinki?', null]];
out.match = Q.map(([q, want]) => [q, want, P6.match(q)]);
const cards = {};
for (const lang of ['en', 'fi']) {
  PJ.setLang(lang); const h = PJ.renderPage();
  const cs = h.split('class="ask6c"').slice(1);
  const g0 = h.indexOf('id="gate"'), s0 = h.indexOf('class="sign"'), n0 = h.indexOf('id="nature"');
  cards[lang] = { n: cs.length, all_quoted: cs.every(c => c.indexOf('<q>') >= 0), all_doc: cs.every(c => /Source document|Lähdeasiakirja/.test(c)),
    panel_in_gate: h.indexOf('class="ask6p"') > g0 && h.indexOf('class="ask6p"') < s0, in_nature: h.indexOf('id="ask6-A7"') > n0,
    gate_cards: h.slice(g0, s0).split('class="ask6c"').length - 1, bad: /NaN|undefined|\[object Object\]/.test(h) };
}
out.cards = cards;
PJ.setLang('en'); PJ.setMode('2032', AT); PJ.preset('route'); PJ.setCut(0);
for (const d of PJ.DECS) PJ.setDec(d.id, 0, AT);
for (const r of window.D.v3.review) PJ.decideReview(r.id, 'accept');
P6.set('A1', 'approved'); P6.set('A4', 'revise');
const h2 = PJ.renderPage();
out.approved_shown = /Approved so far: <b>1<\/b>/.test(h2) && h2.indexOf('Approved by the expert reviewer') >= 0 && h2.indexOf('Sent back for revision') >= 0;
const e = PJ.addEntry(PJ.makePayload('Board chair', AT));
out.fa = e.payload.framework_answers.map(x => [x.id, x.state]);
out.replay = PJ.replay(e).map(r => [r[0], r[1]]);
const f = JSON.parse(PJ.fileOf(e)); out.file_has_fa = Array.isArray(f.payload.framework_answers) && f.payload.framework_answers.length === 7;
const bad = JSON.parse(PJ.fileOf(e)); bad.payload.framework_answers[0].state = 'draft';
out.tamper_fa_refused = PJ.importFile(JSON.stringify(bad)) === null;
process.stdout.write(JSON.stringify(out));
'''
node = shutil.which('node') or shutil.which('bun')
fd, tmp = tempfile.mkstemp(suffix='.js', prefix='pjv6-ask-', dir='/tmp')
os.close(fd)
try:
    Path(tmp).write_text(JS.replace('__APP__', json.dumps(str(APP))))
    r = subprocess.run([node, tmp], capture_output=True, text=True, timeout=120)
finally:
    os.unlink(tmp)
if r.returncode:
    print(r.stderr[-1500:])
    raise SystemExit('ASK CHECK FAIL: node exited %d' % r.returncode)
O = json.loads(r.stdout)
print(json.dumps(O, indent=1, ensure_ascii=False))
ok = {
    'questions reach the right answer (EN, FI), off-topic reaches none': all(w == g for _, w, g in O['match']),
    '7 cards per language, each quoted with a source document': all(c['n'] == 7 and c['all_quoted'] and c['all_doc'] and not c['bad'] for c in O['cards'].values()),
    'panel and 6 cards inside the decision flow, 1 in the nature fold': all(c['panel_in_gate'] and c['gate_cards'] == 6 and c['in_nature'] for c in O['cards'].values()),
    'approval states shown on the page': O['approved_shown'],
    'approval states in the signed record': dict(O['fa']) == {'A1': 'approved', 'A2': 'draft', 'A3': 'draft', 'A4': 'revise', 'A5': 'draft', 'A6': 'draft', 'A7': 'draft'} and O['file_has_fa'],
    'signed record with answers replays green': all(v for _, v in O['replay']),
    'edited approval state in a file is refused': O['tamper_fa_refused'],
}
for k, v in ok.items():
    print(('PASS ' if v else 'FAIL ') + k)
print('ASK CHECK', 'PASS' if all(ok.values()) else 'FAIL')

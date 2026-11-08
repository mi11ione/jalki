/* Headless harness for check.py: loads the v2 app with no DOM, renders page states (language x mode x preset x cut,
   with and without decisions), walks the click graph from each number, signs, approves, downloads and re-imports a record,
   and prints one JSON object. Run via python3 verify_app.py from the repo root (needs Node.js). */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const APP = path.join(__dirname, '..', 'app');
globalThis.window = globalThis;
const store = {};
globalThis.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
function load(f) { vm.runInThisContext(fs.readFileSync(f, 'utf8'), { filename: f }); }
load(path.join(APP, 'data.js'));
load(path.join(APP, 'trail', 'meta.js'));
for (const f of fs.readdirSync(path.join(APP, 'trail', 'l')).sort()) load(path.join(APP, 'trail', 'l', f));
load(path.join(APP, 'app.js'));
const PJ = globalThis.PJ, out = { pages: {}, states: {}, views_bad: [], depth: {}, errors: [], registry: [], sha: {}, reg: {} };
const AT = '2026-11-07T09:00:00.000Z';
function links(html) {
  const r = [], re = /data-(k|v)="([^"]+)"/g; let m;
  while ((m = re.exec(html))) r.push(m[1] === 'k' ? 'k~' + encodeURIComponent(m[2]) : m[2]);
  return r;
}
const seen = new Map();
function render(spec) {
  if (seen.has(spec)) return seen.get(spec);
  let h;
  try { h = PJ.view(spec); } catch (e) { out.errors.push('view ' + spec + ': ' + e.message); h = ''; }
  if (/NaN|undefined|\[object Object\]/.test(h) || h === '<p>—</p>' || h.indexOf('Loading') >= 0 || h.indexOf('Ladataan') >= 0) out.views_bad.push(spec);
  seen.set(spec, h);
  return h;
}
function page(tag) {
  let h;
  try { h = PJ.renderPage(); } catch (e) { out.errors.push('page ' + tag + ': ' + e.message); h = ''; }
  out.pages[tag] = h; out.states[tag] = PJ.state();
}
// 1. page states
for (const lang of ['fi', 'en']) {
  PJ.setLang(lang);
  for (const mode of ['2032', '2035', 'hold']) {
    PJ.setMode(mode, AT);
    for (const pre of ['catalogue', 'route', 'savers', 'none']) {
      PJ.preset(pre);
      for (const cut of [0, 20, 40]) { PJ.setCut(cut); page([lang, mode, pre, cut, 'p'].join('|')); }
    }
    // custom: L11 on, L12 off (the reallocation trap), L03 high
    PJ.preset('catalogue'); PJ.setBand('L12', 'off'); PJ.setBand('L03', 'high'); PJ.setCut(10); page([lang, mode, 'custom', 10, 'p'].join('|'));
  }
}
// 2. all decisions recorded, signer chosen
PJ.setMode('2032', AT); PJ.preset('catalogue'); PJ.setCut(0);
for (const d of PJ.DECS) PJ.setDec(d.id, 0, AT);
PJ.setSigner('Board chair');

out.review = {before:PJ.decReady()};
try { PJ.makePayload('Board chair', AT); out.review.sign_blocked=false; } catch(e) { out.review.sign_blocked=true; }
for (const r of window.D.v3.review) PJ.decideReview(r.id, 'accept');
out.review.accepted=PJ.decReady();
PJ.decideReview(window.D.v3.review[0].id, 'reject');
out.review.rejected=PJ.decReady();
// v5: a rejection may sign, and that record must replay red on the review check (lock: blocking rows are decided, not forced to acceptance)
try { const pr = PJ.makePayload('Board chair', AT); const rr = PJ.replay({ payload: pr, hash: PJ.sha256(PJ.canon(pr)) }); const g = rr.filter(x => x[0] === 'r_gate')[0]; out.review.reject_replay_red = !!g && g[1] === false; } catch (e) { out.review.reject_replay_red = 'error ' + e.message; }
PJ.decideReview(window.D.v3.review[0].id, 'accept');
out.ready = PJ.decReady();

for (const lang of ['fi', 'en']) { PJ.setLang(lang); page([lang, '2032', 'catalogue', 0, 'all'].join('|')); }
// 3. click-graph walk (EN and FI): a number on the page is click 1
for (const lang of ['en', 'fi']) {
  PJ.setLang(lang); seen.clear();
  const pg = PJ.renderPage();
  const starts = Array.from(new Set(links(pg)));
  for (const s of starts) {
    let frontier = [s], d = 1, found = 0;
    const vis = new Set([s]);
    while (frontier.length && d <= 4) {
      const next = [];
      for (const sp of frontier) {
        const h = render(sp);
        if (/class="rec/.test(h)) { found = d; break; }
        for (const l of links(h)) if (!vis.has(l)) { vis.add(l); next.push(l); }
      }
      if (found) break;
      frontier = next; d++;
    }
    if (lang === 'en') out.depth[s] = found;
  }
}
// 4. every line, party, plan, lever, chip, doc view once in each language
for (const lang of ['en', 'fi']) {
  PJ.setLang(lang); seen.clear();
  for (const l of window.TRAIL.index.lines) {
    render('line~' + encodeURIComponent(l.line_id));
    render('line~' + encodeURIComponent(l.line_id) + '~all');
    const nm = l.shard.split('/').pop().replace('.json', '');
    for (const p of Object.keys(window.TRAIL.l[nm].parties)) render('party~' + encodeURIComponent(l.line_id) + '~' + encodeURIComponent(p));
  }
  for (const y of Object.keys(window.D.plan_recs)) render('plan~' + y);
  for (const l of window.D.bundle.levers) render('lever~' + l.id);
  for (const c of PJ.CHIPS) render('chip~' + c.id);
  for (const s of ['flag', 'years', 'seal', 'corr~judgement', 'doc~framework', 'doc~catalogue', 'doc~events', 'levers~rec', 'levers~flag', 'levers~sav', 'levers~all']) render(s);
  for (const k of Object.keys(PJ.R)) render('k~' + encodeURIComponent(k));
}
out.n_views = seen.size;
for (const k of Object.keys(PJ.R)) { const d = PJ.R[k]; out.registry.push({ value:PJ.val(k), source:PJ.sourceOf(k), key: k, src: d.src, unit: d.unit, dp: d.dp, sg: d.sg, parts: d.parts, go: d.go }); }
// 5. sign, approve, download, re-import, replay, seal test
PJ.setLang('en'); PJ.setMode('2032', AT);
const e1 = PJ.addEntry(PJ.makePayload('Board chair', AT));
out.reg.self_approve = PJ.approve(e1, 'Board chair', AT);
out.reg.signer_role_approve = PJ.approve(e1, 'CEO', AT);
out.reg.approve = PJ.approve(e1, 'Group controller', AT);
out.reg.approved_twice = PJ.approve(e1, 'Audit committee chair', AT);
const file = PJ.fileOf(e1);
const reimp = PJ.importFile(file);
out.reg.reimport = !!reimp && reimp.hash === e1.hash && !!reimp.approval;
const bad = JSON.parse(file); bad.payload.route.flag_gap_t[0] -= 1;
out.reg.bad_import_refused = PJ.importFile(JSON.stringify(bad)) === null;
const badA = JSON.parse(file); badA.approval.role = 'CFO';
out.reg.bad_approval_refused = PJ.importFile(JSON.stringify(badA)) === null;
PJ.setMode('hold', AT);
const e2 = PJ.addEntry(PJ.makePayload('CFO', AT));
out.reg.replay_sign = PJ.replay(e1).map(r => [r[0], r[1]]);
out.reg.replay_hold = PJ.replay(e2).map(r => [r[0], r[1]]);
out.reg.seal_test = PJ.sealTest(e1);
out.reg.stored = Object.keys(store);
out.reg.payload = e1.payload;
out.reg.file = JSON.parse(file);
const ev = PJ.view('entry~' + encodeURIComponent(e1.id));
out.reg.entry_view = /class="ok"/.test(ev) && ev.indexOf('Group controller') >= 0;
out.reg.entry_view_bad = /NaN|undefined/.test(ev);
const tamper = JSON.parse(JSON.stringify(e1)); tamper.payload.base_recalculated.flag += 1;
out.reg.tamper_detected = !PJ.replay(tamper)[0][1];
out.sha = { empty: PJ.sha256(''), abc: PJ.sha256('abc'), fi: PJ.sha256('Perusvuosi äö €'), factors: PJ.sha256(window.TRAIL.factors_text), inputs: PJ.sha256(window.TRAIL.inputs_text) };
out.ids = { links: PJ.LINKS, chips: PJ.CHIPS.map(c => c.id), lt: Object.keys(PJ.LT), decs: PJ.DECS.map(d => d.id), consts: PJ.consts };

out.high={};
for (const id of Object.keys(window.D.rlev.reduce((o,l)=>(o[l.id]=1,o),{}))) PJ.setBand(id,'high');
out.high.land=PJ.val('d.rmoved')+PJ.val('d.rrewet');
out.high.pool=window.D.route.peat_ha;
out.high.physical_gap=PJ.val('d.rg_lo');
out.high.booked_bound=PJ.val('p.gap2032_bands_lo');
out.claims=Object.keys(PJ.R).map(k=>({key:k,value:PJ.val(k),source:PJ.sourceOf(k),src:PJ.R[k].src,dp:PJ.R[k].dp,unit:PJ.R[k].unit}));
process.stdout.write(JSON.stringify(out));


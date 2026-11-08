  /* ================================================================ Jälki v6 layer (after the stand)
     Keeps the first screen. Adds, from Apetit's own words at the stand:
     1. "Ask the frameworks" inside the decision flow: GHG Protocol, SBTi (FLAG, V1.3.1, V2) and SBTN answers, each with its
        quoted source passage and an expert-approval state; the live seam (Azure AI Foundry) is named.
     2. Nature as eutrophication by location and yield: phosphorus to water per tonne harvested, one fold.
     3. The board's rapeseed plan framed as what it should measure, never as a wrong decision.
     4. One line on the base: every recalculation replays from the trail.
     5. A fit note in the method fold.
     Every figure is a registry key (v3.n6_*) from v6nature.py / v6ask.py. Synthetic pack only. */
  var V6 = D.v6;
  var ASK6 = {}, ASK6Q = '', ASK6HIT = null, ASK6OPEN = {};
  T.ask_h = ['Ask the frameworks', 'Kysy viitekehyksiltä'];
  function askById(id) { return V6.ask.filter(function (b) { return b.id === id; })[0]; }
  function askState(id) { return ASK6[id] ? ASK6[id].s : 'draft'; }
  function askCard(b) {
    var s = askState(b.id);
    var st = s === 'approved' ? ['Approved by the expert reviewer', 'Asiantuntija hyväksynyt'] : s === 'revise' ? ['Sent back for revision', 'Palautettu korjattavaksi'] : ['AI draft · awaiting expert approval', 'AI-luonnos · odottaa asiantuntijan hyväksyntää'];
    var h = '<div class="ask6c" id="ask6-' + b.id + '"><p class="ask6q"><b>' + esc(L2(b.q)) + '</b> <span class="ask6s s-' + s + '">' + esc(L2(st)) + '</span></p><p>' + fx(b.a) + '</p>';
    h += '<ul class="ask6l">';
    b.cites.forEach(function (c) { h += '<li>' + esc(L2(c.show)) + ' · ' + esc(c.section) + ': <q>' + esc(c.quote) + '</q> <span class="mono">' + esc(c.path) + '</span></li>'; });
    b.docs.forEach(function (d) {
      h += '<li>' + esc(L2(['Source document', 'Lähdeasiakirja'])) + ': ' + esc(d.name) + ' · ' + (d.url ? '<a href="' + esc(d.url) + '" target="_blank" rel="noopener">' + esc(L2(['link from the pack\'s source registry', 'linkki paketin lähdeluettelosta'])) + '</a>' : esc(L2(['named in the digest; no link in the pack', 'mainittu tiivistelmässä; ei linkkiä paketissa']))) + '</li>';
    });
    h += '</ul><div class="ask6b"><span class="small">' + esc(L2(['Expert reviewer (simulated in this prototype):', 'Asiantuntija (simuloitu tässä prototyypissä):'])) + '</span> ' +
      '<button type="button" data-ask6="approved~' + b.id + '" aria-pressed="' + (s === 'approved') + '" class="' + (s === 'approved' ? 'on' : '') + '">' + esc(L2(['Approve', 'Hyväksy'])) + '</button> ' +
      '<button type="button" data-ask6="revise~' + b.id + '" aria-pressed="' + (s === 'revise') + '" class="' + (s === 'revise' ? 'on' : '') + '">' + esc(L2(['Send back', 'Palauta'])) + '</button>' +
      (s !== 'draft' ? ' <button type="button" class="lk" data-ask6="draft~' + b.id + '">' + esc(L2(['Reset', 'Nollaa'])) + '</button> <span class="small mono">' + esc(ASK6[b.id].at.slice(0, 16).replace('T', ' ')) + '</span>' : '') + '</div></div>';
    return h;
  }
  function askFold(ids) {
    var bs = V6.ask.filter(function (b) { return ids.indexOf(b.id) >= 0; });
    if (!bs.length) return '';
    var open = bs.some(function (b) { return ASK6OPEN[b.id]; });
    return '<details class="ask6"' + (open ? ' open' : '') + '><summary>' + esc(L2(T.ask_h)) + ' · ' + bs.map(function (b) { return esc(L2(b.q)); }).join(' · ') + '</summary>' + bs.map(askCard).join('') + '</details>';
  }
  function askMatch(q) {
    var toks = String(q).toLowerCase().split(/[^a-z0-9åäöé+]+/).filter(function (t) { return t.length >= 3; });
    var best = null, bs = 0, tie = false;
    V6.ask.forEach(function (b) {
      var s = 0;
      b.kw.forEach(function (k) { if (toks.some(function (t) { return t.indexOf(k) === 0 || (t.length >= 4 && k.indexOf(t) === 0); })) s++; });
      if (s > bs) { bs = s; best = b; tie = false; } else if (s && s === bs) tie = true;
    });
    /* two keyword hits, or one hit that no other answer shares */
    return bs >= 2 || (bs === 1 && !tie) ? best : null;
  }
  function askPanel() {
    var nA = V6.ask.filter(function (b) { return askState(b.id) === 'approved'; }).length;
    var h = '<div class="ask6p"><h3>' + esc(L2(T.ask_h)) + '</h3><p>' + esc(L2(['The questions a board asks before it signs, answered from the GHG Protocol, SBTi (FLAG, V1.3.1 and V2) and SBTN texts. Each answer quotes the passage it rests on and waits for an expert to approve it. Each one also sits under the decision it informs.',
      'Kysymykset, jotka hallitus esittää ennen allekirjoitusta, vastattuna GHG Protocolin, SBTi:n (FLAG, V1.3.1 ja V2) ja SBTN:n teksteistä. Jokainen vastaus lainaa kohdan, johon se perustuu, ja odottaa asiantuntijan hyväksyntää. Jokainen on myös sen päätöksen alla, johon se liittyy.'])) + '</p>';
    h += '<div class="ask6f"><input id="ask6q" type="text" value="' + esc(ASK6Q) + '" placeholder="' + esc(L2(['Ask about base years, FLAG, removals, SBTN…', 'Kysy perusvuodesta, FLAGista, poistumista, SBTN:stä…'])) + '" aria-label="' + esc(L2(T.ask_h)) + '"><button type="button" data-ask6="go">' + esc(L2(['Ask', 'Kysy'])) + '</button></div>';
    h += '<p class="small">' + esc(L2(['Try:', 'Kokeile:'])) + ' ' + ['A1', 'A2', 'A4'].map(function (id) { return '<button type="button" class="lk" data-ask6="try~' + id + '">' + esc(L2(askById(id).q)) + '</button>'; }).join(' · ') + '</p>';
    if (ASK6Q) h += ASK6HIT ? '<p class="small">' + esc(L2(['Nearest answer in the bank:', 'Lähin vastaus pankissa:'])) + '</p>' + askCard(ASK6HIT)
      : '<p class="small">' + esc(L2(['No answer in the bank matches. In production this question goes to the live agent and comes back here as a draft for expert approval.', 'Pankissa ei ole vastaavaa vastausta. Tuotannossa kysymys menee live-agentille ja palaa tähän luonnoksena asiantuntijan hyväksyttäväksi.'])) + '</p>';
    h += '<p class="small">' + fx(['{n:v3.n6_ask_n} answers, {n:v3.n6_ask_quotes} quoted passages, each found word for word in the file it cites. ', '{n:v3.n6_ask_n} vastausta, {n:v3.n6_ask_quotes} lainattua kohtaa, kukin löydetty sanasta sanaan lähdetiedostostaan. ']) +
      esc(L2(['Approved so far: ', 'Hyväksytty: '])) + '<b>' + nA + '</b></p>';
    h += '<p class="small ask6how"><b>' + esc(L2(['How it works here.', 'Miten tämä toimii.'])) + '</b> ' + esc(L2(['Our AI pipeline drafted each answer from the framework texts in the pack; the build stops if a quoted passage is not in the file it cites. A typed question is matched to the nearest answer in the bank; nothing is generated in this page. Live seam: here Azure AI Foundry would answer from an Azure AI Search index of the framework PDFs and the digest, under the same quote check, and each new answer would arrive as a draft for approval.',
      'AI-ketjumme laati jokaisen vastauksen paketin viitekehysteksteistä; koonti pysähtyy, jos lainattua kohtaa ei löydy lähdetiedostosta. Kirjoitettu kysymys yhdistetään lähimpään pankin vastaukseen; tällä sivulla ei generoida mitään. Live-sauma: tässä Azure AI Foundry vastaisi Azure AI Search -indeksistä, jossa ovat viitekehysten PDF:t ja tiivistelmä, saman lainaustarkistuksen alla, ja jokainen uusi vastaus tulisi luonnoksena hyväksyttäväksi.'])) + '</p></div>';
    return h;
  }
  var gate5 = gate;
  gate = function () {
    var h = gate5(), parts = h.split('<li class="dc');
    for (var i = 1; i < parts.length; i++) {
      var m = /id="dec-(\w+)"/.exec(parts[i]);
      if (!m) throw new Error('v6 anchor missing: decision id');
      var ids = V6.ask.filter(function (b) { return b.dec.indexOf(m[1]) >= 0; }).map(function (b) { return b.id; });
      if (!ids.length) continue;
      var k = parts[i].indexOf('<div class="opts">');
      if (k < 0) throw new Error('v6 anchor missing: opts ' + m[1]);
      parts[i] = parts[i].slice(0, k) + askFold(ids) + parts[i].slice(k);
    }
    h = parts.join('<li class="dc');
    if (h.split('<ol class="decs">').length !== 2) throw new Error('v6 anchor missing: decs');
    return h.replace('<ol class="decs">', askPanel() + '<ol class="decs">');
  };
  var makePayload5 = makePayload;
  makePayload = function (role, at) {
    var p = makePayload5(role, at);
    p.framework_answers = V6.ask.map(function (b) { return { id: b.id, question: b.q[0], state: askState(b.id), at: ASK6[b.id] ? ASK6[b.id].at : null, quoted_sources: b.cites.length, reviewer: 'Expert reviewer (simulated)' }; });
    return p;
  };
  function v6go() { var el = document.getElementById('ask6q'); ASK6Q = el ? String(el.value).trim() : ''; ASK6HIT = ASK6Q ? askMatch(ASK6Q) : null; }
  function v6click(ev) {
    var t = ev.target.closest ? ev.target.closest('[data-ask6]') : null;
    if (!t) return;
    var a = t.getAttribute('data-ask6').split('~');
    if (a[0] === 'go') v6go();
    else if (a[0] === 'try') { var b = askById(a[1]); ASK6Q = L2(b.q); ASK6HIT = askMatch(ASK6Q) || b; }
    else { if (a[0] === 'draft') delete ASK6[a[1]]; else ASK6[a[1]] = { s: a[0], at: new Date().toISOString() }; ASK6OPEN[a[1]] = true; }
    keepScroll(render);
  }
  function v6key(ev) { if (ev.key === 'Enter' && ev.target && ev.target.id === 'ask6q') { ev.preventDefault(); v6go(); keepScroll(render); var el = document.getElementById('ask6q'); if (el) el.focus(); } }

  /* the board decided last year to have contract farmers grow rapeseed: Jälki says what that plan should measure */
  (function () {
    var d = DECS.filter(function (x) { return x.id === 'F'; })[0];
    d.title = ['Measure the rapeseed plan in the field', 'Mitataan rapsisuunnitelma pellolla'];
    d.t = function () { return ['The board\'s plan to grow rapeseed with contract farmers counts toward FLAG by the fields it uses. On mineral soil a Finnish tonne carries {k:p.fi_kgk_min}, below {k:p.imp_kgk} for imported seed; across today\'s mix of mineral and peat parcels it averages {k:p.fi_kgk_all}. So the plan should record which parcels grow it.',
      'Hallituksen suunnitelma kasvattaa rapsia sopimusviljelijöiden kanssa lasketaan FLAG-tavoitteeseen sen peltojen mukaan. Kivennäismaalla kotimainen tonni kantaa {k:p.fi_kgk_min}, vähemmän kuin tuontisiemenen {k:p.imp_kgk}; nykyisellä kivennäis- ja turvelohkojen jakaumalla keskiarvo on {k:p.fi_kgk_all}. Siksi suunnitelman pitää kirjata, millä lohkoilla rapsi kasvaa.']; };
    d.e = function () { return ['The grower programme\'s catalogue cost is {k:lev.L15.cost_eur_yr} a year. Measuring it uses the yield reports contract farmers already send, plus parcel ID and nitrogen rate.',
      'Viljelijäohjelman luettelokustannus on {k:lev.L15.cost_eur_yr} vuodessa. Mittaus käyttää satoilmoituksia, joita sopimusviljelijät jo lähettävät, sekä lohkotunnusta ja typpimäärää.']; };
    d.next = function () { return ['Add parcel ID, yield per hectare and nitrogen rate to the rapeseed grower form for the 2027 season. The soil map then gives each field\'s peat share, and FLAG is credited parcel by parcel.',
      'Lisää rapsin viljelijälomakkeeseen kaudelle 2027 lohkotunnus, hehtaarisato ja typpimäärä. Maaperäkartta antaa silloin kunkin pellon turveosuuden, ja FLAG hyvitetään lohko kerrallaan.']; };
    d.q = ['How does the rapeseed plan count toward FLAG?', 'Miten rapsisuunnitelma lasketaan FLAG-tavoitteeseen?'];
    d.opts = [['Per parcel, from field records: peat share, yield, nitrogen', 'Lohkoittain peltotiedoista: turveosuus, sato, typpi'], ['At the catalogue\'s average tonnes', 'Luettelon keskimääräisillä tonneilla']];
  })();
  LT.L15[2] = ['Its FLAG result depends on the fields: below imported seed on mineral soil, above it on peat. Record parcel, yield and nitrogen from the first season (decision F).',
    'FLAG-vaikutus riippuu pelloista: kivennäismaalla tuontisiementä pienempi, turpeella suurempi. Kirjaa lohko, sato ja typpi ensimmäisestä kaudesta alkaen (päätös F).'];
  T.pr_note = ['Recommended route: the catalogue without the levers the cost rule skips in every scenario, and without L01, L07, L14 and L22, whose capacity the pack does not show. The rapeseed grower programme (L15) counts once its field records exist (decision F).',
    'Suositeltu reitti: luettelo ilman keinoja, jotka kustannussääntö ohittaa kaikissa skenaarioissa, ja ilman L01-, L07-, L14- ja L22-keinoja, joiden kapasiteettia paketti ei osoita. Rapsin viljelijäohjelma (L15) lasketaan, kun sen peltotiedot ovat olemassa (päätös F).'];
  function rep6(pair, a, b) {
    if (pair[0].indexOf(a[0]) < 0 || pair[1].indexOf(a[1]) < 0) throw new Error('v6 anchor missing: ' + a[0]);
    return [pair[0].replace(a[0], b[0]), pair[1].replace(a[1], b[1])];
  }
  R['p.rec_eur'].how = rep6(R['p.rec_eur'].how, ['The catalogue without L15 and without the levers the cost rule skips in every scenario.', 'Luettelo ilman L15:tä ja ilman keinoja, jotka kustannussääntö ohittaa kaikissa skenaarioissa.'],
    ['The catalogue without the levers the cost rule skips in every scenario; L15 counts once its field records exist.', 'Luettelo ilman keinoja, jotka kustannussääntö ohittaa kaikissa skenaarioissa; L15 lasketaan, kun sen peltotiedot ovat olemassa.']);
  R['v4.rec_eur'].how = rep6(R['v4.rec_eur'].how, [', and without L15)', ', ja ilman L15:tä)'], ['; L15 counts once its field records exist)', '; L15 lasketaan, kun sen peltotiedot ovat olemassa)']);
  R['p.l15_adds_t'].lab = ['Extra FLAG if more Finnish rapeseed came from today\'s parcel mix, before parcels are recorded', 'Lisä-FLAG, jos lisärapsi tulisi nykyisestä lohkojakaumasta ennen lohkojen kirjaamista'];

  /* the base: every recalculation replays from the trail */
  T.bases_p = [T.bases_p[0] + ' Every recalculation replays from the trail: each figure opens down to its source record, factor and correction, and each signed base rebuilds from its frozen record, so missing notes no longer cost time.',
    T.bases_p[1] + ' Jokainen uudelleenlaskenta toistuu jäljityksestä: jokainen luku avautuu lähdetietueeseen, kertoimeen ja korjaukseen asti, ja jokainen allekirjoitettu perusvuosi rakentuu lukitusta asiakirjastaan, joten puuttuvat muistiinpanot eivät enää vie aikaa.'];

  /* nature: eutrophication first, by location and yield */
  SUMS.nature = ['Eutrophication first: phosphorus to water per tonne harvested, by catchment.', 'Rehevöityminen ensin: vesiin päätyvä fosfori korjattua tonnia kohden, valuma-alueittain.'];
  var ST6 = { good: ['good', 'hyvä'], moderate: ['moderate', 'tyydyttävä'], poor: ['poor', 'välttävä'], bad: ['bad', 'huono'] };
  function natChart() {
    var rows = V6.catch, W = 640, X0 = 64, XW = 470, hmax = Math.ceil(Math.max.apply(null, rows.map(function (r) { return r.idx; })) * 10) / 10;
    var x = function (v) { return X0 + v / hmax * XW; };
    var col = function (s) { return s === 'bad' || s === 'poor' ? '#c8102e' : s === 'moderate' ? '#e3a1a1' : '#9a9a96'; };
    var s = '<svg class="nat6" viewBox="0 0 ' + W + ' ' + (40 + rows.length * 18) + '" width="100%" role="img" aria-label="' + esc(L2(['Phosphorus to water per tonne harvested, by catchment', 'Vesiin päätyvä fosfori korjattua tonnia kohden, valuma-alueittain'])) + '">';
    s += '<line x1="' + x(1) + '" x2="' + x(1) + '" y1="10" y2="' + (16 + rows.length * 18) + '" stroke="#111" stroke-dasharray="3 3"/><text class="tick" x="' + x(1) + '" y="' + (30 + rows.length * 18) + '" text-anchor="middle">' + esc(L2(['1.0 = typical tonne', '1,0 = tyypillinen tonni'])) + '</text>';
    rows.forEach(function (r, i) {
      var yy = 14 + i * 18, ca = r.id === 'CA12';
      s += '<text class="tick" x="' + (X0 - 6) + '" y="' + (yy + 9) + '" text-anchor="end"' + (ca ? ' font-weight="700"' : '') + '>' + esc(r.id) + '</text>';
      s += '<rect x="' + X0 + '" y="' + (yy + 1) + '" width="' + (x(r.idx) - X0) + '" height="11" fill="' + col(r.status) + '"' + (ca ? ' stroke="#111" stroke-width="1.5"' : '') + '/>';
      s += '<text class="n tick" data-k="v3.n6_c_' + r.id + '" data-u="1" x="' + (x(r.idx) + 6) + '" y="' + (yy + 10) + '">' + esc(fmtk('v3.n6_c_' + r.id, true)) + (ca ? ' · ' + esc(L2(['assess first', 'arvioi ensin'])) : '') + '</text>';
    });
    return s + '</svg><p class="small nat6leg"><i class="sw" style="background:#c8102e"></i>' + esc(L2(['poor or bad status', 'välttävä tai huono tila'])) + ' <i class="sw" style="background:#e3a1a1"></i>' + esc(L2(['moderate', 'tyydyttävä'])) + ' <i class="sw" style="background:#9a9a96"></i>' + esc(L2(['good', 'hyvä'])) + ' · ' + fx(['{n:v3.n6_n_catch} catchments with at least {n:v3.n6_min_farms} delivering farms; model A phosphorus, 2025.', '{n:v3.n6_n_catch} valuma-aluetta, joilla vähintään {n:v3.n6_min_farms} toimittavaa tilaa; mallin A fosfori, 2025.']) + '</p>';
  }
  function natureBlock(old) {
    var h = '<h2>' + esc(L2(['The farms that matter for the lakes are not our biggest emitters.', 'Järville tärkeät tilat eivät ole suurimmat päästäjämme.'])) + '</h2>';
    h += '<p class="lead">' + fx(['Our {n:v3.n6_top_n} contract farms with the largest emissions carry {k:v3.n6_top_t_t_pct} of farm CO₂e but send only {k:v3.n6_top_t_p_pct} of the phosphorus our contract fields deliver to water. None of them is among the {n:v3.n6_top_n} farms that send the most phosphorus. Location and yield drive the lakes, not hectares: so this view ranks catchments by phosphorus reaching water per tonne harvested.',
      '{n:v3.n6_top_n} suurimman päästön sopimustilaamme kantaa {k:v3.n6_top_t_t_pct} tilojen CO₂e:stä, mutta päästää vain {k:v3.n6_top_t_p_pct} siitä fosforista, jonka sopimuspeltomme päästävät vesiin. Yksikään niistä ei ole niiden {n:v3.n6_top_n} tilan joukossa, jotka päästävät eniten fosforia. Järviin vaikuttavat sijainti ja sato, eivät hehtaarit: siksi tämä näkymä järjestää valuma-alueet vesiin päätyvän fosforin mukaan korjattua tonnia kohden.']) + '</p>';
    h += '<h3>' + esc(L2(['Phosphorus to water per tonne harvested, against the same crops elsewhere', 'Vesiin päätyvä fosfori korjattua tonnia kohden, verrattuna samoihin kasveihin muualla'])) + '</h3>' + natChart();
    h += '<p>' + fx(['A tonne harvested costs the water from {k:v3.n6_idx_lo} to {k:v3.n6_idx_hi} the phosphorus of the same crops elsewhere. None of the three highest is among the three catchments with the most farm emissions.',
      'Korjattu tonni maksaa vesistölle {k:v3.n6_idx_lo}–{k:v3.n6_idx_hi} samojen kasvien fosforista muualla. Yksikään kolmesta korkeimmasta ei ole kolmen suurimman tilapäästön valuma-alueen joukossa.']) + '</p>';
    h += '<p class="small">' + fx(['CA12 sends the most contract phosphorus of any catchment, {n:v3.n6_ca12_p} kg a year into a river in poor status, at {k:v3.n6_ca12_idx} the typical phosphorus per tonne.',
      'CA12 päästää sopimusfosforia eniten kaikista valuma-alueista, {n:v3.n6_ca12_p} kg vuodessa välttävässä tilassa olevaan jokeen, {k:v3.n6_ca12_idx} tyypillisestä fosforista tonnia kohden.']) + '</p>';
    h += old.replace('<h2>', '<h3>').replace('</h2>', '</h3>');
    h += '<p>' + esc(L2(['Use the ranking to choose where farm advisory compares yield per input first.', 'Käytä järjestystä valitessasi, missä viljelyneuvonta vertaa satoa panosta kohden ensin.'])) + '</p>';
    return h + askFold(['A7']);
  }
  var fieldsAndNature5 = fieldsAndNature;
  fieldsAndNature = function () {
    var h = fieldsAndNature5(), k = h.indexOf('<details class="s fold" id="nature"');
    if (k < 0) throw new Error('v6 anchor missing: nature fold');
    var b0 = h.indexOf('<div class="body">', k) + '<div class="body">'.length, b1 = h.lastIndexOf('</div></details>');
    if (b0 < k || b1 < b0) throw new Error('v6 anchor missing: nature body');
    return h.slice(0, k) + sec('nature', L2(['Nature', 'Luonto']), natureBlock(h.slice(b0, b1)));
  };

  /* method fold: the fit note and the limits of the two new parts */
  T.m12 = ['Fit to Apetit\'s stack: the page runs as an IT-maintained app (static files, no server code), as a Power BI report on the same tables, or as a Teams tab. The tables map onto a Fabric Lakehouse (raw feeds bronze, cleaned tables silver, inventory lines gold) and the expert approvals onto a Power Apps flow, as the pack\'s Azure quickstart lays out. The framework answers come from Azure AI Foundry: an agent over an Azure AI Search index of the framework PDFs and the digest, with the same quote check before an answer reaches a reviewer.',
    'Sopivuus Apetitin ympäristöön: sivu toimii IT:n ylläpitämänä sovelluksena (staattiset tiedostot, ei palvelinkoodia), Power BI -raporttina samoista tauluista tai Teams-välilehtenä. Taulut vastaavat Fabric Lakehousea (raakasyötteet bronze, puhdistetut taulut silver, inventaariorivit gold) ja asiantuntijahyväksynnät Power Apps -kulkua, kuten paketin Azure-pikaopas kuvaa. Viitekehysvastaukset tulevat Azure AI Foundrysta: agentti Azure AI Search -indeksin päällä (viitekehysten PDF:t ja tiivistelmä), sama lainaustarkistus ennen kuin vastaus menee tarkastajalle.'];
  T.m13 = ['Framework answers: drafted by our AI pipeline from the pack\'s framework digest, docs and lever catalogue, re-using the E-track answers where they existed. The original standards are not in the pack, so a section shown is the section of the text we hold, not a clause number of the standard; pinning the clause is part of expert approval. Approval states are kept in the signed record; the reviewer role is simulated.',
    'Viitekehysvastaukset: AI-ketjumme laati ne paketin viitekehystiivistelmästä, dokumenteista ja keinoluettelosta, ja käytti E-osion vastauksia, kun niitä oli. Alkuperäiset standardit eivät ole paketissa, joten näytetty kohta on hallussamme olevan tekstin kohta, ei standardin pykälänumero; pykälän tarkistus kuuluu asiantuntijan hyväksyntään. Hyväksyntätilat tallentuvat allekirjoitettuun asiakirjaan; tarkastajarooli on simuloitu.'];
  T.m14 = ['Nature: phosphorus to water per parcel is the 2025 estimate of catchment model A; delivered tonnes and farm CO₂e are the 2025 contract-farm lines of the inventory. The index compares each farm and crop with the median phosphorus per tonne of the same crop, so carrots are never compared with rapeseed. At {n:v3.n6_top_n} farms the two lists share {n:v3.n6_overlap} farms, at 20 they share {n:v3.n6_overlap20}; the {n:v3.n6_half_t} farms holding half of farm CO₂e and the {n:v3.n6_half_p} sending half of the phosphorus share {n:v3.n6_half_overlap}.',
    'Luonto: lohkon vesiin päätyvä fosfori on valuma-aluemallin A arvio vuodelle 2025; toimitetut tonnit ja tilojen CO₂e ovat inventaarion vuoden 2025 sopimusviljelyrivejä. Indeksi vertaa kutakin tilaa ja kasvia saman kasvin fosforin mediaaniin tonnia kohden, joten porkkanaa ei verrata rapsiin. {n:v3.n6_top_n} tilan listoilla on {n:v3.n6_overlap} yhteistä tilaa, 20 tilan listoilla {n:v3.n6_overlap20}; ne {n:v3.n6_half_t} tilaa, joilla on puolet CO₂e:stä, ja ne {n:v3.n6_half_p}, jotka päästävät puolet fosforista, jakavat {n:v3.n6_half_overlap} tilaa.'];
  var renderPage5 = renderPage;
  renderPage = function () {
    var h = renderPage5(), a = '<li>' + tx('m11') + '</li>';
    if (h.split(a).length !== 2) throw new Error('v6 anchor missing: method m11');
    return h.replace(a, a + '<li>' + tx('m12') + '</li><li>' + tx('m13') + '</li><li>' + tx('m14') + '</li>');
  };
  /* hooks for the headless ask check (ask_check.py); the page itself does not use them */
  G.PJ6 = { match: function (q) { var b = askMatch(q); return b ? b.id : null; }, set: function (id, s) { if (s === 'draft') delete ASK6[id]; else ASK6[id] = { s: s, at: '2026-11-07T09:00:00.000Z' }; },
    ids: function () { return V6.ask.map(function (b) { return b.id; }); } };
  var boot5 = boot;
  boot = function () { boot5(); document.addEventListener('click', v6click); document.addEventListener('keydown', v6key); };


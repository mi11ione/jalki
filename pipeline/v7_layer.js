  /* ================================================================ Jälki v7 layer (after the stand, second pass)
     From Apetit's own words at the stand:
     1. The board's rapeseed decision ("if you can help them increase yield ... better for them, better for us and better
        for the climate"), measured: yield and nitrogen per tonne on each contract farm, from the field records they
        already receive (v3.n7_* from v7rape.py). Every L15 / rapeseed mention reads as the measurement that shows it pays.
     2. Peat in one plain sentence on first contact; the soil-map floor sits one click down.
     3. "Where every number comes from": a named feature on the first screen, linking to the trail and the method.
     4. Visual pass: one euro format (EUR 514k, 1.75M), tighter first screen, no internal jargon there.
     Synthetic pack only. */

  /* ---- 4. one euro format: under 10k as is, 10k to 1M in thousands, from 1M in millions; a range takes one unit ---- */
  function eurFam(u) { return u === 'eur' || u === 'keur' || u === 'meur'; }
  function eurPick(v) { var a = Math.abs(v); return !(a >= 1e4) ? null : a >= 1e7 ? ['meur', 1] : a >= 1e6 ? ['meur', 2] : ['keur', 0]; }
  var EURP = null, fmtk6 = fmtk, rng6 = rng, wrapU6 = wrapU;
  wrapU = function (u, s) {
    if (u === 'kgnha') return s + ' kg N/ha';
    if (u === 'kgnt') return s + ' kg N/t';
    if (u === 'tco2t') return s + ' t CO₂e/t';
    return wrapU6(u, s);
  };
  fmtk = function (key, unit) {
    var d = R[key]; if (!d || !eurFam(d.unit)) return fmtk6(key, unit);
    var v = val(key); if (typeof v !== 'number' || !isFinite(v)) return fmtk6(key, unit);
    var p = EURP || eurPick(v); if (!p) return fmtk6(key, unit);
    var s = fnum(scaleU(p[0], v), p[1], d.sg);
    return unit === false ? s : wrapU(p[0], s);
  };
  rng = function (a, b) {
    if (R[a] && R[b] && eurFam(R[a].unit) && eurFam(R[b].unit) && !isCut(a) && !isCut(b)) {
      var va = val(a), vb = val(b);
      if (typeof va === 'number' && typeof vb === 'number' && isFinite(va) && isFinite(vb)) {
        var p = eurPick(Math.max(Math.abs(va), Math.abs(vb)));
        if (p) { EURP = p; try { return wrapU(p[0], nb(a, false) + '–' + nb(b, false)); } finally { EURP = null; } }
      }
    }
    return rng6(a, b);
  };

  var vNum6 = vNum;
  vNum = function (key) {
    var h = vNum6(key), d = R[key], v = d ? val(key) : null;
    if (!d || !eurFam(d.unit) || typeof v !== 'number' || !isFinite(v) || !eurPick(v) || isCut(key)) return h;
    var a = '<div class="bigv">' + esc(fmtk(key, true)) + '</div>';
    if (h.indexOf(a) < 0) throw new Error('v7 anchor missing: bigv ' + key);
    return h.replace(a, a + '<p class="small">' + esc(L2(['Exact: ', 'Tarkka arvo: '])) + esc(wrapU('eur', fnum(v, 0, d.sg))) + '</p>');
  };

  /* defect carried from v5 (flagged in v6): lever pros and cons are escaped, not filled, so L07 showed a raw {k:...} token */
  var leverRow6 = leverRow;
  leverRow = function (Lr) { var h = leverRow6(Lr); return h.indexOf('{k:') >= 0 || h.indexOf('{n:') >= 0 || h.indexOf('{r:') >= 0 ? fill(h) : h; };

  /* ---- 1. the rapeseed decision, measured ---- */
  ['n7_resp', 'n7_resp_pct', 'n7_farms', 'n7_q_n', 'n7_y_bot', 'n7_y_top', 'n7_nha_bot', 'n7_nha_top', 'n7_nt_bot', 'n7_nt_top', 'n7_fl_bot', 'n7_fl_top', 'n7_nt_ratio', 'n7_fl_ratio', 'n7_rob_nt', 'n7_rob_fl'].forEach(function (k) {
    if (!R['v3.' + k]) throw new Error('v7 key missing ' + k);
    R['v3.' + k].go = ['line~' + RAPE_LINE];
    R['v3.' + k].how = ['From the farmers\' own 2025 field records (yield, mineral and manure nitrogen) joined to the inventory\'s turnip-rape farm line: parcel hectares, mapped peat, farm CO₂e. Farms are split into yield quarters among those that sent a record.',
      'Viljelijöiden omista vuoden 2025 peltotiedoista (sato, mineraali- ja lantatyppi) yhdistettynä inventaarion rypsin tilariviin: lohkohehtaarit, kartoitettu turve, tilan CO₂e. Tilat jaetaan satoneljänneksiin tietonsa lähettäneiden kesken.'];
  });
  (function () {
    var d = DECS.filter(function (x) { return x.id === 'F'; })[0];
    d.title = ['Show the rapeseed plan pays, farm by farm', 'Näytetään rapsisuunnitelman hyöty tila kerrallaan'];
    d.t = function () { return ['The board\'s plan pays where contract farmers raise yield, and their 2025 field records already show it. With about the same nitrogen per hectare, the highest-yield quarter of farms uses {k:v3.n7_nt_top} of nitrogen per tonne, the lowest {k:v3.n7_nt_bot}. On mineral soil their tonnes carry {k:v3.n7_fl_top} against {k:v3.n7_fl_bot}.',
      'Hallituksen suunnitelma kannattaa siellä, missä sopimusviljelijät nostavat satoa, ja heidän vuoden 2025 peltotietonsa näyttävät sen jo. Lähes samalla hehtaarikohtaisella typellä parhaan satoneljänneksen tilat käyttävät {k:v3.n7_nt_top} typpeä tonnia kohden, heikoimman {k:v3.n7_nt_bot}. Kivennäismaalla niiden tonnit kantavat {k:v3.n7_fl_top} vs. {k:v3.n7_fl_bot}.']; };
    d.e = function () { return ['Uses the yield reports contract farmers already send ({k:v3.n7_resp_pct} of rapeseed farms did for 2025), plus parcel ID. The grower programme\'s catalogue cost is {k:lev.L15.cost_eur_yr} a year.',
      'Käyttää satoilmoituksia, joita sopimusviljelijät jo lähettävät ({k:v3.n7_resp_pct} rypsitiloista lähetti vuodelta 2025), sekä lohkotunnusta. Viljelijäohjelman luettelokustannus on {k:lev.L15.cost_eur_yr} vuodessa.']; };
    d.next = function () { return ['Put parcel ID, yield and nitrogen rate on the 2027 rapeseed grower form; report yield and nitrogen per tonne for each farm every season. Early check: the 2026 harvest records.',
      'Lisää kauden 2027 rapsilomakkeeseen lohkotunnus, sato ja typpimäärä; raportoi jokaisen tilan sato ja tonnikohtainen typpi joka kausi. Ensimmäinen tarkistus: kauden 2026 satotiedot.']; };
    d.q = ['How do we show the rapeseed plan pays?', 'Miten näytämme rapsisuunnitelman hyödyn?'];
    d.opts = [['Farm by farm from field records: yield, nitrogen per tonne, parcel', 'Tila kerrallaan peltotiedoista: sato, typpi tonnia kohden, lohko'], ['At the catalogue\'s average tonnes', 'Luettelon keskimääräisillä tonneilla']];
  })();
  LT.L15[1] = ['Domestic supply; higher yield cuts nitrogen and FLAG per tonne.', 'Kotimainen hankinta; suurempi sato vähentää typpeä ja FLAG-päästöjä tonnia kohden.'];
  LT.L15[2] = ['Credited farm by farm from yield, nitrogen per tonne and parcel (decision F).', 'Hyvitetään tila kerrallaan sadon, tonnikohtaisen typen ja lohkon mukaan (päätös F).'];
  (function () {
    var a = ['The rapeseed grower programme (L15) counts once its field records exist (decision F).', 'Rapsin viljelijäohjelma (L15) lasketaan, kun sen peltotiedot ovat olemassa (päätös F).'];
    if (T.pr_note[0].indexOf(a[0]) < 0 || T.pr_note[1].indexOf(a[1]) < 0) throw new Error('v7 anchor missing: pr_note L15');
    T.pr_note = [T.pr_note[0].replace(a[0], 'The rapeseed grower programme (L15) is credited farm by farm from its field records (decision F).'),
      T.pr_note[1].replace(a[1], 'Rapsin viljelijäohjelma (L15) hyvitetään tila kerrallaan sen peltotiedoista (päätös F).')];
  })();
  R['p.l15_adds_t'].lab = ['What parcel records settle: FLAG of added Finnish tonnes at today\'s parcel mix, against imported seed', 'Mitä lohkotiedot ratkaisevat: lisätonnien FLAG nykyisellä lohkojakaumalla tuontisiemeneen verrattuna'];
  if (D.promise_notes && D.promise_notes.l15_adds_t !== undefined) D.promise_notes.l15_adds_t = 'what parcel records settle: added Finnish tonnes at today\'s mix of mineral and peat parcels, against imported seed';
  SUMS.fields = ['Two crop lists: peas for harvest risk; turnip rape, where higher yield cuts emissions per tonne.', 'Kaksi kasvilistaa: herne satoriskille; rypsi, jossa suurempi sato vähentää päästöjä tonnia kohden.'];
  var fieldsAndNature6 = fieldsAndNature;
  fieldsAndNature = function () {
    var h = fieldsAndNature6(), a = L2(['farm advisory checks the peat behind turnip rape.', 'viljelyneuvonta tarkistaa rypsin turvemaat.']);
    if (h.indexOf(a) < 0) throw new Error('v7 anchor missing: ' + a);
    return h.split(a).join(L2(['farm advisory tracks yield and nitrogen per tonne on each turnip-rape farm, with the peat under it.', 'viljelyneuvonta seuraa jokaisen rypsitilan satoa ja tonnikohtaista typpeä sekä sen turvemaita.']));
  };

  /* ---- 2. peat in one plain sentence; their frame is sales and acquisitions ---- */
  T.base_h = ['Sales, acquisitions, and now soils', 'Myynnit, yritysostot ja nyt maaperä'];
  SUMS.base = ['Sales, acquisitions, and now soils: what moves the base year past the {k:meter.line} line.', 'Myynnit, yritysostot ja nyt maaperä: mikä vie perusvuoden yli {k:meter.line}:n rajan.'];
  T.peat7 = ['A drained peat field is an old bog ditched for crops that keeps releasing CO₂; ours alone move the 2025 base year past the line, as an acquisition would.',
    'Ojitettu turvepelto on viljelyyn kuivattu entinen suo, joka vapauttaa hiilidioksidia vuosittain; omat turvepeltomme yksinään vievät vuoden 2025 perusvuoden rajan yli, kuten yritysosto veisi.'];
  T.bases_p = ['You know the {k:meter.line} rule from selling a business and buying one. Soils can trigger it too. ' + T.peat7[0] + ' On the soil map alone, nothing fitted, the move is {k:chip.peat.lo_pct}, past the line on all {n:v3.floor_n_bases} bases tested. ' + T.bases_p[0],
    '{k:meter.line}:n sääntö on tuttu liiketoiminnan myynnistä ja yritysostosta. Myös maaperä voi laukaista sen. ' + T.peat7[1] + ' Pelkällä maaperäkartalla, ilman sovitusta, muutos on {k:chip.peat.lo_pct}, yli rajan kaikilla {n:v3.floor_n_bases} testatulla perusvuodella. ' + T.bases_p[1]];

  /* ---- 3 + 4. first screen ---- */
  T.h_q7 = ['the {Y} farm and land (FLAG) target', 'vuoden {Y} maatalouden ja maankäytön (FLAG) tavoite'];
  T.h_rec_lead = ['Give procurement its own FLAG mandate.', 'Anna hankinnalle oma FLAG-valtuutus.'];
  T.h_swing = ['Your rapeseed suppliers\' own numbers moved {r:v3.w_sw_lo,v3.w_sw_hi} in one year with no programme; the 2032 route asks them for {r:v3.w_y1_lo,v3.w_y1_hi}.',
    'Rapsitoimittajiesi omat luvut muuttuivat yhdessä vuodessa {r:v3.w_sw_lo,v3.w_sw_hi} ilman ohjelmaa; vuoden 2032 reitti pyytää heiltä {r:v3.w_y1_lo,v3.w_y1_hi}.'];
  T.h_rec_p = ['A field pilot with the three largest seed suppliers, paid per verified tonne, capped at {k:v4.r{Y}.cap} a year. No cut is booked until an offer clears its floor.',
    'Peltopilotti kolmen suurimman siementoimittajan kanssa, maksu todennetuista tonneista, katto {k:v4.r{Y}.cap} vuodessa. Vähennystä ei kirjata ennen kuin tarjous ylittää alarajansa.'];
  T.h_next_p = ['Oilseed procurement sends SUP005, SUP008 and SUP011 the terms: field data (nitrogen, yield, area), a delivery floor and a ceiling of {k:v4.r.price_hi} per verified tonne. If none meets its floor, the target year comes back to the board.',
    'Öljykasvihankinta lähettää SUP005:lle, SUP008:lle ja SUP011:lle ehdot: peltotiedot (typpi, sato, ala), toimituksen alaraja ja katto {k:v4.r.price_hi} todennetulta tonnilta. Jos kukaan ei yllä alarajaansa, tavoitevuosi palaa hallitukselle.'];
  T.tr_h = ['Where every number comes from.', 'Mistä jokainen luku tulee.'];
  T.tr_p = ['Click any underlined figure: its rule, script and source records.', 'Napsauta alleviivattua lukua: sääntö, skripti ja lähdetietueet.'];
  T.tr_trail = ['The trail', 'Jäljitys'];
  T.tr_m = ['Method and limits', 'Menetelmä ja rajat'];
  function trustLine() {
    return '<p class="trust7"><b>' + tx('tr_h') + '</b> ' + tx('tr_p') + ' <span class="trl"><a class="go" href="#trail" data-open="trail">' + tx('tr_trail') + ' →</a> <a class="go" href="#method" data-open="method">' + tx('tr_m') + ' →</a></span></p>';
  }
  hero = function () {
    var b = function (m, lab) { return '<button type="button" class="d0b' + (MODE === m ? ' on' : '') + '" data-mode="' + m + '" aria-pressed="' + (MODE === m) + '">' + tx(lab) + (m === '2032' ? ' <span class="tag">' + tx('h_rec') + '</span>' : '') + '</button>'; };
    return '<header class="hero h7"><p class="hq">' + tx('h_q') + ' <span class="hq2">' + fy(T.h_q7) + '</span></p>' +
      '<h1 class="hv">' + fy(T.h_short) + ' <span class="hv2">' + tx('h_lever') + '</span></h1>' +
      '<p class="hsw">' + tx('h_swing') + ' <b>' + tx('h_swing_b') + '</b></p>' +
      trustLine() +
      '<div class="hrow"><div class="hrec"><span class="olab">' + tx('h_rec_h') + '</span><p class="hlead">' + tx('h_rec_lead') + '</p><p>' + fy(T.h_rec_p) + '</p><p class="hown">' + esc(L2(T.own)) + ': <b>' + tx('h_rec_own') + '</b></p><a class="go" href="#mandates" data-open="mandates">' + tx('h_more') + '</a></div>' +
      '<div class="hnext"><span class="olab">' + tx('h_next_t') + '</span><p>' + tx('h_next_p') + '</p></div></div>' +
      '<div class="d0 d0s"><span class="olab">' + tx('h_d0') + (DEC.P ? ' · <span class="ok">' + tx('d_rec') + '</span>' : '') + '</span><div class="d0r">' + b('2032', 'h_32') + b('2035', 'h_35') + '</div><p class="small">' + tx('h_d0n') + ' <button class="lk" data-v="' + enc(['doc', 'framework']) + '" type="button">' + tx('src_fw') + '</button></p></div></header>';
  };
  pillars = function () {
    return '<div class="pillars quiet p7">' +
      tile('base', L2(['Base year · drained peat', 'Perusvuosi · ojitettu turve']), fx(['{w:chip.peat.lo_pct|Past the 5% line}', '{w:chip.peat.lo_pct|Yli 5 %:n rajan}']), tx('peat7')) +
      tile('route', L2(['Route · cost a year', 'Reitti · vuosikustannus']), nb('d.rcost'), L2(['Every lever priced, with owner, pros and cons. Owner: CFO.', 'Jokainen keino hinnoiteltu, omistaja, hyödyt ja haitat. Omistaja: talousjohtaja.'])) +
      tile('fields', L2(['Climate risk · harvest loss a year', 'Ilmastoriski · satomenetys vuodessa']), nb('v3.eur_historical') + ' → ' + nb('v3.eur_ssp245'), fx(['Today to 2041–60 under mid-range warming; peas carry {k:v3.pea_eur_share}.', 'Nykyilmasto → 2041–60 kohtalaisella lämpenemisellä; herneen osuus {k:v3.pea_eur_share}.'])) +
      tile('nature', L2(['Nature · phosphorus to lakes', 'Luonto · fosfori vesistöihin']), nb('v3.n6_top_t_p_pct'), fx(['of our contract phosphorus to water comes from the {n:v3.n6_top_n} highest-emitting farms. Lakes need their own list: CA12 first.', 'sopimuspeltojen vesiin päätyvästä fosforista tulee {n:v3.n6_top_n} suurimmalta päästäjältä. Vesistöt tarvitsevat oman listansa: CA12 ensin.'])) + '</div>';
  };

  /* ---- 3. the trail is named the same everywhere ---- */
  var sourceTable6 = sourceTable;
  sourceTable = function () {
    var h = sourceTable6(), a = '<details class="sources"><summary>' + L2(['Figures and sources', 'Luvut ja lähteet']) + '</summary>';
    if (h.indexOf(a) !== 0) throw new Error('v7 anchor missing: sources');
    return '<details class="sources" id="trail"' + (OPEN.trail ? ' open' : '') + '><summary><b>' + tx('tr_h') + '</b> <span class="small">' + esc(L2(['The trail: every figure on this page with its script and source.', 'Jäljitys: jokainen sivun luku skripteineen ja lähteineen.'])) + '</span></summary>' + h.slice(a.length);
  };

  /* ---- method: the rapeseed measurement and its limits ---- */
  T.m15 = ['Rapeseed measurement: the {n:v3.n7_resp} of {n:v3.n7_farms} Finnish contract turnip-rape farms that sent a 2025 field record, split into yield quarters of {n:v3.n7_q_n} farms. Nitrogen is mineral plus manure as the farmer reported it; FLAG per tonne is the inventory\'s farm FLAG ÷ (reported yield × parcel hectares), compared on farms with no mapped peat. Self-reported and one season: it shows the spread the programme can work on, not what any farm will achieve. Pessimistic re-run, thirds on mineral-soil farms only: the low-yield third still uses {k:v3.n7_rob_nt} the nitrogen per tonne and {k:v3.n7_rob_fl} the FLAG per tonne of the high-yield third.',
    'Rapsin mittaus: ne {n:v3.n7_resp}/{n:v3.n7_farms} suomalaista rypsin sopimustilaa, jotka lähettivät vuoden 2025 peltotiedot, jaettuna {n:v3.n7_q_n} tilan satoneljänneksiin. Typpi on viljelijän ilmoittama mineraali- ja lantatyppi; FLAG tonnia kohden on inventaarion tilan FLAG ÷ (ilmoitettu sato × lohkohehtaarit), verrattuna tiloilla, joilla ei ole kartoitettua turvetta. Itse ilmoitettua ja yksi kausi: se näyttää vaihtelun, johon ohjelma voi tarttua, ei sitä, mihin yksittäinen tila pääsee. Varovainen uusinta, kolmannekset vain kivennäismaan tiloilla: heikoin kolmannes käyttää yhä {k:v3.n7_rob_nt} typpeä ja {k:v3.n7_rob_fl} FLAG-päästöjä tonnia kohden parhaaseen verrattuna.'];
  T.m16 = ['Number format: euros under 10,000 are shown in full, from 10,000 in thousands (k) and from one million in millions (M); a range uses one unit. Every figure opens its exact value.',
    'Lukumuoto: alle 10 000 euron summat näytetään kokonaan, 10 000:sta alkaen tuhansina (t€) ja miljoonasta alkaen miljoonina; vaihteluväli käyttää yhtä yksikköä. Jokainen luku avaa tarkan arvonsa.'];
  var renderPage6 = renderPage;
  renderPage = function () {
    var h = renderPage6(), a = '<li>' + tx('m14') + '</li>';
    if (h.split(a).length !== 2) throw new Error('v7 anchor missing: method m14');
    return h.replace(a, a + '<li>' + tx('m15') + '</li><li>' + tx('m16') + '</li>');
  };
  var boot6 = boot;
  boot = function () {
    boot6();
    document.addEventListener('toggle', function (e) { if (e.target && e.target.id === 'trail') OPEN.trail = e.target.open; }, true);
    /* a shared link to a fold (#trail, #method, #base ...) opens it and scrolls to it once the page is drawn */
    if (G.location && G.location.hash) { var el = document.getElementById(G.location.hash.slice(1)); if (el) { OPEN[el.id] = true; el.open = true; if (el.scrollIntoView) el.scrollIntoView(); } }
  };

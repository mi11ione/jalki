  /* ================================================================ Jälki v5 layer
     Keeps the v4 first screen. Adds one fold, "Whose numbers", and one sentence on the first screen (pay on field records,
     never on a lower footprint). Applies the reviewer and repair-ticket fixes listed in output.md. Every new figure is a
     registry key (v3.w_*) written by build.py from whose.py and v5model.py. Synthetic pack only. */
  var V5 = D.v5;
  var V5S = 'python3 stages/pj-v5/build.py → data.js#v5';
  SCRIPT.v4 = 'python3 stages/pj-v5/build.py → v4.json';
  [2032, 2035].forEach(function (y) {
    var Y = String(y);
    N('v4.r' + y + '.prem_lo', 'v4:rape.' + Y + '.prem_lo', 'pct', 1, ['Seed-price premium, low end, both demand scenarios', 'Siemenen lisähinta, alaraja, molemmat kysyntäskenaariot'],
      ['Field-programme euros per tonne of seed ÷ the 2025 ERP price paid (spend ÷ audited tonnes; not the contract table), lowest of the two scenarios.', 'Peltohjelman eurot siementonnia kohden ÷ vuoden 2025 ERP-hinta (kulut ÷ todennetut tonnit; ei sopimustaulukko), pienin kahdesta skenaariosta.'], ['v4.r.paid'], ['v4~rape']);
    N('v4.r' + y + '.prem_hi', 'v4:rape.' + Y + '.prem_hi', 'pct', 1, ['Seed-price premium, high end, both demand scenarios', 'Siemenen lisähinta, yläraja, molemmat kysyntäskenaariot'],
      ['As the low end; highest of the two scenarios.', 'Kuten alaraja; suurin kahdesta skenaariosta.'], ['v4.r.paid'], ['v4~rape']);
  });
  R['v4.r.noise'].dp = 1;
  R['v4.r.noise'].how = ['Median of |2025 ÷ 2024 − 1| over the five rapeseed suppliers whose 2025 footprint is in the base and whose 2024 file is valid (per kilogram, period in its year). Files with a 2022 reference period are excluded.', 'Mediaani |2025 ÷ 2024 − 1| viidestä rapsitoimittajasta, joiden vuoden 2025 jalanjälki on perusvuodessa ja vuoden 2024 tiedosto voimassa (kilolta, kausi omana vuonnaan). Vuoden 2022 viitekauden tiedostot jätetään pois.'];
  /* the new figures open onto the records they rest on */
  (function () {
    var RAPEGO = ['line~' + RAPE_LINE], BJGO = ['line~' + LINKS.foodhills[0]];
    var go = { SEED: ['supplier_share', 'supplier_break', 'library_share', 'library_break', 'top_share', 'top_break', 'top_n', 'ghost_flag', 'ghost_years', 'pcf_unassured', 'pcf_n', 'sw_lo', 'sw_hi', 'sw_med', 'sw_n', 'swa_lo', 'swa_med', 'swa_n', 'y1_lo', 'y1_hi', 's5_share', 's5_p24', 's5_p25', 's5_fb', 'reg_n', 'reg_live'],
      RAPE: ['farms_share', 'farms_break', 'grass_t_ha', 'crop_t_ha', 'retire_t', 'retire_pct', 'nol16_lo', 'nol16_hi'], BJ: ['bjuv_gas_mwh', 'ops_share', 'ops_break', 'product_share', 'product_break'], CORR: ['validated_fix_t'] };
    var to = { SEED: SEEDGO, RAPE: RAPEGO, BJ: BJGO, CORR: ['corr~judgement'] };
    Object.keys(go).forEach(function (g) { go[g].forEach(function (k) { if (!R['v3.w_' + k]) throw new Error('v5 key missing ' + k); R['v3.w_' + k].go = to[g]; }); });
  })();
  R['v4.r.noise'].lab = ['Median yearly move in rapeseed suppliers\' own PCFs (valid files)', 'Rapsitoimittajien omien PCF:ien vuosimuutoksen mediaani (voimassa olevat tiedostot)'];
  R['v4.r.paid'].how = ['Price paid per tonne of bought seed, 2025: ERP spend ÷ audited seed tonnes (synthetic pack). Computed from purchase lines, not from the contract price table; the closeness of the two is a shared anchor, not a cross-check.', 'Ostosiemenen hinta tonnilta 2025: ERP-kulut ÷ todennetut siementonnit (synteettinen paketti). Laskettu ostoriveistä, ei sopimushintataulukosta; lukujen läheisyys on yhteinen ankkuri, ei ristiintarkistus.'];
  R['chip.peat.lo_pct'].lab = ['Peat floor, soil map only, % of the 2025 current-practice total', 'Turpeen alaraja, pelkkä maaperäkartta, % vuoden 2025 nykykäytännön kokonaispäästöstä'];
  R['p.probe_k'].lab = ['Mineral findings that trigger a floor review', 'Kivennäismaahavainnot, jotka käynnistävät alarajan tarkistuksen'];
  R['p.imp_kgk'].how = ['Bought seed M102–M107: tonnes ÷ kg in the 2025 inventory, with a supplier PCF where it is valid for 2025 and the library default otherwise.', 'Ostosiemen M102–M107: tonnit ÷ kilot vuoden 2025 inventaariossa; toimittajan PCF, kun se on voimassa vuodelle 2025, muuten kirjaston oletus.'];
  R['p.fi_kgk_min'].how = ['(Farm line − peat add-on) ÷ delivered kg: the rebuilt mineral-soil method, not the current calculator.', '(Tilarivi − turvelisä) ÷ toimitetut kilot: uudelleen laskettu kivennäismaan menetelmä, ei nykyinen laskuri.'];
  R['lev.L03.t_central'].how = ['Central: 95 % of the 2023–25 mean R404A top-up at S-SAK (b-path adoption assumption), not one year at 100 %.', 'Keskiarvo: 95 % S-SAKin R404A-lisäysten 2023–25 keskiarvosta (b-pathin käyttöönotto-oletus), ei yhden vuoden 100 %.'];
  R['lev.L20.t_central'].how = ['Central: 55 % of 2025 road trucking switched to HVO100, after the imported-seed legs L21 takes first (30 %); b-path adoption assumptions, not a full switch.', 'Keskiarvo: 55 % vuoden 2025 tiekuljetuksista HVO100:aan sen jälkeen, kun L21 ottaa tuontisiemenen kuljetuksista ensin 30 %; b-pathin oletuksia, ei täyttä vaihtoa.'];
  B.levers.forEach(function (l) { var k = 'lev.' + l.id + '.cost_eur_yr'; if (R[k]) R[k].how = ['Annual-equivalent: catalogue capex at an assumed 8 % over the lever\'s lifetime, plus catalogue opex scaled to the recomputed tonnes (b-path). Design estimates, not quotes.', 'Vuosikustannusvastine: luettelon investointi oletetulla 8 %:n korolla keinon eliniälle sekä luettelon käyttökustannus skaalattuna uudelleen laskettuihin tonneihin (b-path). Suunnitteluarvioita, ei tarjouksia.']; });

  /* first screen: same four elements; one graft sentence; target-year reason that is not "smaller cut" */
  /* pj-v5b: first screen reordered. Verdict + floor of the gap, the supplier-swing line, the decision with owner and cap,
     next week's letters, then decision 0 (smaller), then the quiet pillars. The full range and its conditions open from the number. */
  T.h_d0n = ['Both years need the same {k:p.pace} FLAG cut a year; 2035 is only longer.',
    'Molemmat vuodet vaativat saman {k:p.pace} FLAG-leikkauksen vuodessa; 2035 on vain pidempi.'];
  T.h_gap = ['FLAG still short of the {Y} target on the recommended route at central lever bands, counting physical cuts only.', 'FLAG-tavoitteesta {Y} jää vajetta suositellulla reitillä keinojen keskitasoilla, kun lasketaan vain fyysiset vähennykset.'];
  T.h_short = ['At least {k:v4.gap{Y}_lo} short.', 'Vajetta vähintään {k:v4.gap{Y}_lo}.'];
  /* pj-v5c: the shortfall leads in red; one plain line under it replaces "Not on today's catalogue." */
  T.h_lever = ['Today\'s lever list can\'t close it.', 'Nykyinen keinoluettelo ei kuro sitä umpeen.'];
  T.h_swing = ['Your rapeseed suppliers\' own numbers moved {r:v3.w_sw_lo,v3.w_sw_hi} in one year, with no programme. The first-year cut the 2032 route asks of them is {r:v3.w_y1_lo,v3.w_y1_hi}.',
    'Rapsitoimittajiesi omat luvut muuttuivat yhdessä vuodessa {r:v3.w_sw_lo,v3.w_sw_hi} ilman mitään ohjelmaa. Vuoden 2032 reitti pyytää heiltä ensimmäisenä vuonna {r:v3.w_y1_lo,v3.w_y1_hi}:n leikkausta.'];
  T.h_swing_b = ['Pay for field tonnes, not better spreadsheets.', 'Maksa siis peltotonneista, ei paremmista taulukoista.'];
  T.h_rec_p = ['Give procurement its own FLAG mandate: a field-programme pilot with the three largest seed suppliers that send footprint files, paid per verified tonne and capped at {k:v4.r{Y}.cap} a year. Book no reduction until an offer clears its delivery floor and cap.',
    'Anna hankinnalle oma FLAG-valtuutus: peltohjelman pilotti kolmen suurimman jalanjälkitiedostoja lähettävän siementoimittajan kanssa, maksu todennetuista tonneista, katto {k:v4.r{Y}.cap} vuodessa. Vähennystä ei kirjata ennen kuin tarjous läpäisee alarajansa ja kattonsa.'];
  T.h_rec_own = ['Head of oilseed procurement; the CFO owns the cap', 'Öljykasvihankinnan johtaja; talousjohtaja omistaa katon'];
  T.h_next_t = ['Next week · three supplier letters', 'Ensi viikko · kolme toimittajakirjettä'];
  hero = function () {
    var y = RY();
    var b = function (m, lab) { return '<button type="button" class="d0b' + (MODE === m ? ' on' : '') + '" data-mode="' + m + '" aria-pressed="' + (MODE === m) + '">' + tx(lab) + (m === '2032' ? ' <span class="tag">' + tx('h_rec') + '</span>' : '') + '</button>'; };
    return '<header class="hero"><p class="hq">' + tx('h_q') + '</p>' +
      '<h1 class="hv">' + fy(T.h_short) + ' <span class="hv2">' + tx('h_lever') + '</span></h1>' +
      '<p class="hsw">' + tx('h_swing') + ' <b>' + tx('h_swing_b') + '</b></p>' +
      '<div class="hrow"><div class="hrec"><span class="olab">' + tx('h_rec_h') + '</span><p>' + fy(T.h_rec_p) + '</p><p class="hown">' + esc(L2(T.own)) + ': <b>' + tx('h_rec_own') + '</b></p><a class="go" href="#mandates" data-open="mandates">' + tx('h_more') + '</a></div>' +
      '<div class="hnext"><span class="olab">' + tx('h_next_t') + '</span><p>' + tx('h_next_p') + '</p></div></div>' +
      '<div class="d0 d0s"><span class="olab">' + tx('h_d0') + (DEC.P ? ' · <span class="ok">' + tx('d_rec') + '</span>' : '') + '</span><div class="d0r">' + b('2032', 'h_32') + b('2035', 'h_35') + '</div><p class="small">' + tx('h_d0n') + ' <button class="lk" data-v="' + enc(['doc', 'framework']) + '" type="button">' + tx('src_fw') + '</button></p></div></header>';
  };
  /* the headline number opens its full range, its conditions and the verdict's worst case */
  var vNum1 = vNum;
  vNum = function (key) {
    var h = vNum1(key), m = /^v4\.gap(2032|2035)_lo$/.exec(key);
    if (!m) return h;
    var g = function (p) { return [p[0].split('{Y}').join(m[1]), p[1].split('{Y}').join(m[1])]; };
    return h + '<h4>' + esc(L2(['Full range and conditions', 'Koko vaihteluväli ja ehdot'])) + '</h4><p><b>' + rng('v4.gap' + m[1] + '_lo', 'v4.gap' + m[1] + '_hi') + '</b> ' + fx(g(T.h_gap)) + '</p>' + numRow('v4.worst' + m[1]);
  };
  pillars = function () {
    return '<div class="pillars quiet">' +
      tile('route', L2(['Route · cost a year', 'Reitti · vuosikustannus']), nb('d.rcost'), L2(['Owner: CFO', 'Omistaja: talousjohtaja'])) +
      tile('fields', L2(['Climate risk · harvest shortfall', 'Ilmastoriski · satovaje']), nb('v3.eur_historical') + ' → ' + nb('v3.eur_ssp245'), L2(['Yield model B · today to SSP2-4.5, 2041–60', 'Satomalli B · nykyilmasto → SSP2-4.5, 2041–60'])) +
      tile('nature', L2(['Nature · rewetted on the route', 'Luonto · soistettu reitillä']), nb('d.rrewet') + ' / ' + nb('p.peat_ha'), fx(['Model hectares (tonnes ÷ {k:p.tpha}) of drained contract peat', 'Mallihehtaareja (tonnit ÷ {k:p.tpha}) ojitetusta sopimusturpeesta'])) +
      tile('base', L2(['Inventory · peat floor, soil map only', 'Inventaario · turpeen alaraja, pelkkä kartta']), nb('chip.peat.lo_pct'), fx(['Past the {k:meter.line} line on all {n:v3.floor_n_bases} bases tested', 'Yli {k:meter.line}:n rajan kaikilla {n:v3.floor_n_bases} testatulla perusvuodella'])) + '</div>';
  };

  /* decisions, chips and route copy */
  (function () {
    var d = function (id) { return DECS.filter(function (x) { return x.id === id; })[0]; };
    d('P').q = ['Which target do we prepare? Recommended: 2032. It needs the same {k:p.pace} of FLAG cut a year as 2035, and it is the five-year target V2 asks for; V2 governs every new or renewed target from 31 January 2028.',
      'Minkä tavoitteen valmistelemme? Suositus: 2032. Se vaatii saman {k:p.pace} FLAG-leikkauksen vuodessa kuin 2035, ja se on V2:n edellyttämä viiden vuoden tavoite; V2 koskee jokaista uutta tai uusittua tavoitetta 31.1.2028 alkaen.'];
    d('M').t = function () { return ['Moves the base {r:chip.peat.lo_pct,chip.peat.hi_pct} of the 2025 current-practice total. On the soil map alone it stays past the {k:meter.line} line on every base tested: {r:v3.floor_min,v3.floor_max}.', 'Muuttaa perusvuotta {r:chip.peat.lo_pct,chip.peat.hi_pct} vuoden 2025 nykykäytännön kokonaispäästöstä. Pelkällä maaperäkartalla muutos pysyy yli {k:meter.line}:n rajan jokaisella testatulla perusvuodella: {r:v3.floor_min,v3.floor_max}.']; };
    d('C').t = function () { return ['{n:chip.pending.n} judgement corrections: rejecting all of them moves the base by at most {k:chip.pending_corrections.t}. Validated unit and duplicate fixes ({k:v3.w_validated_fix_t} of raw-feed typos) are not up for rejection.', '{n:chip.pending.n} harkinnanvaraista korjausta: kaikkien hylkääminen siirtää perusvuotta enintään {k:chip.pending_corrections.t}. Todennetut yksikkö- ja kaksoiskorjaukset ({k:v3.w_validated_fix_t} raakatietojen näppäilyvirheitä) eivät ole hylättävissä.']; };
  })();
  CHIPS[0].stake = ['{k:chip.peat.t} central. Soil-map floor, nothing fitted: {k:chip.peat.lo_pct} of the 2025 current-practice total; {r:v3.floor_min,v3.floor_max} across the {n:v3.floor_n_bases} bases tested, lowest on the target base. The same rule on 2022 gives {r:v3.soil_2022_lo,v3.soil_2022_hi}.',
    '{k:chip.peat.t} keskiarvona. Maaperäkartan alaraja ilman sovitusta: {k:chip.peat.lo_pct} vuoden 2025 nykykäytännön kokonaispäästöstä; {r:v3.floor_min,v3.floor_max} kaikilla {n:v3.floor_n_bases} testatulla perusvuodella, pienin tavoiteperusvuodella. Sama sääntö vuodelle 2022 antaa {r:v3.soil_2022_lo,v3.soil_2022_hi}.'];
  CHIPS.forEach(function (c) {
    if (c.id === 'pudasjarvi') c.stake = ['{k:chip.pudasjarvi.t} central, priced with a placeholder co-packer factor of {k:chip.pudasjarvi.ef}. Band and trigger are both on the reported 2025 total.', '{k:chip.pudasjarvi.t} keskiarvona, hinnoiteltu sopimusvalmistajan paikkakertoimella {k:chip.pudasjarvi.ef}. Vaihteluväli ja raja ovat molemmat raportoidulla vuoden 2025 kokonaispäästöllä.'];
    if (c.id === 'pending_corrections') c.stake = ['{n:chip.pending.n} judgement corrections. Rejecting all of them moves the base by at most {k:chip.pending_corrections.t}. The expert-review queue also lists validated unit and duplicate fixes; their raw sizes are typos removed from the records, not changes to the base.', '{n:chip.pending.n} harkinnanvaraista korjausta. Kaikkien hylkääminen siirtää perusvuotta enintään {k:chip.pending_corrections.t}. Tarkistusjonossa on myös todennettuja yksikkö- ja kaksoiskorjauksia; niiden raakakoot ovat tiedoista poistettuja näppäilyvirheitä, eivät perusvuoden muutoksia.'];
  });
  LT.L07[2] = ['The pack sizes it on about {k:v3.w_bjuv_gas_mwh} MWh a year of Swedish biogas, and Bjuv\'s 2025 meters show natural gas only. Outside the recommended route.', 'Paketti mitoittaa sen noin {k:v3.w_bjuv_gas_mwh} MWh:n vuotuiseen ruotsalaiseen biokaasuun, ja Bjuvin vuoden 2025 mittarit näyttävät vain maakaasua. Suositellun reitin ulkopuolella.'];
  T.pr_note = [T.pr_note[0].replace('L01, L14 and L22', 'L01, L07, L14 and L22'), T.pr_note[1].replace('L01, L14 ja L22', 'L01, L07, L14 ja L22')];
  T.m10 = ['Route: L01, L07, L14 and L22 are left out because the pack does not show the capacity they need (biogas at Säkylä and at Bjuv, the largest volume ever bought from lower-factor origins, an industry coalition). Without L07, own operations are short in 2032; the board mandates table shows by how much. The annual-equivalent cost is catalogue design estimates: a capital charge from catalogue lifetimes at an assumed 8 % plus scaled opex; not quotes, and capex is not added to it. Pausing HVO changes only the non-FLAG target, because transport fuel sits outside FLAG in the inventory. Entered supplier offers are presenter assumptions; the four ticks simulate review and verify nothing.',
    'Reitti: L01, L07, L14 ja L22 jätetään pois, koska paketti ei osoita niiden vaatimaa kapasiteettia (biokaasu Säkylässä ja Bjuvissa, suurin koskaan ostettu määrä vähäpäästöisemmistä alkuperistä, toimialan yhteishanke). Ilman L07:ää oma toiminta jää vuonna 2032 vajeeseen; valtuutustaulukko näyttää paljonko. Vuosikustannusvastine on luettelon suunnitteluarvioita: pääomakustannus luettelon eliniästä oletetulla 8 %:lla sekä skaalattu käyttökustannus; ei tarjouksia, eikä investointia lisätä siihen. HVO:n tauko muuttaa vain muuta kuin FLAG-tavoitetta, koska kuljetuspolttoaine on inventaariossa FLAGin ulkopuolella. Syötetyt toimittajatarjoukset ovat esittäjän oletuksia; neljä rastia simuloivat tarkistusta eivätkä todenna mitään.'];
  T.m1 = ['Data: the organisers\' synthetic pack; no figure is Apetit\'s real emissions. The inventory, bases, levers and gaps come from one pipeline (inventory, then bundle and promise). Three parts come from elsewhere and say so where they appear: the expert-review proposals and the public-key backtest from a second pipeline built blind from the raw pack, the crop-risk rows from the climate join, and the rapeseed plan from its own method, re-run here on this route gap. Every number opens its rule and script; most also open down to source records.',
    'Aineisto: järjestäjien synteettinen paketti; mikään luku ei ole Apetitin todellisia päästöjä. Inventaario, perusvuodet, keinot ja vajeet tulevat yhdestä laskentaketjusta. Kolme osaa tulee muualta, ja se kerrotaan niiden kohdalla: asiantuntijatarkistuksen ehdotukset ja julkisten avainten testi toisesta, raakapaketista sokkona rakennetusta ketjusta, satoriskin rivit ilmastoyhdistelmästä ja rapsisuunnitelma omalla menetelmällään tämän reitin vajeelle. Jokainen luku avaa sääntönsä ja skriptinsä; useimmat myös lähdetietueisiin asti.'];
  T.m2 = [T.m2[0].replace('; headline gaps are rounded to 100 t.', '. Gaps are shown to the tonne; the conservative case (every route lever at its low band) is given beside the offer gate. L16 (pizza recipes) rests on an uncited constant; with L16 at zero the 2032 gap is {r:v3.w_nol16_lo,v3.w_nol16_hi}.'),
    T.m2[1].replace('; otsikkovajeet on pyöristetty sataan tonniin.', '. Vajeet näytetään tonnin tarkkuudella; varovainen tapaus (reitin keinot alatasolla) on tarjousportin vieressä. L16 (pizzareseptit) nojaa lähteettömään vakioon; L16 nollassa vuoden 2032 vaje on {r:v3.w_nol16_lo,v3.w_nol16_hi}.')];
  if (T.m2[0].indexOf('w_nol16') < 0 || T.m2[1].indexOf('w_nol16') < 0) throw new Error('m2 not replaced');
  T.m7 = [T.m7[0] + ' The seal detects changes; it is not a signature. Anyone holding this code can re-seal a file, so a re-hashed forgery replays green. A production version signs with the organisation\'s identity service instead.',
    T.m7[1] + ' Sinetti havaitsee muutokset; se ei ole allekirjoitus. Kuka tahansa tällä koodilla voi sinetöidä tiedoston uudelleen, joten uudelleen tiivistetty väärennös toistuu vihreänä. Tuotantoversio allekirjoittaa organisaation tunnistuspalvelulla.'];
  T.m11 = ['Whose numbers: every 2025 edge in the trail ({n:v3.w_reg_live} factors carrying tonnes) grouped by who writes its factor. "Revision that forces a recalculation" is the uniform change across that author\'s factors that moves the base 5%; it is a threshold, not a forecast. The supplier swing uses the five rapeseed PCFs in the base with a valid 2024 file. Across every valid 2024/25 rapeseed pair in the pack ({n:v3.w_swa_n}, used or not) the smallest move is {k:v3.w_swa_lo} and the median {k:v3.w_swa_med}: the median still exceeds the year-one cut, though not every pair does. Two years of files show that figures move, not why. Climate euros and the pea share come from yield model B, which lost its forward test to model A; read them as an order of magnitude.',
    'Kenen luvut: jokainen vuoden 2025 jäljen rivi ({n:v3.w_reg_live} kerrointa, joilla on tonneja) ryhmiteltynä kertoimen kirjoittajan mukaan. "Uudelleenlaskennan pakottava muutos" on kirjoittajan kaikkien kertoimien tasainen muutos, joka siirtää perusvuotta 5 %; se on raja, ei ennuste. Toimittajavaihtelu käyttää perusvuoden viittä rapsi-PCF:ää, joilla on voimassa oleva vuoden 2024 tiedosto. Kaikilla paketin voimassa olevilla rapsipareilla 2024/25 ({n:v3.w_swa_n}, käytössä tai ei) pienin muutos on {k:v3.w_swa_lo} ja mediaani {k:v3.w_swa_med}: mediaani ylittää yhä ensimmäisen vuoden leikkauksen, vaikka jokainen pari ei. Kahden vuoden tiedostot näyttävät, että luvut liikkuvat, eivät miksi. Ilmastoeurot ja herneen osuus tulevat satomallista B, joka hävisi ennustetestinsä mallille A; lue ne suuruusluokkana.'];
  T.foot = ['Synthetic pack of the Apetit challenge · Jälki · plain HTML, opens from file', 'Apetit-haasteen synteettinen paketti · Jälki · pelkkä HTML, avautuu tiedostosta'];

  /* whose numbers: the graft. Three conditions on signing, review ordered by dependence on who controls the number. */
  SUMS.whose = ['Who writes the factors under the base, and how far each can move it before a restatement.', 'Kuka kirjoittaa perusvuoden kertoimet, ja kuinka paljon kukin voi siirtää sitä ennen uudelleenlaskentaa.'];
  T.lab_whose = ['Whose numbers', 'Kenen luvut'];
  function swingChart() {
    var rows = V5.swing_rows.slice().sort(function (a, b) { return a.swing_pct - b.swing_pct; }), X0 = 0, X1 = 50;
    var x = function (v) { return 70 + (Math.min(X1, Math.max(X0, v)) - X0) / (X1 - X0) * 430; };
    var s = '<svg class="swing" viewBox="0 0 580 ' + (34 + rows.length * 24) + '" width="100%" role="img" aria-label="' + esc(L2(['Supplier footprint moves against the year-one cut', 'Toimittajien jalanjälkien muutos vs. ensimmäisen vuoden leikkaus'])) + '">';
    s += '<rect x="' + x(V5.y1_lo) + '" y="14" width="' + Math.max(2, x(V5.y1_hi) - x(V5.y1_lo)) + '" height="' + (rows.length * 24 + 6) + '" fill="#c8102e" opacity=".18"/>';
    s += '<text class="tick" x="' + x(V5.y1_hi) + '" y="11" fill="#c8102e">' + esc(L2(['year-one cut', 'ensimmäisen vuoden leikkaus'])) + '</text>';
    [0, 10, 20, 30, 40, 50].forEach(function (t) { s += '<text class="tick" x="' + x(t) + '" y="' + (30 + rows.length * 24) + '" text-anchor="middle">' + esc(fnum(t, 0) + (LANG === 'en' ? '%' : ' %')) + '</text>'; });
    rows.forEach(function (r, i) {
      var yy = 26 + i * 24;
      s += '<text class="tick" x="64" y="' + (yy + 4) + '" text-anchor="end">' + esc(r.supplier) + '</text><line x1="' + x(0) + '" x2="' + x(r.swing_pct) + '" y1="' + yy + '" y2="' + yy + '" stroke="#555"/>' +
        '<circle cx="' + x(r.swing_pct) + '" cy="' + yy + '" r="5" fill="#111"/><text class="tick" x="' + (x(r.swing_pct) + 9) + '" y="' + (yy + 4) + '">' + esc((r.signed_pct > 0 ? '+' : '−') + fnum(Math.abs(r.signed_pct), 1) + (LANG === 'en' ? '%' : ' %')) + '</text>';
    });
    return s + '</svg>';
  }
  function whoseBlock() {
    var row = function (g, ctl, ord) { return '<tr><td>' + esc(L2(ctl[0])) + '</td><td>' + nb('v3.w_' + g + '_share') + '</td><td>' + nb('v3.w_' + g + '_break') + '</td><td>' + esc(L2(ctl[1])) + '</td><td>' + esc(L2(ord)) + '</td></tr>'; };
    var h = '<h2>' + L2(['Most of the base is written by someone else.', 'Suurimman osan perusvuodesta kirjoittaa joku muu.']) + '</h2>';
    h += '<p class="lead">' + L2(['Our ERP counts the kilos; someone else writes the CO₂ per kilo. Every tonne of the 2025 base, grouped by who writes its factor, with the revision that would force a recalculation:', 'ERP laskee kilot; hiilidioksidin kiloa kohden kirjoittaa joku muu. Jokainen perusvuoden 2025 tonni ryhmiteltynä kertoimen kirjoittajan mukaan, ja muutos, joka pakottaisi uudelleenlaskentaan:']) + '</p>';
    h += '<div class="table-scroll"><table class="whose"><thead><tr><th>' + L2(['Who writes the factor', 'Kertoimen kirjoittaja']) + '</th><th>' + L2(['Share of the base', 'Osuus perusvuodesta']) + '</th><th>' + L2(['Revision that forces a recalculation', 'Uudelleenlaskentaan pakottava muutos']) + '</th><th>' + L2(['Who controls it', 'Kuka sitä hallitsee']) + '</th><th>' + L2(['Review order', 'Tarkistusjärjestys']) + '</th></tr></thead><tbody>' +
      row('library', [['External factor library', 'Ulkoinen kerroinkirjasto'], ['The library publisher', 'Kirjaston julkaisija']], ['1 · lock the version', '1 · lukitse versio']) +
      row('supplier', [['Suppliers\' own footprints (PCF)', 'Toimittajien omat jalanjäljet (PCF)'], ['Each supplier', 'Kukin toimittaja']], ['2 · assurance and period', '2 · varmennus ja kausi']) +
      row('farms', [['Our contract farms, our method', 'Omat sopimustilat, oma menetelmä'], ['Us', 'Me']], ['3 · the peat method has already crossed', '3 · turvemenetelmä on jo ylittänyt rajan']) +
      row('ops', [['Fuel, power and refrigerant constants', 'Polttoaine-, sähkö- ja kylmäainevakiot'], ['Standard bodies', 'Standardien laatijat']], ['4', '4']) +
      row('product', [['Use and end-of-life constants', 'Käytön ja elinkaaren lopun vakiot'], ['The organisers\' method', 'Järjestäjän menetelmä']], ['5', '5']) + '</tbody></table></div>';
    h += '<p class="small">' + L2(['Review follows dependence: the smaller the revision that moves the base 5%, the earlier that author\'s factors are checked.', 'Tarkistus seuraa riippuvuutta: mitä pienempi muutos siirtää perusvuotta 5 %, sitä aiemmin kirjoittajan kertoimet tarkistetaan.']) + '</p>';
    h += '<h3>' + L2(['Three conditions on signing', 'Kolme ehtoa allekirjoitukselle']) + '</h3><ol class="m">';
    h += '<li><b>' + L2(['A revision is not a reduction.', 'Muutos ei ole vähennys.']) + '</b> ' + fx(['One library source (Agri-footprint / national LCA studies, {n:v3.w_top_n} factors) writes {k:v3.w_top_share} of the base. A {k:v3.w_top_break} revision of that source alone lands exactly on the 5% line, and up to that point nothing forces a recalculation: up to {k:v3.w_ghost_flag} of FLAG could appear or vanish with nobody acting, {n:v3.w_ghost_years} years of the required {k:p.pace} a year. Every factor revision is re-run on the frozen base and reported on its own line, never in the reduction column.',
      'Yksi kirjaston lähde (Agri-footprint / kansalliset LCA-tutkimukset, {n:v3.w_top_n} kerrointa) kirjoittaa {k:v3.w_top_share} perusvuodesta. Pelkän tämän lähteen {k:v3.w_top_break}:n muutos osuu juuri 5 %:n rajalle, eikä siihen asti mikään pakota uudelleenlaskentaan: jopa {k:v3.w_ghost_flag} FLAG-päästöjä voisi ilmestyä tai kadota kenenkään tekemättä mitään, {n:v3.w_ghost_years} vuotta vaadittua {k:p.pace}:n vuosileikkausta. Jokainen kerroinmuutos ajetaan lukittuun perusvuoteen ja raportoidaan omalla rivillään, ei koskaan vähennyksenä.']) + '</li>';
    h += '<li><b>' + L2(['Freeze the factor register.', 'Lukitse kerroinrekisteri.']) + '</b> ' + fx(['The register is already sealed into every signed record: {n:v3.w_reg_n} factors under one SHA-256 fingerprint, ', 'Rekisteri on jo sinetöity jokaiseen allekirjoitettuun asiakirjaan: {n:v3.w_reg_n} kerrointa yhden SHA-256-tiivisteen alla, ']) + '<span class="mono">' + esc(V5.reg_sha.slice(0, 16)) + '…</span>. ' +
      L2(['A changed factor breaks the seal, so a library update cannot pass as delivery.', 'Muuttunut kerroin rikkoo sinetin, joten kirjaston päivitys ei voi näyttää toimitukselta.']) + ' <button type="button" class="pill" data-v5="register">' + L2(['Download the register', 'Lataa rekisteri']) + '</button></li>';
    h += '<li><b>' + L2(['Pay on field records, not on a lower footprint.', 'Maksa peltotiedoista, ei pienemmästä jalanjäljestä.']) + '</b> ' + fx(['The {n:v3.w_sw_n} rapeseed suppliers whose footprints sit in the base and have a valid 2024 file moved {r:v3.w_sw_lo,v3.w_sw_hi} between the two files (median {k:v3.w_sw_med}), with no programme running. The pilot asks a year-one cut of {r:v3.w_y1_lo,v3.w_y1_hi}. Every one of them moved more than that, so a lower supplier figure cannot show whether the pilot bought anything. Credit follows nitrogen rate, yield and area against a like-for-like baseline.',
      'Ne {n:v3.w_sw_n} rapsitoimittajaa, joiden jalanjälki on perusvuodessa ja joilla on voimassa oleva vuoden 2024 tiedosto, muuttuivat tiedostojen välillä {r:v3.w_sw_lo,v3.w_sw_hi} (mediaani {k:v3.w_sw_med}) ilman mitään ohjelmaa. Pilotti pyytää ensimmäiselle vuodelle {r:v3.w_y1_lo,v3.w_y1_hi}:n leikkausta. Jokainen muuttui enemmän, joten pienempi toimittajaluku ei voi osoittaa, ostiko pilotti mitään. Hyvitys seuraa typpimäärää, satoa ja alaa vertailukelpoiseen lähtötasoon nähden.']) + '</li></ol>';
    h += swingChart();
    h += '<p>' + fx(['The largest single number in the base is SUP005\'s own rapeseed footprint, {k:v3.w_s5_share} of it. Its 2025 file lost its assurance and its primary-data share fell from {k:v3.w_s5_p24} to {k:v3.w_s5_p25}. If it falls back to the library default, the base moves {k:v3.w_s5_fb}, inside the line. In all, {k:v3.w_pcf_unassured} of the base rests on supplier footprints with no assurance.',
      'Perusvuoden suurin yksittäinen luku on SUP005:n oma rapsijalanjälki, {k:v3.w_s5_share} perusvuodesta. Sen vuoden 2025 tiedostosta puuttuu varmennus, ja primääridatan osuus laski {k:v3.w_s5_p24}:sta {k:v3.w_s5_p25}:iin. Jos se palaa kirjaston oletukseen, perusvuosi muuttuu {k:v3.w_s5_fb}, rajan sisällä. Kaikkiaan {k:v3.w_pcf_unassured} perusvuodesta nojaa vahvistamattomiin toimittajajalanjälkiin.']) + '</p>';
    h += '<p class="small"><b>' + L2(['Owner', 'Omistaja']) + ':</b> ' + L2(['Head of sustainability with the supplier data lead. Next week: record the library version in the register and ask SUP005 for an assured 2025 file; no budget. Falsifier: if a re-run on the frozen base shows a factor revision larger than a reported cut, that cut was a revision.', 'Vastuullisuusjohtaja ja toimittajadatan vastaava. Ensi viikko: kirjaa kirjaston versio rekisteriin ja pyydä SUP005:ltä varmennettu vuoden 2025 tiedosto; ei budjettia. Kumoaja: jos lukittuun perusvuoteen ajettu uusinta näyttää raportoitua leikkausta suuremman kerroinmuutoksen, se leikkaus oli muutos.']) + '</p>';
    return h;
  }
  renderPage = function () {
    var h = '<div class="wrap"><div class="rail"><span class="kick">' + tx('kicker') + '</span><span class="rr"><span class="synth tagc">' + tx('synth') + '</span><span class="lang"><button type="button" data-lang="fi" class="' + (LANG === 'fi' ? 'on' : '') + '">FI</button> <button type="button" data-lang="en" class="' + (LANG === 'en' ? 'on' : '') + '">EN</button></span></span></div>';
    h += hero();
    h += pillars();
    h += sec('mandates', tx('lab_mand'), mandatesBlock());
    h += sec('plan', tx('lab_plan'), rapeBlock());
    h += sec('whose', tx('lab_whose'), whoseBlock());
    h += sec('route', tx('lab_route'), routeBlock());
    h += sec('rotation', tx('lab_rot'), '<h2>' + tx('rot_h') + '</h2><h3>' + tx('visit_h') + '</h3><p>' + tx('visit_p') + '</p><p>' + tx('visit_owner') + '</p><p class="lead">' + tx('rot_p') + '</p>' + planChart() + '<p style="margin-top:14px"><b>' + tx('rot_dec') + '</b></p>');
    h += sec('base', tx('lab_base'), '<h2>' + tx('base_h') + '</h2><p>' + tx('bases_p') + '</p>' + basesTable() + '<p style="margin-top:22px">' + tx('meter_p') + '</p>' + meter());
    h += fieldsAndNature();
    h += sec('review', L2(['Expert review', 'Asiantuntijatarkistus']), reviewBlock());
    h += sec('gate', tx('lab_gate'), gate().replace('</h2>', '</h2><p class="simnote"><span class="synth sim">' + tx('sim') + '</span></p>'));
    h += sec('method', tx('lab_m'), '<h2>' + tx('m_h') + '</h2><ul class="m">' + ['m1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'm10', 'm11'].map(function (k) { return '<li>' + tx(k) + '</li>'; }).join('') + '</ul>');
    h += sourceTable();
    h += '<footer>' + tx('synth') + ' · ' + tx('foot') + '</footer></div>';
    return h;
  };

  /* expert review (pj-review4 R1, repaired as in step-12696-2): the lock's rule is "decided", not "accepted"; sizes read against the raw record */
  var INV = B.inventory_2025.totals.total_market;
  function blockingRow(r) { return r.impact === null || Math.abs(r.impact) >= D.v3.numbers.review_threshold.v; }
  DYN.q_n = function () { return D.v3.review.length; };
  DYN.q_block = function () { return D.v3.review.filter(blockingRow).length; };
  N('d.q_n', 'd:q_n', 'n', 0, ['Second-pipeline proposals in expert review', 'Toisen laskentaketjun ehdotukset asiantuntijatarkistuksessa'], ['Rows in data.js#v3.review.', 'Rivit data.js#v3.review.'], [], ['corr~judgement']);
  N('d.q_block', 'd:q_block', 'n', 0, ['Proposals that need a decision before signing', 'Ennen allekirjoitusta päätettävät ehdotukset'], ['Size at or above the blocking threshold, or unquantified.', 'Koko vähintään lukitusraja tai arvioimaton.'], [], ['corr~judgement']);
  reviewReady = function () { return D.v3.review.every(function (r) { var v = REVIEW[r.id]; return !blockingRow(r) || !!(v && (v.choice === 'accept' || v.choice === 'reject')); }); };
  function reviewSummary(rv) {
    var s = { proposals: D.v3.review.length, accepted: 0, rejected: 0, blocking_open: 0, figures_recomputed: false };
    D.v3.review.forEach(function (r) { var v = rv && rv[r.id]; if (v && v.choice === 'accept') s.accepted++; else if (v && v.choice === 'reject') s.rejected++; else if (blockingRow(r)) s.blocking_open++; });
    return s;
  }
  reviewBlock = function () {
    var ready = reviewReady();
    var h = '<h2>' + L2(['Decide each correction before signing.', 'Päätä korjaukset ennen allekirjoitusta.']) + '</h2><p>' + fx(['Diagnostics from a second pipeline built blind from the raw pack, reviewed by role: Expert reviewer (simulated in this prototype). The size column is each proposal against the raw record; the largest rows are unit errors the inventory already removes, so their raw size is not a change to the signed base. What review can still move is the judgement corrections in The base: at most {k:chip.pending_corrections.t}. Deciding a proposal records it in the signed record and recomputes no figure. Each of the {n:d.q_block} proposals of {k:v3.review_threshold} or more, or unquantified, needs a decision before signing; after a rejection the record and its replay say the figures were not recomputed.',
      'Toisen, sokkona rakennetun laskentaketjun ehdotukset. Tarkistajarooli: asiantuntija (simuloitu tässä prototyypissä). Kokosarake mittaa ehdotuksen raakatietuetta vastaan; suurimmat rivit ovat yksikkövirheitä, jotka inventaario jo poistaa, joten niiden raakakoko ei ole allekirjoitettavan perusvuoden muutos. Tarkistus voi yhä siirtää vain harkinnanvaraisia korjauksia: enintään {k:chip.pending_corrections.t}. Päätös kirjataan allekirjoitettuun asiakirjaan eikä laske lukuja uudelleen. Jokainen {n:d.q_block} ehdotuksesta, joka on vähintään {k:v3.review_threshold} tai arvioimaton, päätetään ennen allekirjoitusta; hylkäyksen jälkeen asiakirja ja sen toisto kertovat, ettei lukuja laskettu uudelleen.']) +
      '</p><p>' + L2(['Blocking threshold', 'Lukitusraja']) + ': ' + nb('v3.review_threshold') + ' · <b class="' + (ready ? 'ok' : 'red') + '">' + L2(ready ? ['Review complete', 'Tarkistus valmis'] : ['Review required', 'Tarkistus kesken']) + '</b></p>';
    function pc(v) { return esc(fnum(v, 2) + (LANG === 'en' ? '%' : ' %')); }
    function impactCell(r) {
      if (r.impact === null) return L2(['Unquantified: review required', 'Arvioimaton: tarkistus vaaditaan']);
      var x = Math.abs(r.impact) / INV;
      if (x >= 1) return L2(['Unit error in the raw record, ', 'Raakatietueen yksikkövirhe, ']) + esc(fnum(x, 1)) + '× ' + L2(['the whole inventory; already removed', 'koko inventaario; jo poistettu']) + ' <small>(' + nb('v3.review_' + r.id + '_impact') + ')</small>';
      return nb('v3.review_' + r.id + '_impact') + ' <small>(' + pc(100 * r.impact / INV) + ' ' + L2(['of the inventory', 'inventaariosta']) + ')</small>';
    }
    function reviewRow(r, open) { var v = REVIEW[r.id]; return '<details class="review-item"' + (open ? ' open' : '') + '><summary>' + esc(r.key) + ' · ' + esc(r.type) + ' · ' + (v ? esc(v.choice) : L2(['open', 'avoin'])) + '</summary><p>' + esc(r.rule) + '</p><table><thead><tr><th>Field</th><th>Old</th><th>Proposed</th><th>' + L2(['Size vs the raw record', 'Koko raakatietueeseen nähden']) + '</th><th>Source</th><th>Label</th></tr></thead><tbody><tr><td>' + esc(r.field) + '</td><td>' + esc(r.old) + '</td><td>' + esc(r.new) + '</td><td>' + impactCell(r) + '</td><td class="src">' + esc(D.v3.review_source) + ' · ' + esc(r.table) + ' · ' + esc(r.key) + '</td><td>synthetic' + (r.impact === null ? '' : ' · ' + esc(labelOf('v3.review_' + r.id + '_impact'))) + '</td></tr></tbody></table><button data-review="' + r.id + '~accept">' + L2(['Accept individually', 'Hyväksy yksittäin']) + '</button> <button data-review="' + r.id + '~reject">' + L2(['Reject · sign as not recomputed', 'Hylkää · allekirjoitus ilman uudelleenlaskentaa']) + '</button></details>'; }
    var active = D.v3.review.filter(function (r) { return blockingRow(r) && !REVIEW[r.id]; })[0];
    if (active) h += reviewRow(active, true);
    h += '<details class="review-history"><summary>' + L2(['All proposals and decisions', 'Kaikki ehdotukset ja päätökset']) + '</summary>' + D.v3.review.map(function (r) { return reviewRow(r, false); }).join('') + '</details>';
    h += '<h3>' + L2(['Second pipeline: backtest on the public keys', 'Toinen laskentaketju: testi julkisilla avaimilla']) + '</h3><table><thead><tr><th>Year</th><th>Cleaned</th><th>Uncleaned</th><th>Source</th><th>Label</th></tr></thead><tbody>';
    ['2023'].forEach(function (y) { h += '<tr><td>' + y + '</td><td>' + nb('v3.backtest_' + y + '_score') + '</td><td>' + nb('v3.backtest_' + y + '_naive') + '</td><td class="src">second pipeline · analysis.py · validation.a2</td><td>synthetic · ' + esc(lbls(['v3.backtest_' + y + '_score', 'v3.backtest_' + y + '_naive'])) + '</td></tr>'; });
    return h + '</tbody></table>';
  };
  DECS.filter(function (x) { return x.id === 'C'; })[0].t = function () { return ['{n:chip.pending.n} judgement corrections, a separate list from the {n:d.q_n} second-pipeline proposals under Expert review. Rejecting all of them moves the base by at most {k:chip.pending_corrections.t}, nearly all of it one commuting rule, R-COMM-1. Validated unit and duplicate fixes ({k:v3.w_validated_fix_t} of raw-feed typos) are not up for rejection.', '{n:chip.pending.n} harkinnanvaraista korjausta, eri lista kuin asiantuntijatarkistuksen {n:d.q_n} toisen laskentaketjun ehdotusta. Kaikkien hylkääminen siirtää perusvuotta enintään {k:chip.pending_corrections.t}, lähes kokonaan yksi työmatkasääntö, R-COMM-1. Todennetut yksikkö- ja kaksoiskorjaukset ({k:v3.w_validated_fix_t} raakatietojen näppäilyvirheitä) eivät ole hylättävissä.']; };

  /* the signed record (pj-review4 R2, R3, S1, S2): review state, decision conflicts, all three gaps and the factor register; replay checks them */
  function conflicts(p) { return Object.keys(p.decisions || {}).filter(function (k) { var d = DECS.filter(function (x) { return x.id === k; })[0]; return k !== 'P' && (!d || p.decisions[k].choice !== d.opts[0][0]); }).sort(); }
  var makePayload1 = makePayload;
  makePayload = function (role, at) {
    var p = makePayload1(role, at), s = reviewSummary(p.expert_review);
    p.review_summary = s;
    p.label = String(p.label).replace('Every correction is pending expert approval.', 'Expert review: ' + s.accepted + ' accepted and ' + s.rejected + ' rejected of ' + s.proposals + ' proposals; figures not recomputed from these decisions.');
    p.decision_conflicts = conflicts(p).map(function (k) { return { decision: k, choice: p.decisions[k].choice, figures_recomputed: false }; });
    p.route.s12_gap_t = [val('d.tg_s12_lo'), val('d.tg_s12_hi')];
    p.route.s3nf_gap_t = [val('d.tg_s3nf_lo'), val('d.tg_s3nf_hi')];
    p.factor_register = { n: V5.reg_n, sha256: V5.reg_sha, rule: 'a factor revision is re-run on this frozen base and reported on its own line, never as a reduction' };
    return p;
  };
  var replayChecks1 = replayChecks;
  replayChecks = function (e) {
    var out = replayChecks1(e), p = e.payload, r = p.route || {}, conf = conflicts(p);
    var stored = (p.decision_conflicts || []).map(function (c) { return c.decision; }).sort();
    out.push(['r_dec', conf.length === 0 && stored.length === 0, conf.concat(stored.filter(function (k) { return conf.indexOf(k) < 0; })).join(' ')]);
    var rs = reviewSummary(p.expert_review || {}), s = p.review_summary || {};
    out.push(['r_gate', rs.blocking_open === 0 && rs.rejected === 0 && s.accepted === rs.accepted && s.rejected === rs.rejected && s.figures_recomputed === false, rs.rejected ? rs.rejected + ' rejected' : rs.blocking_open ? rs.blocking_open + ' open' : '']);
    var savedBand = BAND, savedCut = CUT, savedMode = MODE, g = [];
    try { BAND = {}; (r.levers_on || []).forEach(function (x) { var a = x.split(':'); BAND[a[0]] = a[1]; }); CUT = r.supplier_cut_pct; MODE = String(r.year);
      g = [DYN.tg_s12_lo(), DYN.tg_s12_hi(), DYN.tg_s3nf_lo(), DYN.tg_s3nf_hi()]; } finally { BAND = savedBand; CUT = savedCut; MODE = savedMode; }
    var fz = (r.s12_gap_t || []).concat(r.s3nf_gap_t || []);
    out.push(['r_gaps', fz.length === 4 && fz.every(function (v, i) { return isNum(v) && Math.abs(v - g[i]) < 1e-6; }), '']);
    out.push(['r_reg', !!p.factor_register && p.factor_register.sha256 === V5.reg_sha && sha256(TR.factors_text) === V5.reg_sha, p.factor_register ? p.factor_register.sha256.slice(0, 16) : '']);
    return out;
  };
  T.r_dec = ['Every decision is the option the figures were computed on', 'Jokainen päätös on vaihtoehto, jolla luvut on laskettu'];
  T.r_gate = ['Every blocking proposal decided and none rejected, as frozen', 'Jokainen lukitseva ehdotus päätetty eikä yhtään hylätty, kuten lukittu'];
  T.r_gaps = ['Frozen Scope 1+2 and other Scope 3 gaps replay', 'Lukitut Scope 1+2- ja muun Scope 3:n vajeet toistuvat'];
  T.r_reg = ['Factor register matches the frozen fingerprint', 'Kerroinrekisteri vastaa lukittua tiivistettä'];

  /* pj-review4 R9: climate euros come from yield model B; R11: a retired parcel is not a rewetted one */
  var mandatesBlock1 = mandatesBlock;
  mandatesBlock = function () {
    var h = mandatesBlock1(), a = L2(['of modelled harvest-shortfall euros sit in peas', 'mallinnetuista satovaje-euroista on herneessä']);
    if (h.indexOf(a) < 0) throw new Error('v5 anchor missing: ' + a);
    return h.split(a).join(L2(['of model B harvest-shortfall euros sit in peas', 'mallin B satovaje-euroista on herneessä']));
  };
  var fieldsAndNature1 = fieldsAndNature;
  fieldsAndNature = function () {
    var h = fieldsAndNature1(), a = L2(['of harvest-risk euros;', 'satoriskin euroista;']);
    if (h.indexOf(a) < 0) throw new Error('v5 anchor missing: ' + a);
    return h.split(a).join(L2(['of harvest-risk euros (model B);', 'satoriskin euroista (malli B);'])).split('<th>Shortfall €/yr (model B)</th>').join('<th>' + L2(['Shortfall €/yr (model B)', 'Satovaje €/v (malli B)']) + '</th>');
  };
  (function () {
    var d = DECS.filter(function (x) { return x.id === 'L'; })[0];
    d.t = function () { return ['L11 counts {k:lev.L11.t_central} by moving crops off {k:p.l11_ha}; L12 rewets {k:p.l12_ha}. Retiring a parcel to grass is not rewetting: drained peat under grass still emits {k:v3.w_grass_t_ha} against {k:v3.w_crop_t_ha} under crops, so retiring L11\'s hectares saves {k:v3.w_retire_t}, {k:v3.w_retire_pct} of the credit per hectare.', 'L11 laskee {k:lev.L11.t_central} siirtämällä viljelyn pois {k:p.l11_ha}:lta; L12 soistaa {k:p.l12_ha}. Käytöstä poisto nurmelle ei ole uudelleensoistusta: ojitettu turve nurmella päästää yhä {k:v3.w_grass_t_ha} vs. {k:v3.w_crop_t_ha} viljelyssä, joten L11:n hehtaarien poisto säästää {k:v3.w_retire_t}, {k:v3.w_retire_pct} hehtaarikohtaisesta hyvityksestä.']; };
    d.opts[0] = ['Count rewetted parcels in full, retired parcels only at the grass factor', 'Uudelleen soistetut lohkot kokonaan, käytöstä poistetut vain nurmikertoimella'];
    var a = 'earns no credit until the same parcels are retired or rewetted.', b = 'ei saa hyvitystä ennen kuin samat lohkot poistetaan käytöstä tai soistetaan.';
    if (T.m2[0].indexOf(a) < 0 || T.m2[1].indexOf(b) < 0) throw new Error('v5 anchor missing: m2 retire');
    T.m2 = [T.m2[0].replace(a, 'earns no credit until the same parcels are rewetted; a parcel retired to grass earns only {k:v3.w_retire_pct} of the credit per hectare.'), T.m2[1].replace(b, 'ei saa hyvitystä ennen kuin samat lohkot soistetaan; nurmelle poistettu lohko saa vain {k:v3.w_retire_pct} hehtaarikohtaisesta hyvityksestä.')];
  })();
  function v5click(ev) {
    var t = ev.target.closest ? ev.target.closest('[data-v5]') : null;
    if (!t || t.getAttribute('data-v5') !== 'register') return;
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([TR.factors_text], { type: 'application/json' }));
    a.download = 'pipeline-factor-register-2025-' + V5.reg_sha.slice(0, 8) + '.json';
    document.body.appendChild(a); a.click(); a.remove();
  }
  var boot1 = boot;
  boot = function () { boot1(); document.addEventListener('click', v5click); };


  /* ================================================================ Jälki v8 layer (narrow pass after R7)
     1. The promise and its price in one headline: the recommended route's annual cost (v4.rec_eur) beside the 2032
        FLAG shortfall it still leaves (v4.gap{Y}_lo). Both figures are on the same recommended route.
     2. The nature card worded so it cannot be misread (the 10 biggest CO2 farms send only 2.5% of the phosphorus).
     3. The phosphorus contract clause for lake catchments, one line in the nature fold (v3.n8_* from v8clause.py).
     4. No internal paths or development names on screen: a display-only pass over text and tooltips (never over
        data attributes, so every click-through key stays exact). Synthetic pack only. */

  /* ---- 1. the promise and its price ---- */
  T.h_short = ['The {Y} promise: {k:v4.rec_eur} a year, and still at least {k:v4.gap{Y}_lo} short.',
    'Lupaus {Y}: {k:v4.rec_eur} vuodessa – ja silti vajetta vähintään {k:v4.gap{Y}_lo}.'];

  /* ---- 2. the nature card ---- */
  pillars = function () {
    return '<div class="pillars quiet p7">' +
      tile('base', L2(['Base year · drained peat', 'Perusvuosi · ojitettu turve']), fx(['{w:chip.peat.lo_pct|Past the 5% line}', '{w:chip.peat.lo_pct|Yli 5 %:n rajan}']), tx('peat7')) +
      tile('route', L2(['Route · cost a year', 'Reitti · vuosikustannus']), nb('d.rcost'), L2(['Every lever priced, with owner, pros and cons. Owner: CFO.', 'Jokainen keino hinnoiteltu, omistaja, hyödyt ja haitat. Omistaja: talousjohtaja.'])) +
      tile('fields', L2(['Climate risk · harvest loss a year', 'Ilmastoriski · satomenetys vuodessa']), nb('v3.eur_historical') + ' → ' + nb('v3.eur_ssp245'), fx(['Today to 2041–60 under mid-range warming; peas carry {k:v3.pea_eur_share}.', 'Nykyilmasto → 2041–60 kohtalaisella lämpenemisellä; herneen osuus {k:v3.pea_eur_share}.'])) +
      '<div class="pillar"><a class="olab" href="#nature" data-open="nature">' + L2(['Nature · phosphorus to lakes', 'Luonto · fosfori vesistöihin']) + '</a><div class="pillar-value pv8">' +
      fx(['Our {n:v3.n6_top_n} biggest CO₂ farms send only {k:v3.n6_top_t_p_pct} of the phosphorus.', '{n:v3.n6_top_n} eniten CO₂:ta päästävää tilaamme tuottaa vain {k:v3.n6_top_t_p_pct} vesiin päätyvästä fosforista.']) +
      '</div><p>' + esc(L2(['The lakes need a different list: CA12 first.', 'Järvet tarvitsevat eri listan: CA12 ensin.'])) + '</p></div></div>';
  };

  /* ---- 3. the phosphorus clause, one line in the nature fold ---- */
  ['n8_cl_dmax', 'n8_cl_parcels', 'n8_cl_farms', 'n8_cl_kg', 'n8_cl_pct', 'n8_cl_half_kg', 'n8_cl_ca12_parcels'].forEach(function (k) {
    if (!R['v3.' + k]) throw new Error('v8 key missing ' + k);
    R['v3.' + k].how = ['The 2025 contract parcels in the inventory trail, joined to the parcel register (buffer strip, distance to water, catchment), the catchment table (ecological status) and the catchment phosphorus model A (phosphorus delivered to water per parcel). The clause covers parcels with no buffer strip, within {n:v3.n8_cl_dmax} m of water, in catchments below good status. Model A multiplies a parcel\'s field phosphorus by 0.75 when it has a buffer strip, so the saving is a quarter of those parcels\' phosphorus to water. That coefficient is the model\'s assumption; at half its effect the clause still saves about {n:v3.n8_cl_half_kg} kg a year.',
      'Vuoden 2025 sopimuslohkot inventaarion jäljityksestä yhdistettynä lohkorekisteriin (suojakaista, etäisyys veteen, valuma-alue), valuma-aluetaulukkoon (ekologinen tila) ja valuma-alueiden fosforimalliin A (vesiin päätyvä fosfori lohkoittain). Lauseke koskee lohkoja, joilla ei ole suojakaistaa, jotka ovat enintään {n:v3.n8_cl_dmax} m:n päässä vedestä ja joiden valuma-alue on hyvää huonommassa tilassa. Malli A kertoo lohkon peltofosforin 0,75:llä, kun suojakaista on, joten säästö on neljännes näiden lohkojen vesiin päätyvästä fosforista. Kerroin on mallin oletus; puolella vaikutuksesta lauseke säästää yhä noin {n:v3.n8_cl_half_kg} kg vuodessa.'];
  });
  var fieldsAndNature7 = fieldsAndNature;
  fieldsAndNature = function () {
    var h = fieldsAndNature7(), a = '<p>' + esc(L2(['Use the ranking to choose where farm advisory compares yield per input first.', 'Käytä järjestystä valitessasi, missä viljelyneuvonta vertaa satoa panosta kohden ensin.'])) + '</p>';
    if (h.split(a).length !== 2) throw new Error('v8 anchor missing: nature ranking line');
    return h.replace(a, '<p class="cl8">' + fx(['**Contract clause for lake catchments:** a buffer strip on every contract parcel without one that lies within {n:v3.n8_cl_dmax} m of water in a catchment below good status. That is {n:v3.n8_cl_parcels} parcels on {n:v3.n8_cl_farms} farms, CA12 first: about {n:v3.n8_cl_kg} kg less phosphorus to water a year, {k:v3.n8_cl_pct} of our contract total.',
      '**Sopimuslauseke järvien valuma-alueille:** suojakaista jokaiselle sopimuslohkolle, jolta se puuttuu ja joka on enintään {n:v3.n8_cl_dmax} m:n päässä vedestä hyvää huonommassa tilassa olevalla valuma-alueella. Se koskee {n:v3.n8_cl_parcels} lohkoa {n:v3.n8_cl_farms} tilalla, CA12 ensin: noin {n:v3.n8_cl_kg} kg vähemmän fosforia vesiin vuodessa, {k:v3.n8_cl_pct} sopimuspeltojemme fosforista.']).replace(/\*\*([^*]+)\*\*/, '<b>$1</b>') + '</p>' + a);
  };

  /* ---- 4. no internal paths or development names on screen ---- */
  var SCRUB = [
    [/\ba-final inventory\b/g, 'inventory'],
    [/\btwin\/data\/data\//g, 'data/'],
    [/\btwin\/data\/tasks\/dev\b/g, 'the pack dev set'],
    [/\btwin\/data: /g, 'pack data: '],
    [/\btwin\/data\//g, 'pack/'],
    [/\bum-\d{10}-\d+ twin route\b/g, 'audit route'],
    [/\btwin route\b/g, 'audit route'],
    [/\btwin development keys?\b/g, 'pack development keys'],
    [/\btwin-only\b/g, 'synthetic-only'],
    [/\b[Tt]win\b/g, 'pack'],
    [/\b(?:um|audit)-\d{10}-\d+(?:\/pj-v3)?/g, 'audit'],
    [/\baudit \d{10}-\d+/g, 'audit'],
    [/\ba-finalin\b/g, 'inventaarion'],
    [/\ba-final\b/g, 'inventory'],
    [/\bb-pathin\b/g, 'polkumallin'], [/\bb-path's\b/g, 'the pathways model\'s'], [/\bb-path\b/g, 'pathways'],
    [/\bapp\/trail\b/g, 'the trail'],
    [/\bwork\//g, ''],
    [/\bpj-data\b/g, 'bundle'], [/\bpj-(?:promise|v2)\b/g, 'promise'], [/\bpj-v3\b/g, 'route'], [/\bpj-future\b/g, 'climate'], [/\bpj-rape\b/g, 'rapeseed'],
    [/\bpj-review\d*\b/g, 'checks'], [/\bpj-[A-Za-z0-9][\w\-]*/g, 'pipeline'],
    [/\bar-(?:e)xploit2\b/g, 'mandates'], [/\bar-(?:e)xploit3\b/g, 'whose'], [/\bar-(?:e)xploit\d*\b/g, 'pillars'], [/\bar-(?:c)ontrol-?\w*\b/g, 'second-pipeline'], [/\bar-(?:c)anary\b/g, 'checks']
  ];
  function scrubT(s) { for (var i = 0; i < SCRUB.length; i++) s = s.replace(SCRUB[i][0], SCRUB[i][1]); return s; }
  function scrubH(h) {
    if (typeof h !== 'string') return h;
    return h.replace(/(<[^>]*>)|([^<]+)/g, function (m, tag, text) {
      if (tag) return tag.replace(/\b(title|aria-label)="([^"]*)"/g, function (a, at, t) { return at + '="' + scrubT(t) + '"'; });
      return scrubT(text);
    });
  }
  function scrubbed(f) { return function () { return scrubH(f.apply(this, arguments)); }; }
  renderPage = scrubbed(renderPage);
  view = scrubbed(view);
  pillars = scrubbed(pillars);
  sourceTable = scrubbed(sourceTable);
  mandatesBlock = scrubbed(mandatesBlock);
  leverRow = scrubbed(leverRow);
  if (typeof routeOut === 'function') routeOut = scrubbed(routeOut);
  if (typeof gate === 'function') gate = scrubbed(gate);
  if (typeof routeBlock === 'function') routeBlock = scrubbed(routeBlock);
  if (typeof offerResult === 'function') offerResult = scrubbed(offerResult);
  if (typeof crumbLabel === 'function') crumbLabel = scrubbed(crumbLabel);

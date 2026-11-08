/* Jälki · instrument panel (ui-a, polished as pj-v12, made readable at first sight as pj-v13, named Jälki in pj-v14). An app with five views, one sources drawer, AI drafts a person approves, and a
   signed base that replays. Plain JS, no libraries, no network. Every number is a registry key resolved from
   window.UI.nums (built by python3 ui-a/build.py from the v11 pipeline's data.js and the gap navigator).
   Synthetic pack only: no figure here is Apetit's real emissions. */
(function (G) {
  'use strict';
  var D = G.D, TR = G.TRAIL, U = G.UI, NUM = U.nums, B = D.bundle;
  var LANG = 'fi', VIEW = 'promise', YEAR = '2032', SCEN = 'lo';
  var GAPSEL = 'G03', DECSEL = 'P', REVI = 0, SIGNER = '';
  var CHART = 'bar', OFFER = false, SHOWN = '', HINT = false;   /* promise chart: the gap bar or the waterfall; first-visit offer bar; last view drawn (fade only on a view change) */
  var ASK = {}, GAPST = {}, DEC = {}, REVIEW = {}, REG = [];
  var KEY = 'jälki-a-';
  var VIEWS = ['promise', 'gaps', 'suppliers', 'lakes', 'sign'];

  /* ---------------- copy ---------------- */
  var T = {
    synth: ['Synthetic data · not Apetit\'s emissions', 'Synteettinen data · ei Apetitin päästöjä'],
    brand: ['Base year 2025 · climate and nature', 'Perusvuosi 2025 · ilmasto ja luonto'],
    tour_b: ['90-second tour', '90 sekunnin esittely'],
    t_promise: ['The promise', 'Lupaus'], t_gaps: ['What\'s missing', 'Mitä puuttuu'], t_suppliers: ['Suppliers', 'Toimittajat'],
    t_lakes: ['Farms and lakes', 'Tilat ja järvet'], t_sign: ['Decide and sign', 'Päätä ja allekirjoita'], t_method: ['Method and limits', 'Menetelmä ja rajat'],
    ts_promise: ['Promise', 'Lupaus'], ts_gaps: ['Gaps', 'Puutteet'], ts_suppliers: ['Suppliers', 'Toimit­tajat'], ts_lakes: ['Lakes', 'Järvet'], ts_sign: ['Sign', 'Allekir­joita'],
    foot_tap: ['Tap any number for its source.', 'Napauta mitä tahansa lukua nähdäksesi sen lähteen.'],
    /* v13: one plain sentence per view (what this page tells you, what to do), the first-visit hint, labels that follow the language */
    pl_promise: ['Even the best route found still falls short of the {Y} target (red), so the board picks the target year before signing.',
      'Kaikki suosittelemamme toimet jäävät vuoden {Y} tavoitteesta (punainen), joten tavoitevuosi on päätettävä ennen allekirjoitusta.'],
    pl_gaps: ['This is the data we still lack for the climate and nature standards; start at number 1 and approve or send back each AI suggestion.',
      'Tässä on data, joka meiltä vielä puuttuu ilmasto- ja luontostandardeja varten; aloita kohdasta 1 ja hyväksy tai palauta jokainen tekoälyn ehdotus.'],
    pl_suppliers: ['Suppliers’ own climate figures move more in one year than the cut we ask, so pay for changes measured in the field, not for a lower number on paper.',
      'Toimittajien omat ilmastoluvut heiluvat yhdessä vuodessa enemmän kuin pyytämämme leikkaus, joten maksa pellolla mitatuista muutoksista, älä paperilla pienemmästä luvusta.'],
    pl_lakes: ['The farms that emit most are not the ones that send most nutrients into lakes and rivers, so look at the red area, CA12, first.',
      'Eniten päästävät tilat eivät ole niitä, jotka kuormittavat järviä ja jokia eniten, joten katso ensin punaista aluetta CA12.'],
    pl_sign: ['Go through the eight decisions one by one; signing opens when they and the expert checks are done.',
      'Käy kahdeksan päätöstä läpi yksi kerrallaan; allekirjoitus avautuu, kun ne ja asiantuntijatarkistukset on tehty.'],
    pl_method: ['How every number was made and where its limits are: read this before you rely on a figure.',
      'Miten jokainen luku on laskettu ja missä sen rajat ovat: lue tämä ennen kuin nojaat lukuun.'],
    hint: ['Tap any number to see where it comes from.', 'Napauta mitä tahansa lukua, niin näet, mistä se tulee.'],
    r_gap_hi_k: ['Gap if demand follows net zero 2050', 'Vaje, jos kysyntä seuraa nettonollaa 2050'], r_gap_lo_k: ['Gap if demand follows current policies', 'Vaje, jos kysyntä seuraa nykypolitiikkaa'],
    r_gap_alt_lo: ['{k:gap.{Y}.lo} if demand follows current policies.', '{k:gap.{Y}.lo}, jos kysyntä seuraa nykypolitiikkaa.'],
    a_lang: ['Language', 'Kieli'], a_views: ['Views', 'Näkymät'], a_src: ['Source', 'Lähde'], a_back: ['Back', 'Takaisin'], a_close: ['Close', 'Sulje'],
    a_tour: ['Guided tour', 'Esittely'], a_gloss: ['What does this mean?', 'Mitä tämä tarkoittaa?'], a_map: ['Map of catchments', 'Valuma-aluekartta'],
    /* promise */
    p_kick: ['What are we promising?', 'Mitä lupaamme?'],
    p_h: ['The {Y} promise: {k:price} a year, and still {k:gap.{Y}.{S}} short.', 'Vuoden {Y} lupaus: {k:price} vuodessa, ja silti {k:gap.{Y}.{S}} vajetta.'],
    p_sub: ['On the ground, the catalogue\'s levers cut {k:lev.{Y}.{S}}. The target needs far more.', 'Pellolla luettelon keinot leikkaavat {k:lev.{Y}.{S}}. Tavoite vaatii paljon enemmän.'],
    p_yr: ['Target year', 'Tavoitevuosi'], p_sc: ['Demand', 'Kysyntä'], sc_lo: ['Current policies', 'Nykypolitiikka'], sc_hi: ['Net zero 2050', 'Nettonolla 2050'],
    b_base: ['2025 base', 'Perusvuosi 2025'], b_bau: ['{Y}, nothing done', '{Y} ilman toimia'], b_lev: ['Physical levers', 'Fyysiset keinot'], b_route: ['Left above the target', 'Jää tavoitteen yli'],
    b_tgt: ['{Y} target', 'Tavoite {Y}'], b_gap: ['Gap', 'Vaje'], b_unit: ['t CO₂e, FLAG', 't CO₂e, FLAG'],
    h_need: ['Cut needed by {Y}', 'Tarvittava leikkaus {Y}'], h_del: ['Delivered', 'Toteutuu'], h_lev: ['Physical levers', 'Fyysiset keinot'],
    h_miss: ['Still missing', 'Puuttuu yhä'],
    c_wf: ['Waterfall view', 'Vesiputouskaavio'], c_bar: ['Gap bar', 'Vajepalkki'],
    r_gap: ['Still short in {Y}', 'Vajetta vuonna {Y}'], r_gap_c: ['Up to {k:gap.{Y}.hi} if demand follows net zero 2050.', 'Jopa {k:gap.{Y}.hi}, jos kysyntä seuraa nettonollaa 2050.'],
    r_price: ['Route price', 'Reitin hinta'], r_price_c: ['A year + {k:capex} investment.', 'Vuodessa + {k:capex} investointeja.'],
    r_base: ['Base year', 'Perusvuosi'], r_base_v: ['Past the line', 'Yli rajan'], r_base_c: ['Peat moves it {k:peat.lo_pct}; the line is {k:meter.line}.', 'Turve siirtää sitä {k:peat.lo_pct}; raja on {k:meter.line}.'],
    p_face: ['The catalogue\'s FLAG column ({k:face.cat}) adds up only by counting a data change and a move.', 'Luettelon FLAG-sarake ({k:face.cat}) riittää vain, jos tietomuutos ja siirto lasketaan.'],
    p_rec_k: ['Recommended decision', 'Suositeltu päätös'],
    p_rec: ['Give procurement its own FLAG mandate: a field pilot capped at {k:pilot.cap} a year.', 'Hankinnalle oma FLAG-valtuutus: peltopilotti, katto {k:pilot.cap} vuodessa.'],
    p_rec_go: ['Why suppliers →', 'Miksi toimittajat →'], p_dec_go: ['Decide the target year →', 'Päätä tavoitevuosi →'],
    p_falsk: ['Early check', 'Varhainen testi'],
    p_fals: ['No supplier quotes its floor under the ceiling? The target year goes back to the board.', 'Ei tarjousta alarajalla katon alla? Tavoitevuosi palaa hallitukselle.'],
    /* gaps */
    g_kick: ['Data gaps · SBTi, GHG Protocol, SBTN', 'Datapuutteet · SBTi, GHG Protocol, SBTN'],
    g_h: ['What is missing, and what to do next.', 'Mitä puuttuu ja mitä tehdä seuraavaksi.'],
    g_sub: ['Each tile is a requirement. Tap one.', 'Jokainen ruutu on vaatimus. Napauta ruutua.'],
    st_missing: ['Missing', 'Puuttuu'], st_partial: ['Partial', 'Osittain'], st_have: ['Have', 'On'],
    fw_sbti: ['SBTi FLAG', 'SBTi FLAG'], fw_ghg: ['GHG Protocol', 'GHG Protocol'], fw_sbtn: ['SBTN', 'SBTN'],
    lg_3: ['High: ≥5% of base or blocks signing', 'Suuri: ≥5 % tai estää allekirjoituksen'], lg_2: ['Medium', 'Keskisuuri'], lg_1: ['Low', 'Pieni'],
    g_next: ['Do this next', 'Tee seuraavaksi'], g_next_c: ['Ranked by impact per day of effort.', 'Järjestetty vaikutuksen ja työpäivien suhteen mukaan.'],
    f_req: ['Requirement', 'Vaatimus'], f_have: ['What we have', 'Mitä meillä on'], f_why: ['Why it matters', 'Miksi tärkeää'], f_next: ['Do this next', 'Tee seuraavaksi'],
    f_owner: ['Owner', 'Vastuu'], f_days: ['Effort', 'Työmäärä'], days: ['{d} d', '{d} pv'], f_stake: ['At stake', 'Pelissä'],
    f_src: ['Sources →', 'Lähteet →'], f_dec: ['Decision {d} →', 'Päätös {d} →'], f_lakes: ['Farms and lakes →', 'Tilat ja järvet →'],
    ai: ['AI draft', 'AI-luonnos'], approve: ['Approve', 'Hyväksy'], sendback: ['Send back', 'Palauta'], undo: ['Undo', 'Kumoa'],
    s_ok: ['Approved by a person', 'Ihminen hyväksyi'], s_back: ['Sent back by a person', 'Ihminen palautti'],
    reviewer: ['Expert reviewer (simulated role)', 'Asiantuntija (simuloitu rooli)'],
    rec_line: ['Signed-record entry', 'Allekirjoitetun asiakirjan merkintä'],
    /* suppliers */
    s_kick: ['Whose numbers is the base made of?', 'Kenen luvuista perusvuosi koostuu?'],
    s_h: ['Supplier figures swing more than the cut we ask.', 'Toimittajien luvut heiluvat enemmän kuin pyydetty leikkaus.'],
    s_sub: ['Each bar: one rapeseed supplier\'s own footprint, 2024 → 2025, no programme running.', 'Palkki: yhden rapsitoimittajan oma jalanjälki 2024–2025 ilman ohjelmaa.'],
    s_band: ['Cut asked, year one', 'Pyydetty leikkaus, 1. vuosi'], s_down: ['lower', 'pienempi'], s_up: ['higher', 'suurempi'],
    s_read: ['A lower supplier figure proves nothing. Credit follows nitrogen, yield and area.', 'Pienempi toimittajaluku ei todista mitään. Hyvitys seuraa typpeä, satoa ja alaa.'],
    s_pcap: ['Pilot cap, year one', 'Pilotin katto, 1. vuosi'], s_pk: ['The pilot, year one', 'Pilotti, ensimmäinen vuosi'], s_cap: ['Spending cap', 'Kustannuskatto'], s_floor: ['Delivery floor', 'Toimituksen alaraja'],
    s_ceil: ['Ceiling per verified tonne', 'Katto todennetulta tonnilta'], s_share: ['of bought-seed FLAG', 'ostetun siemenen FLAG:sta'],
    s_who: ['Who writes the factors', 'Kertoimien kirjoittajat'],
    w_library: ['Factor library', 'Kerroinkirjasto'], w_supplier: ['Suppliers', 'Toimittajat'], w_farms: ['Our farms', 'Omat tilat'], w_ops: ['Energy constants', 'Energiavakiot'], w_product: ['Use, end of life', 'Käyttö, elinkaaren loppu'],
    s_rk: ['Contract rapeseed: does higher yield pay?', 'Sopimusrapsi: kannattaako suurempi sato?'],
    s_rtop: ['Highest-yield quarter', 'Paras satoneljännes'], s_rbot: ['Lowest-yield quarter', 'Heikoin satoneljännes'],
    s_rc: ['Nitrogen per tonne harvested. Farms already send yields: {k:rf.resp_pct} for 2025.', 'Typpi korjattua tonnia kohden. Tilat lähettävät jo satonsa: {k:rf.resp_pct} vuodelta 2025.'],
    /* lakes */
    l_kick: ['Nature · eutrophication', 'Luonto · rehevöityminen'],
    l_h: ['Our biggest emitters are not the farms that matter for the lakes.', 'Suurimmat päästäjämme eivät ole järville tärkeät tilat.'],
    l_sub: ['Catchments by water status. Red: assess first.', 'Valuma-alueet vesien tilan mukaan. Punainen: arvioi ensin.'],
    st_good: ['good', 'hyvä'], st_moderate: ['moderate', 'tyydyttävä'], st_poor: ['poor', 'välttävä'], st_bad: ['bad', 'huono'], st_un: ['not ranked', 'ei järjestetty'],
    l_leg: ['Water status', 'Vesien tila'], l_two: ['Farms on both top lists', 'Tiloja molemmilla kärkilistoilla'],
    l_co2: ['{n:nat.top_n} biggest CO₂ farms', '{n:nat.top_n} suurinta CO₂-tilaa'], l_p: ['{n:nat.top_n} biggest phosphorus farms', '{n:nat.top_n} suurinta fosforitilaa'],
    l_ofco2: ['of farm CO₂e', 'tilojen CO₂e:stä'], l_ofp: ['of phosphorus to water', 'vesiin päätyvästä fosforista'],
    l_ca: ['CA12', 'CA12'],
    l_ca_c: ['{n:nat.ca12_p} kg of contract phosphorus a year into a poor-status river: {k:nat.ca12_idx} typical.', '{n:nat.ca12_p} kg sopimusfosforia vuodessa välttävän tilan jokeen: {k:nat.ca12_idx} tyypillinen.'],
    l_cl: ['Buffer-strip clause', 'Suojakaistaehto'],
    l_cl_c: ['{n:cl.parcels} parcels ({k:cl.ha}) send {k:cl.pct} of contract phosphorus: contract a buffer.', '{n:cl.parcels} lohkoa ({k:cl.ha}) tuottaa {k:cl.pct} sopimusfosforista: sovi suojakaista.'],
    l_ask: ['Ask the frameworks', 'Kysy viitekehyksiltä'],
    /* sign */
    d_kick: ['Decide, then sign', 'Päätä, sitten allekirjoita'],
    d_h: ['Eight decisions, each with an owner. Then sign and freeze the base.', 'Kahdeksan päätöstä, kullakin vastuuhenkilö. Sitten perusvuosi allekirjoitetaan ja lukitaan.'],
    c_dec: ['Decisions', 'Päätökset'], c_rev: ['Corrections', 'Korjaukset'], c_ask: ['Framework answers', 'Viitekehysvastaukset'], c_gap: ['Gap actions', 'Puutetoimet'],
    d_q: ['The question', 'Kysymys'], d_t: ['Tonnes', 'Tonnit'], d_e: ['Euros', 'Eurot'], d_n: ['Next week', 'Ensi viikolla'], d_owner: ['Owner', 'Vastuu'],
    recd: ['recommended', 'suositus'], d_done: ['Decided by a person', 'Ihminen päätti'], d_open: ['open', 'avoin'], d_sim: ['(simulated role)', '(simuloitu rooli)'],
    d_asks: ['Framework answers', 'Viitekehysvastaukset'],
    q_k: ['Review queue', 'Tarkistusjono'],
    q_c: ['Corrections of {k:rev.th} or more wait for a person. No bulk accept.', 'Korjaukset ≥ {k:rev.th} odottavat ihmisen päätöstä. Ei massahyväksyntää.'],
    q_old: ['Raw', 'Raaka'], q_new: ['Proposed', 'Ehdotus'], q_eff: ['Effect', 'Vaikutus'], q_rule: ['Rule', 'Sääntö'],
    accept: ['Accept', 'Hyväksy'], reject: ['Reject', 'Hylkää'], prev: ['Previous', 'Edellinen'], nextb: ['Next', 'Seuraava'], q_jump: ['Next open', 'Seuraava avoin'],
    q_acc: ['accepted by a person', 'ihminen hyväksyi'], q_rej: ['rejected by a person', 'ihminen hylkäsi'], q_open: ['needs a person', 'odottaa ihmistä'],
    sg_k: ['Signing', 'Allekirjoitus'],
    sg_c: ['The record keeps each decision, role and time, seals the inputs and replays.', 'Asiakirja tallentaa päätökset, roolit ja ajat, sinetöi lähtötiedot ja toistuu.'],
    signer: ['Signing role', 'Allekirjoittajan rooli'], choose: ['Choose…', 'Valitse…'], sign_b: ['Sign and freeze', 'Allekirjoita ja lukitse'],
    sg_need: ['Opens when all decisions and reviews are done.', 'Avautuu, kun päätökset ja tarkistukset ovat valmiit.'],
    reg_h: ['Signed records', 'Allekirjoitetut asiakirjat'], reg_empty: ['None yet.', 'Ei vielä yhtään.'],
    approver: ['Second role approves', 'Toinen rooli hyväksyy'], appr_b: ['Approve record', 'Hyväksy asiakirja'], open: ['Replay', 'Toista'], dl: ['Download', 'Lataa'],
    load: ['Load a record file', 'Lataa asiakirjatiedosto'], st_draft: ['Awaiting second approval', 'Odottaa toista hyväksyntää'], st_app: ['Approved', 'Hyväksytty'],
    load_bad: ['Refused: the file does not match its own hash.', 'Hylätty: tiedosto ei vastaa omaa tiivistettään.'], load_notrec: ['Refused: not a Jälki record.', 'Hylätty: ei Jälki-asiakirja.'],
    load_ok: ['Loaded. Replay below.', 'Ladattu. Toisto alla.'],
    /* drawer */
    dr_src: ['Source', 'Lähde'], dr_script: ['Script', 'Skripti'], dr_prov: ['Provenance', 'Alkuperä'], dr_how: ['How', 'Miten'], dr_parts: ['Made from', 'Koostuu'],
    dr_recs: ['Records', 'Tietueet'], dr_exact: ['Exact value', 'Tarkka arvo'], dr_rounded: ['shown rounded to 100 t', 'näytetään sadan tonnin tarkkuudella'],
    dr_loading: ['Loading records…', 'Ladataan tietueita…'], dr_all: ['All records', 'Kaikki tietueet'], dr_parties: ['Farms and suppliers', 'Tilat ja toimittajat'],
    dr_rec: ['Record', 'Tietue'], dr_rawclean: ['Raw → clean', 'Raaka → puhdistettu'], dr_factor: ['Factor', 'Kerroin'], dr_corr: ['Correction', 'Korjaus'],
    dr_cites: ['Sources, phrases checked', 'Lähteet, lauseet tarkistettu'],
    dr_rank: ['Ranking', 'Järjestys'], dr_quote: ['Quoted passages', 'Lainatut kohdat'], dr_full: ['Full answer', 'Koko vastaus'],
    k_data: ['data', 'data'], k_derivation: ['derivation', 'johdettu'], k_assumption: ['assumption', 'oletus'], k_cut: ['not shown', 'ei näytetä'], k_none: ['computed', 'laskettu'],
    dr_route: ['Recommended route by lever', 'Suositeltu reitti keinoittain'], dr_routego: ['Levers in the route →', 'Reitin keinot →'],
    rp_int: ['Record unchanged (hash)', 'Asiakirja muuttumaton (tiiviste)'], rp_inp: ['Input files sealed', 'Lähtötiedostot sinetöity'], rp_fac: ['Factor register sealed', 'Kerroinrekisteri sinetöity'],
    rp_code: ['Pipeline code seal', 'Laskentaketjun koodisinetti'], rp_base: ['Base rebuilt from the lines', 'Perusvuosi koottu riveistä'], rp_fig: ['Every frozen figure equals this build', 'Jokainen lukittu luku vastaa tätä versiota'],
    rp_ask: ['Framework-answer states carried', 'Viitekehysvastausten tilat mukana'], rp_pass: ['pass', 'ok'], rp_fail: ['fail', 'virhe'],
    rp_test: ['Change one factor by 1% and re-seal', 'Muuta yhtä kerrointa 1 % ja sinetöi uudelleen'], rp_broke: ['Seal breaks: a changed factor cannot pass as delivery.', 'Sinetti murtuu: muutettu kerroin ei mene toimituksesta.'],
    /* method */
    m_h: ['Method and limits', 'Menetelmä ja rajat'],
    m1: ['Data: the organisers\' synthetic pack in Apetit\'s schema, not Apetit\'s emissions.', 'Data: järjestäjien synteettinen paketti Apetitin rakenteessa, ei Apetitin päästöjä.'],
    m2: ['Inventory: rebuilt from raw feeds; a second pipeline matches Scope 1, 2 and category 1.', 'Inventaario: koottu raakasyötteistä; toinen ketju täsmää: Scope 1, 2 ja luokka 1.'],
    m3: ['Trail: every number opens its script, pack files and records.', 'Jälki: jokainen luku avaa skriptinsä, pakettitiedostonsa ja tietueensa.'],
    m4: ['AI: drafts answers and gap actions from the framework texts; quotes checked.', 'AI: luonnostelee vastaukset ja toimet viitekehysteksteistä; lainaukset tarkistetaan.'],
    m5: ['People decide: each draft and decision carries a role and time. Roles are simulated.', 'Ihmiset päättävät: jokaisella päätöksellä on rooli ja aika. Roolit ovat simuloituja.'],
    m6: ['Fit: static files for IT, Power BI or a Teams tab; Fabric; Azure AI Foundry.', 'Sopivuus: staattiset tiedostot IT:lle, Power BI tai Teams; Fabric; Azure AI Foundry.'],
    m_lim: ['Limits', 'Rajat'],
    l1: ['Peat rests on the soil map: {n:probe.n} field probes settle it before signing.', 'Turve nojaa maaperäkarttaan: {n:probe.n} kairausta ratkaisee sen ennen allekirjoitusta.'],
    l2: ['No supplier offer exists yet: the pilot\'s floor is the first test.', 'Toimittajatarjousta ei vielä ole: pilotin alaraja on ensimmäinen testi.'],
    l3: ['Lever costs are catalogue design estimates, not quotes.', 'Keinojen kustannukset ovat luettelon suunnitteluarvioita, eivät tarjouksia.'],
    /* tour */
    to_offer: ['First time here?', 'Ensimmäistä kertaa täällä?'], to_offer_c: ['Five views, 90 seconds.', 'Viisi näkymää, 90 sekuntia.'],
    to_start: ['Start the tour', 'Aloita esittely'], to_no: ['Not now', 'Ei nyt'], to_back: ['Back', 'Takaisin'], to_next: ['Next', 'Seuraava'], to_done: ['Done', 'Valmis'], to_close: ['Close tour', 'Sulje esittely']
  };
  /* jargon, glossed once per view where it first appears: a short line on tap, hover or focus */
  var GLOSS = {
    flag: { re: /\bFLAG\b/, t: ['FLAG (Forest, Land and Agriculture): emissions from the land itself – fields, fertiliser on the field, drained peat, land-use change. Food companies set a separate target for them.',
      'FLAG (Forest, Land and Agriculture): maasta itsestään syntyvät päästöt – pellot, lannoitteen päästöt pellolla, ojitettu turve, maankäytön muutos. Elintarvikeyritys asettaa niille oman tavoitteen.'] },
    sbti: { re: /\bSBTi\b/, t: ['SBTi (Science Based Targets initiative) checks that a climate target follows the science. Under its new standard (V2) the target year here is 2032; under the older V1.3.1, usable until the end of 2027, it is 2035.',
      'SBTi (Science Based Targets initiative) tarkistaa, että ilmastotavoite on tieteen mukainen. Sen uudessa standardissa (V2) tavoitevuosi on tässä 2032; vanhemmassa V1.3.1:ssä, jota voi käyttää vuoden 2027 loppuun, se on 2035.'] },
    sbtn: { re: /\bSBTN\b/, t: ['SBTN (Science Based Targets Network): the same idea as SBTi, for nature – targets for water, land and biodiversity.',
      'SBTN (Science Based Targets Network): sama ajatus kuin SBTi:ssä, mutta luonnolle – tavoitteet vesille, maalle ja monimuotoisuudelle.'] },
    ghg: { re: /\bGHG Protocol\b/, t: ['GHG Protocol: the common rulebook for counting a company’s greenhouse gas emissions.', 'GHG Protocol: yhteinen sääntökirja yrityksen kasvihuonekaasupäästöjen laskemiseen.'] },
    pcf: { re: /\bPCF/, t: ['PCF (product carbon footprint): a supplier’s own figure for the emissions of one product.', 'PCF (tuotteen hiilijalanjälki): toimittajan oma luku yhden tuotteen päästöistä.'] },
    base: { re: /\b[Bb]ase year\b|\b[Pp]erusvuo[a-zäö]*/, t: ['Base year: the year (here 2025) that every later cut is measured against. If the company or the method changes enough, it is recalculated.',
      'Perusvuosi: vuosi (tässä 2025), johon jokaista myöhempää vähennystä verrataan. Jos yritys tai laskentatapa muuttuu riittävästi, se lasketaan uudelleen.'] },
    scope: { re: /\bScope [123]\b/, t: ['Scope 1: our own fuels. Scope 2: the energy we buy. Scope 3: the value chain we do not own – farms, suppliers, transport, use of our products.',
      'Scope 1: omat polttoaineet. Scope 2: ostettu energia. Scope 3: arvoketju, jota emme omista – tilat, toimittajat, kuljetukset, tuotteiden käyttö.'] }
  };
  var GORDER = ['flag', 'sbti', 'sbtn', 'ghg', 'pcf', 'base', 'scope'];
  var STEPS = [
    { v: 'promise', sel: '#chart', t: ['The promise at a glance', 'Lupaus yhdellä silmäyksellä'], x: ['The bar is the cut the 2032 target needs. Black is what the levers deliver; red is the gap still missing. Then the price of the route.', 'Palkki on vuoden 2032 tavoitteen vaatima leikkaus. Musta on keinojen vaikutus, punainen puuttuva vaje. Sitten reitin hinta.'] },
    { v: 'promise', sel: '#chart .seg-gap', open: 'gap.2032.lo', t: ['Every number has a source', 'Jokaisella luvulla on lähde'], x: ['Tap any number or bar. The drawer shows how it is made, the script, and the pack records under it.', 'Napauta mitä tahansa lukua tai palkkia. Laatikko näyttää laskutavan, skriptin ja paketin tietueet.'] },
    { v: 'gaps', sel: '#matrix', t: ['What is missing', 'Mitä puuttuu'], x: ['Every SBTi FLAG, GHG Protocol and SBTN requirement by status. Dark tiles carry the most impact.', 'Jokainen SBTi FLAG-, GHG Protocol- ja SBTN-vaatimus tilan mukaan. Tummat ruudut painavat eniten.'] },
    { v: 'gaps', sel: '#gd', approve: 'G03', t: ['AI drafts, a person decides', 'AI luonnostelee, ihminen päättää'], x: ['The first action is an AI draft. Press Approve to decide as the expert reviewer.', 'Ensimmäinen toimi on AI-luonnos. Paina Hyväksy ja päätä asiantuntijana.'] },
    { v: 'gaps', sel: '#gd .stamp', only: 'G03', t: ['Approved: by whom, when, on the record', 'Hyväksytty: kuka, milloin, asiakirjaan'], x: ['The stamp shows the role and the time. Under it, the entry the signed record will carry.', 'Leima näyttää roolin ja ajan. Sen alla merkintä, jonka allekirjoitettu asiakirja sisältää.'] },
    { v: 'suppliers', sel: '#swing', t: ['Pay for field tonnes', 'Maksa peltotonneista'], x: ['Suppliers\' own figures move more in a year than the cut we ask. A lower figure proves nothing.', 'Toimittajien omat luvut liikkuvat vuodessa enemmän kuin pyydetty leikkaus. Pienempi luku ei todista mitään.'] },
    { v: 'lakes', sel: '#lakes-main', t: ['Two different lists', 'Kaksi eri listaa'], x: ['The farms that emit most are not the farms that feed the lakes. Assess CA12 first.', 'Eniten päästävät tilat eivät ole järviä kuormittavat tilat. Arvioi ensin CA12.'] },
    { v: 'sign', sel: '#decs', t: ['Decide and sign', 'Päätä ja allekirjoita'], x: ['Eight decisions with owners. When they and the review queue are done, sign: the base freezes and replays.', 'Kahdeksan päätöstä vastuineen. Kun ne ja tarkistusjono ovat valmiit, allekirjoita: perusvuosi lukittuu ja toistuu.'] }
  ];

  /* ---------------- helpers ---------------- */
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function L2(a) { return a ? a[LANG === 'en' ? 0 : 1] : ''; }
  function canon(o) {
    if (o === null || typeof o !== 'object') return JSON.stringify(o);
    if (Array.isArray(o)) return '[' + o.map(canon).join(',') + ']';
    return '{' + Object.keys(o).sort().map(function (k) { return JSON.stringify(k) + ':' + canon(o[k]); }).join(',') + '}';
  }
  var KK = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }
  function sha256(str) {
    var m = new TextEncoder().encode(str), l = m.length, n = ((l + 9 + 63) >> 6) << 6;
    var buf = new Uint8Array(n); buf.set(m); buf[l] = 0x80;
    var dv = new DataView(buf.buffer), bits = l * 8;
    dv.setUint32(n - 4, bits >>> 0); dv.setUint32(n - 8, Math.floor(bits / 4294967296));
    var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19], w = new Uint32Array(64);
    for (var i = 0; i < n; i += 64) {
      for (var t = 0; t < 16; t++) w[t] = dv.getUint32(i + t * 4);
      for (t = 16; t < 64; t++) { var x = w[t - 15], y = w[t - 2]; w[t] = (w[t - 16] + (rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3)) + w[t - 7] + (rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10))) >>> 0; }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (t = 0; t < 64; t++) {
        var t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + KK[t] + w[t]) >>> 0;
        var t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      H = [(H[0] + a) >>> 0, (H[1] + b) >>> 0, (H[2] + c) >>> 0, (H[3] + d) >>> 0, (H[4] + e) >>> 0, (H[5] + f) >>> 0, (H[6] + g) >>> 0, (H[7] + h) >>> 0];
    }
    return H.map(function (v) { return ('00000000' + v.toString(16)).slice(-8); }).join('');
  }
  function store(k, v) { try { G.localStorage.setItem(KEY + k, JSON.stringify(v)); } catch (e) { /* memory only */ } }
  function load(k, d) { try { var v = JSON.parse(G.localStorage.getItem(KEY + k)); return v == null ? d : v; } catch (e) { return d; } }

  /* ---------------- numbers ---------------- */
  function fnum(v, dp, sg) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    var s = Math.abs(v).toFixed(dp), p = s.split('.'), ip = p[0], fp = p[1];
    ip = ip.replace(/\B(?=(\d{3})+(?!\d))/g, LANG === 'en' ? ',' : ' ');
    var out = ip + (fp ? (LANG === 'en' ? '.' : ',') + fp : ''), zero = /^[0.]+$/.test(s);
    if (v < 0 && !zero) out = '−' + out; else if (sg && v > 0 && !zero) out = '+' + out;
    return out;
  }
  function wrapU(u, s) {
    var en = LANG === 'en';
    switch (u) {
      case 't': return s + ' t';
      case 'pct': return s + (en ? '%' : ' %');
      case 'ha': return s + ' ha';
      case 'kg': return s + ' kg';
      case 'm': return s + ' m';
      case 'x': return s + '×';
      case 'kgnt': return s + ' kg N/t';
      case 'tha': return s + ' t/ha';
      case 'eur': case 'keur': case 'meur':
        var suf = u === 'keur' ? (en ? 'k' : ' t€') : u === 'meur' ? (en ? 'M' : ' milj. €') : (en ? '' : ' €');
        if (en) { var neg = s.charAt(0) === '−'; return (neg ? '−' : '') + '€' + (neg ? s.slice(1) : s) + suf; }
        return s + suf;
      default: return s;
    }
  }
  function nv(k) { var n = NUM[k]; if (!n) throw new Error('unknown number ' + k); return n.v; }
  function scaled(n, v) { return n.u === 'keur' ? v / 1e3 : n.u === 'meur' ? v / 1e6 : v; }
  function fk(k, bare, sg) { var n = NUM[k]; if (!n) throw new Error('unknown number ' + k); var s = fnum(scaled(n, n.v), n.dp, sg); return bare ? s : wrapU(n.u, s); }
  function K(k, bare, sg, cls) { return '<button type="button" class="n' + (cls ? ' ' + cls : '') + '" data-k="' + k + '">' + esc(fk(k, bare, sg)) + '</button>'; }
  function fill(s) {
    return s.replace(/\{Y\}/g, YEAR).replace(/\{S\}/g, SCEN).replace(/\{([knr]):([^}]+)\}/g, function (m, t, a) {
      if (t === 'k') return K(a);
      if (t === 'n') return K(a, true);
      var ab = a.split(','); return wrapU(NUM[ab[0]].u, K(ab[0], true) + '–' + K(ab[1], true));
    });
  }
  function tx(id, rep) { if (!T[id]) throw new Error('unknown text ' + id); var s = esc(L2(T[id])); if (rep) Object.keys(rep).forEach(function (k) { s = s.split('{' + k + '}').join(rep[k]); }); return fill(s); }
  function fx(pair) { return fill(esc(L2(pair))); }
  function plain(pair) { return L2(pair).replace(/\{Y\}/g, YEAR).replace(/\{S\}/g, SCEN).replace(/\{([knr]):([^}]+)\}/g, function (m, t, a) { if (t === 'r') { var ab = a.split(','); return wrapU(NUM[ab[0]].u, fk(ab[0], true) + '–' + fk(ab[1], true)); } return fk(a, t === 'n'); }); }

  /* ---------------- shell ---------------- */
  function shell() {
    var h = '<header class="top"><div class="brand"><span class="logo">JÄLKI</span><span class="mono dim">' + tx('brand') + '</span></div>' +
      '<div class="tools"><span class="synth mono">' + tx('synth') + '</span>' +
      '<button type="button" class="tb-tour" data-a="tour" aria-label="' + esc(L2(T.tour_b)) + '">▶ <span class="tl">' + tx('tour_b') + '</span><span class="ts">90 s</span></button>' +
      '<span class="lang" role="group" aria-label="' + esc(L2(T.a_lang)) + '"><button type="button" data-lang="fi" lang="fi" aria-label="Suomi" aria-pressed="' + (LANG === 'fi') + '">FI</button><button type="button" data-lang="en" lang="en" aria-label="English" aria-pressed="' + (LANG === 'en') + '">EN</button></span></div></header>';
    h += '<nav class="tabs" role="tablist" aria-label="' + esc(L2(T.a_views)) + '">' + VIEWS.map(function (v, i) {
      var on = VIEW === v;
      return '<button type="button" role="tab" id="tab-' + v + '" aria-selected="' + on + '" aria-controls="view" tabindex="' + (on ? 0 : -1) + '" data-view="' + v + '"><span class="ti mono">0' + (i + 1) + '</span><span class="tl">' + tx('t_' + v) + '</span><span class="ts">' + tx('ts_' + v) + '</span>' + badge(v) + '</button>';
    }).join('') + '</nav>';
    /* first visit: a slim bar in the page flow, so it pushes content down and covers nothing */
    if (OFFER) h += '<div class="offer" id="offer" role="region" aria-label="' + esc(L2(T.to_offer)) + '"><p><b>' + tx('to_offer') + '</b> <span>' + tx('to_offer_c') + '</span></p>' +
      '<div class="ob"><button type="button" class="btn red" data-t="start">▶ ' + tx('to_start') + '</button><button type="button" class="btn ghost" data-t="no">' + tx('to_no') + '</button></div></div>';
    /* v13: no fade on a view change; the content is there at full strength on the first frame */
    h += '<main id="view" role="tabpanel" tabindex="-1" aria-labelledby="tab-' + VIEW + '" class="v-' + VIEW + '">' + renderView() + '</main>';
    SHOWN = VIEW;
    h += '<footer class="foot"><span class="mono">' + tx('foot_tap') + '</span><button type="button" class="lk" data-view="method">' + tx('t_method') + ' →</button><span class="mono dim">' + tx('synth') + '</span></footer>';
    return h;
  }
  function badge(v) {
    var n = 0, of = 0;
    if (v === 'gaps') { of = U.gaps.length; n = U.gaps.filter(function (g) { return GAPST[g.id]; }).length; return '<span class="bd mono" aria-hidden="true">' + n + '/' + of + '</span>'; }
    if (v === 'sign') { of = DECS.length; n = DECS.filter(function (d) { return DEC[d.id]; }).length; return '<span class="bd mono" aria-hidden="true">' + n + '/' + of + '</span>'; }
    return '';
  }
  function renderView() {
    if (VIEW === 'promise') return vPromise();
    if (VIEW === 'gaps') return vGaps();
    if (VIEW === 'suppliers') return vSuppliers();
    if (VIEW === 'lakes') return vLakes();
    if (VIEW === 'sign') return vSign();
    return vMethod();
  }
  /* the view head: a tool title, then the one plain sentence (what this page tells you, what to do), then an optional chart caption */
  function head(kick, h, sub) { return '<div class="vh">' + (kick ? '<p class="kick mono">' + kick + '</p>' : '') + '<h1>' + h + '</h1><p class="plain">' + tx('pl_' + VIEW) + '</p>' + (sub ? '<p class="sub">' + sub + '</p>' : '') + '</div>'; }
  function seg(name, opts, cur) {
    var lab = name === 'p_yr' ? '<button type="button" class="seg-l mono gt" data-g="sbti" aria-describedby="tip">' + tx(name) + '</button>' : '<span class="seg-l mono">' + tx(name) + '</span>';
    return '<div class="seg" role="group" aria-label="' + esc(L2(T[name])) + '">' + lab + opts.map(function (o) {
      return '<button type="button" data-' + (name === 'p_yr' ? 'year' : 'scen') + '="' + o[0] + '" aria-pressed="' + (cur === o[0]) + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  /* ---------------- 01 the promise ---------------- */
  function vPromise() {
    var Y = YEAR, S = SCEN;
    var base = NUM['base.flag'].x, bau = NUM['bau.' + Y + '.' + S].x, tgt = NUM['tgt.' + Y].x, gap = NUM['gap.' + Y + '.' + S].x, lev = NUM['lev.' + Y + '.' + S].x;
    var top = Math.max(base, NUM['bau.2035.hi'].x) * 1.06, pc = function (v) { return (100 * v / top).toFixed(2) + '%'; };
    var h = head(tx('p_kick'), tx('p_h'), '');   /* v13: p_sub dropped, its figure (levers deliver) is the hero legend's */
    h += '<div class="ctl">' + seg('p_yr', [['2032', '2032 · SBTi V2'], ['2035', '2035 · V1.3.1']], Y) + seg('p_sc', [['lo', tx('sc_lo')], ['hi', tx('sc_hi')]], S) + '</div>';
    h += '<section class="panel chartp" id="chart" aria-label="' + esc(plain(T.p_h)) + '"><div class="cgrid c-' + CHART + '">';
    var kY = Y + '.' + S, aria = function (k) { return ' data-k="' + k + '" aria-label="' + esc(plain([NUM[k].lab[0] + ' {k:' + k + '}', NUM[k].lab[1] + ' {k:' + k + '}'])) + '"'; };
    if (CHART === 'bar') {
      /* the hero: one bar for the cut the target needs, split into what the levers deliver and the gap still missing */
      var need = NUM['need.' + kY].x, w = function (v) { return (100 * v / need).toFixed(2) + '%'; };
      h += '<div class="hero"><div class="hrow"><span class="mono hl">' + tx('h_need', { Y: Y }) + '</span><span class="hv">' + K('need.' + kY) + '</span></div>' +
        '<button type="button" class="hneed" data-eq="1"' + aria('need.' + kY) + '></button>' +
        '<div class="hbar"><button type="button" class="hlev" data-eq="1" style="width:' + w(lev) + '"' + aria('lev.' + kY) + '><span class="mono">' + tx('h_del') + '</span></button>' +
        '<button type="button" class="seg-gap"' + aria('gap.' + kY) + ' style="width:' + w(gap) + '"><span class="hg-v take">' + tx('b_gap') + ': ' + esc(fk('gap.' + kY)) + '</span></button></div>' +
        '<div class="hleg"><span><i class="sw sw3"></i>' + tx('h_lev') + ' ' + K('lev.' + kY) + '</span><span class="mono dim">' + tx('b_tgt', { Y: Y }) + ' ' + K('tgt.' + Y) + ' · ' + tx('b_unit') + '</span></div></div>';
      h += '<div class="price"><p class="mono kick">' + tx('r_price') + '</p><p class="big">' + K('price') + '</p><p class="cap">' + tx('r_price_c') + '</p></div></div>';
      h += '<p class="axis mono">' + (HINT ? '<span class="hint" id="hint">' + tx('hint') + '</span>' : '') + '<button type="button" class="lk" data-chart="wf" aria-pressed="false">' + tx('c_wf') + ' →</button></p></section>';
      return h + promiseBelow(Y);
    }
    h += '<div class="bars">';
    h += '<div class="tline" style="top:calc(var(--ch) * ' + (1 - tgt / top).toFixed(4) + ' + var(--pt))"><span class="mono">' + tx('b_tgt', { Y: Y }) + ' ' + K('tgt.' + Y) + '</span></div>';
    var bar = function (cls, label, inner, valk) { return '<div class="col ' + cls + '"><div class="stack">' + inner + '</div><div class="cl mono">' + label + '</div><div class="cv">' + (valk ? K(valk) : '') + '</div></div>'; };
    /* v13: every bar's accessible name carries its figure, in the page language */
    h += bar('c-base', tx('b_base'), '<button type="button" class="seg-b" data-eq="1"' + aria('base.flag') + ' style="height:' + pc(base) + '"></button>', 'base.flag');
    h += bar('c-bau', tx('b_bau', { Y: Y }), '<button type="button" class="seg-b" data-eq="1"' + aria('bau.' + Y + '.' + S) + ' style="height:' + pc(bau) + '"></button>', 'bau.' + Y + '.' + S);
    h += bar('c-lev', tx('b_lev'), '<button type="button" class="seg-lev" data-eq="1"' + aria('lev.' + Y + '.' + S) + ' style="bottom:' + pc(bau - lev) + ';height:' + pc(lev) + '"></button>' +
      '<button type="button" class="levtag mono n" data-k="lev.' + Y + '.' + S + '" style="bottom:calc(' + pc(bau) + ' + 6px)">−' + esc(fk('lev.' + Y + '.' + S)) + '</button>', null);
    h += '<div class="col c-route"><div class="stack"><button type="button" class="seg-b seg-in" data-eq="1"' + aria('tgt.' + Y) + ' style="height:' + pc(tgt) + '"></button>' +
      '<button type="button" class="seg-gap" data-eq="1"' + aria('gap.' + Y + '.' + S) + ' style="bottom:' + pc(tgt) + ';height:' + pc(gap) + '"></button></div>' +
      '<div class="cl mono">' + tx('b_route', { Y: Y }) + '</div><div class="cv red take">' + tx('b_gap') + ': ' + K('gap.' + Y + '.' + S) + '</div></div>';
    h += '</div><div class="price"><p class="mono kick">' + tx('r_price') + '</p><p class="big">' + K('price') + '</p><p class="cap">' + tx('r_price_c') + '</p></div></div>';
    h += '<p class="axis mono"><span>' + tx('b_unit') + '</span><button type="button" class="lk" data-chart="bar" aria-pressed="true">← ' + tx('c_bar') + '</button></p></section>';
    return h + promiseBelow(Y);
  }
  function promiseBelow(Y) {
    var h = '<div class="readouts">' +
      '<div class="ro ro-red alt-sc"><p class="mono kick">' + tx(SCEN === 'lo' ? 'r_gap_hi_k' : 'r_gap_lo_k') + '</p><p class="big">' + K('gap.' + Y + '.' + (SCEN === 'lo' ? 'hi' : 'lo')) + '</p></div>' +
      '<div class="ro"><p class="mono kick">' + tx('r_base') + '</p><p class="big">' + tx('r_base_v') + '</p><p class="cap">' + tx('r_base_c') + '</p></div>' +
      '<div class="ro ro-dark"><p class="mono kick">' + tx('p_rec_k') + '</p><p class="cap strong">' + tx('p_rec') + '</p><p class="go"><button type="button" class="lk inv" data-view="suppliers">' + tx('p_rec_go') + '</button></p></div></div>';
    h += '<div class="notes">' + (CHART === 'wf' ? '<p class="note">' + tx('p_face') + '</p>' : '') + '<p class="note"><span class="mono kick">' + tx('p_falsk') + '</span> ' + tx('p_fals') + '</p><p class="note"><button type="button" class="lk" data-view="sign" data-dsel="P">' + tx('p_dec_go') + '</button></p></div>';
    return h;
  }

  /* ---------------- 02 what's missing ---------------- */
  var FW = [['SBTi FLAG', 'fw_sbti'], ['GHG Protocol', 'fw_ghg'], ['SBTN', 'fw_sbtn']], STS = ['missing', 'partial', 'have'];
  function gapById(id) { return U.gaps.filter(function (g) { return g.id === id; })[0]; }
  function vGaps() {
    var gs = U.gaps, cnt = {}; STS.forEach(function (s) { cnt[s] = gs.filter(function (g) { return g.status === s; }).length; });
    var h = head(tx('g_kick'), tx('g_h'), tx('g_sub'));
    h += '<p class="strip take">' + STS.map(function (s) { return '<span class="sb sb-' + s + '" style="flex:' + cnt[s] + '"><b>' + cnt[s] + '</b> ' + tx('st_' + s) + '</span>'; }).join('') + '</p>';
    h += '<div class="gl"><div class="gleft"><section class="panel" id="matrix" aria-label="' + esc(L2(T.g_h)) + '"><div class="mx">';
    h += '<div class="mx-c mx-h"></div>' + STS.map(function (s) { return '<div class="mx-c mx-h mono h-' + s + '">' + tx('st_' + s) + '</div>'; }).join('');
    FW.forEach(function (f) {
      h += '<div class="mx-c mx-r mono">' + tx(f[1]) + '</div>';
      STS.forEach(function (s) {
        h += '<div class="mx-c mx-cell s-' + s + '" data-stl="' + esc(L2(T['st_' + s])) + '">' + gs.filter(function (g) { return g.fw === f[0] && g.status === s; }).sort(function (a, b) { return a.rank - b.rank; }).map(tile).join('') + '</div>';
      });
    });
    h += '</div><p class="legend mono">' + [3, 2, 1].map(function (i) { return '<span class="lgi"><i class="sw sw' + i + '"></i>' + tx('lg_' + i) + '</span>'; }).join('') + '</p></section>';
    h += '<section class="panel" id="next"><p class="mono kick">' + tx('g_next') + '</p><p class="cap">' + tx('g_next_c') + '</p><ol class="nx">' +
      gs.slice().sort(function (a, b) { return a.rank - b.rank; }).slice(0, 5).map(function (g) {
        var st = GAPST[g.id];
        return '<li class="' + (GAPSEL === g.id ? 'on' : '') + '"><button type="button" class="nx-b" data-gap="' + g.id + '" title="' + esc(glossTitle(L2(g.short))) + '"><span class="nx-r">' + g.rank + '</span><span class="nx-t"><b>' + fx(g.short) + '</b></span><span class="nx-s mono ' + (st ? 'ok-' + st.s : '') + '">' + (st ? (st.s === 'approved' ? '✓' : '↩') : tx('ai')) + '</span></button></li>';
      }).join('') + '</ol></section></div>';
    h += '<div class="gright">' + gapDetail(gapById(GAPSEL)) + '</div></div>';
    return h;
  }
  function tile(g) {
    var on = g.id === GAPSEL, st = GAPST[g.id];
    return '<button type="button" class="tile t' + g.cls + ' s-' + g.status + (on ? ' on' : '') + '" data-gap="' + g.id + '" aria-pressed="' + on + '" title="' + esc(glossTitle(L2(g.short))) + '"><span class="tr mono">' + g.rank + '</span>' + (st ? '<span class="tid mono">' + (st.s === 'approved' ? '✓' : '↩') + '</span>' : '') + '<span class="tn">' + shy(esc(L2(g.short))) + '</span></button>';
  }
  /* a term inside a tile (a button cannot hold another button) is glossed in the tile's hover title instead */
  function glossTitle(s) { var out = [s]; GORDER.forEach(function (g) { if (GLOSS[g].re.test(s)) out.push(L2(GLOSS[g].t)); }); return out.join(' — '); }
  /* soft hyphens at Finnish compound joints, so narrow tiles break words where a reader expects, never mid-syllable */
  var SHY = [['uudelleenlaskentasääntö', 'uudelleen­laskenta­sääntö'], ['asiantuntijahyväksyntä', 'asiantuntija­hyväksyntä'], ['olennaisuusseulonta', 'olennaisuus­seulonta'],
    ['Tavoitestandardi', 'Tavoite­standardi'], ['viljelijätiedot', 'viljelijä­tiedot'], ['rapsisuunnitelman', 'rapsi­suunnitelman'], ['Turvemenetelmä', 'Turve­menetelmä'],
    ['peltohjelma', 'pelt­ohjelma'],['perusvuoteen', 'perus­vuoteen'], ['perusvuosi', 'perus­vuosi'], ['FLAG-inventaariossa', 'FLAG-inventaa­riossa']];
  function shy(s) { if (LANG !== 'fi') return s; SHY.forEach(function (p) { s = s.split(p[0]).join(p[1]); }); return s; }
  function stamp(st, line) {
    return '<div class="stamp stamp-' + (st.s === 'approved' ? 'ok' : 'back') + '" role="status"><span class="si" aria-hidden="true">' + (st.s === 'approved' ? '✓' : '↩') + '</span><div><p><b>' + tx(st.s === 'approved' ? 's_ok' : 's_back') + '</b></p><p class="mono">' + tx('reviewer') + ' · ' + esc(st.at.slice(0, 16).replace('T', ' ')) + '</p>' +
      '<p class="recl"><span class="mono kick">' + tx('rec_line') + '</span><span class="mono">' + esc(line) + '</span></p></div></div>';
  }
  function gapRec(g) { var s = GAPST[g.id]; return { id: g.id, framework: g.fw, action: g.short[0], state: s ? s.s : 'draft', at: s ? s.at : null, reviewer: 'Expert reviewer (simulated)' }; }
  function gapLine(g) { var r = gapRec(g); return 'gap_actions · ' + r.id + ' · ' + r.state + ' · ' + r.reviewer + ' · ' + r.at; }
  function gapDetail(g) {
    var st = GAPST[g.id];
    var h = '<section class="panel gd" id="gd" aria-live="polite"><div class="gd-h"><span class="gd-rank">' + g.rank + '</span><div><p class="mono kick">' + esc(g.id) + ' · ' + esc(g.fw) + ' · <span class="h-' + g.status + '">' + tx('st_' + g.status) + '</span></p><h2>' + fx(g.short) + '</h2></div></div>';
    if (g.stake) h += '<p class="stake"><span class="mono kick">' + tx('f_stake') + '</span> <span class="big2">' + K(g.stake) + '</span></p>';
    h += '<dl class="fields">' +
      '<dt class="mono">' + tx('f_req') + '</dt><dd>' + fx(g.req) + '</dd>' +
      '<dt class="mono">' + tx('f_have') + '</dt><dd>' + fx(g.have) + '</dd>' +
      '<dt class="mono">' + tx('f_why') + '</dt><dd>' + fx(g.why) + '</dd>' +
      '<dt class="mono red">' + tx('f_next') + '</dt><dd class="strong">' + fx(g.next) + '</dd>' +
      '<dt class="mono">' + tx('f_owner') + '</dt><dd>' + esc(L2(g.owner)) + ' · ' + tx('days', { d: fnum(g.days, g.days % 1 ? 1 : 0) }) + '</dd></dl>';
    h += '<div class="ai-row"><span class="aib mono">' + tx('ai') + '</span>';
    h += st ? '<button type="button" class="btn ghost" data-gapst="' + g.id + '~undo">' + tx('undo') + '</button>'
      : '<button type="button" class="btn primary" data-gapst="' + g.id + '~approved">' + tx('approve') + '</button><button type="button" class="btn" data-gapst="' + g.id + '~sent_back">' + tx('sendback') + '</button>';
    h += '</div>' + (st ? stamp(st, gapLine(g)) : '');
    h += '<p class="links"><button type="button" class="lk" data-v="gap~' + g.id + '">' + tx('f_src') + '</button>';
    if (g.link === 'lakes') h += ' <button type="button" class="lk" data-view="lakes">' + tx('f_lakes') + '</button>';
    else if (g.link) h += ' <button type="button" class="lk" data-view="sign" data-dsel="' + g.link + '">' + tx('f_dec', { d: g.link }) + '</button>';
    return h + '</p></section>';
  }

  /* ---------------- 03 suppliers ---------------- */
  function vSuppliers() {
    var rows = D.v5.swing_rows.slice().sort(function (a, b) { return a.signed_pct - b.signed_pct; });
    var M = 50, pos = function (v) { return (50 + 50 * v / M).toFixed(2) + '%'; };
    var lo = nv('y1.lo'), hi = nv('y1.hi');
    var h = head(tx('s_kick'), tx('s_h'), tx('s_sub'));
    h += '<section class="panel" id="swing"><p class="read take">' + tx('s_read') + '</p><p class="sw-key mono"><i class="bandsw" aria-hidden="true"></i><span>' + tx('s_band') + ' ' + wrapU('pct', K('y1.lo', true) + '–' + K('y1.hi', true)) + '</span></p><div class="sw-wrap"><div class="sw-axis mono"><span>−50%</span><span>0</span><span>+50%</span></div><div class="sw-rows">';
    h += '<div class="band" style="left:' + pos(-hi) + ';width:calc(' + ((hi - lo) / M * 50).toFixed(2) + '% + 6px)"></div><div class="zero"></div>';
    rows.forEach(function (r) {
      var v = r.signed_pct, k = 'sw.' + r.supplier, l = v < 0 ? pos(v) : '50%', w = (Math.abs(v) / M * 50).toFixed(2) + '%', inside = Math.abs(v) > 30, end = parseFloat(pos(v));
      var vs = v < 0 ? (inside ? 'left:calc(' + end.toFixed(2) + '% + 6px)' : 'right:calc(' + (100 - end).toFixed(2) + '% + 6px)')
        : (inside ? 'right:calc(' + (100 - end).toFixed(2) + '% + 6px)' : 'left:calc(' + end.toFixed(2) + '% + 6px)');
      h += '<div class="sw-row"><span class="sw-l mono">' + esc(r.supplier) + '</span><div class="sw-track"><button type="button" class="sw-bar' + (v < 0 ? ' neg' : '') + '" data-eq="1" data-k="' + k + '" style="left:' + l + ';width:' + w + '" aria-label="' + esc(plain([NUM[k].lab[0] + ' {k:' + k + '}', NUM[k].lab[1] + ' {k:' + k + '}'])) + '"></button>' +
        '<span class="sw-v' + (inside ? ' in' : '') + '" style="' + vs + '">' + K(k, false, true) + '</span></div></div>';
    });
    h += '</div></div></section>';
    h += '<div class="readouts">' +
      '<div class="ro ro-dark"><p class="mono kick">' + tx('s_pcap') + '</p><p class="big">' + K('pilot.cap') + '</p><p class="cap">' + K('pilot.share') + ' ' + tx('s_share') + '</p></div>' +
      '<div class="ro"><p class="mono kick">' + tx('s_floor') + '</p><p class="big">' + K('pilot.floor') + '</p><p class="cap">' + ['SUP005', 'SUP008', 'SUP011'].map(function (s) { return '<span class="mono">' + s + '</span> ' + K('offer.' + s + '.floor'); }).join(' · ') + '</p></div>' +
      '<div class="ro"><p class="mono kick">' + tx('s_ceil') + '</p><p class="big">' + K('pilot.price') + '</p></div></div>';
    var W = [['library', 'w_library'], ['supplier', 'w_supplier'], ['farms', 'w_farms'], ['ops', 'w_ops'], ['product', 'w_product']];
    h += '<div class="two"><section class="panel"><p class="mono kick">' + tx('s_who') + '</p><div class="who">' + W.map(function (w) {
      return '<button type="button" class="who-s w-' + w[0] + '" data-eq="1" data-k="who.' + w[0] + '" style="flex:' + nv('who.' + w[0]).toFixed(2) + '" aria-label="' + esc(L2(T[w[1]]) + ' ' + fk('who.' + w[0])) + '"></button>';
    }).join('') + '</div><ul class="who-l">' + W.map(function (w) { return '<li><i class="sw w-' + w[0] + '"></i><span>' + tx(w[1]) + '</span>' + K('who.' + w[0]) + '</li>'; }).join('') + '</ul></section>';
    var mx = Math.max(nv('rf.nt_top'), nv('rf.nt_bot')) * 1.15;
    h += '<section class="panel"><p class="mono kick">' + tx('s_rk') + '</p><div class="hb">' +
      '<div class="hb-r"><span class="mono">' + tx('s_rtop') + ' · ' + K('rf.y_top') + '</span><div class="hb-t"><i style="width:' + (100 * nv('rf.nt_top') / mx).toFixed(1) + '%"></i>' + K('rf.nt_top') + '</div></div>' +
      '<div class="hb-r"><span class="mono">' + tx('s_rbot') + ' · ' + K('rf.y_bot') + '</span><div class="hb-t"><i class="r" style="width:' + (100 * nv('rf.nt_bot') / mx).toFixed(1) + '%"></i>' + K('rf.nt_bot') + '</div></div></div><p class="cap">' + tx('s_rc') + '</p></section></div>';
    return h;
  }

  /* ---------------- 04 farms and lakes ---------------- */
  function vLakes() {
    var g = D.v10.geo, s = '<svg class="map" viewBox="-4 -4 ' + (g.w + 8) + ' ' + (Math.ceil(g.h) + 8) + '" role="img" aria-label="' + esc(L2(T.l_sub)) + '">', top = '';
    D.v10.catch.forEach(function (c) {
      var ca = c.id === 'CA12', k = 'nat.c.' + c.id, cls = 'ca st-' + (c.ranked ? c.status : 'un') + (ca ? ' ca12' : '');
      var title = c.id + ' · ' + L2(T['st_' + (c.ranked ? c.status : 'un')]) + (c.ranked && NUM[k] ? ' · ' + fk(k) : '');
      var p = '<path d="' + c.d + '" class="' + cls + '"' + (c.ranked && NUM[k] ? ' data-k="' + k + '" tabindex="0" role="button" aria-label="' + esc(title) + '"' : '') + '><title>' + esc(title) + '</title></path>';
      if (ca) top = p; else s += p;
    });
    s += top;
    var c12 = D.v10.catch.filter(function (c) { return c.id === 'CA12'; })[0];
    s += '<text x="' + c12.cx + '" y="' + (c12.cy + 4) + '" text-anchor="middle" class="ml">CA12</text></svg>';
    var h = head(tx('l_kick'), tx('l_h'), '');
    h += '<div class="lk-grid" id="lakes-main"><section class="panel mapp">' + s + '<p class="legend mono"><span>' + tx('l_leg') + ':</span> <i class="sw m-good"></i>' + tx('st_good') + ' <i class="sw m-moderate"></i>' + tx('st_moderate') + ' <i class="sw m-poor"></i>' + tx('st_poor') + ' <i class="sw m-bad"></i>' + tx('st_bad') + '</p></section>';
    var pair = function (lab, co2, p) {
      return '<div class="pr"><p class="mono">' + tx(lab) + '</p><div class="pr-b"><i style="width:' + nv(co2).toFixed(1) + '%"></i><span>' + K(co2) + ' ' + tx('l_ofco2') + '</span></div><div class="pr-b pr-p"><i style="width:' + nv(p).toFixed(1) + '%"></i><span>' + K(p) + ' ' + tx('l_ofp') + '</span></div></div>';
    };
    h += '<div class="lk-side"><section class="panel"><p class="mono kick">' + tx('l_two') + '</p><p class="huge take">' + K('nat.overlap', true) + '</p>' + pair('l_co2', 'nat.top_t_t_pct', 'nat.top_t_p_pct') + pair('l_p', 'nat.top_p_t_pct', 'nat.top_p_p_pct') + '</section>';
    h += '<section class="panel ro-red"><p class="mono kick">' + tx('l_ca') + '</p><p class="cap">' + tx('l_ca_c') + '</p></section>';
    h += '<section class="panel"><p class="mono kick">' + tx('l_cl') + '</p><p class="cap">' + tx('l_cl_c') + '</p></section></div></div>';
    h += '<section class="panel"><p class="mono kick">' + tx('l_ask') + '</p>' + D.v6.ask.filter(function (a) { return a.where === 'nature'; }).map(askCard).join('') + '</section>';
    return h;
  }

  /* ---------------- framework answers (AI draft, a person decides) ---------------- */
  function askById(id) { return D.v6.ask.filter(function (a) { return a.id === id; })[0]; }
  function askState(id) { return ASK[id] ? ASK[id].s : 'draft'; }
  function askRec(b) { return { id: b.id, question: b.q[0], state: askState(b.id), at: ASK[b.id] ? ASK[b.id].at : null, quoted_sources: b.cites.length, reviewer: 'Expert reviewer (simulated)' }; }
  function askLine(b) { var r = askRec(b); return 'framework_answers · ' + r.id + ' · ' + r.state + ' · ' + r.reviewer + ' · ' + r.at; }
  function askLead(b) {
    var t = L2(b.a), re = /[.!?](\s|$)/g, m = re.exec(t), cut = m ? m.index + 1 : t.length;
    if (cut < 40) { m = re.exec(t); if (m) cut = m.index + 1; }
    var s = t.slice(0, cut);
    if (s.length > 96) { s = s.slice(0, 90); s = s.slice(0, s.lastIndexOf(' ')).replace(/[,;:(]$/, '') + '…'; }
    return s;
  }
  function askCard(b) {
    var st = ASK[b.id];
    var h = '<article class="ask" id="ask-' + b.id + '"><p class="aq"><span class="mono kick">' + b.id + '</span> ' + esc(L2(b.q)) + '</p><p class="aa">' + esc(askLead(b)) + '</p>';
    h += '<div class="ai-row"><span class="aib mono">' + tx('ai') + '</span>' + (st ? '<button type="button" class="btn ghost" data-ask="' + b.id + '~undo">' + tx('undo') + '</button>'
      : '<button type="button" class="btn primary" data-ask="' + b.id + '~approved">' + tx('approve') + '</button><button type="button" class="btn" data-ask="' + b.id + '~sent_back">' + tx('sendback') + '</button>') +
      '<button type="button" class="lk" data-v="ask~' + b.id + '">' + tx('dr_full') + ' →</button></div>';
    return h + (st ? stamp(st, askLine(b)) : '') + '</article>';
  }

  /* ---------------- 05 decide and sign ---------------- */
  var DECS = [
    { id: 'P', title: ['Target year', 'Tavoitevuosi'], owner: ['Board chair', 'Hallituksen puheenjohtaja'],
      q: ['Which target? Recommended: 2032, the same {k:pace} FLAG cut a year as 2035.', 'Mikä tavoite? Suositus: 2032, sama {k:pace} FLAG-leikkaus vuodessa kuin 2035.'],
      t: ['Physical cuts only: 2032 is {r:gap.2032.lo,gap.2032.hi} short.', 'Vain fyysiset vähennykset: 2032 jää {r:gap.2032.lo,gap.2032.hi} vajaaksi.'],
      e: ['Route {k:price} a year, {k:capex} investment.', 'Reitti {k:price} vuodessa, {k:capex} investointeja.'],
      n: ['The CFO puts the route\'s yearly cost into the 2027 budget draft.', 'Talousjohtaja vie reitin vuosikustannuksen vuoden 2027 budjettiluonnokseen.'],
      opts: [['Sign for 2032 (V2)', 'Allekirjoita 2032 (V2)'], ['Sign for 2035 (V1.3.1)', 'Allekirjoita 2035 (V1.3.1)'], ['Hold for the supplier FLAG split', 'Odota toimittajien FLAG-jakoa']] },
    { id: 'S', title: ['Commission the field programme', 'Tilataan toimittajien peltohjelma'], owner: ['Head of oilseed procurement', 'Öljykasviostojen päällikkö'],
      q: ['Commission the pilot before signing, and book nothing until an offer clears its floor?', 'Tilataanko pilotti ennen allekirjoitusta, eikä kirjata mitään ennen kuin tarjous ylittää alarajansa?'],
      t: ['2032 needs a {r:cut.2032.lo,cut.2032.hi} cut in bought-rapeseed field emissions.', 'Vuosi 2032 vaatii {r:cut.2032.lo,cut.2032.hi} leikkauksen ostetun rapsin peltopäästöihin.'],
      e: ['Full scale {r:eur.lo,eur.hi} a year; the pilot is capped at {k:pilot.cap}.', 'Täysi laajuus {r:eur.lo,eur.hi} vuodessa; pilotin katto {k:pilot.cap}.'],
      n: ['Send SUP005, SUP008 and SUP011 the terms: floor {k:pilot.floor}, ceiling {k:pilot.price} a tonne.', 'Lähetä SUP005:lle, SUP008:lle ja SUP011:lle ehdot: alaraja {k:pilot.floor}, katto {k:pilot.price} tonnilta.'],
      opts: [['Commission it before signing', 'Tilataan ennen allekirjoitusta'], ['Sign first, size it later', 'Allekirjoitetaan ensin, mitoitetaan myöhemmin']] },
    { id: 'L', title: ['Count L11 only where the land changes', 'L11 lasketaan vain, kun maa muuttuu'], owner: ['Farm advisory lead', 'Viljelyneuvonnan päällikkö'],
      q: ['Does moving crops off peat (L11) count as a cut before the land changes?', 'Lasketaanko viljelyn siirto pois turpeelta (L11) vähennykseksi ennen kuin maa muuttuu?'],
      t: ['L11 moves {k:l11.t} off {k:l11.ha}; L12 rewets {k:l12.ha}.', 'L11 siirtää {k:l11.t} pois {k:l11.ha}:lta; L12 soistaa {k:l12.ha}.'],
      e: ['{k:l11.eurt} per moved tonne: cheap, but a reallocation.', '{k:l11.eurt} siirrettyä tonnia kohden: halpa, mutta siirto.'],
      n: ['List the parcels L11 releases; ask owners: retire or rewet?', 'Listaa L11:n vapauttamat lohkot; kysy omistajilta käytöstä poistosta tai soistamisesta.'],
      opts: [['Only on retired or rewetted parcels', 'Vain käytöstä poistetuilla tai soistetuilla lohkoilla'], ['Count it in full', 'Lasketaan kokonaan']] },
    { id: 'R', title: ['Show rotation as rotation', 'Kierto näytetään kiertona'], owner: ['Sustainability reporting lead', 'Vastuullisuusraportoinnin vastaava'],
      q: ['Label rotation automatically, so a crop leaving peat never reads as a cut?', 'Merkitäänkö kierto automaattisesti, ettei turpeelta lähtevää kasvia lueta vähennykseksi?'],
      t: ['Rotation moves about {k:rot.t} a year with no lever pulled.', 'Kierto liikuttaa noin {k:rot.t} vuodessa ilman toimia.'],
      e: ['No cost: a reporting rule.', 'Ei kustannusta: raportointisääntö.'],
      n: ['Tag every peat-area change "rotation, not reduction" in the template.', 'Merkitse jokainen turvealan muutos pohjaan "kierto, ei vähennys".'],
      opts: [['Label rotation automatically', 'Kierto merkitään automaattisesti'], ['Leave it open', 'Jätetään avoimeksi']] },
    { id: 'M', title: ['Peat method in the base', 'Turvemenetelmä mukaan perusvuoteen'], owner: ['Head of sustainability', 'Vastuullisuusjohtaja'],
      q: ['Accept the soil map plus farmer reports as the method for peat soils?', 'Hyväksytäänkö maaperäkartta ja viljelijöiden ilmoitukset turvemaiden menetelmäksi?'],
      t: ['Moves the base {r:peat.lo_pct,peat.hi_pct}: past the {k:meter.line} line on all {n:floor.n} bases tested.', 'Muuttaa perusvuotta {r:peat.lo_pct,peat.hi_pct}: yli {k:meter.line}:n rajan kaikilla {n:floor.n} testatulla perusvuodella.'],
      e: ['No lever cost; advisory days for the probe.', 'Ei keinokustannusta; neuvontapäiviä kairaukseen.'],
      n: ['{n:probe.n} area-weighted probes; {n:probe.k} or more mineral results trigger a rerun.', '{n:probe.n} pinta-alapainotettua kairausta; vähintään {n:probe.k} kivennäismaatulosta käynnistää uudelleenlaskennan.'],
      opts: [['Carry the peat method', 'Turvemenetelmä mukaan'], ['Keep today\'s calculator', 'Pidetään nykyinen laskuri']] },
    { id: 'F', title: ['Show the rapeseed plan pays, farm by farm', 'Näytetään rapsisuunnitelman hyöty tila kerrallaan'], owner: ['Head of procurement', 'Hankintajohtaja'],
      q: ['How do we show the board\'s rapeseed plan pays?', 'Miten näytämme hallituksen rapsisuunnitelman hyödyn?'],
      t: ['Highest-yield quarter: {k:rf.nt_top} of nitrogen per tonne; lowest: {k:rf.nt_bot}.', 'Paras satoneljännes: {k:rf.nt_top} typpeä tonnia kohden; heikoin: {k:rf.nt_bot}.'],
      e: ['Uses yields farms already send; grower programme {k:l15.cost} a year.', 'Käyttää tilojen jo lähettämiä satoja; viljelijäohjelma {k:l15.cost} vuodessa.'],
      n: ['Parcel ID, yield and nitrogen rate on the 2027 rapeseed grower form.', 'Lohkotunnus, sato ja typpimäärä kauden 2027 rapsilomakkeelle.'],
      opts: [['Farm by farm from field records', 'Tila kerrallaan peltotiedoista'], ['At the catalogue\'s average tonnes', 'Luettelon keskimääräisillä tonneilla']] },
    { id: 'E', title: ['Start the money-saving levers', 'Säästävät keinot käyntiin'], owner: ['CFO', 'Talousjohtaja'],
      q: ['Do the money-saving levers wait for the target decision?', 'Odottavatko säästävät keinot tavoitepäätöstä?'],
      t: ['{n:sav.n} levers cut {k:sav.t} a year.', '{n:sav.n} keinoa vähentää {k:sav.t} vuodessa.'],
      e: ['Net {k:sav.eur} a year: they pay back in every scenario.', 'Netto {k:sav.eur} vuodessa: ne maksavat itsensä takaisin kaikissa skenaarioissa.'],
      n: ['Confirm each lever\'s owner and start them now.', 'Vahvista kunkin keinon vastuuhenkilö ja käynnistä ne nyt.'],
      opts: [['Start now', 'Aloitetaan nyt'], ['Wait for the route', 'Odotetaan reittiä']] },
    { id: 'C', title: ['Approve pending corrections', 'Odottavat korjaukset hyväksytään'], owner: ['Group controller', 'Konsernicontroller'],
      q: ['Which judgement corrections go into the frozen base?', 'Mitkä harkinnanvaraiset korjaukset menevät lukittuun perusvuoteen?'],
      t: ['{n:pend.n} judgement corrections; rejecting all moves the base at most {k:pend.t}.', '{n:pend.n} harkinnanvaraista korjausta; kaikkien hylkääminen siirtää perusvuotta enintään {k:pend.t}.'],
      e: ['No cost: a review.', 'Ei kustannusta: tarkastus.'],
      n: ['Review the commuting rule R-COMM-1 against the survey before freezing.', 'Tarkasta työmatkasääntö R-COMM-1 kyselyä vasten ennen lukitsemista.'],
      opts: [['All except R-COMM-1 until reviewed', 'Kaikki paitsi R-COMM-1, kunnes tarkastettu'], ['Approve all', 'Kaikki hyväksytään']] }
  ];
  var SIGNERS = [['Board chair', 'Hallituksen puheenjohtaja'], ['CEO', 'Toimitusjohtaja'], ['CFO', 'Talousjohtaja']];
  var APPROVERS = [['Group controller', 'Konsernicontroller'], ['Audit committee chair', 'Tarkastusvaliokunnan puheenjohtaja'], ['Head of sustainability', 'Vastuullisuusjohtaja']];
  var TH = nv('rev.th');
  var BLOCK = D.v3.review.filter(function (r) { return r.impact === null || Math.abs(r.impact) >= TH; });
  function reviewReady() { return BLOCK.every(function (r) { return !!REVIEW[r.id]; }); }
  function decReady() { return DECS.every(function (d) { return !!DEC[d.id]; }) && reviewReady(); }
  function counter(lab, n, of) { return '<div class="ctr' + (lab === 'c_dec' ? ' ctr-main' : '') + '"><p class="mono kick">' + tx(lab) + '</p><p class="big3' + (lab === 'c_dec' ? ' take' : '') + '"><b>' + n + '</b><span>/' + of + '</span></p><span class="cbar" aria-hidden="true"><i style="width:' + (of ? Math.round(100 * n / of) : 0) + '%"></i></span></div>'; }
  function vSign() {
    var nD = DECS.filter(function (d) { return DEC[d.id]; }).length, nR = BLOCK.filter(function (r) { return REVIEW[r.id]; }).length;
    var nA = D.v6.ask.filter(function (a) { return ASK[a.id]; }).length, nG = U.gaps.filter(function (g) { return GAPST[g.id]; }).length;
    var h = head('', tx('d_h'), '');
    h += '<div class="ctrs">' + counter('c_dec', nD, DECS.length) + counter('c_rev', nR, BLOCK.length) + counter('c_ask', nA, D.v6.ask.length) + counter('c_gap', nG, U.gaps.length) + '</div>';
    h += '<div class="dl"><section class="panel" id="decs"><div class="dgrid">' + DECS.map(function (d) {
      var r = DEC[d.id], on = d.id === DECSEL;
      return '<button type="button" class="dt' + (on ? ' on' : '') + (r ? ' done' : '') + '" data-dsel="' + d.id + '" aria-pressed="' + on + '"><span class="dl-id">' + d.id + '</span><span class="dl-t">' + shy(esc(L2(d.title))) + '</span>' + (r ? '<span class="dl-s mono">✓ ' + esc(L2(d.opts[r.o])) + '</span>' : '') + '</button>';
    }).join('') + '</div></section>';
    h += decDetail(DECS.filter(function (d) { return d.id === DECSEL; })[0]) + '</div>';
    h += '<div class="two">' + reviewCard() + signPanel() + '</div>';
    return h;
  }
  function decDetail(d) {
    var r = DEC[d.id];
    var h = '<section class="panel dd" id="dd"><div class="gd-h"><span class="gd-rank">' + d.id + '</span><div><p class="mono kick">' + tx('d_owner') + ' · ' + esc(L2(d.owner)) + '</p><h2>' + esc(L2(d.title)) + '</h2></div></div>';
    h += '<p class="dq">' + fx(d.q) + '</p><dl class="fields"><dt class="mono">' + tx('d_t') + '</dt><dd>' + fx(d.t) + '</dd><dt class="mono">' + tx('d_e') + '</dt><dd>' + fx(d.e) + '</dd><dt class="mono red">' + tx('d_n') + '</dt><dd class="strong">' + fx(d.n) + '</dd></dl>';
    h += '<div class="opts">' + d.opts.map(function (o, i) {
      var on = r && r.o === i;
      return '<button type="button" class="opt' + (on ? ' on' : '') + '" data-dec="' + d.id + '~' + i + '" aria-pressed="' + !!on + '">' + esc(L2(o)) + (i === 0 ? ' <span class="tag mono">' + tx('recd') + '</span>' : '') + '</button>';
    }).join('') + '</div>';
    if (r) h += '<div class="stamp stamp-ok" role="status"><span class="si" aria-hidden="true">✓</span><div><p><b>' + tx('d_done') + '</b> · ' + esc(L2(d.opts[r.o])) + '</p><p class="mono">' + esc(L2(d.owner)) + ' ' + tx('d_sim') + ' · ' + esc(r.at.slice(0, 16).replace('T', ' ')) + '</p></div></div>';
    var asks = D.v6.ask.filter(function (a) { return a.dec.indexOf(d.id) >= 0; });
    if (asks.length) h += '<p class="mono kick asks-k">' + tx('d_asks') + '</p>' + asks.map(askCard).join('');
    return h + '</section>';
  }
  function reviewCard() {
    var n = BLOCK.length, i = Math.max(0, Math.min(REVI, n - 1)), r = BLOCK[i], st = REVIEW[r.id];
    var h = '<section class="panel" id="queue"><p class="mono kick">' + tx('q_k') + ' · ' + (i + 1) + '/' + n + '</p><p class="cap">' + tx('q_c') + '</p>';
    h += '<div class="qc"><p class="mono qkey">' + esc(r.key) + '</p><p class="mono dim">' + esc(r.table) + ' · ' + esc(r.type) + ' · ' + esc(r.field) + '</p>' +
      '<div class="qv"><div><span class="mono kick">' + tx('q_old') + '</span><b class="mono">' + esc(r.old) + '</b></div><span aria-hidden="true">→</span><div><span class="mono kick">' + tx('q_new') + '</span><b class="mono">' + esc(r.new) + '</b></div></div>' +
      '<p class="cap"><span class="mono kick">' + tx('q_rule') + '</span> ' + esc(r.rule) + '</p>' +
      '<p class="mono qst ' + (st ? (st.choice === 'accept' ? 'ok' : 'redt') : '') + '">' + (st ? (st.choice === 'accept' ? '✓ ' + tx('q_acc') : '↩ ' + tx('q_rej')) + ' · ' + esc(st.at.slice(0, 16).replace('T', ' ')) : tx('q_open')) + '</p></div>';
    h += '<div class="qb"><button type="button" class="btn" data-q="prev"' + (i === 0 ? ' disabled' : '') + '>← ' + tx('prev') + '</button><button type="button" class="btn primary" data-review="' + r.id + '~accept">' + tx('accept') + '</button><button type="button" class="btn" data-review="' + r.id + '~reject">' + tx('reject') + '</button><button type="button" class="btn" data-q="next"' + (i >= n - 1 ? ' disabled' : '') + '>' + tx('nextb') + ' →</button><button type="button" class="btn ghost" data-q="open">' + tx('q_jump') + '</button></div>';
    return h + '</section>';
  }
  function signPanel() {
    var ready = decReady();
    var h = '<section class="panel ro-dark" id="signp"><p class="mono kick">' + tx('sg_k') + '</p><p class="cap">' + tx('sg_c') + '</p>';
    h += '<div class="srow"><label><span class="mono kick">' + tx('signer') + '</span><select id="signer"><option value="">' + tx('choose') + '</option>' + SIGNERS.map(function (s) { return '<option value="' + esc(s[0]) + '"' + (SIGNER === s[0] ? ' selected' : '') + '>' + esc(L2(s)) + '</option>'; }).join('') + '</select></label>' +
      '<button type="button" class="btn red" data-a="sign"' + (ready && SIGNER ? '' : ' disabled') + '>' + tx('sign_b') + '</button></div>';
    if (!ready) h += '<p class="cap dim">' + tx('sg_need') + '</p>';
    h += '<p class="mono kick reg-k">' + tx('reg_h') + '</p>';
    if (!REG.length) h += '<p class="cap dim">' + tx('reg_empty') + '</p>';
    REG.slice().reverse().forEach(function (e) {
      var ap = e.approval, p = e.payload;
      h += '<div class="rec"><p class="mono"><b>' + esc(e.id) + '</b></p><p class="mono dim">' + esc(L2(SIGNERS.filter(function (s) { return s[0] === p.signed_by; })[0] || [p.signed_by, p.signed_by])) + ' · ' + esc(p.signed_at.slice(0, 16).replace('T', ' ')) + ' · sha256 ' + esc(e.hash.slice(0, 12)) + '…</p>' +
        '<p class="mono ' + (ap ? 'ok' : '') + '">' + (ap ? '✓ ' + tx('st_app') + ' · ' + esc(L2(APPROVERS.filter(function (a) { return a[0] === ap.role; })[0] || [ap.role, ap.role])) : tx('st_draft')) + '</p>' +
        '<div class="rb"><button type="button" class="btn" data-v="entry~' + esc(e.id) + '">' + tx('open') + '</button><button type="button" class="btn" data-a="dl~' + esc(e.id) + '">' + tx('dl') + '</button></div>' +
        (ap ? '' : '<div class="rb"><select data-apr="' + esc(e.id) + '" aria-label="' + esc(L2(T.approver)) + '"><option value="">' + tx('approver') + '</option>' + APPROVERS.map(function (a) { return '<option value="' + esc(a[0]) + '">' + esc(L2(a)) + '</option>'; }).join('') + '</select><button type="button" class="btn" data-a="approve~' + esc(e.id) + '">' + tx('appr_b') + '</button></div>') + '</div>';
    });
    h += '<label class="loadf"><span class="mono kick">' + tx('load') + '</span><input type="file" id="loadf" accept=".json,application/json"></label><p class="cap" id="loadmsg" aria-live="polite"></p>';
    return h + '</section>';
  }

  /* ---------------- the signed record (schema 4; v11's checks, plus gap actions) ---------------- */
  var FIGS = ['gap.2032.lo', 'gap.2032.hi', 'gap.2035.lo', 'gap.2035.hi', 'price', 'capex', 'peat.lo_pct', 'peat.hi_pct', 'rot.t', 'base.flag', 'tgt.2032', 'tgt.2035', 'inv.total', 'pilot.cap', 'pilot.floor', 'sw.lo', 'sw.hi', 'y1.lo', 'y1.hi'];
  function sumLines(pred, f) { return B.inventory_2025.lines.reduce(function (a, l) { return a + (pred(l) ? l[f] : 0); }, 0); }
  function rebuildReported() {
    return { s12: sumLines(function (l) { return l.scope === 'scope1' || l.scope === 'scope2_market'; }, 'tco2e'), flag: sumLines(function () { return true; }, 'flag_t'),
      s3: sumLines(function (l) { return l.scope === 'scope3'; }, 'tco2e') };
  }
  function makePayload(role, at) {
    if (!decReady()) throw new Error('Resolve decisions and expert review before signing');
    var decs = {}, figs = {};
    DECS.forEach(function (d) { var r = DEC[d.id]; decs[d.id] = { decision: d.title[0], choice: d.opts[r.o][0], recommended: r.o === 0, owner: d.owner[0], at: r.at }; });
    FIGS.forEach(function (k) { figs[k] = nv(k); });
    var y = DEC.P.o === 0 ? 2032 : DEC.P.o === 1 ? 2035 : null;
    var p = { schema: 'jälki.signed-base/4', label: B.label, synthetic: true, kind: y ? 'sign' : 'hold', year: y, signed_by: role, signed_at: at || new Date().toISOString(), pipeline: D.seal.pipeline,
      decisions: decs, expert_review: JSON.parse(JSON.stringify(REVIEW)), review_source: D.v3.review_source, l11_credit_t: 0,
      framework_answers: D.v6.ask.map(askRec), gap_actions: U.gaps.map(gapRec),
      base_recalculated: { flag: nv('base.flag') }, targets: y ? { flag: nv('tgt.' + y) } : null,
      reported_from_lines: rebuildReported(), figures: figs,
      seal: { inputs: D.seal.inputs, factors: D.seal.factors, code: D.seal.code, bundle: D.seal.bundle, n_inputs: D.seal.n_inputs, n_factors: D.seal.n_factors } };
    if (canon(p.framework_answers) !== canon(D.v6.ask.map(askRec)) || canon(p.gap_actions) !== canon(U.gaps.map(gapRec))) throw new Error('the record differs from the entries shown on the page');
    return p;
  }
  function addEntry(p) {
    var hash = sha256(canon(p)), e = { id: 'JÄLKI-2025-' + ('00' + (REG.length + 1)).slice(-3) + '-' + hash.slice(0, 8), payload: p, hash: hash, approval: null };
    REG.push(e); store('reg', REG); return e;
  }
  function approveRec(e, role, at) {
    if (!e || e.approval || !role || SIGNERS.some(function (r) { return r[0] === role; }) || role === e.payload.signed_by) return false;
    var a = { role: role, at: at || new Date().toISOString(), of: e.hash }; a.hash = sha256(canon({ role: a.role, at: a.at, of: a.of }));
    e.approval = a; store('reg', REG); return true;
  }
  function recordProblem(o) {
    if (!o || typeof o !== 'object' || !o.payload || typeof o.hash !== 'string') return 'load_notrec';
    if (sha256(canon(o.payload)) !== o.hash) return 'load_bad';
    if (typeof o.id !== 'string' || !/^JÄLKI-[A-Za-z0-9-]{1,80}$/.test(o.id) || !o.payload.seal) return 'load_notrec';
    if (o.approval) { var a = o.approval; if (sha256(canon({ role: a.role, at: a.at, of: a.of })) !== a.hash || a.of !== o.hash || a.role === o.payload.signed_by) return 'load_bad'; }
    return null;
  }
  function importFile(txt) {
    var o; try { o = JSON.parse(txt); } catch (x) { return ['load_notrec', null]; }
    var pr = recordProblem(o); if (pr) return [pr, null];
    var e = { id: o.id, payload: o.payload, hash: o.hash, approval: o.approval || null, imported: true };
    REG = REG.filter(function (z) { return z.id !== e.id; }); REG.push(e); store('reg', REG); return [null, e];
  }
  function replay(e) {
    var p = e.payload, rb = rebuildReported();
    var same = function (k, v) { var now; try { now = nv(k); } catch (x) { return false; } return typeof v === 'number' && Math.abs(now - v) < 1e-6; };
    var figOk = Object.keys(p.figures || {}).every(function (k) { return same(k, p.figures[k]); }) && same('base.flag', (p.base_recalculated || {}).flag);
    return [
      ['rp_int', sha256(canon(p)) === e.hash, e.hash.slice(0, 16)],
      ['rp_inp', sha256(TR.inputs_text) === p.seal.inputs, p.seal.inputs.slice(0, 16)],
      ['rp_fac', sha256(TR.factors_text) === p.seal.factors, p.seal.factors.slice(0, 16)],
      ['rp_code', D.seal.code === p.seal.code, p.seal.code.slice(0, 16)],
      ['rp_base', Math.abs(rb.s12 - p.reported_from_lines.s12) < 0.5 && Math.abs(rb.flag - p.reported_from_lines.flag) < 0.5 && Math.abs(rb.s3 - p.reported_from_lines.s3) < 0.5, ''],
      ['rp_fig', figOk, Object.keys(p.figures || {}).length + ''],
      ['rp_ask', Array.isArray(p.framework_answers) && p.framework_answers.length === D.v6.ask.length && Array.isArray(p.gap_actions) && p.gap_actions.length === U.gaps.length, '']
    ];
  }
  function sealTest(e) {
    var txt = TR.factors_text, key = '"FUEL_EF:diesel":{', i = txt.indexOf(key), j = txt.indexOf('"value":', i), k = j + 8, m = k;
    while (m < txt.length && /[0-9eE.+\-]/.test(txt.charAt(m))) m++;
    var v = parseFloat(txt.slice(k, m)), mod = txt.slice(0, k) + String(v * 1.01) + txt.slice(m);
    return { factor: 'FUEL_EF:diesel', from: v, to: v * 1.01, same: sha256(mod) === e.payload.seal.factors, hash: sha256(mod).slice(0, 16) };
  }
  function fileOf(e) { return JSON.stringify({ id: e.id, hash: e.hash, payload: e.payload, approval: e.approval }, null, 1); }
  function download(e) {
    var blob = new Blob([fileOf(e)], { type: 'application/json' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = e.id + '.json'; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  /* ---------------- method (a quiet footer page) ---------------- */
  function vMethod() {
    var h = head('', tx('m_h'), '');
    h += '<section class="panel method"><ol class="ml">' + ['m1', 'm2', 'm3', 'm4', 'm5', 'm6'].map(function (k, i) { return '<li><span class="mono">0' + (i + 1) + '</span><p' + (i === 0 ? ' class="take"' : '') + '>' + tx(k) + '</p></li>'; }).join('') + '</ol>';
    h += '<p class="mono kick">' + tx('m_lim') + '</p><ul class="ml2">' + ['l1', 'l2', 'l3'].map(function (k) { return '<li>' + tx(k) + '</li>'; }).join('') + '</ul>';
    h += '<p class="mono dim seal">' + D.seal.n_inputs + ' inputs · ' + D.seal.n_factors + ' factors · sha256 ' + esc(D.seal.factors.slice(0, 12)) + '…</p></section>';
    return h;
  }

  /* ---------------- the drawer: one view of a source, the same everywhere ---------------- */
  var STACK = [], LOADING = {}, OPENER = null;
  function lineById(id) { for (var i = 0; i < TR.index.lines.length; i++) if (TR.index.lines[i].line_id === id) return TR.index.lines[i]; return null; }
  function shardName(id) { var l = lineById(id); return l ? l.shard.split('/').pop().replace('.json', '') : null; }
  function need(nm) {
    if (LOADING[nm]) return; LOADING[nm] = 1;
    var s = document.createElement('script'); s.src = 'trail/l/' + nm + '.js'; s.onload = drawDrawer; document.body.appendChild(s);
  }
  function drow(label, right, v) { return '<button type="button" class="drow" data-v="' + esc(v) + '"><span>' + esc(label) + '</span><span class="mono">' + right + '</span></button>'; }
  function provParts(pv) {
    if (!pv) return null;
    var s = pv.s, scr = (s.match(/\[(python3[^\]]+)\]\s*$/) || [])[1] || '', files = [];
    (s.match(/(?:twin\/data(?:\/data)?:\s*)([^;\[|]+)/) || [, ''])[1].split(',').forEach(function (f) { f = f.trim(); if (f) files.push(f); });
    return { kind: pv.l, script: scr, files: files, note: s.replace(/\s*\[python3[^\]]+\]\s*$/, '') };
  }
  function dNum(k) {
    var n = NUM[k], pv = provParts(n.prov);
    var h = '<p class="mono kick">' + esc(L2(n.lab)) + '</p><p class="dbig">' + esc(fk(k)) + '</p>';
    if (n.how) h += '<p class="dhow">' + esc(L2(n.how)) + '</p>';
    if (n.r100) h += '<p class="mono dim">' + tx('dr_exact') + ': ' + esc(wrapU(n.u, fnum(n.x, 1))) + ' · ' + tx('dr_rounded') + '</p>';
    if (n.parts.length) h += '<p class="mono kick dsec">' + tx('dr_parts') + '</p>' + n.parts.map(function (p) { return drow(L2(NUM[p].lab), esc(fk(p)), 'k~' + p); }).join('');
    if (k === 'price' || k === 'capex') h += drow(L2(T.dr_route), '→', 'route~rec');
    h += '<p class="mono kick dsec">' + tx('dr_src') + '</p><dl class="dsrc"><dt class="mono">' + tx('dr_script') + '</dt><dd class="mono">' + esc((pv && pv.script) || n.script) + '</dd>' +
      '<dt class="mono">' + tx('dr_prov') + '</dt><dd><span class="kind mono k-' + (pv ? pv.kind : 'none') + '">' + tx('k_' + (pv ? pv.kind : 'none')) + '</span>' + (pv && pv.files.length ? ' <span class="mono dim">' + esc(pv.files.join(' · ')) + '</span>' : '') + '</dd></dl>';
    if (pv) h += '<p class="mono dnote">' + esc(pv.note) + '</p>';
    if (n.lines.length) h += '<p class="mono kick dsec">' + tx('dr_recs') + '</p>' + n.lines.map(function (l) { var bl = B.inventory_2025.lines.filter(function (x) { return x.line_id === l; })[0]; return drow(l.split('|').slice(1).join(' · '), bl ? esc(fnum(bl.tco2e, 0)) + ' t' : '→', 'line~' + l); }).join('');
    return h;
  }
  function edgeTable(edges) {
    var h = '<div class="tw"><table class="src"><thead><tr><th>' + tx('dr_rec') + '</th><th>' + tx('dr_rawclean') + '</th><th>' + tx('dr_factor') + '</th><th>t</th><th>' + tx('dr_corr') + '</th></tr></thead><tbody>';
    edges.forEach(function (e) {
      var f = TR.factors && TR.factors[e[9]];
      h += '<tr' + (e[13] ? ' class="cf"' : '') + '><td class="mono">' + esc(e[1]) + '<span class="dim">' + esc(TR.index.files[e[2]] || '') + (e[3] ? ':' + e[3] : '') + '</span></td><td class="mono">' + esc(String(e[5])) + ' ' + esc(e[6] || '') + ' → ' + esc(String(e[7])) + ' ' + esc(e[8] || '') + '</td><td class="mono">' + esc(e[9] || '') + (f ? '<span class="dim">' + esc(String(f.value)) + ' ' + esc(f.unit || '') + '</span>' : '') + '</td><td class="mono">' + esc(fnum(e[11], 2)) + '</td><td class="mono">' + esc(e[13] || '') + '</td></tr>';
    });
    return h + '</tbody></table></div>';
  }
  function dLine(id, all) {
    var nm = shardName(id); if (!nm) return '<p>—</p>';
    var sh = TR.l[nm]; if (!sh) { need(nm); return '<p class="mono">' + tx('dr_loading') + '</p>'; }
    var h = '<p class="mono kick">' + esc(sh.scope) + ' · ' + esc(sh.category) + '</p><p class="dbig">' + esc(fnum(sh.t, 0)) + ' t</p><p class="dhow">' + esc(sh.item) + '</p>';
    var pk = Object.keys(sh.parties);
    if (pk.length > 1) {
      pk.sort(function (a, b) { return sh.parties[b].t - sh.parties[a].t; });
      h += '<p class="mono kick dsec">' + tx('dr_parties') + ' (' + pk.length + ')</p>';
      (all ? pk : pk.slice(0, 30)).forEach(function (p) { h += drow(p.replace(/^farm:/, ''), esc(fnum(sh.parties[p].t, 1)) + ' t', 'party~' + id + '~' + p); });
      if (!all && pk.length > 30) h += drow(L2(T.dr_all) + ' (' + pk.length + ')', '→', 'lineall~' + id);
      return h;
    }
    var ed = sh.edges.slice().sort(function (a, b) { return Math.abs(b[11]) - Math.abs(a[11]); });
    h += '<p class="mono kick dsec">' + tx('dr_recs') + ' (' + ed.length + ')</p>' + edgeTable(all ? ed : ed.slice(0, 40));
    if (!all && ed.length > 40) h += drow(L2(T.dr_all) + ' (' + ed.length + ')', '→', 'lineall~' + id);
    return h;
  }
  function dParty(id, party) {
    var nm = shardName(id); if (!nm) return '<p>—</p>';
    var sh = TR.l[nm]; if (!sh) { need(nm); return '<p class="mono">' + tx('dr_loading') + '</p>'; }
    var p = sh.parties[party] || {};
    return '<p class="mono kick">' + esc(sh.item) + '</p><p class="dbig">' + esc(fnum(p.t, 1)) + ' t</p><p class="dhow mono">' + esc(party) + '</p>' + edgeTable(sh.edges.filter(function (e) { return e[14] === party; }));
  }
  function dGap(id) {
    var g = gapById(id);
    var h = '<p class="mono kick">' + esc(g.id) + ' · ' + esc(g.fw) + '</p><p class="dhow"><b>' + fx(g.short) + '</b></p>';
    h += '<p class="mono kick dsec">' + tx('dr_cites') + '</p>' + g.cites.map(function (c) { return '<div class="cite"><p class="mono">' + esc(c.document) + '</p><p class="mono dim">' + esc(c.section) + '</p><p class="q">“' + esc(c.checked_phrase) + '”</p></div>'; }).join('');
    h += '<p class="mono kick dsec">' + tx('dr_rank') + '</p><p class="mono dnote">' + esc(U.gap_meta.ranking_rule) + ' · class ' + g.cls + ' · ' + g.days + ' d · ' + g.ipd + '</p>';
    h += '<dl class="dsrc"><dt class="mono">' + tx('dr_script') + '</dt><dd class="mono">' + esc(U.gap_meta.script) + '</dd><dt class="mono">' + tx('dr_prov') + '</dt><dd class="mono dim">' + esc(U.gap_meta.drafted_by) + '</dd></dl>';
    return h;
  }
  function dAsk(id) {
    var b = askById(id);
    return '<p class="mono kick">' + esc(b.id) + ' · ' + tx('ai') + ' · ' + tx(ASK[b.id] ? (ASK[b.id].s === 'approved' ? 's_ok' : 's_back') : 'd_open') + '</p><p class="dhow"><b>' + esc(L2(b.q)) + '</b></p><p class="dhow">' + esc(L2(b.a)) + '</p><p class="mono kick dsec">' + tx('dr_quote') + ' (' + b.cites.length + ')</p>' +
      b.cites.map(function (c) { return '<div class="cite"><p class="mono">' + esc(L2(c.show)) + ' · ' + esc(c.path) + '</p><p class="mono dim">' + esc(c.section) + '</p><p class="q">“' + esc(c.quote) + '”</p></div>'; }).join('') +
      '<p class="mono dim dnote">' + esc(D.v6.ask_check) + '</p>';
  }
  function dRoute() {
    var h = '<p class="mono kick">' + tx('dr_route') + '</p><p class="dbig">' + esc(fk('price')) + '</p>';
    D.route.rec.forEach(function (id) {
      var l = B.levers.filter(function (x) { return x.id === id; })[0]; if (!l) return;
      h += '<div class="lev"><p><span class="mono">' + id + '</span> ' + esc(l.name) + '</p><p class="mono dim">' + esc(fnum(l.t_central, 0)) + ' t · ' + esc(wrapU('keur', fnum(l.cost_eur_yr / 1e3, 0))) + ' · ' + esc(l.cls) + '</p></div>';
    });
    return h + '<p class="mono dim dnote">' + esc(D.v4.script) + '</p>';
  }
  function dEntry(id) {
    var e = REG.filter(function (z) { return z.id === id; })[0]; if (!e) return '<p>—</p>';
    var r = replay(e), ok = r.every(function (x) { return x[1]; });
    var h = '<p class="mono kick">' + esc(e.id) + '</p><p class="dbig ' + (ok ? '' : 'red') + '">' + r.filter(function (x) { return x[1]; }).length + '/' + r.length + '</p><ul class="rp">' +
      r.map(function (x) { return '<li class="' + (x[1] ? 'ok' : 'redt') + '"><span class="mono">' + (x[1] ? '✓' : '✗') + '</span> ' + tx(x[0]) + (x[2] ? ' <span class="mono dim">' + esc(x[2]) + '</span>' : '') + '</li>'; }).join('') + '</ul>';
    h += '<p class="mono kick dsec">' + tx('rp_test') + '</p><div id="testres"><button type="button" class="btn" data-a="test~' + esc(e.id) + '">' + tx('rp_test') + '</button></div>';
    h += '<p class="mono kick dsec">sha256</p><p class="mono dnote">' + esc(e.hash) + '</p>';
    return h;
  }
  function dView(spec) {
    var a = spec.split('~');
    if (a[0] === 'k') return dNum(a[1]);
    if (a[0] === 'line') return dLine(a[1], false);
    if (a[0] === 'lineall') return dLine(a[1], true);
    if (a[0] === 'party') return dParty(a[1], a.slice(2).join('~'));
    if (a[0] === 'gap') return dGap(a[1]);
    if (a[0] === 'ask') return dAsk(a[1]);
    if (a[0] === 'route') return dRoute();
    if (a[0] === 'entry') return dEntry(a.slice(1).join('~'));
    return '<p>—</p>';
  }
  function crumb(spec) {
    var a = spec.split('~');
    if (a[0] === 'k') return L2(NUM[a[1]].lab);
    if (a[0] === 'line' || a[0] === 'lineall') return a[1].split('|').pop();
    if (a[0] === 'party') return a.slice(2).join('~').replace(/^farm:/, '');
    if (a[0] === 'route') return L2(T.dr_route);
    return a.slice(1).join(' ');
  }
  function drawDrawer() {
    if (!STACK.length) return;
    var spec = STACK[STACK.length - 1];
    document.getElementById('drin').innerHTML = dView(spec);
    document.getElementById('crumb').textContent = STACK.map(crumb).join(' › ');
    document.getElementById('back').hidden = STACK.length < 2;
  }
  /* v13 (bug a): opening and closing the drawer never moves the page. The scroll position is taken when it opens,
     focus moves with preventScroll, and on close the reader is put back exactly where they were. */
  var SAVED = null;
  function openV(spec, reset) {
    var dr = document.getElementById('dr'), wasOpen = dr.classList.contains('open');
    if (reset) STACK = [];
    if (!wasOpen) { OPENER = document.activeElement; SAVED = { x: G.scrollX, y: G.scrollY }; }
    STACK.push(spec); drawDrawer(); hideTip();
    if (HINT) { HINT = false; store('hinted', 1); }   /* the hint has done its job; it goes at the next redraw, never under the reader's eyes */
    dr.classList.add('open'); dr.setAttribute('aria-hidden', 'false'); document.getElementById('scrim').classList.add('on');
    document.documentElement.classList.add('dr-open');   /* the page behind cannot be dragged while the drawer is open */
    document.getElementById('drin').scrollTop = 0;
    if (!wasOpen) { var c = document.getElementById('close'); c.focus({ preventScroll: true }); keep(); }
  }
  function keep() { if (SAVED && (G.scrollY !== SAVED.y || G.scrollX !== SAVED.x)) G.scrollTo(SAVED.x, SAVED.y); }
  function closeDr() {
    var dr = document.getElementById('dr'); if (!dr.classList.contains('open')) return;
    STACK = []; dr.classList.remove('open'); dr.setAttribute('aria-hidden', 'true'); document.getElementById('scrim').classList.remove('on');
    document.documentElement.classList.remove('dr-open');
    if (OPENER && document.body.contains(OPENER)) OPENER.focus({ preventScroll: true });
    keep(); SAVED = null;
  }

  /* ---------------- tour ---------------- */
  var TI = -1;
  function tourCard() {
    var el = document.getElementById('tour');
    document.querySelectorAll('.tour-on').forEach(function (x) { x.classList.remove('tour-on'); });
    var root = document.documentElement;
    if (TI < 0) { el.hidden = true; el.innerHTML = ''; root.classList.remove('touring'); root.style.removeProperty('--tourpad'); return; }
    var st = STEPS[TI], last = TI === STEPS.length - 1, appr = st.approve && !GAPST[st.approve];
    el.hidden = false;
    el.innerHTML = '<p class="mono kick">' + (TI + 1) + '/' + STEPS.length + '</p><p class="tt">' + esc(L2(st.t)) + '</p><p class="tx">' + esc(L2(st.x)) + '</p><div class="tb">' +
      '<button type="button" class="btn ghost" data-t="close" aria-label="' + esc(L2(T.to_close)) + '">✕</button>' + (TI > 0 ? '<button type="button" class="btn" data-t="back">' + tx('to_back') + '</button>' : '') +
      '<button type="button" class="btn ' + (appr ? 'red' : 'primary') + '" data-t="' + (appr ? 'approve' : last ? 'close' : 'next') + '">' + (appr ? tx('approve') + ' →' : last ? tx('to_done') : tx('to_next') + ' →') + '</button></div>';
    /* the card is docked at the bottom; the page gets that much extra room at its end, so every target can scroll clear of it */
    var card = el.getBoundingClientRect();
    root.classList.add('touring'); root.style.setProperty('--tourpad', Math.ceil(G.innerHeight - card.top + 16) + 'px');
    var tgt = document.querySelector(st.sel);
    if (tgt) {
      tgt.classList.add('tour-on');
      var tabs = document.querySelector('.tabs'), tb = tabs ? tabs.getBoundingClientRect() : null;
      var off = (tb && getComputedStyle(tabs).position === 'sticky' ? tb.height : 0) + 16;
      var r = tgt.getBoundingClientRect();
      if (r.top < off || r.bottom > card.top - 12) G.scrollTo(0, Math.max(0, G.scrollY + r.top - off));
    }
  }
  function tourClear() {
    var c = document.getElementById('tour'), t = document.querySelector('.tour-on');
    if (!c || c.hidden || !t) return null;
    var a = c.getBoundingClientRect(), b = t.getBoundingClientRect();
    return { cardTop: Math.round(a.top), tgtTop: Math.round(b.top), tgtBottom: Math.round(b.bottom), clear: b.bottom <= a.top || (b.top >= 0 && b.top + 40 <= a.top) };
  }
  function tourGo(i) {
    if (i < 0 || i >= STEPS.length) { TI = -1; tourCard(); return; }
    var st = STEPS[i];
    if (st.only && !GAPST[st.only]) i = (TI === i - 1) ? i + 1 : i - 1, st = STEPS[i];
    TI = i; OFFER = false;
    if (st.v === 'promise') CHART = 'bar';
    if (st.approve) GAPSEL = st.approve;
    if (VIEW !== st.v) setView(st.v, true); else render();
    if (st.open) openV('k~' + st.open, true); else closeDr();
    tourCard();
  }

  /* ---------------- render and events ---------------- */
  function render() {
    var y = G.scrollY;
    document.documentElement.lang = LANG;
    document.title = 'Jälki · ' + L2(T['t_' + VIEW]) + ' · ' + L2(T.synth);
    hideTip();
    document.getElementById('app').innerHTML = shell();
    gloss();
    /* (bug b) the static frame follows the language too: drawer, its buttons, the tour dialog, the tooltip */
    var lab = function (id, k) { var e = document.getElementById(id); if (e) e.setAttribute('aria-label', L2(T[k])); };
    lab('dr', 'a_src'); lab('back', 'a_back'); lab('close', 'a_close'); lab('tour', 'a_tour'); lab('drlang', 'a_lang');
    /* the drawer covers the header's language switch (it is full width on a phone), so the drawer carries its own */
    var dl = document.getElementById('drlang');
    if (dl) dl.innerHTML = '<button type="button" data-lang="fi" lang="fi" aria-label="Suomi" aria-pressed="' + (LANG === 'fi') + '">FI</button><button type="button" data-lang="en" lang="en" aria-label="English" aria-pressed="' + (LANG === 'en') + '">EN</button>';
    bind();
    if (STACK.length) drawDrawer();
    if (TI >= 0) tourCard();
    G.scrollTo(0, y);
  }
  /* ---------------- glossary: the first appearance of each term in a view becomes a small button with a one-line meaning ---------------- */
  function gloss() {
    var root = document.getElementById('view'); if (!root) return;
    var done = {};
    root.querySelectorAll('.gt').forEach(function (b) { done[b.getAttribute('data-g')] = 1; });
    var walk = function () {
      var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n;
      while ((n = tw.nextNode())) {
        var pe = n.parentElement;
        if (!pe || pe.closest('button, select, option, svg, .gt, .ai-row, .recl, .qc, .seal')) continue;
        var best = null;
        GORDER.forEach(function (g) { if (done[g]) return; var m = GLOSS[g].re.exec(n.nodeValue); if (m && (!best || m.index < best.i)) best = { g: g, i: m.index, s: m[0] }; });
        if (!best) continue;
        /* in a flex or grid box a bare text node would lose its spaces once split: give it its own inline box first */
        if (/flex|grid/.test(getComputedStyle(pe).display)) { var sp = document.createElement('span'); pe.replaceChild(sp, n); sp.appendChild(n); }
        var after = n.splitText(best.i); after.splitText(best.s.length);
        var b = document.createElement('button'); b.type = 'button'; b.className = 'gt'; b.setAttribute('data-g', best.g); b.setAttribute('aria-describedby', 'tip');
        b.textContent = best.s; after.parentNode.replaceChild(b, after); done[best.g] = 1;
        return true;   /* the tree changed: walk again from the top */
      }
      return false;
    };
    for (var guard = 0; guard < GORDER.length && walk(); guard++) { /* one term per pass */ }
  }
  var TIPFOR = null;
  function showTip(b) {
    var tip = document.getElementById('tip'); if (!tip || !b) return;
    TIPFOR = b; tip.textContent = L2(GLOSS[b.getAttribute('data-g')].t); tip.hidden = false;
    var r = b.getBoundingClientRect(), w = Math.min(320, G.innerWidth - 16);
    tip.style.width = w + 'px';
    var left = Math.max(8, Math.min(G.innerWidth - w - 8, r.left + r.width / 2 - w / 2));
    tip.style.left = left + 'px';
    var th = tip.getBoundingClientRect().height, below = r.bottom + 8;
    tip.style.top = (below + th > G.innerHeight - 8 && r.top - th - 8 > 0 ? r.top - th - 8 : below) + 'px';
    b.setAttribute('aria-expanded', 'true');
  }
  function hideTip() {
    var tip = document.getElementById('tip'); if (tip) tip.hidden = true;
    if (TIPFOR) TIPFOR.setAttribute('aria-expanded', 'false'); TIPFOR = null;
  }
  function setView(v, keepTour) {
    if (VIEWS.indexOf(v) < 0 && v !== 'method') v = 'promise';
    VIEW = v; SAVED = null;
    if (G.location.hash !== '#' + v) { try { G.history.replaceState(null, '', G.location.pathname + (G.location.search || '') + '#' + v); } catch (e) { G.location.hash = v; } }
    render(); G.scrollTo(0, 0);
    if (!keepTour && TI >= 0 && STEPS[TI].v !== v) { TI = -1; tourCard(); }
  }
  function bind() {
    var s = document.getElementById('signer');
    if (s) s.addEventListener('change', function () { SIGNER = s.value; render(); });
    var f = document.getElementById('loadf');
    if (f) f.addEventListener('change', function () {
      var file = f.files[0]; if (!file) return;
      var rd = new FileReader();
      rd.onload = function () { var r = importFile(String(rd.result)); if (r[0]) { document.getElementById('loadmsg').innerHTML = '<span class="redt">' + tx(r[0]) + '</span>'; return; } render(); openV('entry~' + r[1].id, true); };
      rd.readAsText(file);
    });
  }
  function act(a) {
    var p = a.split('~');
    if (p[0] === 'tour') { store('toured', 1); return tourGo(0); }
    if (p[0] === 'sign') { if (!decReady() || !SIGNER) return; var e = addEntry(makePayload(SIGNER)); render(); return openV('entry~' + e.id, true); }
    if (p[0] === 'dl') return download(REG.filter(function (z) { return z.id === p[1]; })[0]);
    if (p[0] === 'approve') {
      var sel = document.querySelector('select[data-apr="' + p[1] + '"]'), en = REG.filter(function (z) { return z.id === p[1]; })[0];
      if (sel && approveRec(en, sel.value)) { render(); openV('entry~' + en.id, true); }
      return;
    }
    if (p[0] === 'test') {
      var r = sealTest(REG.filter(function (z) { return z.id === p[1]; })[0]);
      document.getElementById('testres').innerHTML = '<p class="mono">' + esc(r.factor) + ' ' + esc(String(r.from)) + ' → ' + esc(String(r.to)) + '</p><p class="' + (r.same ? 'redt' : 'ok') + '">' + tx(r.same ? 'rp_fail' : 'rp_broke') + ' <span class="mono dim">' + esc(r.hash) + '</span></p>';
    }
  }
  function onClick(ev) {
    var gt = ev.target.closest ? ev.target.closest('.gt') : null;
    if (gt) { showTip(gt); return; }
    if (TIPFOR && !(ev.target.closest && ev.target.closest('#tip'))) hideTip();
    var t = ev.target.closest ? ev.target.closest('[data-k],[data-v],[data-a],[data-lang],[data-view],[data-year],[data-scen],[data-gap],[data-gapst],[data-ask],[data-dec],[data-dsel],[data-review],[data-q],[data-t],[data-chart]') : null;
    if (!t || t.disabled) return;
    var A = function (n) { return t.getAttribute(n); };
    if (t.hasAttribute('data-t')) {
      var c = A('data-t');
      if (c === 'start') { store('toured', 1); return tourGo(0); }
      if (c === 'no') { store('toured', 1); OFFER = false; render(); var tb = document.querySelector('.tb-tour'); if (tb) tb.focus(); return; }
      if (c === 'close') { store('toured', 1); TI = -1; return tourCard(); }
      if (c === 'next') return tourGo(TI + 1);
      if (c === 'back') return tourGo(TI - 1);
      if (c === 'approve') { var gid = STEPS[TI].approve; GAPST[gid] = { s: 'approved', at: new Date().toISOString() }; store('gap', GAPST); return tourGo(TI + 1); }
    }
    var inDr = !!t.closest('#dr');
    if (t.hasAttribute('data-lang')) {
      var where = inDr ? '#drlang' : '.top .lang';
      LANG = A('data-lang'); store('lang', LANG); render();
      var nb = document.querySelector(where + ' [data-lang=' + LANG + ']'); if (nb) nb.focus({ preventScroll: true });   /* focus stays on the switch */
      return;
    }
    if (t.hasAttribute('data-dsel') && !t.hasAttribute('data-view')) { DECSEL = A('data-dsel'); return render(); }
    if (t.hasAttribute('data-view')) { if (t.hasAttribute('data-dsel')) DECSEL = A('data-dsel'); closeDr(); return setView(A('data-view')); }
    if (t.hasAttribute('data-chart')) { CHART = A('data-chart'); render(); var cb = document.querySelector('[data-chart]'); if (cb) cb.focus(); return; }
    if (t.hasAttribute('data-year')) { YEAR = A('data-year'); return render(); }
    if (t.hasAttribute('data-scen')) { SCEN = A('data-scen'); return render(); }
    if (t.hasAttribute('data-gapst')) {
      var gs = A('data-gapst').split('~');
      if (gs[1] === 'undo') delete GAPST[gs[0]]; else GAPST[gs[0]] = { s: gs[1], at: new Date().toISOString() };
      store('gap', GAPST); return render();
    }
    if (t.hasAttribute('data-gap')) {
      GAPSEL = A('data-gap'); render();
      var gd = document.getElementById('gd'); if (gd && G.innerWidth < 900) gd.scrollIntoView({ block: 'start' });
      return;
    }
    if (t.hasAttribute('data-ask')) {
      var as = A('data-ask').split('~');
      if (as[1] === 'undo') delete ASK[as[0]]; else ASK[as[0]] = { s: as[1], at: new Date().toISOString() };
      store('ask', ASK); return render();
    }
    if (t.hasAttribute('data-dec')) { var dd = A('data-dec').split('~'); DEC[dd[0]] = { o: +dd[1], at: new Date().toISOString() }; store('dec', DEC); if (dd[0] === 'P' && +dd[1] < 2) YEAR = dd[1] === '0' ? '2032' : '2035'; return render(); }
    if (t.hasAttribute('data-review')) { var rv = A('data-review').split('~'); REVIEW[rv[0]] = { choice: rv[1], role: 'Expert reviewer', at: new Date().toISOString() }; store('review', REVIEW); REVI = Math.min(REVI + 1, BLOCK.length - 1); return render(); }
    if (t.hasAttribute('data-q')) {
      var q = A('data-q');
      if (q === 'prev') REVI = Math.max(0, REVI - 1);
      if (q === 'next') REVI = Math.min(BLOCK.length - 1, REVI + 1);
      if (q === 'open') { for (var i = 0; i < BLOCK.length; i++) { var j = (REVI + 1 + i) % BLOCK.length; if (!REVIEW[BLOCK[j].id]) { REVI = j; break; } } }
      return render();
    }
    if (t.hasAttribute('data-a')) return act(A('data-a'));
    if (t.hasAttribute('data-k')) return openV('k~' + A('data-k'), !inDr);
    if (t.hasAttribute('data-v')) return openV(A('data-v'), !inDr);
  }
  function onKey(e) {
    if (e.key === 'Escape' && TIPFOR) { var tf = TIPFOR; hideTip(); if (document.activeElement !== tf) tf.focus({ preventScroll: true }); return; }
    if (e.key === 'Escape') { if (document.getElementById('dr').classList.contains('open')) return closeDr(); if (TI >= 0) { TI = -1; return tourCard(); } }
    var t = e.target;
    if (t && t.getAttribute && t.getAttribute('role') === 'tab' && (e.key === 'ArrowRight' || e.key === 'ArrowLeft' || e.key === 'Home' || e.key === 'End')) {
      var i = VIEWS.indexOf(t.getAttribute('data-view')), n = VIEWS.length;
      i = e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + n) % n;
      setView(VIEWS[i]); var nt = document.getElementById('tab-' + VIEWS[i]); if (nt) nt.focus(); e.preventDefault(); return;
    }
    if (t && t.getAttribute && t.getAttribute('data-k') && t.tagName === 'path' && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openV('k~' + t.getAttribute('data-k'), true); }
    if (document.getElementById('dr').classList.contains('open') && e.key === 'Tab') {
      var f = Array.prototype.filter.call(document.querySelectorAll('#dr button, #dr [tabindex]'), function (x) { return !x.hidden && x.offsetParent !== null; });
      if (f.length) { if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); } }
    }
  }
  function boot() {
    var q = G.location.search || '';
    var ql = (q.match(/[?&]lang=(fi|en)/) || [])[1];
    LANG = ql || load('lang', 'fi');
    ASK = load('ask', {}); GAPST = load('gap', {}); DEC = load('dec', {}); REVIEW = load('review', {});
    REG = (load('reg', []) || []).filter(function (e) { return !recordProblem(e); });
    var hv = (G.location.hash || '').slice(1);
    VIEW = VIEWS.indexOf(hv) >= 0 || hv === 'method' ? hv : 'promise';
    if (DEC.P && DEC.P.o === 1) YEAR = '2035';
    var tq = (q.match(/[?&]tour=(\d+)/) || [])[1];
    OFFER = !tq && !load('toured', 0) && VIEW === 'promise';   /* decided before the first paint: the bar is part of the layout, no shift */
    HINT = !tq && !load('hinted', 0); store('hinted', 1);         /* the tap hint: first visit only, also decided before the first paint */
    render();
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
    /* glossary: hover and keyboard focus show the meaning; leaving hides it; scrolling hides it */
    document.addEventListener('mouseover', function (e) { var g = e.target.closest && e.target.closest('.gt'); if (g && g !== TIPFOR && G.matchMedia('(hover: hover)').matches) showTip(g); });
    document.addEventListener('mouseout', function (e) { var g = e.target.closest && e.target.closest('.gt'); if (g && g === TIPFOR && !(e.relatedTarget && g.contains(e.relatedTarget)) && document.activeElement !== g) hideTip(); });
    document.addEventListener('focusin', function (e) { var g = e.target.closest && e.target.closest('.gt'); if (g) showTip(g); else if (TIPFOR) hideTip(); });
    G.addEventListener('scroll', function () { if (TIPFOR) showTip(TIPFOR); }, { passive: true });   /* the meaning stays next to its word */
    G.addEventListener('resize', function () { if (TIPFOR) showTip(TIPFOR); });
    document.getElementById('close').addEventListener('click', closeDr);
    document.getElementById('scrim').addEventListener('click', closeDr);
    document.getElementById('back').addEventListener('click', function () { if (STACK.length > 1) { STACK.pop(); drawDrawer(); } });
    G.addEventListener('hashchange', function () { var h = (G.location.hash || '').slice(1); if (h && h !== VIEW && (VIEWS.indexOf(h) >= 0 || h === 'method')) setView(h); });
    if (tq) { store('toured', 1); tourGo(Math.max(0, Math.min(STEPS.length - 1, (+tq) - 1))); }
  }
  /* hooks for the headless checks (check.py); the page itself does not use them */
  G.PJA = { NUM: NUM, DECS: DECS, BLOCK: BLOCK, fk: fk, setLang: function (l) { LANG = l; render(); }, setView: setView, decReady: decReady, makePayload: makePayload, addEntry: addEntry,
    approveRec: approveRec, replay: replay, importFile: importFile, fileOf: fileOf, sealTest: sealTest, recordProblem: recordProblem, REG: function () { return REG; },
    decideAll: function (at) { DECS.forEach(function (d) { DEC[d.id] = { o: 0, at: at }; }); BLOCK.forEach(function (r) { REVIEW[r.id] = { choice: 'accept', role: 'Expert reviewer', at: at }; }); render(); },
    setSigner: function (s) { SIGNER = s; render(); }, askLine: function (id) { return askLine(askById(id)); }, gapLine: function (id) { return gapLine(gapById(id)); }, tour: function () { return TI; }, tourClear: tourClear, sha256: sha256, canon: canon,
    T: T, STEPS: STEPS, GLOSS: GLOSS, lang: function () { return LANG; }, state: function () { return { view: VIEW, year: YEAR, scen: SCEN, chart: CHART }; },
    openK: function (k) { openV('k~' + k, true); }, closeDr: closeDr, fnum: fnum, wrapU: wrapU };
  if (typeof document !== 'undefined' && document.getElementById('app')) boot();
})(window);

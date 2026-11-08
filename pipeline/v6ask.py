"""Jälki v6 "Ask the frameworks": the answer bank and its citation check.

The answers were drafted by our AI pipeline (a language model) from the framework texts in the organisers' pack:
data/07_frameworks/framework_digest.md, source_registry.csv, the pack's docs and the lever catalogue. Four of them
re-use the E-track copilot's rubric answers (E30-E39 in stages/e-copilot/E_answers_submission.csv), shortened.
Nothing here is generated at page time.

The check (this script fails the build if any of these breaks):
  1. every quoted passage appears word for word (whitespace-normalised) in the file it cites;
  2. every cited section label appears in that file (a heading, a bold label or a CSV row id);
  3. every source document is either a row of source_registry.csv (its URL is shown) or a name that appears in the
     digest, shown as "named in the digest; no link in the pack";
  4. every E-track answer referenced exists in the E answers file.
Pinpoint clause numbers in the original standards are NOT given: the originals are not in the pack, so the
section shown is the section of the text we hold. That is the honest limit and the expert reviewer checks it.
Run: python3 stages/pj-v8/v6ask.py      Writes stages/pj-v8/ask6.json. Stdlib only.
"""
import csv, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[1]
DIG = 'twin/data/data/07_frameworks/framework_digest.md'
REG = 'twin/data/data/07_frameworks/source_registry.csv'
LEV = 'twin/data/data/05_scenarios/decarbonisation_levers.csv'
METH = 'twin/data/docs/METHODOLOGY.md'
ASSU = 'twin/data/docs/ASSUMPTIONS_AND_LIMITATIONS.md'
NAT = 'twin/data/docs/NATURE_SBTN.md'
BRIEF = 'run/brief.md'
EANS = 'stages/e-copilot/E_answers_submission.csv'
SHOW = {DIG: ['Framework digest (pack, status 3 Nov 2026)', 'Viitekehystiivistelmä (paketti, tilanne 3.11.2026)'],
        LEV: ['Lever catalogue (pack)', 'Keinoluettelo (paketti)'],
        METH: ['Pack methodology', 'Paketin menetelmäkuvaus'],
        ASSU: ['Pack assumptions and limitations', 'Paketin oletukset ja rajoitukset'],
        NAT: ['Pack nature and SBTN note', 'Paketin luonto- ja SBTN-kuvaus'],
        BRIEF: ['Apetit challenge briefing, 6 Nov 2026 (team notes)', 'Apetitin haastebriefing 6.11.2026 (tiimin muistiinpanot)']}
PATH = {DIG: 'data/07_frameworks/framework_digest.md', LEV: 'data/05_scenarios/decarbonisation_levers.csv', METH: 'docs/METHODOLOGY.md',
        ASSU: 'docs/ASSUMPTIONS_AND_LIMITATIONS.md', NAT: 'docs/NATURE_SBTN.md', BRIEF: 'Apetit briefing notes'}
GHG_CORP = 'Corporate Standard / Scope 3 Standard'


def c(file, section, quote):
    return {'file': file, 'section': section, 'quote': quote}


BANK = [
    dict(id='A1', dec=['S'], e_ref=['E39'],
         q=['Does a lower supplier footprint (PCF) count as a reduction?', 'Lasketaanko toimittajan pienempi jalanjälki (PCF) vähennykseksi?'],
         a=['Not by itself. A new or revised PCF changes the data, not the field. The GHG Protocol handles methodology and data changes through base-year recalculation once they pass a significance threshold, not as abatement, and the pack\'s lever catalogue labels the move to supplier-specific data a measurement improvement, not abatement. Count a cut only when field activity changes (nitrogen rate, yield, area) against a like-for-like baseline; re-run a revised PCF on the frozen base and report it on its own line.',
            'Ei sellaisenaan. Uusi tai korjattu PCF muuttaa tietoa, ei peltoa. GHG Protocol käsittelee menetelmä- ja tietomuutokset perusvuoden uudelleenlaskentana, kun ne ylittävät merkittävyysrajan, ei vähennyksinä, ja paketin keinoluettelo kutsuu siirtymää toimittajakohtaiseen dataan mittaamisen parantamiseksi, ei vähennykseksi. Laske vähennys vain, kun peltotoiminta muuttuu (typpimäärä, sato, ala) vertailukelpoiseen lähtötasoon nähden; aja korjattu PCF lukittuun perusvuoteen ja raportoi se omalla rivillään.'],
         kw=['pcf', 'footprint', 'supplier', 'reduction', 'lower', 'revised', 'jalanjälki', 'toimittaja', 'vähennys', 'pienempi'],
         cites=[c(DIG, 'Accounting: GHG Protocol', 'Base-year recalculation after structural changes (acquisitions, divestments) and methodology changes above a significance threshold.'),
                c(LEV, 'L27', 'Spend-based to supplier-specific data (measurement improvement, not abatement)'),
                c(LEV, 'L27', 'reported change is not a real reduction')],
         docs=[GHG_CORP]),
    dict(id='A2', dec=['M'], e_ref=['E32'],
         q=['When must the base year be recalculated?', 'Milloin perusvuosi on laskettava uudelleen?'],
         a=['After a structural change (an acquisition or a divestment) or a methodology change that passes the significance threshold. Apetit\'s briefing puts that threshold at {k:meter.line}. In the pack it is already triggered once: Foodhills was acquired on 27 November 2025, and the pack\'s methodology names that acquisition as a reason to recalculate. The peat method is a methodology change, so The base measures it against the same line. For a new base year, SBTi V2 prefers the most recent year with comprehensive data.',
            'Rakennemuutoksen (yritysosto tai -myynti) tai merkittävyysrajan ylittävän menetelmämuutoksen jälkeen. Apetitin briefingissä raja on {k:meter.line}. Paketissa se on jo lauennut kerran: Foodhills ostettiin 27.11.2025, ja paketin menetelmäkuvaus nimeää oston syyksi laskea uudelleen. Turvemenetelmä on menetelmämuutos, joten Perusvuosi-osio mittaa sen samaa rajaa vasten. Uudeksi perusvuodeksi SBTi V2 suosii viimeisintä vuotta, jolta on kattavat tiedot.'],
         kw=['base', 'year', 'recalculat', 'restat', 'threshold', 'acquisition', 'divest', 'perusvuo', 'uudelleen', 'raja', 'yritysost'],
         cites=[c(DIG, 'Accounting: GHG Protocol', 'Base-year recalculation after structural changes (acquisitions, divestments) and methodology changes above a significance threshold.'),
                c(METH, '1. Organisational boundary and structural changes', 'Because of the acquisition, a base-year recalculation is needed.'),
                c(DIG, 'Climate targets: SBTi', 'V2 prefers the most recent year with comprehensive data as base year'),
                c(BRIEF, 'Base year recalculations', 'Apetit must recalculate its base year (such as a 2025 baseline) under science-based target rules.')],
         docs=[GHG_CORP, 'SBTi Corporate Net-Zero Standard V2.0']),
    dict(id='A3', dec=['L'], e_ref=['E34'],
         q=['Does moving crops off peat count as a FLAG reduction?', 'Lasketaanko viljelyn siirto pois turpeelta FLAG-vähennykseksi?'],
         a=['Only where the land changes. Drained organic soils are FLAG emissions, so they leave our FLAG inventory when our contract crop leaves the parcel. But a drained parcel keeps emitting whoever farms it: under grass the pack\'s method still charges {k:v3.w_grass_t_ha} against {k:v3.w_crop_t_ha} under annual crops. The digest gives no rule that credits a contract move as a cut on the land, so Jälki counts it only on rewetted parcels (decision L) and labels rotation "rotation, not reduction".',
            'Vain kun maa muuttuu. Ojitettujen eloperäisten maiden päästöt ovat FLAG-päästöjä, joten ne poistuvat FLAG-inventaariostamme, kun sopimuskasvimme lähtee lohkolta. Ojitettu lohko päästää kuitenkin edelleen, kuka sitä viljeleekin: nurmella paketin menetelmä laskee yhä {k:v3.w_grass_t_ha} vs. {k:v3.w_crop_t_ha} yksivuotisilla kasveilla. Tiivistelmässä ei ole sääntöä, joka hyvittäisi sopimuksen siirron maan vähennyksenä, joten Jälki laskee sen vain uudelleen soistetuilla lohkoilla (päätös L) ja merkitsee kierron "kierto, ei vähennys".'],
         kw=['peat', 'organic', 'drained', 'moving', 'move', 'crops', 'rotation', 'turve', 'turpeelta', 'siirto', 'ojitet', 'kierto'],
         cites=[c(DIG, 'Climate targets: SBTi', 'FLAG = land-based emissions and removals: on-farm N2O and CH4, drained organic soils, liming, land-use change, soil carbon.'),
                c(METH, '5. Contract-farm footprint', '29.0 t CO2/ha/yr for annual crops (20.9 for grass)'),
                c(LEV, 'L11', 'Shift contract area away from drained organic (peat) soils')],
         docs=['SBTi FLAG']),
    dict(id='A4', dec=['L'], e_ref=['E37'],
         q=['What counts as a removal?', 'Mikä lasketaan poistumaksi?'],
         a=['Under the GHG Protocol Land Sector and Removals Standard (v1.1, effective 1 January 2027), reporting removals is optional, and a removal must be monitored and traceable, with reversals accounted for. The pack models no removals (soil carbon from catch crops is listed as not modelled), so Jälki claims none. The L12 rewetting pilot is counted as lower emissions from drained soil, not as a removal.',
            'GHG Protocolin maankäyttö- ja poistumastandardin (v1.1, voimaan 1.1.2027) mukaan poistumien raportointi on vapaaehtoista, ja poistuman on oltava seurattu ja jäljitettävä, ja sen palautuminen on otettava huomioon. Paketti ei mallinna poistumia (kerääjäkasvien maaperän hiili on mainittu mallintamattomana), joten Jälki ei väitä yhtään. L12-soistuspilotti lasketaan ojitetun maan pienempinä päästöinä, ei poistumana.'],
         kw=['removal', 'removals', 'sequestr', 'carbon', 'rewet', 'catch', 'poistum', 'hiili', 'soist', 'lsr'],
         cites=[c(DIG, 'Land Sector and Removals Standard (LSR)', 'v1.0 January 2026, v1.1 June 2026, effective 1 January 2027.'),
                c(DIG, 'Land Sector and Removals Standard (LSR)', 'removals (optional to report; must be monitored, traceable and reversals accounted for)'),
                c(ASSU, 'Not modelled', 'removals (for example soil carbon from catch crops), which are optional under the GHG Protocol LSR Standard and require monitoring')],
         docs=['GHG Protocol Land Sector and Removals Standard']),
    dict(id='A5', dec=['P'], e_ref=[],
         q=['Which SBTi standard sets our target year?', 'Mikä SBTi-standardi määrää tavoitevuotemme?'],
         a=['Apetit committed in December 2025 and has 24 months to submit. Version 1.3.1 stays usable until the end of 2027; V2.0 takes effect on 1 February 2027 and is mandatory for new and renewed targets from 31 January 2028. V2 asks for five-year near-term targets, which is why 2032 is the recommended target year; 2035 fits V1.3.1\'s window of 5 to 10 years from submission.',
            'Apetit sitoutui joulukuussa 2025, ja sillä on 24 kuukautta aikaa jättää tavoitteet. Versio 1.3.1 on käytettävissä vuoden 2027 loppuun; V2.0 tulee voimaan 1.2.2027 ja on pakollinen uusille ja uusituille tavoitteille 31.1.2028 alkaen. V2 edellyttää viiden vuoden lähiajan tavoitteita, siksi suositeltu tavoitevuosi on 2032; 2035 mahtuu V1.3.1:n 5–10 vuoden ikkunaan jättämisestä.'],
         kw=['sbti', 'version', 'standard', 'target', '2032', '2035', 'submit', 'tavoitevuo', 'versio', 'standardi'],
         cites=[c(DIG, 'Climate targets: SBTi', 'Committed in December 2025 to set near-term targets (24 months to submit).'),
                c(DIG, 'Climate targets: SBTi', 'V1.3.1 remains usable until end-2027; V2 is mandatory for new and renewed targets from 31 January 2028.'),
                c(DIG, 'Climate targets: SBTi', 'V2.0 published 11 June 2026, effective 1 February 2027.'),
                c(DIG, 'Climate targets: SBTi', 'Near-term targets cover 5-10 years from submission (V2: 5 years).')],
         docs=['SBTi Corporate Net-Zero Standard V2.0', 'SBTi CNZS V1.3.1 Method Appendix']),
    dict(id='A6', dec=['P'], e_ref=['E30', 'E31'],
         q=['Do we need a separate FLAG target, and at what pace?', 'Tarvitsemmeko erillisen FLAG-tavoitteen, ja millä vauhdilla?'],
         a=['Yes. SBTi makes a FLAG target mandatory for food production and food and beverage processing companies, whatever their FLAG share, and it comes with a commitment to eliminate deforestation (cut-off no later than 2020). The minimum pace in the V1.3.1 method appendix is {k:rate.flag} a year for FLAG, next to {k:rate.s12} for Scope 1+2 and {k:rate.s3nf} for other Scope 3. That is why the three targets carry separate mandates.',
            'Kyllä. SBTi edellyttää FLAG-tavoitetta elintarviketuotannon sekä elintarvike- ja juomateollisuuden yrityksiltä niiden FLAG-osuudesta riippumatta, ja siihen kuuluu sitoumus lopettaa metsäkato (raja-aika viimeistään 2020). V1.3.1:n menetelmäliitteen vähimmäisvauhti on FLAG:lle {k:rate.flag} vuodessa, Scope 1+2:lle {k:rate.s12} ja muulle Scope 3:lle {k:rate.s3nf}. Siksi kolmella tavoitteella on omat valtuutuksensa.'],
         kw=['flag', 'separate', 'pace', 'rate', 'mandatory', 'deforest', 'erillinen', 'vauhti', 'metsäkato', 'pakollinen'],
         cites=[c(DIG, 'Climate targets: SBTi', 'Mandatory for food production and food & beverage processing companies, and for any company whose FLAG emissions exceed 20 % of the total.'),
                c(DIG, 'Climate targets: SBTi', 'Requires a commitment to eliminate deforestation, with a cut-off date no later than 2020'),
                c(DIG, 'Minimum ambition (V1.3.1 method appendix)', 'Scope 1+2: 4.2 %/yr linear (1.5 C). Scope 3: 2.5 %/yr (well-below 2 C). FLAG: 3.03 %/yr.')],
         docs=['SBTi FLAG', 'SBTi CNZS V1.3.1 Method Appendix']),
    dict(id='A7', dec=[], where='nature', e_ref=['E38'],
         q=['Which SBTN step ranks our catchments, and on what?', 'Mikä SBTN-vaihe asettaa valuma-alueemme järjestykseen, ja millä perusteella?'],
         a=['Step 2, interpret and prioritise: pressure times the state of nature. For freshwater quality, SBTN targets the limiting nutrient at sub-basin level, often phosphorus in Finnish lakes. This fold ranks catchments on phosphorus reaching water per tonne harvested and shows each catchment\'s ecological status beside it. Setting a target is step 3.',
            'Vaihe 2, tulkinta ja priorisointi: paine kertaa luonnon tila. Vedenlaadussa SBTN kohdistaa tavoitteet rajoittavaan ravinteeseen osavaluma-aluetasolla, Suomen järvissä usein fosforiin. Tämä osio järjestää valuma-alueet vesiin päätyvän fosforin mukaan korjattua tonnia kohden ja näyttää kunkin ekologisen tilan rinnalla. Tavoitteen asettaminen on vaihe 3.'],
         kw=['sbtn', 'catchment', 'nature', 'phosphorus', 'lake', 'eutroph', 'water', 'nutrient', 'valuma', 'fosfor', 'järv', 'rehevöi', 'luonto', 'ravin'],
         cites=[c(DIG, 'Nature: SBTN, TNFD, ESRS', '2 interpret & prioritise (pressure x state of nature)'),
                c(DIG, 'Freshwater quality', 'Nutrient targets focus on the limiting nutrient (often phosphorus in Finnish lakes) at sub-basin level'),
                c(NAT, 'Mapping to SBTN steps', 'Freshwater quality: the limiting nutrient in Finnish lakes is often phosphorus.')],
         docs=['SBTN Step 2 technical guidance v1.1']),
]


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('**', '')).strip()


texts = {}


def text(f):
    if f not in texts:
        texts[f] = norm((R / f).read_text(encoding='utf-8'))
    return texts[f]


reg = {r['source']: r for r in csv.DictReader(open(R / REG, encoding='utf-8'))}
eids = {r[0] for r in csv.reader(open(R / EANS, encoding='utf-8')) if r}
bad = []
n_quotes = 0
for b in BANK:
    for ci in b['cites']:
        t = text(ci['file'])
        if ci['file'] == LEV:
            row = [l for l in (R / LEV).read_text(encoding='utf-8').splitlines() if l.startswith(ci['section'] + ',')]
            ok_s = len(row) == 1
            ok_q = ok_s and norm(ci['quote']) in norm(row[0])
        else:
            ok_s = norm(ci['section']) in t
            ok_q = norm(ci['quote']) in t
        n_quotes += 1
        if not (ok_s and ok_q):
            bad.append((b['id'], ci['file'], ci['section'], ok_s, ok_q, ci['quote'][:60]))
        ci['show'] = SHOW[ci['file']]
        ci['path'] = PATH[ci['file']]
    sd = []
    for d in b['docs']:
        if d in reg:
            sd.append({'name': d, 'url': reg[d]['url'], 'in_registry': True})
        elif norm(d) in text(DIG):
            sd.append({'name': 'GHG Protocol ' + d, 'url': None, 'in_registry': False})
        else:
            bad.append((b['id'], 'doc', d))
    b['docs'] = sd
    for e in b['e_ref']:
        if e not in eids:
            bad.append((b['id'], 'e_ref', e))
    b.setdefault('where', 'gate')
if bad:
    for x in bad:
        print('CITATION CHECK FAILED', x)
    raise SystemExit(1)
out = {'synthetic_only': True, 'script': 'python3 stages/pj-v8/v6ask.py', 'n': len(BANK), 'n_quotes': n_quotes,
       'check': 'every quote found word for word in its cited file; every section label found; every source document in the registry or named in the digest',
       'bank': BANK}
(HERE / 'ask6.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print('ASK CHECK PASS:', len(BANK), 'answers,', n_quotes, 'quoted passages verified in', len(texts), 'files;',
      sum(1 for b in BANK for d in b['docs'] if d['in_registry']), 'registry links,', sum(1 for b in BANK for d in b['docs'] if not d['in_registry']), 'digest-named without link')

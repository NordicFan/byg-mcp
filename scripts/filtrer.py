"""Filtrering af datakilder.csv -> datakilder_filtreret.csv.
Regler (i rækkefølge): eksplicitte beslutninger > kommerciel > aftale/login > ingen H > fragmenteret/verificér > MVP."""
import csv, sys
src, dst = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(src, encoding='utf-8'), delimiter=';'))

EXPLICIT = {
 'A03': ('Frasorteret', 'Lukket i 2026 - erstattet af DAR via Datafordeleren (A02)'),
 'G01': ('Frasorteret', 'FBB lukket medio 2026 - erstattes af nyt statsligt system (fredede) og G02 (bevaringsværdige)'),
 'I08': ('Frasorteret', 'Fødevaredata - ikke byggevarer'),
 'A09': ('MVP', 'Hjælpekilde: kommune/myndighed for et sted - bruges internt af andre værktøjer'),
 'B06': ('MVP', 'Hjælpekilde: baggrundskort til kortudsnit'),
 'H01': ('MVP', 'Kernekilde trods manglende API - scrapes til egen versioneret vidensbase'),
 'I01': ('MVP', 'Grænseværdier og generiske data er få tabeller - kan vedligeholdes manuelt'),
 'E04': ('MVP', 'Simple filer pr. vejrstation - lav indsats, høj værdi for simulering'),
 'E03': ('Fase 2', 'Overlapper E04 - DMI-filer tilføjes hvis EPW ikke er tilstrækkeligt'),
 'D06': ('Fase 2', 'Ingen API og BR18 kræver radonsikring generelt - lav merværdi'),
 'H03': ('Fase 2', 'Høj værdi men tung scraping og fortolkning'),
 'H04': ('Fase 2', 'Primært regler via Retsinformation (H02) - vejledninger senere'),
 'I03': ('Fase 2', 'Vejledningstekst - indgår i vidensbasen efter BR18'),
 'I02': ('Fase 2', 'Filformat-integration (LCAbyg JSON) - efter datalaget er på plads'),
 'I09': ('Parkeret', 'Manualer er kommercielle - ingen API'),
 'J06': ('Fase 2', 'PDF-tabeller - værdifulde ved renovering men kræver udtræk'),
 'G03': ('Fase 2', 'Moderat relevans - fortidsmindebeskyttelseslinjen dækkes allerede af C03'),
 'M01': ('Fase 2', 'Byggeomkostningsindeks nyttigt for konstruktører - simpelt API, ikke kernefunktion'),
 'C05': ('MVP', 'Åben WMS/WFS og høj relevans - kun kortlægningsrunden skal verificeres'),
 'D05': ('MVP', 'WMS og download er åbne - API-delen verificeres undervejs'),
 'M04': ('Fase 2', 'Kun web/PDF - erfaringsviden til vidensbasen senere'),
 'J04': ('Fase 2', 'Filer med begrænset kerneværdi - tilføjes med energimodulet'),
 'I07': ('Fase 2', 'Primært nordamerikansk datagrundlag - ECO Portal og ÖKOBAUDAT dækker BR18-behov'),
}
COMMERCIAL = ('Kommerciel',)
AGREEMENT = ('Aftale', 'Login', 'Uklart', 'Delvist beskyttet')
FRAGMENT = ('Fragmenteret', 'Verificér', 'verificér', 'Afklar')

for r in rows:
    i = r['id']; has_h = 'H' in (r['arkitekt'], r['ingenioer'], r['konstruktoer'])
    if i in EXPLICIT: fase, why = EXPLICIT[i]
    elif r['adgang'].startswith(COMMERCIAL): fase, why = 'Parkeret', 'Kommerciel licens - kun henvisninger indtil licens er afklaret'
    elif r['adgang'].startswith(AGREEMENT): fase, why = 'Fase 2', 'Kræver aftale, login eller afklaring af adgang'
    elif not has_h: fase, why = 'Parkeret', 'Ingen høj relevans for nogen rolle'
    elif any(r['status'].startswith(f) or f in r['status'] for f in FRAGMENT) or 'verificér' in r['teknik'].lower():
        fase, why = 'Fase 2', 'Fragmenteret eller uverificeret adgang - skal afklares først'
    else: fase, why = 'MVP', 'Høj relevans og åben, stabil adgang'
    r['fase'], r['begrundelse'] = fase, why

fields = list(rows[0].keys())
with open(dst, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, delimiter=';'); w.writeheader(); w.writerows(rows)
from collections import Counter
print(Counter(r['fase'] for r in rows))
for fase in ('MVP','Fase 2','Parkeret','Frasorteret'):
    print(f'\n== {fase}')
    for r in rows:
        if r['fase']==fase: print(f"{r['id']} | {r['navn']} | {r['begrundelse']}")

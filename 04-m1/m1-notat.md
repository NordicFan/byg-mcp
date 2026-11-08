# M1-notat: sted og bygning

*8. november 2026. Mål: ID-kæden adresse → husnummer → jordstykke → BFE → BBR, med cache og kildeangivelse.*

## Resultat

- `sted_find` tager adresse, matrikel, BFE-nummer eller koordinat og returnerer ejendommen: BFE, alle jordstykker (matrikelnr., ejerlav, registreret areal, vejareal), samlet grundareal og noteringer om fredskov, strandbeskyttelse og klitfredning.
- `bygning_bbr` (nyt) returnerer bygningerne på ejendommen med koder oversat via BBR's officielle kodelister, valgfrit med etager, samt indikatorer for bebyggelsesprocent.
- Cachen ligger nu i SQLite (`data/cache.sqlite`) og overlever genstart.
- 20 tests består: 6 enhedstests og 14 live-tests.

Eksempel: Bispensgade 3, Aalborg → matr. 220 Aalborg Bygrunde, BFE 5539730, 608 m² → etageboligbygning fra 2023, 3 etager, 1.676 m², mursten, fibercementtag, fjernvarme.

## Vigtigste tekniske fund

1. **De almindelige registertjenester (DAR/v3, BBR/v3, MAT/v3) kræver et objekt-ID.** Man kan ikke spørge "alle bygninger på jordstykke X".
2. **Løsningen er `FlexibleCurrent/v3`.** Den kræver kun `virkningstid` og tillader filtre på relationer (fx `BBR_Bygning.jordstykke`) og geografi (`intersects` med WKT). `in`-filtre tager op til 100 værdier. Hele kæden kører gennem den.
3. **gsearch har ressourcerne `husnummer` og `matrikel`.** De giver direkte husnummer-ID og jordstykke-ID/BFE, så første led i kæden kan springes over.
4. **gsearch er fuzzy.** Findes den søgte adresse ikke, returneres den nærmeste: "Nørre Allé 1" bliver til "Nørre Allé 11", og "Hovedgaden 1, Roskilde" bliver til en adresse i Gundsømagle. Svar markeres derfor med `match: eksakt/usikkert` og en advarsel.
5. **BBR-kodelister** findes på teknik.bbr.dk som HTML og hentes med `scripts/hent_bbr_kodelister.py` til JSON (19 lister).
6. **BBR har historiske bygninger.** Nedrevne og fejlregistrerede bygninger (livscyklus 9, 10, 11, 14) udelades som standard. Bispensgade 3 har fx kontorbygningen fra 1917 som "Historisk".

## Sikkerhedshændelse og rettelse

- **Hvad skete der:** httpx logger forespørgsler med fuld URL på INFO-niveau, og MCP-SDK'et aktiverer INFO-logning. Begge nøgler står i URL'en, fordi kilderne kræver det. Under en røgtest blev **begge nøgler skrevet i fuld længde** i sessionens output. Tidligere var en del af Datafordeler-nøglen også kommet med i en fejlbesked.
- **Rettet:** `infra/logging.py` dæmper httpx/httpcore til WARNING og maskerer `apiKey=`, `token=`, `password=` og `username=` i alle logbeskeder. Datafordeler-fejl indeholder aldrig URL'en. Cache-nøgler indeholder aldrig hemmeligheder. Begge dele er dækket af enhedstests.
- **Anbefaling:** Lav nye nøgler hos begge udbydere, og slet de gamle (se nedenfor).

## Kendte begrænsninger

- Bebyggelsesprocenten er en **indikator** ud fra BBR's samlede bygningsareal. Den er ikke beregnet efter BR18's regler.
- BBR's bebyggede areal kan overstige grundarealet (fx 624 m² på en grund på 608 m²), hvis registreringen dækker flere grunde eller udhæng.
- Ejerlejligheder vises som et flag (`opdelt_i_ejerlejligheder`), men de enkelte lejligheder slås ikke op.
- Bygninger på fremmed grund findes kun, hvis de har en jordstykke- eller husnummerreference.
- Uden Datafordeler-nøgle virker `sted_find` kun med koordinater fra OpenStreetMap, uden ejendomsdata.

## Næste: M2

`plan_laes_lokalplan` (PDF-udtræk) og udvidelse af `restriktioner` med jordforurening (V1/V2), støj, strandbeskyttelse og fortidsminder.

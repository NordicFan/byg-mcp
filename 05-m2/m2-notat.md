# M2-notat: plan og restriktioner

*8. november 2026. Mål: læse lokalplanens bestemmelser og samle restriktioner fra alle relevante kilder.*

## Resultat

- **`plan_laes_lokalplan` (nyt):** henter lokalplanens PDF fra Plandata, finder bestemmelserne og deler dem op i nummererede bestemmelser med underpunkter og sidetal. Kan filtreres på emne. Resultatet caches i 30 dage.
- **`restriktioner` (udvidet)** samler nu fem kilder i ét kald:
  - Arealinformation (bygge-/beskyttelseslinjer, fredninger, § 3, Natura 2000, områdeklassificering, grundvand)
  - DKjord (V1/V2 med link til jordforureningsattest)
  - Miljøstyrelsens støjkortlægning (Lden 1,5 m fra vej, jernbane, virksomheder, lufthavne)
  - Fund og Fortidsminder (fredede fortidsminder og beskyttelseslinjer)
  - Matriklen (strandbeskyttelse, klitfredning, fredskov)
- **Fejltekster når frem til modellen.** Forventede fejl, fx ugyldig koordinat eller ejendom der ikke findes, sendes som `ToolError` med forklaring. Før blev de skjult som "Error executing tool".
- 26 tests består: 9 enhedstests og 17 live-tests.

Eksempel: Bispensgade 3, Aalborg →
- Lokalplan 1-1-143, emne "højde" → **5.2 Bebyggelsens omfang** (maks. 4 etager mod Bispensgade, 3 mod Cortesgyde), **5.4 Højder** og **5.5 Altaner**, med sidetal
- Restriktioner → områdeklassificering, **inden for fortidsmindebeskyttelseslinjen** omkring et herregårdsanlæg/slot (Aalborghus). Lokalplanen nævner selv, at realiseringen kræver dispensation fra den.

## Tekniske fund

1. **Miljøportalens katalog-API giver tjeneste-URL'erne**, når man spørger med `include=wfsSource,wmsSource,wmtsSource`. Det var nøglen til at finde DKjord, fortidsminder og matrikellag. Metadataposter på geodata-info.dk havde dem ikke.
2. **BBOX er upålideligt.** Flere GeoServere har "loose bbox" slået til og returnerer objekter, hvis omsluttende rektangel rammer punktet. For støj gav det fx flere modstridende dB-intervaller. Alle punktopslag bruger nu `CQL_FILTER=INTERSECTS(geom, POINT(x y))`, og ved radius `DWITHIN`.
3. **Geometrifelter varierer:** `geometri` (Plandata), `Shape` (Arealinformation), `Fladegeometri` (DKjord), `wkb_geometry` (støj) og `geom` (fortidsminder).
4. **Støjlagene er heterogene.** Nogle har `db_low/db_high`, lufthavne har `lden_min/lden_max`, og jernbane/virksomheder har kun klasseindekset `noise_in`. Indekset er afledt ud fra lag med begge felter (5 = 55–59 dB … 1 = 75+ dB) og markeres som "afledt". Jernbanebåndene ligger inden i hinanden, så det højeste bånd bruges. **Vej er kortlagt 2022, jernbane 2017.** Året vises i svaret.
5. **Miljøportalen har lagt sin egen Datafordeler-nøgle offentligt** i katalogets URL'er til Matrikel-WFS. Den bruges ikke. Strandbeskyttelse og klitfredning hentes i stedet som matrikelnoteringer med vores egen nøgle.
6. **Lokalplaner findes i to formater.** Digitale planer bruger "5. Overskrift / 5.1 Underpunkt / Ad 5.1", ældre bruger "§ 5 / Stk. 1". Parseren genkender begge. Indholdsfortegnelsen springes over ved at kræve brødtekst mellem overskrifterne og vælge den seneste fortløbende serie.
7. **PDF-udtræk med pypdf** (BSD-licens) frem for PyMuPDF (AGPL), så projektet kan være open source uden licensproblemer.

## Sikkerhed

- `plan_laes_lokalplan` henter kun fra `https://dokument.plandata.dk`. Vilkårlige URL'er afvises, så modellen ikke kan bruges til at hente fra andre servere. PDF'er er begrænset til 60 MB.

## Fejlrettelse undervejs

- Et kontroltegn (backspace i stedet for `\b`) var sneget sig ind i emnefilterets regex via en shell-heredoc. Det gav tomme resultater. Det er fundet og rettet, og der er nu en enhedstest for ordstart-match.

## Kendte begrænsninger

- **Kortbilag kan ikke læses.** Byggefelter, højdekoter på kort og illustrationer kommer ikke med. Byggefelter findes dog som geometri i `plan_gaeldende`.
- Emnefilteret er nøgleordsbaseret og kan give falske positiver. Hele bestemmelsen kan altid hentes uden emne.
- Lokalplaner med usædvanligt layout kan give `format: ukendt`. Så returneres en advarsel og link til PDF'en.
- Støjkortlægningen er strategisk og erstatter ikke en konkret støjberegning efter Miljøstyrelsens vejledning.
- Bevaringsværdige bygninger (efter FBB-lukningen) er ikke med endnu. Status skal undersøges (fase 2).

## Næste: M3

Grund og terræn plus grundrapport. Jordartskort og boringer (GEUS), terrænkoter (Danmarks Højdemodel), kortudsnit (ortofoto/skråfoto) og det samlede `grundrapport`-værktøj med prompten `grundscreening`.

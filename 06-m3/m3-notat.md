# M3-notat: terræn, jord og grundrapport

*8. november 2026. Mål: terræn, geologi, grundvand og kort, samlet i én grundrapport til tidlig fase.*

## Resultat

Fire nye værktøjer og én prompt:

| Værktøj | Indhold |
|---|---|
| `terraen` | Kote i punktet, min/maks/middel og højdeforskel inden for matrikelgrænsen, middelhældning, højde over terræn på grunden og i 30 m-zonen omkring den |
| `jord_geologi` | Jordart (GEUS 1:25.000 og 1:200.000), nærmeste boringer (dybde, formål, år, terrænkote, jordlagssymboler, seneste vandstand, link til borerapport), terrænnært grundvand vinter/sommer (HIP) |
| `kort_udsnit` | Ortofoto eller skyggekort som billede direkte i svaret plus link til skråfoto |
| `grundrapport` | Samler ejendom, bygninger, plangrundlag, restriktioner, terræn og jord/grundvand parallelt (< 2 sek.) |
| Prompt `grundscreening` | Fører modellen gennem rapport → lokalplanens bestemmelser → struktureret screening med kilder |

33 tests består: 14 enhedstests og 19 live-tests. Ingen nøgler i logs over stdio (kontrolleret).

Eksempel: Strandvejen 200A, Snekkersten →
- To matrikler (2.217 m²), hvoraf 305 m² med strandbeskyttelse
- Villa fra 1936
- Lokalplan "Det gamle Snekkersten": bebyggelsesprocent 30, maks. 2 etager og 8,5 m
- 6,2 m terrænfald på grunden (12,5 % middelhældning)
- Saltvandsgrus

## Tekniske fund

1. **Datafordelerens DHMKoter-REST er udfaset** (403). Højdedata hentes i stedet fra Dataforsyningens WCS (`dhm_wcs_DAF`). Den leverer kun GeoTIFF og læses med `tifffile` og `numpy`. Både terræn (DTM) og overflade (DSM) ligger i 0,4 m.
2. **Højde over terræn = DSM − DTM.** Det giver en brugbar indikator for nabobebyggelsens og træernes højde, men skelner ikke mellem dem.
3. **GEUS' jordartskort er flyttet** fra MapServer (`geusmap/ows`) til ArcGIS (`data.geus.dk/arcgis/rest/services/Denmark/Jordartskort_25000`). Det blev igen fundet via Miljøportalens katalog-API. Jupiter-boringerne ligger stadig på MapServer-WFS'en.
4. **Byområder er ikke kortlagt** på jordartskortet ("BY – Byområde"). Svaret siger det og henviser til boringerne.
5. **HIP-grundvand** findes kun som WMS. GetFeatureInfo giver kun `text/plain`. Værdierne fortolkes som **centimeter**, fx 145 = 1,45 m ved Aalborg havnefront, 2,8 m over havet. Fortolkningen er plausibel, men ikke bekræftet i dokumentation. Kontrollér den, før dybderne bruges til dimensionering.
6. **I Jupiter betyder dybde 0 og år 0 "ikke registreret".** Felterne udelades.
7. **Ortofoto-billeder hentes med vores token, men kun billedet sendes videre.** URL'en med tokenet når aldrig modellen. Skråfoto-linket indeholder ikke token.
8. **Miljøportalen offentliggør endnu en nøgle**, et Dataforsyningen-token, i katalogets HIP-URL'er. Den bruges ikke.

## Kendte begrænsninger

- `terraen` uden Datafordeler-nøgle bruger en cirkel med radius 10 m i stedet for matrikelgrænsen.
- Hældningen er et gennemsnit over grunden. Lokale skrænter kan være væsentligt stejlere.
- Jordlagssymbolerne (fx "l,s") er grove. Den fulde lagfølge står i borerapporten (link).
- Grundvandsdybden er modelleret (10 m-grid) og erstatter ikke pejlinger på grunden.
- Servitutter (tinglysning) indgår ikke i grundrapporten endnu (fase 2).

## Status på arkitekturens milepæle

| Milepæl | Status |
|---|---|
| M0 Spike | ✅ |
| M1 Sted og bygning | ✅ |
| M2 Plan og restriktioner | ✅ |
| M3 Grundrapport | ✅ **Første brugbare version for praktikere** |
| M4 Regler (BR18-vidensbase) | Næste |
| M5 Klima, LCA og BIM | |
| M6 Fase 2-kilder (tinglysning, energimærker, bevaringsværdige bygninger, nævnsafgørelser) | |

# M5-notat: klima, energi, LCA og BIM

*8. november 2026. Mål: datagrundlag til energi, indeklima, LCA og BIM i tidlig fase.*

## Resultat

Seks nye værktøjer. MCP'en har nu **21 værktøjer, 2 prompts og 2 ressourcer**, og alle **17 kilder** melder "ok" i `kilde_status`.

| Værktøj | Indhold | Kilde |
|---|---|---|
| `klima_data` | 18 klimaparametre for kommunen over 1–30 år: temperatur, graddage, årsnedbør, største 30-min.-regn, vind/vindstød, sol, stråling, fugt, sommerdage, tropenætter, frost, sne | DMI (nøglefri) |
| `sol_og_pv` | Årsproduktion, kWh/kWp, månedsfordeling, indstråling, optimal eller valgt hældning/orientering, horisont fra terrænmodel | PVGIS 5.3 |
| `vejrfil` | EPW (TMY) som link og lokal fil | PVGIS 5.3 |
| `el_co2` | CO2 for el nu og seneste dage (DK1/DK2 findes ud fra stedet) + BR18 tabel 8.1 (el, fjernvarme, gas) inkl. 50-års middel | Energinet, BR18 |
| `lca_materiale` | GWP (A1-A3, C3, C4, D) pr. deklareret enhed fra BR18's generiske datagrundlag (507 datasæt) og/eller ÖKOBAUDAT-EPD'er | BR18 bilag 2 tabel 7, ÖKOBAUDAT |
| `bim_klassifikation` | Søgning i CCI (Molio), IFC 4.3 og DTU's BR18-bygningsdele + egenskabssæt for en klasse | bSDD |

51 tests: 50 består, og 1 springes over, når Energinet begrænser antallet af kald. Der er ingen nøgler i logs over stdio.

Eksempler:
- Aalborg, 2021–2025: middeltemperatur 9,2 °C, ca. 2.900 graddage, største 30-min.-regn 34 mm
- 6 kWp mod sydøst (30°) i Snekkersten: 5.447 kWh/år (908 kWh/kWp)
- "beton c25" → Fabriksbeton C25/30: 241 kg CO₂e/m³ (A1–A3)
- BR18 emissionsfaktor for el 2026: 0,071 kg CO₂e/kWh. 50-års middel fra 2026: 0,029.

## Fund

1. **BR18's generiske LCA-data (bilag 2, tabel 7) findes som Excel** på bygningsreglementet.dk. Filnavnet skifter med versionen, så scriptet finder linket på bilagssiden. Tabellen indeholder 132 danske generiske datasæt (AAU/BUILD), 38 branche-EPD'er, 322 generiske tyske datasæt og 15 standardværdier for installationer.
2. **Tabel 8.1 indeholder fremskrevne emissionsfaktorer pr. år** (2025–2049) for el, fjernvarme og gas. Det er dem, BR18 kræver til driftsenergien (B6). De fremgår ikke af selve paragrafteksten.
3. **bSDD har en dansk ordbog fra DTU** over BR18 bilag 2, tabel 6 (bygningsdele til LCA) med kobling til IFC. **CCI** (Molio) findes kun med engelske navne.
4. **bSDD's ordbogsfilter er ikke strikt.** Søgning i DTU's BR18-ordbog gav også en anden DTU-ordbog, så der filtreres på klientsiden.
5. **Rate-limiting:** bSDD og Energinet svarede 429 under test. Alle kilder får nu ét genforsøg efter pause (`Retry-After`, maks. 5 sek.), og ellers en forståelig fejl til modellen. Energinet-kald rundes til hele timer, så cachen genbruges.
6. **DMI's årsværdier** kan pga. tidszone komme med for det igangværende år. Der filtreres eksplicit på perioden.
7. **ÖKOBAUDAT er på tysk og engelsk.** Danske søgeord oversættes med en ordliste (beton → Beton, mineraluld → Mineralwolle …).

## Kendte begrænsninger

- **DMI klimaatlas** (klimafremskrivninger) er ikke med. Kun målte værdier.
- **DRY** (Design Reference Year), som Be18 kræver, er ikke med. `vejrfil` giver PVGIS-TMY til simulering og gør tydeligt opmærksom på forskellen.
- **50-års middelemissionsfaktoren er en forenkling** til tidlig fase. Tabellen slutter i 2049, og senere år er sat til sidste værdi. Den erstatter ikke en LCAbyg-beregning.
- PVGIS medregner terrænhorisont, men ikke skygge fra bygninger og træer.
- **EPD Danmark og ECO Platform** er ikke koblet direkte på. Danske branche-EPD'er indgår dog i BR18's tabel 7.
- CCI-søgning kræver engelske ord.

## Status

| Milepæl | Status |
|---|---|
| M0–M3 Sted, bygning, plan, restriktioner, terræn, jord, grundrapport | ✅ |
| M4 Regler (BR18 + love) | ✅ (BR-vejledninger mangler) |
| M5 Klima, energi, LCA, BIM | ✅ |
| M4b BR-vejledninger | Forslag |
| M6 Fase 2-kilder: tinglysning/servitutter, energimærker, bevaringsværdige bygninger, nævnsafgørelser | Kræver aftaler/afklaring |

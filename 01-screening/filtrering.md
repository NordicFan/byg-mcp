# Filtrering af datakilder

*Fase 2 af screeningen. 7. november 2026. Grundlag: [datakilder.csv](datakilder.csv) (101 kilder).*
*Resultat med fase og begrundelse pr. kilde: [datakilder_filtreret.csv](datakilder_filtreret.csv). Reglerne ligger i [filtrer.py](../scripts/filtrer.py) og kan køres igen, når listen ændres.*

## Resultat

| Fase | Antal | Betydning |
|---|---|---|
| **MVP** | 39 | Bygges i første version: høj relevans og åben, stabil adgang |
| **Fase 2** | 29 | Relevant, men kræver aftale, login, scraping eller afklaring |
| **Parkeret** | 30 | Lav relevans for alle tre roller, eller kommerciel licens |
| **Frasorteret** | 3 | Lukket eller irrelevant: DAWA, FBB, Concito-klimadatabasen |

## Regler (anvendt i rækkefølge)

1. **Eksplicitte beslutninger** med begrundelse, fx BR18 med i MVP trods manglende API.
2. **Kommerciel licens:** parkeret. MCP'en kan henvise til kilden, men ikke levere indholdet.
3. **Aftale, login eller uklar adgang:** fase 2.
4. **Ingen høj relevans for nogen rolle:** parkeret.
5. **Fragmenteret eller uverificeret adgang:** fase 2.
6. **Resten** (høj relevans plus åben adgang): MVP.

## MVP: 39 kilder fordelt på 9 værktøjsgrupper

Grupperne er et første bud på, hvordan MCP'ens værktøjer kan skæres. Hver gruppe svarer på et konkret spørgsmål fra praksis.

| # | Værktøjsgruppe | Spørgsmål den besvarer | Kilder |
|---|---|---|---|
| 1 | **Stedsopslag** | "Hvilken ejendom, matrikel og kommune er det?" | Datafordeleren (P01), DAR (A02), Matriklen (A04), DAGI (A09) |
| 2 | **Eksisterende bygning** | "Hvad står der i dag?" | BBR (A01) |
| 3 | **Plangrundlag** | "Hvad må jeg bygge her?" | Plandata (C01), zonestatus (C02), beskyttelseslinjer (C03), Arealinformation (D01), støjkort (C05) |
| 4 | **Grund og jord** | "Hvordan er jorden, grundvandet og forureningen?" | DKjord (D02), Jupiter (D03), geologiske kort (D04), HIP (D05), okker/OSD (D10), kystdata (D08), historiske kort (B05) |
| 5 | **Terræn og kort** | "Hvordan ser grunden og omgivelserne ud?" | Dataforsyningen (P02), GeoDanmark (B01), højdemodel (B02), ortofoto (B03), skråfoto (B04), skærmkort (B06), fikspunkter (B10) |
| 6 | **Klima og energi-input** | "Hvilke klimadata skal jeg regne med?" | DMI Open Data (E01), Klimaatlas (E02), EPW-filer (E04), PVGIS (E05), Energi Data Service (F02) |
| 7 | **Regler** | "Hvilke krav gælder?" | BR18 (H01), Retsinformation (H02), BR18-klimakrav (I01), IKT-bekendtgørelsen (L04) |
| 8 | **Materialer og LCA** | "Hvad er klimaaftrykket af materialet?" | ECO Portal (I05), ÖKOBAUDAT (I06) |
| 9 | **Produkter og BIM** | "Hvordan klassificeres og specificeres det?" | bSDD (L01), CCI via bSDD (L02), IFC/IDS (L03), EPREL (J03) |

**Kombineret "grundrapport":** grupperne 1–5 kan samles i ét værktøj. Det tager en adresse og returnerer matrikel, bygninger, plangrundlag, restriktioner, jord og terræn. Det er sandsynligvis den mest værdifulde enkeltfunktion for alle tre roller.

## Fase 2: 29 kilder

**Høj prioritet, kræver afklaring:**
- **Tinglysning (A07):** servitutter er afgørende for, hvad der må bygges, men kræver system-til-system-aftale.
- **Bevaringsværdige bygninger (G02)** og FBB's statslige afløser for fredede bygninger. Status skal undersøges, da FBB er lukket.
- **Energimærker (J01):** kræver henvendelse til Energistyrelsen.
- **Nævnsafgørelser (H03):** høj værdi til fortolkning, men tung scraping.
- **Kommunale byggesagsarkiver (A10):** fragmenteret, ingen fælles API.

**Øvrige:** EBR/EJF (A05), 3D-bymodeller (B07), radonkort (D06), DRY-filer (E03), skybrudskort (E06), LER (F01), varmeplanlægning (F04), Rejseplanen (F05), spildevandsplaner (F07), Fund og Fortidsminder (G03), Arbejdstilsynet (H04), LCAbyg (I02), Videncenter for klima (I03), EPD Danmark (I04), EC3 (I07), Svanemærket (I10), Indeklimamærket (I12), vinduesmærkning (J05), standardværdikatalog (J06), varmepumpeliste (J04), Byggeskadefonden (M04), Statistikbanken (M01), Byg og Miljø (N01), Jordweb (N02).

## Parkeret: 30 kilder

**Kommerciel licens (7):** Dansk Standard, BUILD-anvisninger, Byg-Erfa, DBI, Be18, Molio prisdata, DGNB. De kan blive relevante, hvis der kommer en licensaftale, fx via en organisation eller uddannelsesinstitution.

**Lav relevans (23):** fx CVR, ejendomsvurdering, OpenStreetMap, vejbyggelinjer, lufthavnsbegrænsninger, artsdata (bilag IV), EUR-Lex, Høringsportalen, udbudsportaler og BIM-platforme (Speckle/APS).

## Grænsetilfælde at tage stilling til

| Kilde | Nuværende placering | Argument for at flytte |
|---|---|---|
| Artsdata/bilag IV (D07) | Parkeret | Flagermus er ofte et problem ved renovering og nedrivning |
| Vejbyggelinjer (C06) | Parkeret | Kan være afgørende for byggefeltet langs større veje |
| Høringsportalen (H11) | Parkeret | Nyttig til at opdage kommende ændringer i BR18 |
| Tinglysning (A07) | Fase 2 | Servitutter hører naturligt til i "grundrapporten" |
| BUILD-anvisninger (H06) | Parkeret | Hvis I har licens (fx via UCN), er de centrale for BR18-fortolkning |

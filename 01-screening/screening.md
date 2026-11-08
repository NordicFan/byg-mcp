# Screening: datakilder for bygningsdesignere i Danmark

*Fase 1 – bred indsamling (uden frasortering). Udarbejdet 7. november 2026.*

**Målgruppe:** arkitekter (A), ingeniører (I) og bygningskonstruktører (K).
**Omfang:** 101 kilder i 14 kategorier. Den fulde, filtrerbare liste ligger i [datakilder.csv](datakilder.csv) (Excel-version: [datakilder_excel.csv](datakilder_excel.csv)).

Relevans pr. rolle er angivet som H/M/L (høj/middel/lav) i rækkefølgen A/I/K. Det er et første skøn, som skal justeres i filtreringsfasen.

## Hovedfund

1. **Datafordeleren er rygraden.** BBR, adresser (DAR), matrikel, ejerforhold, vurdering, CVR og GeoDanmark ligger samme sted. Platformen er midt i en modernisering, hvor REST-tjenesterne udfases til fordel for GraphQL. MCP'en bør bygges direkte på GraphQL.
2. **DAWA er lukket (2026).** Det gamle nøglefri adresse-API må ikke bruges. Kilderne er uenige om datoen (1. juli eller 1. oktober 2026). Adresseopslag skal gå via Datafordeleren, og Klimadatastyrelsen har annonceret et nyt "Adressevælgeren"-API til autocomplete.
3. **FBB lukkes medio 2026.** Fredede bygninger flyttes til et nyt statsligt system. Data om bevaringsværdige bygninger overdrages til kommunerne (sandsynligvis GeoFA). Den kilde skal følges tæt, fordi den er afgørende ved renovering.
4. **Plandata.dk har maskinlæsbar geometri, men bestemmelserne ligger som PDF.** Bebyggelsesprocent, højder og anvendelse står som tekst i lokalplanerne. Det kræver PDF-udtræk eller sprogmodel-parsing, og det er en af de mest værdifulde funktioner, MCP'en kan levere.
5. **De vigtigste regelkilder har ingen API.** BR18 og vejledningerne, Dansk Standard, BUILD-anvisninger, Byg-Erfa og Molio skal enten scrapes (åbne kilder) eller kræver licens (kommercielle). BR18 er åbent og bør struktureres som en egen vidensbase med versionsstyring. Klimakravene blev skærpet 1. juli 2025 og skærpes igen i 2027 og 2029.
6. **Retsinformation har et åbent API**, og der findes allerede en MCP-server ([dk-eli-mcp](https://pypi.org/project/dk-eli-mcp)), som kan genbruges eller bruges som inspiration.
7. **DMI kræver ikke længere API-nøgle** (fra 2. december 2025, via opendataapi.dmi.dk).
8. **Huller uden åben adgang:** energimærker (EMO), Byg og Miljø, tinglyste servitutter og LER kræver aftaler, login eller henvendelse. Noteret som "afklar adgang".
9. **Der findes ingen eksisterende MCP for danske bygge- og geodata.** Søgningen fandt ingen.

## Adgangsprofil (overblik)

| Adgang | Typiske kilder | Betydning for MCP |
|---|---|---|
| Åben, nøglefri | DMI, Retsinformation, PVGIS, Arealinformation, Plandata WFS, GEUS | Kan bygges straks |
| Åben med gratis bruger/token | Datafordeleren, Dataforsyningen, CVR, EC3, EPREL | Kræver konfiguration af nøgler |
| Aftale/login | Tinglysning, LER, Byg og Miljø, Rejseplanen | Senere fase, juridisk afklaring |
| Kommerciel licens | Dansk Standard, BUILD, Byg-Erfa, Molio, DBI | Kun henvisninger, med mindre der er licens |
| Ingen API (web/PDF) | BR18, nævnsafgørelser, vejledninger | Scraping og egen vidensbase |

## Forslag til filtreringskriterier (næste fase)

1. **Relevans:** mindst ét H for en af de tre roller.
2. **Adgang:** åben eller gratis bruger i første version. Kommercielle kilder parkeres.
3. **Stabilitet:** kilder under lukning eller ombygning (DAWA, FBB, Datafordeler-REST) bygges kun på den nye løsning.
4. **Værdi pr. indsats:** kilder, der svarer på et konkret spørgsmål ("hvad må jeg bygge her?"), prioriteres over generiske datasæt.
5. **Fejlkilder:** fx I08 (Concito-klimadatabasen handler om fødevarer, ikke byggevarer) frasorteres.

**Bemærk:** Status og URL'er for kilder markeret "verificér" er ikke bekræftet og skal tjekkes, før der bygges på dem.

## Kildeoversigt pr. kategori

### Platform (2)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| P01 | [Datafordeleren](https://datafordeler.dk) | Fælles distributionsplatform for grunddata: BBR, DAR, MAT, EBR, EJF, VUR, CVR, DAGI, GeoDanmark, DHM m.fl. | H/H/H | Åben (gratis bruger) - visse data beskyttede | GraphQL (moderniseret) + REST (udfases) + filudtræk + hændelser | Modernisering i gang 2025-26 - REST migreres til entitetsbaseret GraphQL |
| P02 | [Dataforsyningen](https://dataforsyningen.dk) | Kort- og geodatatjenester (WMS/WMTS/WFS/WCS) og filudtræk: skærmkort, ortofoto, skråfoto, højdemodel, historiske kort | H/H/H | Åben (gratis token) | WMS/WMTS/WFS/WCS + REST + filer | Aktiv - DAWA-delen er lukket (se A03) |

### Ejendom og bygning (10)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| A01 | [BBR - Bygnings- og Boligregistret](https://datafordeler.dk/dataoversigt/bygnings-og-boligregistret-bbr/) | Bygninger og enheder: anvendelse, opførelses-/ombygningsår, etager, arealer, ydervæg/tagmateriale, varme- og vandforsyning, byggesager | H/H/H | Åben (Datafordeler-bruger) | GraphQL /BBR/v1 + REST | Aktiv - REST udfases til fordel for GraphQL |
| A02 | [DAR - Danmarks Adresseregister](https://datafordeler.dk) | Adresser, adgangsadresser, vejnavne, husnumre, adressepunkter | H/H/H | Åben (Datafordeler-bruger) | GraphQL + REST | Aktiv - datamodel 1.0 (DAWA brugte 0.9) |
| A03 | [DAWA - Danmarks Adressers Web API](https://confluence.sdfi.dk/display/DML/Mapning+fra+DAWA+til+Datafordeleren) | Tidligere nøglefri adresse/autocomplete-API | H/H/H | Lukket | REST | LUKKET 2026 (1/7 eller 1/10 - kilder uenige). Erstatning: Datafordeler GraphQL + kommende 'Adressevælgeren' |
| A04 | [Matriklen (MAT)](https://datafordeler.dk) | Jordstykker, matrikelkort, registreret areal, vejareal, noteringer (fredskov, strandbeskyttelse, klitfredning), samlet fast ejendom | H/H/H | Åben (Datafordeler-bruger) | GraphQL + REST + WFS | Aktiv |
| A05 | [EBR og Ejerfortegnelsen (EJF)](https://datafordeler.dk) | Ejendomsbeliggenhed (BFE-nummer) og ejere/administratorer | M/L/M | Delvist beskyttet (personoplysninger kræver særlig adgang) | GraphQL + REST | Aktiv |
| A06 | [Ejendomsvurdering (VUR)](https://datafordeler.dk) | Ejendoms- og grundværdier, vurderingsgrundlag | L/L/M | Åben (Datafordeler-bruger) | GraphQL + REST | Aktiv |
| A07 | [Tinglysning (e-TL) - servitutter og deklarationer](https://www.tinglysning.dk) | Tinglyste servitutter: byggelinjer, højde-/bebyggelsesbegrænsninger, tilslutningspligt, deklarationer | H/M/H | Aftale/certifikat (system-til-system) - opslag via tinglysning.dk | SOAP/REST system-til-system + PDF-akter | Aktiv - servitutter ofte kun som scannede PDF'er |
| A08 | [CVR - Det Centrale Virksomhedsregister](https://datacvr.virk.dk) | Virksomheder: rådgivere, entreprenører, producenter, branchekoder | L/L/M | Åben (gratis bruger til distribution) | Elasticsearch-API (distribution.virk.dk) + Datafordeler | Aktiv |
| A09 | [DAGI - administrative grænser](https://dataforsyningen.dk) | Kommuner, regioner, sogne, postnumre, retskredse, opstillingskredse | M/M/M | Åben | REST/GraphQL + WFS | Aktiv |
| A10 | [Kommunale byggesagsarkiver (Weblager m.fl.)](https://www.weblager.dk) | Historiske byggetegninger, tilladelser, ibrugtagningstilladelser | H/H/H | Varierer - ofte åbent opslag pr. kommune | Ingen fælles API - weblager.dk + kommunale portaler | Fragmenteret - kræver kommune-specifik scraping |

### Kort og geodata (10)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| B01 | [GeoDanmark vektordata](https://dataforsyningen.dk) | Bygningsflader, veje, fortove, søer, vandløb, beplantning, tekniske anlæg | H/H/H | Åben | WFS + filer (GeoPackage) + Datafordeler | Aktiv |
| B02 | [Danmarks Højdemodel (DHM)](https://dataforsyningen.dk/data/930) | Terræn- og overflademodel (0,4 m), punktsky, kurver, højdeopslag pr. punkt | H/H/H | Åben | WCS/WMS + REST højdeopslag + filer (GeoTIFF/LAZ) | Aktiv |
| B03 | [Ortofoto (forår/sommer)](https://dataforsyningen.dk) | Luftfoto i høj opløsning, årlige optagelser | H/M/H | Åben | WMS/WMTS | Aktiv |
| B04 | [Skråfoto](https://skraafoto.dataforsyningen.dk) | Skråbilleder fra fire retninger | H/M/H | Åben (token) | STAC REST-API (skraafoto-api) + viewer | Aktiv |
| B05 | [Historiske kort (målebordsblade m.fl.)](https://dataforsyningen.dk) | Historiske topografiske kort ca. 1800-1990 | M/H/M | Åben | WMS/WMTS | Aktiv |
| B06 | [Topografiske skærmkort](https://dataforsyningen.dk) | Baggrundskort i flere stilarter | M/M/M | Åben (token) | WMTS | Aktiv |
| B07 | [3D bymodeller (København m.fl.)](https://www.kk.dk/erhverv/kort-og-data) | 3D-modeller af bygninger (CityGML/IFC/SketchUp) | H/M/M | Varierer - ofte åben download | Filer - ingen fælles API | Fragmenteret - kun visse kommuner |
| B08 | [Opendata.dk (kommunale åbne data)](https://www.opendata.dk) | Kommunale datasæt: træer, parkering, skoler, støj, byggeprojekter mv. | M/M/M | Åben | CKAN REST-API | Aktiv - kvalitet varierer pr. kommune |
| B09 | [OpenStreetMap / Overpass API](https://overpass-api.de) | Bygninger, POI, stier, servicefunktioner | M/L/L | Åben (fair use) | REST (Overpass) + Nominatim | Aktiv |
| B10 | [Fikspunktsregistret](https://dataforsyningen.dk) | Geodætiske fikspunkter med koter | L/M/H | Åben | WFS/REST | Aktiv |

### Planlægning (8)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| C01 | [Plandata.dk](https://www.plandata.dk) | Lokalplaner (inkl. delområder og PDF), kommuneplanrammer, zonestatus, landsplandirektiver, byggefelter m.m. | H/H/H | Åben | WFS (geoserver.plandata.dk) + REST + PDF | Aktiv - bestemmelser ligger primært som PDF-tekst |
| C02 | [Zonestatus (by-/land-/sommerhuszone)](https://www.plandata.dk) | Zoneafgrænsning | H/M/H | Åben | WFS | Aktiv |
| C03 | [Beskyttelseslinjer (strand, klit, sø/å, skov, kirke, fortidsminde)](https://arealinformation.miljoeportal.dk) | Byggelinjer efter naturbeskyttelsesloven §§ 15-19 | H/M/H | Åben | WMS/WFS | Aktiv |
| C04 | [Kystnærhedszone og planlovens særlige zoner](https://arealinformation.miljoeportal.dk) | Kystnærhedszone, områder til byudvikling | M/L/M | Åben | WMS/WFS | Aktiv |
| C05 | [Støjkortlægning (vej, jernbane, lufthavn)](https://mst.dk/erhverv/rent-miljoe-og-sikker-forsyning/stoej) | Strategisk støjkortlægning (Lden) - opdateres hvert 5. år | H/H/M | Åben | WMS/WFS | Aktiv - verificér seneste kortlægningsrunde |
| C06 | [Vejbyggelinjer og vejplaner](https://www.vejdirektoratet.dk) | Byggelinjer langs statsveje og kommuneveje | M/M/M | Varierer | WMS + tinglysning | Verificér datatilgængelighed |
| C07 | [Hindringsflader og højdebegrænsninger ved lufthavne](https://www.trafikstyrelsen.dk) | Højdebegrænsninger, radar- og indflyvningszoner | M/M/L | Varierer | Ingen kendt åben API | Verificér |
| C08 | [Landsplandirektiver og Fingerplanen](https://www.plandata.dk) | Overordnet planlægning (fx stationsnærhed i hovedstadsområdet) | M/L/L | Åben | Plandata WFS + PDF | Aktiv |

### Natur, miljø og jord (10)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| D01 | [Danmarks Arealinformation](https://arealinformation.miljoeportal.dk) | Samlet kortportal: § 3-natur, Natura 2000, fredninger, OSD, drikkevandsinteresser, beskyttelseslinjer m.m. | H/H/H | Åben | WMS/WFS | Aktiv |
| D02 | [DKjord - jordforurening](https://www.miljoeportal.dk) | Kortlagte grunde (V1/V2), områdeklassificering (lettere forurenet byjord) | H/H/H | Åben | WFS + REST | Aktiv |
| D03 | [Jupiter - boringsdatabasen](https://www.geus.dk/produkter-ydelser-og-faciliteter/data-og-kort/national-boringsdatabase-jupiter) | Boringer med jordlagsbeskrivelser, vandstand, vandkemi | M/H/H | Åben | WMS/WFS + database-download + REST | Aktiv |
| D04 | [Geologiske kort (jordartskort 1:25.000/1:200.000)](https://www.geus.dk) | Overfladenære jordarter, prækvartær, Danmarks digitale geologiske kort | L/H/M | Åben | WMS/WFS | Aktiv |
| D05 | [HIP - Hydrologisk Informations- og Prognosesystem](https://hip.dataforsyningen.dk) | Terrænnær grundvandsstand nu og i fremtidens klima, vandløbsdata | M/H/H | Åben | WMS + datadownload + API (verificér) | Aktiv |
| D06 | [Radonkort](https://www.sst.dk/da/radon) | Radonrisiko pr. område | L/M/H | Åben | Kortviser - ingen kendt API | Lav prioritet - BR18 kræver radonsikring generelt |
| D07 | [Naturdatabasen og artsdata (bilag IV)](https://naturdata.miljoeportal.dk) | Naturbesigtigelser, beskyttede arter (fx flagermus, markfirben) | M/M/M | Åben | REST/OData API | Aktiv |
| D08 | [Kystatlas og kystdata](https://kyst.dk) | Højvandsstatistik, kysterosion, stormflodsrisiko | M/H/M | Åben | WMS + filer | Aktiv |
| D09 | [MiljøGIS (vandområdeplaner m.fl.)](https://miljoegis.mim.dk) | Vandområdeplaner, Natura 2000-planer, nitratdata | L/M/L | Åben | WMS/WFS | Aktiv |
| D10 | [Okker- og grundvandsbeskyttelsesområder](https://arealinformation.miljoeportal.dk) | OSD, indvindingsoplande, okkerpotentiale | L/H/M | Åben | WMS/WFS | Aktiv |

### Klima og vejr (7)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| E01 | [DMI Open Data API](https://opendatadocs.dmi.govcloud.dk) | Meteorologiske observationer, klimadata (døgn/time), prognoser (EDR), radar, lyn | M/H/M | Åben - ingen API-nøgle fra 2/12-2025 (fair use) | REST (OGC API Features/EDR) | Aktiv - brug opendataapi.dmi.dk |
| E02 | [DMI Klimaatlas](https://www.dmi.dk/klimaatlas) | Klimafremskrivninger pr. kommune: nedbør, ekstremregn, havniveau, temperatur | M/H/M | Åben | Download + kortviser | Aktiv |
| E03 | [Design Reference Year (DRY) / vejrdatafiler](https://www.dmi.dk) | Referenceår til energi- og indeklimasimulering | M/H/M | Åben | Filer | Aktiv |
| E04 | [EPW-vejrfiler (climate.onebuilding.org)](https://climate.onebuilding.org) | EPW-filer for danske stationer | H/H/L | Åben | Filer | Aktiv |
| E05 | [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/) | Solindstråling, PV-ydelse, horisontprofil, TMY | H/H/M | Åben | REST | Aktiv |
| E06 | [Skybruds-/bluespotkortlægning](https://scalgo.com/da-DK/live) | Lavninger og strømningsveje ved skybrud | H/H/H | Åben (KDS) / kommerciel (SCALGO Live) | WMS / web | Verificér konkret KDS-tjeneste |
| E07 | [Copernicus Climate Data Store (ERA5 m.fl.)](https://cds.climate.copernicus.eu) | Reanalyse- og klimadata globalt | L/M/L | Åben (gratis bruger) | REST (cdsapi) | Aktiv |

### Forsyning og infrastruktur (7)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| F01 | [LER 2.0 - Ledningsejerregistret](https://ler.dk) | Ledningsoplysninger (el, vand, gas, fjernvarme, tele, kloak) | L/H/H | Login (MitID Erhverv) - system-til-system API | REST/SOAP API | Aktiv - kræver registrering |
| F02 | [Energi Data Service](https://www.energidataservice.dk) | Elpriser, CO2-emission fra elproduktion (time), produktionsmix | M/H/L | Åben | REST | Aktiv |
| F03 | [Fjernvarmepriser og -statistik](https://forsyningstilsynet.dk) | Fjernvarmepriser pr. værk | L/M/M | Åben | Filer (Excel) | Aktiv |
| F04 | [Varmeplanlægning / forsyningsområder](https://ens.dk) | Fjernvarme- og naturgasområder, tilslutningspligt | M/H/M | Varierer | Plandata/kommunale WMS - ingen samlet API | Fragmenteret - verificér |
| F05 | [Rejseplanen API](https://labs.rejseplanen.dk) | Kollektiv trafik: stoppesteder, afgange, rejsetider | M/L/L | Aftale (gratis for ikke-kommercielle) | REST | Aktiv - verificér nye vilkår |
| F06 | [Vejdirektoratets åbne data (trafiktal m.fl.)](https://www.vejdirektoratet.dk) | Trafiktal (ÅDT), vejnet, trafikinformation | L/M/L | Åben | REST/WFS + filer | Aktiv |
| F07 | [Spildevandsplaner og kloakopland](https://www.plandata.dk) | Separat-/fælleskloakering, afløbskoefficienter | L/H/M | Varierer | Plandata/kommunale WMS | Fragmenteret |

### Kulturarv (4)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| G01 | [FBB - Fredede og Bevaringsværdige Bygninger](https://www.kulturarv.dk/fbb) | Fredede bygninger og SAVE-registrerede bevaringsværdige bygninger | H/M/H | Åben | Web + WMS (verificér) | LUKKES medio 2026 - nyt statsligt system kun for fredede - bevaringsværdige overdrages til kommunerne |
| G02 | [Bevaringsværdige bygninger i GeoFA / kommunale data](https://www.geodanmark.dk) | Kommunale registreringer af bevaringsværdige bygninger efter FBB-lukning | H/M/H | Åben (forventet) | WFS (GeoFA) - verificér | Ny kilde - status skal følges |
| G03 | [Fund og Fortidsminder](https://www.kulturarv.dk/fundogfortidsminder) | Fortidsminder, fredede fortidsminder, arkæologiske fund | M/M/M | Åben | WMS/WFS + download | Aktiv |
| G04 | [Kulturmiljøer og kirkeomgivelser](https://www.plandata.dk) | Værdifulde kulturmiljøer (kommuneplan), kirkeomgivelser | M/L/L | Åben | Plandata WFS + Arealinformation | Aktiv |

### Lov og regler (12)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| H01 | [Bygningsreglementet BR18 + vejledninger](https://www.bygningsreglementet.dk) | Alle bygningstekniske krav: brand, konstruktioner, energi, indeklima, lyd, tilgængelighed, LCA/klimakrav (skærpet 1/7-2025) | H/H/H | Åben | Ingen officiel API - web (bygningsreglementet.dk) + BEK på Retsinformation | Aktiv - skal scrapes/struktureres - versionsstyring vigtig |
| H02 | [Retsinformation API](https://www.retsinformation.dk/offentlig/vejledning/Retsinformation%20REST%20API%20vejledning%20v1.pdf) | Love og bekendtgørelser: byggeloven, planloven, BR18-BEK, naturbeskyttelsesloven, miljøbeskyttelsesloven, energimærkning, arbejdsmiljø m.fl. | H/H/H | Åben (nøglefri) | REST harvest-API + ELI (XML/LexDania) + Atom-feed | Aktiv - harvest kun 03-23:45 og rate limit. Eksisterende MCP: dk-eli-mcp |
| H03 | [Afgørelser: Planklagenævnet / Byggeklageenheden / Miljø- og Fødevareklagenævnet](https://naevneneshus.dk) | Praksis og fortolkning af plan-, bygge- og miljøregler | H/M/H | Åben | Web-søgning - ingen kendt API | Scraping nødvendig |
| H04 | [Arbejdstilsynet - regler og AT-vejledninger](https://at.dk) | Projekterendes og rådgivers pligter, bygherrens pligter, PSS/PSP, byggepladsregler | M/M/H | Åben | Web - ingen API (BEK via Retsinformation) | Aktiv |
| H05 | [Dansk Standard (Eurocodes + DK NA, DS 418, DS 447, DS 490, DS/EN 16798 m.fl.)](https://www.ds.dk) | Beregnings- og produktstandarder | M/H/H | Kommerciel | Ingen åben API - webshop/metadata | Kun metadata/henvisninger realistisk |
| H06 | [BUILD-anvisninger (tidl. SBi-anvisninger)](https://build.dk) | Anvisninger der uddyber BR18 (fx tilgængelighed, fugt, brand, lyd) | H/H/H | Kommerciel (abonnement) - nogle gratis | Web - ingen API | Licensforhold skal afklares |
| H07 | [Byg-Erfa erfaringsblade](https://byg-erfa.dk) | Erfaringsblade om byggetekniske detaljer og skader | M/M/H | Kommerciel | Web - ingen API | Licens |
| H08 | [Vejregler](https://www.vejregler.dk) | Regler for veje, stier, parkering, belysning | M/M/M | Åben | Web/PDF - ingen API | Aktiv |
| H09 | [Certificerede statikere og brandrådgivere](https://bpst.dk) | Register over certificerede rådgivere og klasser | L/M/M | Åben | Web-liste | Verificér kilde |
| H10 | [EUR-Lex (CPR, EPBD, taksonomi m.fl.)](https://eur-lex.europa.eu) | EU-retsakter og ELI | M/M/M | Åben | SPARQL + REST + ELI | Aktiv |
| H11 | [Høringsportalen](https://hoeringsportalen.dk) | Lovudkast og bekendtgørelser i høring | M/M/M | Åben | Web + RSS (verificér) | Aktiv |
| H12 | [DBI-vejledninger (brand)](https://brandogsikring.dk) | Brandtekniske vejledninger (ABA, flugtvejsbelysning m.m.) | M/H/M | Kommerciel | Web - ingen API | Licens |

### Bæredygtighed og LCA (12)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| I01 | [BR18 klimakrav og generiske data (bilag 2 tabel 7)](https://www.bygningsreglementet.dk) | Grænseværdier (fx 7,1 kg CO2e/m²/år fra 2025 - skærpes 2027/2029), generiske data, emissionsfaktorer for energi | H/H/H | Åben | Tabeller/web - ingen API | Aktiv - grænseværdier skal holdes opdateret |
| I02 | [LCAbyg + datagrundlag](https://www.lcabyg.dk) | LCA-værktøj til BR18, generiske data, JSON-projektformat | H/H/H | Åben (gratis værktøj) | Desktop + filformat (JSON) - ingen web-API | Aktiv |
| I03 | [Videncenter for Bygningers Klimapåvirkning](https://byggeriogklima.dk) | Vejledninger, obligatorisk LCA-rapporteringsformat, guides til rådgivere | H/H/H | Åben | Web/PDF | Aktiv |
| I04 | [EPD Danmark](https://www.epddanmark.dk) | Danske EPD'er for byggevarer | H/H/H | Åben | Web + digitale EPD'er via ECO Platform (verificér API) | Aktiv |
| I05 | [ECO Platform - ECO Portal](https://www.eco-platform.org) | Samlet portal for europæiske digitale EPD'er (ILCD+EPD) | H/H/H | Åben | soda4LCA REST-API | Aktiv |
| I06 | [ÖKOBAUDAT](https://www.oekobaudat.de) | Tysk LCA-database - grundlag for BR18's generiske data | H/H/H | Åben | soda4LCA REST-API | Aktiv |
| I07 | [EC3 (Building Transparency)](https://buildingtransparency.org) | Global EPD-database med sammenligning af materialer | H/H/M | Åben (gratis bruger) | REST-API | Aktiv |
| I08 | [Den Store Klimadatabase](https://denstoreklimadatabase.dk) | Klimaaftryk for fødevarer - IKKE byggevarer | L/L/L | Åben | Download | Frasorteringskandidat |
| I09 | [DGNB Danmark / Green Building Council](https://www.dk-gbc.dk) | DGNB-kriterier, Bæredygtighedsklassen, certificerede projekter | H/H/M | Delvist åben - manualer kommercielle | Web - ingen API | Verificér |
| I10 | [Svanemærket byggeri og produkter](https://www.ecolabel.dk) | Svanemærkede byggevarer og krav til svanemærket byggeri | M/M/H | Åben | Web (produktsøgning) - API verificér | Verificér |
| I11 | [EU Ecolabel og EU-taksonomien (Taxonomy Compass)](https://ec.europa.eu/sustainable-finance-taxonomy) | Miljømærkede produkter og tekniske screeningskriterier for byggeri | M/M/M | Åben | Download/REST (verificér) | Aktiv |
| I12 | [Dansk Indeklima Mærkning](https://www.teknologisk.dk/indeklimamaerket) | Indeklimamærkede byggevarer (afgasning) | M/M/H | Åben | Web-liste - ingen API | Verificér |

### Energi (6)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| J01 | [Energimærker (EMO-databasen)](https://sparenergi.dk) | Energimærker for eksisterende bygninger (>1,1 mio.), forbedringsforslag | H/H/H | Uklart - opslag via SparEnergi.dk | Ingen dokumenteret åben API - kræver henvendelse | Afklar adgang med ENS |
| J02 | [Be18 (energiberegning)](https://be18.dk) | Beregning af energiramme efter BR18 | H/H/H | Kommerciel licens | Desktop + XML-filformat | Kun filintegration |
| J03 | [EPREL - EU's produktregister for energimærkning](https://eprel.ec.europa.eu) | Energimærkede produkter: varmepumper, ventilation, vandvarmere, lyskilder | M/H/M | Åben (API-nøgle) | REST | Aktiv |
| J04 | [Energistyrelsens varmepumpeliste og teknologikataloger](https://ens.dk) | Godkendte varmepumper, teknologidata for forsyning | L/H/M | Åben | Filer | Aktiv |
| J05 | [Energimærkning af vinduer](https://www.energimaerkning.dk) | Energimærkede vinduer og glas (Eref, U-værdier) | H/M/H | Åben | Web - verificér API | Verificér |
| J06 | [Standardværdikatalog og Håndbog for Energikonsulenter](https://ens.dk) | Standardværdier for eksisterende konstruktioner og installationer | M/H/H | Åben | PDF/web | Aktiv |

### BIM og klassifikation (6)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| L01 | [buildingSMART Data Dictionary (bSDD)](https://search.bsdd.buildingsmart.org) | IFC-klasser, egenskaber og klassifikationer - inkl. CCI (Molio) | H/H/H | Åben | REST + GraphQL | Aktiv |
| L02 | [CCI/CCS og Molio-egenskaber](https://molio.dk) | Dansk klassifikation, egenskabsdata, BIM7AA-vejledninger | H/H/H | Delvist åben (via bSDD) / kommerciel | bSDD + Molio-værktøjer | Aktiv |
| L03 | [IFC og IDS-specifikationer](https://technical.buildingsmart.org) | Åbne skemaer for BIM og informationskrav | M/H/H | Åben | Specifikationer + open source-værktøjer (IfcOpenShell, ifctester) | Aktiv |
| L04 | [IKT-bekendtgørelsen og bips-standarder](https://www.retsinformation.dk) | Krav til IKT i offentligt byggeri, IKT-ydelsesspecifikation | M/M/H | Åben (BEK) / delvist kommerciel | Retsinformation + web | Aktiv |
| L05 | [Molio prisdata og beskrivelsesværktøj](https://molio.dk) | Byggepriser (V&S prisbøger), udbudsbeskrivelser | M/M/H | Kommerciel | Web/værktøjer - API verificér | Licens |
| L06 | [Speckle / Autodesk Platform Services / BCF-API](https://speckle.systems) | Adgang til BIM-modeller og issues | M/M/M | Åben/kommerciel | REST/GraphQL | Værktøjsintegration - senere fase |

### Marked og statistik (5)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| M01 | [Danmarks Statistik - Statistikbanken API](https://www.dst.dk/da/Statistik/brug-statistikken/muligheder-i-statistikbanken/api) | Byggeomkostningsindeks, byggeaktivitet, boligbestand, befolkning | M/M/H | Åben | REST (api.statbank.dk) | Aktiv |
| M02 | [TED - Tenders Electronic Daily](https://ted.europa.eu) | EU-udbud og arkitektkonkurrencer | M/M/M | Åben | REST API v3 | Aktiv |
| M03 | [Udbud.dk / danske udbudsportaler](https://udbud.dk) | Danske offentlige udbud | M/M/M | Åben | Web/RSS - verificér | Verificér nuværende platform |
| M04 | [Byggeskadefonden](https://www.bsf.dk) | Svigtrapporter, erfaringsformidling fra alment byggeri | M/M/H | Åben | Web/PDF | Aktiv |
| M05 | [BEC - Byggeriets Evaluerings Center](https://www.byggeriets-evaluerings-center.dk) | Nøgletal for byggesagers kvalitet og tid | L/L/M | Delvist åben | Web | Lav prioritet |

### Byggesag og myndighed (2)

| ID | Kilde | Indhold | A/I/K | Adgang | Teknik | Status |
|---|---|---|---|---|---|---|
| N01 | [Byg og Miljø](https://bygogmiljoe.dk) | Digital byggeansøgning og sagsforløb | H/M/H | Login (MitID) - integration for systemer findes | Ingen dokumenteret åben API | Afklar med KOMBIT |
| N02 | [Jordflytning (Jordweb)](https://www.jordweb.dk) | Anmeldelse af jordflytning | L/M/H | Login | Web | Lav prioritet |
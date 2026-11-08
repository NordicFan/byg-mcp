# M0-notat: spike-resultater

*7. november 2026. Formål: afklare adgang til de tre kernekilder og få et kørende MCP-skelet.*

## Resultat

En kørende MCP-server med 4 værktøjer. Den virker **uden nøgler** for plan, restriktioner og adressesøgning (via OpenStreetMap som reserve). 6 live-tests består, og serveren starter over stdio.

Eksempel: Bispensgade 3, Aalborg →
- Byzone
- Lokalplan 1-1-143 "Bolig og erhverv, Bispensgade 3": delområde med **maks. 4 etager og 12,5 m bygningshøjde**, link til PDF
- Kommuneplanramme 1.1.C1: maks. 6 etager
- Områdeklassificering (lettere forurenet byjord)

## Hvad spiken afklarede

### Plandata.dk: virker, nøglefri
- WFS: `https://geoserver.plandata.dk/geoserver/wfs`. Geometrifeltet hedder `geometri`. Punktopslag med `CQL_FILTER=INTERSECTS(geometri,POINT(x y))` i EPSG:25832.
- **Fund:** kommuneplanrammer skal hentes fra `theme_pdk_kommuneplanramme_alle_vedtaget_v`. Det almindelige lag mangler rammer fra kommuneplantillæg.
- **Positivt fund:** lokalplandelområder og kommuneplanrammer har ofte strukturerede felter (`maxetager`, `maxbygnhjd`, `bebygpct`). Så er PDF-læsning ikke altid nødvendig for nøgletallene.

### Danmarks Arealinformation: virker delvist, nøglefri
- Arealinformation er flyttet til en ny app (danmarksarealinformation.miljoeportal.dk). De gamle ArcGIS-adresser omdirigerer.
- WFS: `https://arealeditering-dist-geo.miljoeportal.dk/geoserver/wfs`, workspace `dai` med 25 lag. **BBOX-filter virker.** Geometrifeltets navn er ikke standard, så CQL-intersects er ikke brugt.
- **Mangler:** jordforurening V1/V2, støj, strandbeskyttelse, klitfredning og fortidsminder ligger ikke i `dai`. Miljøportalens datakatalog-API (`datakatalog.miljoeportal.dk/api/datasets`, 1.511 datasæt) indeholder dem, men giver ikke tjeneste-URL'er. Det skal løses i M2.

### Datafordeleren: kræver API-nøgle
- GraphQL: `https://graphql.datafordeler.dk/<register>/<version>` (fx `BBR/v1`, `DAR/v1`). Skema på `/schema`.
- Auth: `?apiKey=<nøgle>` fra et **IT-system** oprettet i Datafordelerens selvbetjening. Uden nøgle: HTTP 401.
- Den gamle REST-tjeneste svarede HTTP 500 ved test.
- Adapteren er skrevet, men **ikke testet**, fordi der ingen nøgle er.

### Adresser: DAWA er lukket
- `api.dataforsyningen.dk/adresser` svarer **HTTP 410 Gone** (bekræftet).
- Dataforsyningens gsearch kræver token. Adapteren er skrevet, men svarformatet er **ikke verificeret**.
- Reserve: OpenStreetMap Nominatim (fair use, max 1 kald/sek, licens ODbL). Svaret markeres tydeligt som ikke-officielt.

### MCP SDK
- Den installerede `mcp` er version 2.3. `FastMCP` hedder nu `MCPServer` (`mcp.server.mcpserver`). Koden er skrevet til v2.

## Opdatering: nøgler sat op (7/11-2026, aften)

- **Dataforsyningen-token virker.** gsearch returnerer DAR-adresser med UUID og adgangspunkt som MultiPoint i EPSG:25832. `sted_find` bruger nu det officielle register.
- **Datafordeler-nøglen virker.** IT-systemet "byg-mcp" er oprettet på portal.datafordeler.dk (privat bruger, kun frie data). En ny nøgle giver 401 "Unrecognized key" i ca. 15 minutter, før den bliver aktiv.
- **Versioner:** `v1` findes ikke for DAR, BBR og MAT (404). Gældende versioner: **DAR v3, BBR v3, MAT v3, DAGI v2, EBR v1**. Skemaet hentes på `/<register>/<version>/schema`.
- **Queries kræver** `virkningstid` eller `registreringstid` og et filter på `id_lokalId` eller `datafordelerRowId`. Fritekstsøgning direkte i DAR er altså ikke mulig, så gsearch skal bruges til at finde ID'et først.
- Testopslag: DAR_Adresse for Bispensgade 3 → husnummer-ID `0a3f509c-…`, som er nøglen videre til BBR og matrikel i M1.

## Det skal du gøre før M1 *(udført)*

1. **Datafordeleren:** opret en bruger og et IT-system på datafordeler.dk og generér en API-nøgle.
2. **Dataforsyningen:** opret en gratis bruger på dataforsyningen.dk og lav et token.
3. Læg begge i `.env` (se `.env.example`). Filen er udelukket fra git.

Jeg kan ikke oprette konti for dig. Når nøglerne ligger der, kan M1 (DAR → BFE → matrikel → BBR) bygges og testes.

## Kendte begrænsninger i M0

- Cachen ligger kun i hukommelsen. SQLite kommer i M1.
- `restriktioner` med radius 1 m rammer kun flader, ikke linjeobjekter (fx sten- og jorddiger). Brug større radius.
- OpenStreetMap-geokodning kan være upræcis for nye adresser.

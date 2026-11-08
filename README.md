# byg-mcp: MCP for bygningsdesign i Danmark

En MCP-server, der giver sprogmodeller adgang til danske data for arkitekter, ingeniører og bygningskonstruktører.

**Status:** M5 færdig, se [08-m5/m5-notat.md](08-m5/m5-notat.md), [07-m4/m4-notat.md](07-m4/m4-notat.md), [06-m3/m3-notat.md](06-m3/m3-notat.md), [05-m2/m2-notat.md](05-m2/m2-notat.md), [04-m1/m1-notat.md](04-m1/m1-notat.md) og [03-m0/m0-notat.md](03-m0/m0-notat.md). Baggrund: [screening](01-screening/screening.md), [filtrering](01-screening/filtrering.md), [arkitektur](02-arkitektur/arkitektur.md).

## Værktøjer

| Tool | Hvad | Kilde | Nøgle |
|---|---|---|---|
| `kilde_status` | Hvilke kilder kan nås, og hvilke mangler nøgler | alle | - |
| `sted_find` | Adresse, matrikel, BFE eller koordinat → koordinater, husnummer, BFE, jordstykker, grundareal, noteringer (fredskov, strandbeskyttelse, klitfredning). Markerer usikre match | gsearch + Datafordeleren (DAR, MAT) | ja (reserve: OpenStreetMap uden ejendom) |
| `bygning_bbr` | Bygninger med anvendelse, år, arealer, etager, materialer, asbest, varme, fredning. Indikator for bebyggelsesprocent | Datafordeleren (BBR) | ja |
| `plan_gaeldende` | Lokalplaner, delområder, forslag, kommuneplanramme, zonestatus, byggefelter | Plandata.dk | nej |
| `plan_laes_lokalplan` | Lokalplanens bestemmelser fra PDF'en, opdelt i nummererede bestemmelser og underpunkter med side. Filter på emne (højde, parkering, facade …) | Plandata.dk | nej |
| `restriktioner` | Bygge- og beskyttelseslinjer, fredninger, § 3, Natura 2000, områdeklassificering, grundvand, jordforurening V1/V2, støj (Lden), fortidsminder, matrikelnoteringer | Arealinformation, DKjord, MiljøGIS, Fund og Fortidsminder, Matriklen | nej (matrikelnoteringer: ja) |
| `terraen` | Koter (DVR90), højdeforskel og hældning på grunden, højde over terræn (bygninger/træer) på grunden og hos naboer | Danmarks Højdemodel | ja |
| `jord_geologi` | Jordart (1:25.000/1:200.000), nærmeste boringer med jordlag og vandstand, terrænnært grundvand (vinter/sommer) | GEUS, HIP | ja (HIP) |
| `kort_udsnit` | Billede: ortofoto eller skyggekort af terræn/overflade + link til skråfoto | Dataforsyningen | ja |
| `grundrapport` | Samlet screening: ejendom, bygninger, plangrundlag, restriktioner, terræn, jord og grundvand | alle ovenstående | ja |
| `br18_soeg` | Fritekstsøgning i bygningsreglementet (aktuel konsolideret version), med synonymer (fx LCA → klimapåvirkning) | bygningsreglementet.dk (lokal kopi) | nej |
| `br18_paragraf` | Fuld ordlyd af §§ eller bilag ("58", "251-256", "Bilag 2") med links til vejledninger og standarder | bygningsreglementet.dk (lokal kopi) | nej |
| `br18_kapitel` | Oversigt over kapitler, afsnit og paragrafnumre | bygningsreglementet.dk (lokal kopi) | nej |
| `lov_soeg` / `lov_paragraf` | Gældende love og bekendtgørelser, enkelte paragraffer (byggeloven, planloven, naturbeskyttelsesloven m.fl.) | Retsinformation | nej |
| `klima_data` | Målt klima for kommunen: temperatur, graddage, nedbør inkl. største 30-min.-regn, vind, sol, sne m.m. | DMI | nej |
| `sol_og_pv` | Solcelleydelse og indstråling (valgfri eller optimal hældning/orientering, horisont) | PVGIS | nej |
| `vejrfil` | EPW-vejrfil (TMY) til simulering, link og lokal fil | PVGIS | nej |
| `el_co2` | CO2 fra el nu og seneste dage (DK1/DK2) + BR18's emissionsfaktorer (tabel 8.1) | Energinet, BR18 | nej |
| `lca_materiale` | GWP for materialer: BR18's generiske data (tabel 7) og/eller ÖKOBAUDAT-EPD'er | BR18, ÖKOBAUDAT | nej |
| `bim_klassifikation` | Klasser og egenskaber: CCI (Molio), IFC 4.3, DTU's BR18-bygningsdele | bSDD | nej |

**Prompts:** `grundscreening` (adresse, evt. projektidé) og `br18_tjek` (projektbeskrivelse, evt. emner).

**Ressourcer:** `br18://oversigt` og `br18://paragraf/{nr}`.

## Installation

Kræver [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Valgfrit: kopiér `.env.example` til `.env` og indsæt nøgler til Datafordeleren og Dataforsyningen.

## Brug i Claude Code

```bash
claude mcp add byg-dk -- uv run --directory "C:\Users\peter\Ultimate MCP for Construction in DK" byg-mcp
```

## Brug i Claude Desktop

Tilføj til `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "byg-dk": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\Users\\peter\\Ultimate MCP for Construction in DK", "byg-mcp"]
    }
  }
}
```

## Test

```bash
uv run pytest -m "not live"
```

```bash
uv run pytest -m live
```

Live-testene kalder de rigtige kilder over nettet og kræver nøgler i `.env`.

## Vedligehold

BBR-kodelisterne ligger i `src/byg_mcp/data/bbr_kodelister.json`. Opdatér dem med:

```bash
uv run python scripts/hent_bbr_kodelister.py
```

Bygningsreglementet opdateres typisk 1. januar og 1. juli. Hent den nye version med:

```bash
uv run python scripts/indsaml_br18.py
```

BR18's LCA-data (bilag 2, tabel 7, 8.1, 8.2) opdateres med:

```bash
uv run python scripts/hent_br18_lca_data.py
```

Cachen ligger i `data/cache.sqlite` og kan slettes uden risiko.

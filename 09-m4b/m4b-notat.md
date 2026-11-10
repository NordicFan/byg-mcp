# M4b-notat: BR-vejledninger

*8. november 2026. Mål: gøre Bygningsreglementets vejledninger søgbare, så modellen kan svare med præ-accepterede løsninger og ikke kun med paragrafteksten.*

## Resultat

To nye værktøjer, og `br18_soeg` er udvidet. MCP'en har nu **23 værktøjer, 2 prompts og 2 ressourcer**.

| Værktøj | Indhold |
|---|---|
| `br18_vejledning_soeg` | Fritekstsøgning i vejledningerne (HTML-sider og PDF-bilag) med kapitel, dokument, side og uddrag. Kan begrænses til ét kapitel. |
| `br18_vejledning_hent` | Fuld tekst af et stykke plus op til 3 naboer før og efter fra samme dokument, fx forrige og næste side i en PDF. |
| `br18_soeg` | Viser nu også de 4 bedste vejledningshits (`inkl_vejledninger=True` som standard). |

Vidensbasen indeholder **6.093 tekststykker** fra 33 kapitler inklusive klimasikringsvejledningen, heraf 994 fra HTML-sider og 5.099 fra **243 PDF'er**. Filen fylder 2,0 MB komprimeret (`src/byg_mcp/data/br18_vejledninger.jsonl.gz`).

53 tests består. Et stdio-tjek (tools/list, vejledningssøgning og `sted_find`) viser ingen nøgler i output.

Eksempler:
- "redningsåbning" → Kapitel 5 Brand, præ-accepteret løsning, s. 32
- "U-værdi ydervæg" → Kapitel 11, s. 29–31
- "radon" → Kapitel 13 Forureninger
- "klimasikring skybrud" → Vejledning om klimasikring, s. 19

## Fund

1. **Vejledningerne ligger under hvert kapitels fane "Vejledninger"** som en træstruktur af HTML-sider. Mange sider er kun indgang til PDF-bilag, fx de præ-accepterede brandløsninger. Crawleren går bredt gennem kapitlets egne sider (højst 350 pr. kapitel) og henter alle PDF'er, den støder på.
2. **Der er massive dubletter.** Samme PDF linkes fra mange sider, og de findes i flere versioner, både med og uden ændringsmarkeringer. Rensningen beholder kun den nyeste version pr. dokument, dropper udgaverne med ændringsmarkeringer og vandmærker og fjerner tekstdubletter. Det reducerede rådata fra 67.851 til 6.093 stykker.
3. **Nogle sektioner hentes med ajax** (`data-href ?ajax=1`). De skal hentes særskilt, ellers mangler indholdet.
4. **Links skal samles, før navigationen fjernes.** Ellers mister crawleren undersiderne.
5. **Søgningen vægter titlen højt** (BM25 med vægtene titel 3, tekst 1). Den prøver først med alle ord og falder tilbage til et af ordene. Hits fra samme dokument og side vises kun én gang.

## Kendte begrænsninger

- **Kapitel 1 ramte loftet på 350 sider.** Det betyder, at sider kan mangle. Det er mest sider om administration og byggesagsbehandling. Loftet kan hæves i `MAKS_SIDER_PR_KAPITEL`.
- Kapitel 6, 24, 31, 35 og 37 gav ingen vejledningssider. De har tilsyneladende ingen fane med vejledninger. Kapitel 36 gav kun ét stykke.
- **Billeder, tabeller som grafik og skannede PDF'er** giver ingen eller dårlig tekst. pypdf udtrækker kun tekstlaget.
- Søgningen er leksikalsk (FTS5) og ikke semantisk. Synonymer skal derfor stå i forespørgslen, fx både "rampe" og "niveaufri".
- **Vejledningerne er vejledende.** Det er paragraffen i BR18, der er bindende, og værktøjerne gør opmærksom på det.
- Data er en lokal kopi fra 8. november 2026. Opdatér med `uv run python scripts/indsaml_vejledninger.py`. Det tager ca. 70 minutter. Med `--kun-rens` renses den gemte fil igen uden ny crawl, fx efter ændrede rensningsregler.

## Status

| Milepæl | Status |
|---|---|
| M0–M3 Sted, bygning, plan, restriktioner, terræn, jord, grundrapport | ✅ |
| M4 Regler (BR18 + love) | ✅ |
| M4b BR-vejledninger | ✅ |
| M5 Klima, energi, LCA, BIM | ✅ |
| M6 Fase 2-kilder: tinglysning/servitutter, energimærker, bevaringsværdige bygninger, nævnsafgørelser | Kræver aftaler/afklaring |

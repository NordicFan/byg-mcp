# M4-notat: regler (BR18 og love)

*8. november 2026. Mål: gøre bygningsreglementet og de vigtigste love søgbare og citerbare.*

## Resultat

- **BR18-vidensbase:** 562 af 565 paragraffer og 26 bilagsafsnit fra den aktuelle konsoliderede version på bygningsreglementet.dk. De ligger som `src/byg_mcp/data/br18.jsonl` (0,6 MB) og indekseres i hukommelsen med SQLite FTS5 (0,02 sek.). Hver paragraf har kapitel, afsnit, link, links til BR-vejledninger og henvisninger til standarder.
- **Nye værktøjer:**
  - `br18_soeg`: fritekst med præfiks-match og fagsynonymer (LCA → klimapåvirkning, U-værdi → transmissionskoefficient …)
  - `br18_paragraf`: "58", "251-256", "297 og 298", "6a", "Bilag 2"
  - `br18_kapitel`: oversigt
  - `lov_soeg` og `lov_paragraf`: Retsinformation, gældende love
- **Ressourcer:** `br18://oversigt`, `br18://paragraf/{nr}`.
- **Prompt:** `br18_tjek` gennemgår et projekt mod relevante krav og svarer i tabelform med paragrafhenvisninger.
- 42 tests består: 18 enhedstests og 24 live-tests.

Eksempler:
- "værn højde altan" → § 58: "Højden på værn eller rækværker er mindst 1,0 m."
- "LCA" → §§ 297–298 og bilag 2 (grænseværdier: 6,7 kg CO₂e/m²/år for enfamiliehuse, 7,5 for etageboliger og kontor)
- Planloven § 15 (lokalplanens indhold), naturbeskyttelsesloven § 16 (150 m søbeskyttelseslinje)

## Vigtigste fund

1. **Retsinformations BR18 er ikke konsolideret.** BEK nr. 1399 af 12/12/2019 er den oprindelige tekst. Senere ændringer ligger i separate ændringsbekendtgørelser. Fx handler § 298 dér om vedvarende energi, mens den gældende § 298 indeholder CO₂-grænseværdierne. **bygningsreglementet.dk er derfor den eneste kilde til den konsoliderede tekst.** `lov_paragraf` sender BR18-forespørgsler videre til vidensbasen og forklarer hvorfor.
2. **Indsamlingen kræver omhu:**
   - Paragrafnummeret står i hver rækkes eget mærke og ikke i teksten.
   - Punktopstillinger ligger i `<div>` og ikke kun i `<p>`.
   - Ord er delt over flere `<span>`-elementer ("V"+"arme"). Mellemrum mellem spans gav "V arme", så teksten samles nu uden mellemrum.
   - Alle tre fejl blev fundet ved at tjekke dækning (§ 1–565) og tekstkvalitet. De er nu dækket af tests.
3. **Historiske versioner** findes på bygningsreglementet.dk tilbage til 2018 (`/historisk/version-N/`). Den aktuelle version gælder fra 1/1-2026, for den seneste historiske sluttede 31/12-2025.
4. **Retsinformations søge-API** (`/api/documentsearch`) markerer gældende dokumenter med `isHistoryFlag: false`. Paragraffer hentes som LexDania-XML via ELI og caches i 7 dage.
5. **Rangering:** "klimapåvirkning" står i kapiteltitlen for hele kapitel 11. Kapiteltitlen vægtes derfor lavt (0,3) og afsnitsoverskriften højt (5,0).

## Kendte begrænsninger

- **BR-vejledningerne er ikke indekseret.** De indeholder ofte de konkrete løsninger og tal (fx brandteknisk vejledning, dagslys, lyd). I dag vises kun links. Det er den største mangel og et oplagt næste skridt (M4b).
- § 366, 479 og 562 findes ikke i den aktuelle version, formentlig ophævet. Det er ikke verificeret.
- Tabeller i bilagene er gengivet som tekst med "|" mellem celler. De er læsbare, men ikke strukturerede.
- Fuldtekstsøgning forstår ikke sammensatte ord fuldt ud ("energiramme" findes, men "ramme" alene giver ikke energirammen). Synonymlisten afhjælper de mest almindelige.
- Vidensbasen opdateres ikke automatisk. Kør `scripts/indsaml_br18.py` ved hver ny BR-version (typisk 1/1 og 1/7).

## Status på milepæle

| Milepæl | Status |
|---|---|
| M0–M3 (sted, bygning, plan, restriktioner, terræn, jord, grundrapport) | ✅ |
| M4 Regler | ✅ (BR-vejledninger mangler, se M4b) |
| M4b BR-vejledninger i vidensbasen | Forslag |
| M5 Klima, LCA og BIM | Næste |
| M6 Fase 2-kilder | |

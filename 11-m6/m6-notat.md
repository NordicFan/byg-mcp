# M6-notat: klimafremskrivninger, oversvømmelse og energimærker

*17. november 2026. Mål: data om fremtidig klima- og driftsrisiko for et sted, bl.a. til xR-projektet (Expected Risk) med Frankfurt UAS.*

## Resultat

Tre nye værktøjer. MCP'en har nu **26 værktøjer**, og `kilde_status` viser **20 kilder**. Klimaatlas og Havvand på Land/Bluespot melder "ok". Energimærker melder "ikke konfigureret", indtil der er adgang fra Energistyrelsen.

| Værktøj | Indhold | Kilde |
|---|---|---|
| `klima_fremskrivning` | Kommunens nedbør (gennemsnit, skybrud, døgn over 20 mm, 10- og 100-årshændelser for time- og døgnnedbør), temperatur, hedebølgedage, frostdøgn og frysepunktspassager. Nær kysten også middelvandstand, 20- og 100-årsstormflod og hyppigheden af nutidens 20-årsstormflod. Lav, mellem og høj udledning, 2011-2100, median og 10-90 % | DMI Klimaatlas v2025a (ArcGIS REST, nøglefri) |
| `oversvoemmelse` | Havniveau der oversvømmer stedet, sammenholdt med stormflod for kyststrækningen. Regn der fylder lavningen (Bluespot). Terrænnært grundvand. Laveste værdi i en ring om punktet | Havvand på Land og Bluespot (Dataforsyningen `wms/dhm`), HIP, Klimaatlas |
| `energimaerke` | Energimærker for ejendommen (BFE, ellers koordinat), det gældende mærke og forbedringsforslag med investering, årlig besparelse, levetid, rentabilitet og opnåelig klasse | Energistyrelsen, EMOData (kræver brugernavn og adgangskode) |

29 enhedstests består (8 nye). Live-tests ligger i `tests/test_live_m6.py`.

Eksempler fra live-kørsel 17/11-2026:
- **Aalborg Kommune, RCP4,5, 2071-2100:** skybrud 0,32 → 0,46 hændelser pr. år (+43 %). 100-årshændelse for timenedbør 44,6 → 56,4 mm. Middeltemperatur 8,2 → 10,1 °C. Frostdøgn 82 → 50.
- **Limfjord østlig (LF1), SSP2-4,5, 2071-2100:** middelvandstand +37 cm (13-69). 100-årsstormflod 149 → 186 cm. Nutidens 20-årsstormflod forekommer 11,8 gange pr. 20 år mod 1 i dag.
- **Havnefronten i Aalborg (555882, 6323400):** oversvømmes ved et havniveau på 1,41 m. Allerede nutidens 100-årsstormflod (1,49 m) når stedet. Terrænnært grundvand ca. 1,0 m under terræn om vinteren.
- **UCN, Sofiendalsvej 60 (kote ca. 20 m):** ingen havvandstærskel, grundvand ca. 12 m under terræn.

## Fund

1. **Klimaatlas ligger som åbne ArcGIS-tjenester.** Tjenester med endelsen `_latest` peger på nyeste version (v2025a). Kommunekoden skrives uden foranstillet nul ("851"). Kommunedata bruger RCP-scenarier, kystdata SSP-scenarier. Værktøjet parrer dem som lav (RCP2,6/SSP1-2,6), mellem (RCP4,5/SSP2-4,5) og høj (RCP8,5/SSP5-8,5), som i DMI's rapporter.
2. **DMI anbefaler absolutte fremtidsværdier direkte fra Klimaatlas**, ikke beregnet ud fra reference og ændring. Værktøjet viser begge, og DMI's ændring kun dér, hvor enheden er kendt (% for nedbør, °C for temperatur).
3. **Havvand på Land er i meter og følger terrænkoten**, hvor der er forbindelse til havet. Celler uden gyldig tærskel returnerer **300**. Det sås midt i en bebyggelse i kote 2,8 m og ved UCN i kote 20 m. Det tolkes som en kode og filtreres fra; ringen om punktet finder så den laveste gyldige tærskel (2,15 m inden for 40 m i bebyggelsen).
4. **Bluespot er i meter regn** og omregnes til mm. Værdierne nær havnen var små (2-4 mm), dvs. lavninger der fyldes ved almindelig regn, når kloakken ikke regnes med.
5. **EMOData svarer HTTP 200 med status "ACCESS_DENIED"** uden adgang. Afviste svar caches derfor ikke. Datoer kan komme i WCF-format (`/Date(…+0200)/`) og omregnes.
6. **Kendt fejl i eksisterende værktøj:** `terraen` med `omgivelser_m=0` fejler ("zero-size array to reduction operation fmin"). Ikke rettet i M6.

## Kendte begrænsninger

- **Klimaatlas er kommunegennemsnit og kyststrækninger**, ikke punktværdier. Stormflod er uden bølgebidrag.
- **Havvand på Land og Bluespot er screening** uden kloak, nedsivning og bølger. Erstatter ikke kommunens risikokortlægning eller en hydraulisk analyse.
- **Tolkningen af koden 300** bygger på observationer, ikke på dokumentation fra Klimadatastyrelsen. Bør bekræftes hos KDS.
- **`energimaerke` er ikke live-testet**, da der endnu ikke er adgang. Bygget mod EMOData's swagger (17/11-2026).
- Fremskrivningerne er ikke koblet til `grundrapport`.

## Status

| Milepæl | Status |
|---|---|
| M0-M3 Sted, bygning, plan, restriktioner, terræn, jord, grundrapport | ✅ |
| M4/M4b Regler (BR18, vejledninger, love) | ✅ |
| M5 Klima, energi, LCA, BIM | ✅ |
| M6 Klimafremskrivninger, oversvømmelse, energimærker | ✅ (energimærker afventer adgang) |

## Opdatering 17. november 2026: energimaerke live-testet

EMOData-adgang er givet af Energistyrelsen, og `kilde_status` melder "ok". `energimaerke` er kørt på de seks pilotbygninger i Aalborg og på Fjelstrupvej 77, Haderslev. Forslagenes summer pr. bygning stemmer med EMOData's egne totaler (ProposalsCalculations), så parsningen er verificeret mod rigtige svar.

Fund i data (ikke fejl i adapteren):
- Ældre mærker (fx Haderslev 2011) har årlig besparelse 0 på alle forslag og enkelte urealistiske investeringer (10 kr.).
- Mærket for Sofiendalsvej 60 knytter alle 15 forslag til bygningsnr. 2, selvom teksten nævner bygning 1, 2, 4 og 5.
- Toldbod Plads 1 (fredet) og Vestre Fjordvej 15 har ingen mærker, hverken på BFE eller koordinat.

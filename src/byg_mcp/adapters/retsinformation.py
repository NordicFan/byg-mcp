"""Retsinformation: søg i gældende love/bekendtgørelser og hent enkelte paragraffer som tekst.

Verificeret 8/11-2026:
- Søgning: https://www.retsinformation.dk/api/documentsearch?t=<tekst>  (JSON, isHistoryFlag=false = gældende)
- Dokument: https://www.retsinformation.dk/eli/lta/<år>/<nr>/xml  (LexDania-XML, <Paragraf localId="16">)
Nøglefri. Vi cacher, så kilden ikke belastes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

BASE = "https://www.retsinformation.dk"

# Almindelige navne → søgetekst, der rammer lovens populærtitel.
ALIAS = {
    "byggeloven": "byggeloven",
    "planloven": "planloven",
    "naturbeskyttelsesloven": "naturbeskyttelsesloven",
    "miljøbeskyttelsesloven": "miljøbeskyttelsesloven",
    "jordforureningsloven": "jordforureningsloven",
    "bygningsfredningsloven": "bygningsfredningsloven",
    "museumsloven": "museumsloven",
    "arbejdsmiljøloven": "arbejdsmiljøloven",
    "vejloven": "vejloven",
    "privatvejsloven": "privatvejsloven",
    "skovloven": "skovloven",
    "kystbeskyttelsesloven": "kystbeskyttelsesloven",
    "br18": "bygningsreglement 2018",
    "bygningsreglementet": "bygningsreglement 2018",
    "energimærkning": "bekendtgørelse om energimærkning af bygninger",
}


class RetsinformationAdapter(Adapter):
    kilde = Kilde(
        id="H02",
        navn="Retsinformation",
        udbyder="Civilstyrelsen",
        url=BASE,
        licens="Offentlige retsforskrifter - fri anvendelse",
    )

    async def soeg(self, tekst: str, kun_gaeldende: bool = True, maks: int = 10) -> list[dict[str, Any]]:
        data = await self.get_json(f"{BASE}/api/documentsearch", {"t": ALIAS.get(tekst.lower().strip(), tekst)}, ttl=7 * 24 * 3600)
        ud = []
        for d in data.get("documents", []):
            if kun_gaeldende and d.get("isHistoryFlag"):
                continue
            ud.append({
                "titel": d.get("title"),
                "populaertitel": d.get("popularTitle") or None,
                "betegnelse": d.get("shortName"),
                "type": d.get("documentType"),
                "ministerium": d.get("ressortName"),
                "eli": d.get("retsinfoLink"),
                "url": BASE + (d.get("retsinfoLink") or ""),
            })
            if len(ud) >= maks:
                break
        return [{k: v for k, v in u.items() if v} for u in ud]

    async def find_lov(self, navn: str) -> dict[str, Any] | None:
        """Bedste gældende lov/lovbekendtgørelse/bekendtgørelse for et navn (populærtitel foretrækkes)."""
        hits = await self.soeg(navn, maks=15)
        n = navn.lower().strip()
        for h in hits:
            if (h.get("populaertitel") or "").lower() == n:
                return h
        for h in hits:
            if h.get("type") in ("Lovbekendtgørelse", "Lov", "Bekendtgørelse"):
                return h
        return hits[0] if hits else None

    async def _xml(self, eli: str) -> ET.Element:
        if not re.fullmatch(r"/eli/[a-z]+/\d{4}/\d+", eli or ""):
            raise ValueError(f"Ugyldigt ELI-link: {eli}")
        key = f"retsinfo:xml:{eli}"
        tekst = self.cache.get(key)
        if tekst is None:
            resp = await self.client.get(f"{BASE}{eli}/xml", timeout=60)
            resp.raise_for_status()
            tekst = resp.text
            self.cache.set(key, tekst, 7 * 24 * 3600)
        return ET.fromstring(tekst.encode("utf-8"))

    @staticmethod
    def _tekst(el: ET.Element) -> str:
        linjer: list[str] = []
        for stk in el.iter("Stk"):
            exp = stk.find("Explicatus")
            dele = [("".join(exp.itertext()).strip() + " ") if exp is not None else ""]
            for linea in stk.iter("Linea"):
                t = re.sub(r"\s+", " ", "".join(linea.itertext())).strip()
                if t:
                    dele.append(t)
            linjer.append((dele[0] + " ".join(dele[1:])).strip())
        if not linjer:
            linjer = [re.sub(r"\s+", " ", "".join(el.itertext())).strip()]
        return "\n".join(linjer)

    async def paragraf(self, eli: str, nr: str) -> dict[str, Any] | None:
        rod = await self._xml(eli)
        nr = nr.replace("§", "").strip().lower().replace(" ", "")
        forældre = {c: p for p in rod.iter() for c in p}
        for p in rod.iter("Paragraf"):
            if (p.get("localId") or "").lower().replace(" ", "") == nr:
                gruppe = forældre.get(p)
                overskrift = None
                if gruppe is not None and gruppe.tag == "ParagrafGruppe" and gruppe.find("Rubrica") is not None:
                    overskrift = re.sub(r"\s+", " ", "".join(gruppe.find("Rubrica").itertext())).strip()
                kap = None
                el = p
                while el in forældre:
                    el = forældre[el]
                    if el.tag == "Kapitel":
                        exp, rub = el.find("Explicatus"), el.find("Rubrica")
                        kap = " ".join(re.sub(r"\s+", " ", "".join(x.itertext())).strip() for x in (exp, rub) if x is not None)
                        break
                exp = p.find("Explicatus")
                return {
                    "paragraf": "".join(exp.itertext()).strip() if exp is not None else f"§ {nr}.",
                    "overskrift": overskrift,
                    "kapitel": kap,
                    "tekst": self._tekst(p),
                }
        return None

    async def titel(self, eli: str) -> dict[str, Any]:
        rod = await self._xml(eli)
        meta = rod.find(".//Meta")

        def f(tag: str) -> str | None:
            el = meta.find(tag) if meta is not None else None
            return el.text.strip() if el is not None and el.text else None

        return {"titel": f("DocumentTitle"), "populaertitel": f("PopularTitle"), "type": f("DocumentType"),
                "nummer": f("Number"), "aar": f("Year"), "status": f("Status")}

    async def status(self) -> str:
        await self.get_json(f"{BASE}/api/documentsearch", {"t": "byggeloven"}, ttl=0)
        return "ok"

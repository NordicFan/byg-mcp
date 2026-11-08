"""Materialer og BIM: ÖKOBAUDAT (EPD'er og generiske LCA-data) og buildingSMART Data Dictionary (bSDD).

Verificeret 8/11-2026 (nøglefri):
- ÖKOBAUDAT (soda4LCA): https://oekobaudat.de/OEKOBAU.DAT/resource/processes?search=true&name=...&format=json
  Detaljer: /processes/{uuid}?format=json&view=extended → LCIAResults (GWP-total pr. modul).
- bSDD: https://api.bsdd.buildingsmart.org/api/TextSearch/v1 og /api/Class/v1?Uri=...&IncludeClassProperties=true
  CCI: https://identifier.buildingsmart.org/uri/molio/cciconstruction/1.0 (kun engelske navne).
"""

from __future__ import annotations

import asyncio
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

OBD = "https://oekobaudat.de/OEKOBAU.DAT/resource/processes"
BSDD = "https://api.bsdd.buildingsmart.org/api"
CCI_URI = "https://identifier.buildingsmart.org/uri/molio/cciconstruction/1.0"
IFC_URI = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3"

# Dansk → tysk søgeord til ÖKOBAUDAT (som er på tysk/engelsk).
DA_DE = {
    "beton": "Beton", "betonelement": "Betonfertigteil", "cement": "Zement", "stål": "Stahl", "armering": "Bewehrungsstahl",
    "træ": "Holz", "konstruktionstræ": "Konstruktionsvollholz", "limtræ": "Brettschichtholz", "clt": "Brettsperrholz",
    "krydslamineret": "Brettsperrholz", "krydsfiner": "Sperrholz", "osb": "OSB", "spånplade": "Spanplatte",
    "mineraluld": "Mineralwolle", "stenuld": "Steinwolle", "glasuld": "Glaswolle", "eps": "EPS", "xps": "XPS",
    "træfiber": "Holzfaser", "papiruld": "Zellulose", "gips": "Gips", "gipsplade": "Gipsplatte", "tegl": "Ziegel",
    "mursten": "Mauerziegel", "tagsten": "Dachziegel", "glas": "Glas", "vindue": "Fenster", "aluminium": "Aluminium",
    "zink": "Zink", "kobber": "Kupfer", "tagpap": "Bitumenbahn", "asfalt": "Asphalt", "mørtel": "Mörtel",
    "puds": "Putz", "maling": "Farbe", "letbeton": "Porenbeton", "gasbeton": "Porenbeton", "letklinker": "Blähton",
    "fibercement": "Faserzement", "linoleum": "Linoleum", "tæppe": "Teppich", "fliser": "Fliesen", "skifer": "Schiefer",
    "grus": "Kies", "sand": "Sand", "pvc": "PVC", "membran": "Abdichtung",
}


class OekobaudatAdapter(Adapter):
    kilde = Kilde(
        id="I06",
        navn="ÖKOBAUDAT",
        udbyder="Bundesinstitut für Bau-, Stadt- und Raumforschung (BBSR)",
        url="https://www.oekobaudat.de",
        licens="Frie data - kildeangivelse: ÖKOBAUDAT, BBSR",
    )

    async def soeg(self, tekst: str, maks: int = 8, kun_generiske: bool = False) -> list[dict[str, Any]]:
        ord_ = tekst.lower().split()
        q = " ".join(DA_DE.get(w, w) for w in ord_)
        d = await self.get_json(OBD, {"search": "true", "name": q, "format": "json", "pageSize": 60}, ttl=30 * 24 * 3600)
        hits = []
        for x in d.get("data", []):
            if kun_generiske and x.get("type") == "EPD":
                continue
            hits.append({"uuid": x["uuid"], "navn": x.get("name"), "type": x.get("type"), "klassifikation": x.get("classific"),
                         "referenceaar": x.get("refYear"), "gyldig_til": x.get("validUntil"), "geografi": x.get("geo")})
        # Gyldige og nyeste først
        hits.sort(key=lambda h: (-(h.get("gyldig_til") or 0), -(h.get("referenceaar") or 0)))
        return hits[:maks]

    async def gwp(self, uuid: str) -> dict[str, Any]:
        d = await self.get_json(f"{OBD}/{uuid}", {"format": "json", "view": "extended"}, ttl=30 * 24 * 3600)
        moduler: dict[str, float] = {}
        for r in (d.get("LCIAResults") or {}).get("LCIAResult", []):
            navne = [s.get("value", "") for s in r.get("referenceToLCIAMethodDataSet", {}).get("shortDescription", [])]
            if any("GWP-total" in n for n in navne) or (not moduler and any("Global warming" in n or "GWP" in n for n in navne)):
                for a in r.get("other", {}).get("anies", []):
                    if "module" in a and a.get("value") not in (None, ""):
                        try:
                            moduler[a["module"]] = round(float(a["value"]), 4)
                        except ValueError:
                            pass
                if moduler:
                    break
        enhed = None
        for e in (d.get("exchanges") or {}).get("exchange", []):
            if e.get("referenceFlow"):
                for fp in e.get("flowProperties", []):
                    if fp.get("referenceFlowProperty"):
                        enhed = f"{e.get('resultingflowAmount') or e.get('meanAmount')} {fp.get('referenceUnit') or ''}".strip()
        return {"gwp_total_kg_co2e": moduler, "deklareret_enhed": enhed,
                "url": f"https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid={uuid}"}

    async def status(self) -> str:
        await self.get_json(OBD, {"search": "true", "name": "Beton", "format": "json", "pageSize": 1}, ttl=0)
        return "ok"


class BsddAdapter(Adapter):
    kilde = Kilde(
        id="L01",
        navn="buildingSMART Data Dictionary (bSDD)",
        udbyder="buildingSMART International",
        url="https://search.bsdd.buildingsmart.org",
        licens="Ordbøgernes egne licenser (IFC: CC BY-ND, CCI: Molio)",
    )

    async def soeg(self, tekst: str, ordbog: str | None, maks: int = 10) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"SearchText": tekst, "Limit": maks}
        if ordbog:
            params["DictionaryUris"] = ordbog
        d = await self.get_json(f"{BSDD}/TextSearch/v1", params, ttl=30 * 24 * 3600)
        return [
            {k: v for k, v in {
                "navn": c.get("name"), "kode": c.get("referenceCode"), "ordbog": c.get("dictionaryName"),
                "beskrivelse": (c.get("description") or "")[:300] or None, "overordnet": c.get("parentClassName"),
                "ifc": c.get("relatedIfcEntityNames") or None, "uri": c.get("uri"),
            }.items() if v not in (None, "", '""')}
            for c in d.get("classes", [])
            # bSDD's ordbogsfilter er ikke altid strikt (verificeret 8/11-2026), så vi filtrerer selv
            if not ordbog or (c.get("dictionaryUri") or "").rstrip("/") == ordbog.rstrip("/")
        ]

    async def klasse(self, uri: str, maks_egenskaber: int = 40) -> dict[str, Any]:
        d = await self.get_json(f"{BSDD}/Class/v1", {"Uri": uri, "IncludeClassProperties": "true"}, ttl=30 * 24 * 3600)
        if d.get("error"):
            raise LookupError(d.get("message") or "Klassen findes ikke i bSDD")
        props = d.get("classProperties") or []
        pr_saet: dict[str, list[str]] = {}
        for p in props:
            pr_saet.setdefault(p.get("propertySet") or "(uden sæt)", []).append(p.get("name"))
        return {
            "navn": d.get("name"), "kode": d.get("referenceCode"), "definition": d.get("definition") or d.get("description"),
            "ordbog": d.get("dictionaryUri"), "uri": uri,
            "ifc": d.get("relatedIfcEntityNames"),
            "antal_egenskaber": len(props),
            "egenskabssaet": {k: v[:maks_egenskaber] for k, v in list(pr_saet.items())[:15]},
        }

    async def status(self) -> str:
        await self.get_json(f"{BSDD}/TextSearch/v1", {"SearchText": "wall", "Limit": 1}, ttl=0)
        return "ok"


__all__ = ["OekobaudatAdapter", "BsddAdapter", "CCI_URI", "IFC_URI", "asyncio"]

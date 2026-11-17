"""DMI Klimaatlas: klimafremskrivninger for kommuner og kyststrækninger.

Verificeret 17/11-2026 (nøglefrit, ArcGIS REST):
- Basis: https://services9.arcgis.com/qH1Ysxh3VVYXbkQU/arcgis/rest/services/<tjeneste>/FeatureServer
- Tjenesterne med endelsen `_latest` peger på nyeste version (v2025a pr. 17/11-2026).
- Kommuner: NedboerKommuner_latest/0 og TemperaturKommuner_latest/0, nøgle `komkode` uden foranstillet nul
  ("851" for Aalborg). Scenarier RCP2,6 (26), RCP4,5 (45), RCP8,5 (85); historisk = 0.
- Kyst: VandstandStormflodKyst_latest/0 (værdier), /1 (kystinddeling, polygoner), nøgle `kystkode`.
  Scenarier SSP1-2,6 (126), SSP2-4,5 (245), SSP5-8,5 (585) m.fl.
- Fælles koder: periode 1=1981-2010, 2=2011-2040, 3=2041-2070, 4=2071-2100; aarstid 1=hele året, 2-5=årstider;
  absolutaendring 1=absolut, 2=ændring ift. 1981-2010; percentil 10, 50, 90.
Enheder fra DMI's Klimaatlas-rapport v2025a og tjenesternes beskrivelser. DMI anbefaler at bruge absolutte
fremtidsværdier direkte fra Klimaatlas frem for at regne dem ud fra reference og ændring.
"""

from __future__ import annotations

from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

KA = "https://services9.arcgis.com/qH1Ysxh3VVYXbkQU/arcgis/rest/services"

SCENARIER_KOMMUNE = {"lav": (26, "RCP2,6"), "mellem": (45, "RCP4,5"), "hoej": (85, "RCP8,5")}
SCENARIER_KYST = {"lav": (126, "SSP1-2,6"), "mellem": (245, "SSP2-4,5"), "hoej": (585, "SSP5-8,5")}
PERIODER = {"start": 2, "midt": 3, "slut": 4}
PERIODE_TEKST = {1: "1981-2010", 2: "2011-2040", 3: "2041-2070", 4: "2071-2100"}
AARSTIDER = {"hele_aaret": 1, "vinter": 2, "foraar": 3, "sommer": 4, "efteraar": 5}

# felt → (navn, enhed for absolut værdi, enhed for DMI's ændring eller None, decimaler)
KOMMUNE_INDIKATORER: dict[str, list[tuple[str, str, str, str | None, int]]] = {
    "NedboerKommuner_latest": [
        ("Gennemsnitsnedboer", "Gennemsnitsnedbør", "mm pr. døgn", "%", 2),
        ("Skybrud", "Skybrud (over 15 mm på 30 min.)", "hændelser pr. år", "%", 2),
        ("Doegn20mm", "Døgn med over 20 mm nedbør", "døgn", None, 1),
        ("Time10Aarsh", "10-årshændelse, timenedbør", "mm på 1 time", "%", 1),
        ("Time100Aarsh", "100-årshændelse, timenedbør", "mm på 1 time", "%", 1),
        ("Doegn10Aarsh", "10-årshændelse, døgnnedbør", "mm på 1 døgn", "%", 1),
        ("Doegn100Aarsh", "100-årshændelse, døgnnedbør", "mm på 1 døgn", "%", 1),
    ],
    "TemperaturKommuner_latest": [
        ("Gennemsnitstemperatur", "Gennemsnitstemperatur", "°C", "°C", 1),
        ("Hedeboelgedage", "Hedebølgedage (3 dage over 28 °C)", "dage", None, 1),
        ("Frostdoegn", "Frostdøgn", "døgn", None, 0),
        ("Frysepunktspassager", "Dage med frysepunktspassager", "dage", None, 0),
    ],
}
KYST_INDIKATORER: list[tuple[str, str, str, int]] = [
    ("Middelvandstand", "Middelvandstand (ændring ift. 1981-2010)", "cm", 0),
    ("Stormfl20Aarsh", "Stormflod, 20-årshændelse", "cm", 0),
    ("Stormfl100Aarsh", "Stormflod, 100-årshændelse", "cm", 0),
    ("StormflNuvaerende20Aarsh", "Hyppighed af nuværende 20-årsstormflod", "hændelser pr. 20 år", 1),
]


def _r(v: Any, d: int) -> float | None:
    return None if v is None else round(float(v), d) if d else round(float(v))


def opstil(
    rows: list[dict[str, Any]],
    felter: list[tuple[str, str, str, str | None, int]],
    scenarier: list[tuple[str, int, str]],
    perioder: list[int],
) -> list[dict[str, Any]]:
    """Rækker fra Klimaatlas → pr. indikator: reference (1981-2010) og fremskrivning pr. scenarie og periode,
    med median og 10-90 %-interval."""
    idx: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for r in rows:
        idx[(r["scenarie"], r["periode"], r["absolutaendring"], r["percentil"])] = r

    def tre(scen: int, per: int, abs_aend: int, felt: str, d: int) -> dict[str, Any] | None:
        med = idx.get((scen, per, abs_aend, 50), {}).get(felt)
        if med is None:
            return None
        lo = idx.get((scen, per, abs_aend, 10), {}).get(felt)
        hi = idx.get((scen, per, abs_aend, 90), {}).get(felt)
        ud: dict[str, Any] = {"median": _r(med, d)}
        if lo is not None and hi is not None:
            ud["interval_10_90"] = sorted([_r(lo, d), _r(hi, d)])
        return ud

    ud = []
    for felt, navn, enhed, aend_enhed, d in felter:
        ind: dict[str, Any] = {"indikator": navn, "enhed": enhed}
        if (ref := tre(0, 1, 1, felt, d)) is not None:
            ind["reference_1981_2010"] = ref
        frem: dict[str, Any] = {}
        for etiket, kode, tekst in scenarier:
            pr_periode: dict[str, Any] = {}
            for p in perioder:
                v = tre(kode, p, 1, felt, d)
                if v is None:
                    continue
                if aend_enhed and (a := tre(kode, p, 2, felt, 1)) is not None:
                    v["aendring_median"] = a["median"]
                    v["aendring_enhed"] = aend_enhed
                pr_periode[PERIODE_TEKST[p]] = v
            if pr_periode:
                frem[f"{etiket} ({tekst})"] = pr_periode
        if frem:
            ind["fremskrivning"] = frem
        if len(ind) > 2:
            ud.append(ind)
    return ud


class KlimaatlasAdapter(Adapter):
    kilde = Kilde(
        id="E02",
        navn="DMI Klimaatlas (fremskrivninger)",
        udbyder="Danmarks Meteorologiske Institut",
        url="https://www.dmi.dk/klimaatlas/",
        licens="Frie data - kildeangivelse: DMI Klimaatlas",
    )

    async def _query(self, tjeneste: str, lag: int, params: dict[str, Any], ttl: float = 30 * 24 * 3600) -> dict[str, Any]:
        data = await self.get_json(f"{KA}/{tjeneste}/FeatureServer/{lag}/query", {"f": "json", **params}, ttl=ttl)
        if "error" in data:
            raise RuntimeError(f"Klimaatlas: {data['error'].get('message')}")
        return data

    async def _rows(self, tjeneste: str, where: str, felter: list[str]) -> tuple[list[dict[str, Any]], str | None]:
        data = await self._query(tjeneste, 0, {
            "where": where,
            "outFields": ",".join(["scenarie", "periode", "absolutaendring", "percentil", "version", *felter]),
            "returnGeometry": "false",
            "resultRecordCount": 2000,
        })
        rows = [f["attributes"] for f in data.get("features", [])]
        version = next((r.get("version") for r in rows if r.get("version")), None)
        return rows, version

    async def kommune(self, kommunekode: str, scenarier: list[str], perioder: list[int], aarstid: int) -> dict[str, Any]:
        kode = str(int(kommunekode))  # Klimaatlas bruger "851", ikke "0851"
        valgte = [(s, *SCENARIER_KOMMUNE[s]) for s in scenarier]
        ud: dict[str, Any] = {}
        version = None
        for tjeneste, felter in KOMMUNE_INDIKATORER.items():
            rows, v = await self._rows(tjeneste, f"komkode='{kode}' AND aarstid={aarstid}", [f[0] for f in felter])
            version = version or v
            ud.update({i["indikator"]: i for i in opstil(rows, felter, valgte, perioder)})
        if not ud:
            raise LookupError(f"Klimaatlas har ingen data for kommunekode {kommunekode}")
        return {"version": version, "indikatorer": list(ud.values())}

    async def kyststraekning(self, x: float, y: float, maks_afstand_m: float) -> dict[str, Any] | None:
        """Nærmeste kyststrækning inden for maks_afstand_m (kystinddelingen er polygoner)."""
        from shapely.geometry import Point, shape

        data = await self._query("VandstandStormflodKyst_latest", 1, {
            "geometry": f"{x:.0f},{y:.0f}", "geometryType": "esriGeometryPoint", "inSR": 25832,
            "spatialRel": "esriSpatialRelIntersects", "distance": maks_afstand_m, "units": "esriSRUnit_Meter",
            "outFields": "kystkode,kystnavn", "returnGeometry": "true", "outSR": 25832,
            "maxAllowableOffset": 50, "f": "geojson",
        }, ttl=90 * 24 * 3600)
        bedst = None
        for feat in data.get("features", []):
            try:
                afstand = shape(feat["geometry"]).distance(Point(x, y))
            except Exception:  # noqa: BLE001 - defekt geometri springes over
                continue
            if bedst is None or afstand < bedst[0]:
                bedst = (afstand, feat["properties"])
        if bedst is None:
            return None
        return {"kystkode": bedst[1]["kystkode"], "kystnavn": str(bedst[1]["kystnavn"]).strip().replace("_", " "),
                "afstand_m": round(bedst[0])}

    async def kyst(self, kystkode: str, scenarier: list[str], perioder: list[int]) -> dict[str, Any]:
        valgte = [(s, *SCENARIER_KYST[s]) for s in scenarier]
        felter = [(f, n, e, None, d) for f, n, e, d in KYST_INDIKATORER]
        rows, version = await self._rows("VandstandStormflodKyst_latest", f"kystkode='{kystkode}' AND aarstid=1", [f[0] for f in felter])
        return {"version": version, "indikatorer": opstil(rows, felter, valgte, perioder)}

    async def stormflod_m(self, kystkode: str) -> list[dict[str, Any]]:
        """Stormflodshøjder i meter (median) til sammenligning med Havvand på Land."""
        rows, _ = await self._rows("VandstandStormflodKyst_latest", f"kystkode='{kystkode}' AND aarstid=1 AND percentil=50 AND absolutaendring=1",
                                   ["Stormfl20Aarsh", "Stormfl100Aarsh"])
        navne = {0: "historisk", **{k: t for k, t in SCENARIER_KYST.values()}}
        ud = []
        for r in rows:
            if r["scenarie"] not in navne or (r["scenarie"] == 0) != (r["periode"] == 1):
                continue
            for felt, aar in (("Stormfl20Aarsh", 20), ("Stormfl100Aarsh", 100)):
                if r.get(felt) is not None:
                    ud.append({"haendelse": f"{aar}-årsstormflod", "scenarie": navne[r["scenarie"]],
                               "periode": PERIODE_TEKST[r["periode"]], "hoejde_m": round(r[felt] / 100, 2)})
        return ud

    async def status(self) -> str:
        data = await self.get_json(f"{KA}/NedboerKommuner_latest/FeatureServer/0", {"f": "json"}, ttl=0)
        if "error" in data:
            raise RuntimeError(data["error"].get("message"))
        return "ok"

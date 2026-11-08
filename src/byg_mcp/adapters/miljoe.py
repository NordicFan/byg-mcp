"""Jordforurening (DKjord), støjkortlægning (MiljøGIS) og fortidsminder (Fund og Fortidsminder).

Tjeneste-URL'er fundet 8/11-2026 via Miljøportalens katalog-API
(datakatalog.miljoeportal.dk/api/datasets?include=wfsSource,wmsSource,wmtsSource).
Alle nøglefri. Punktopslag med CQL (præcist), ikke BBOX.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

DKJORD_WFS = "https://jord.miljoeportal.dk/geo/wfs"
STOEJ_WFS = "https://wfs2-miljoegis.mim.dk/stoej/wfs"
FF_WFS = "https://www.kulturarv.dk/ffgeoserver/public/wfs"


class JordforureningAdapter(Adapter):
    kilde = Kilde(
        id="D02",
        navn="DKjord - jordforurening",
        udbyder="Regionerne / Danmarks Miljøportal",
        url="https://jord.miljoeportal.dk",
        licens="Frie data - kildeangivelse: Danmarks Miljøportal (DKjord)",
    )
    _LAG = {"V1": "DKJord:View_V1Flader", "V2": "DKJord:View_V2Flader"}
    _FELTER = {
        "Lokalitetsnr": "lokalitetsnr",
        "Lokalitetsnavn": "lokalitetsnavn",
        "Lokalitetetsforureningsstatus": "status",
        "Lokalitetetsadresse": "adresse",
        "Regionsnavn": "region",
        "Lokalitetsmatrikler": "matrikler",
        "Jordforureningsattester": "jordforureningsattest",
        "SenesteInddateringsdato": "senest_opdateret",
    }

    async def ved_punkt(self, x: float, y: float, radius: float = 0) -> dict[str, list[dict[str, Any]]]:
        res = await asyncio.gather(
            *(self.wfs_ved_punkt(DKJORD_WFS, t, "Fladegeometri", x, y, radius, ttl=24 * 3600) for t in self._LAG.values())
        )
        out: dict[str, list[dict[str, Any]]] = {}
        for niveau, rows in zip(self._LAG, res):
            if rows:
                out[niveau] = [{ny: r[gl] for gl, ny in self._FELTER.items() if r.get(gl) not in (None, "")} for r in rows]
        return out

    async def status(self) -> str:
        await self.wfs_ved_punkt(DKJORD_WFS, self._LAG["V1"], "Fladegeometri", 555882, 6323238, ttl=0)
        return "ok"


class StoejAdapter(Adapter):
    kilde = Kilde(
        id="C05",
        navn="Strategisk støjkortlægning",
        udbyder="Miljøstyrelsen (MiljøGIS)",
        url="https://miljoegis.mim.dk",
        licens="Frie data - kildeangivelse: Miljøstyrelsen",
    )
    # Lden i 1,5 m højde (dansk opgørelseshøjde). Geometrifelt 'wkb_geometry'.
    _LAG = {
        "Veje i by": "stoej:b1_dk_aggroad_lden1_5_test",
        "Større veje": "stoej:a1_mroad_lden_1_5",
        "Jernbaner i by (metro, letbane, lokalbane)": "stoej:d1_mtr_agg_rail_lden_1_5",
        "Større jernbaner (Banedanmark)": "stoej:c1_bdk_mrail_lden_1_5",
        "Virksomheder i by": "stoej:mst_agg_ind_lden_1_5_g1",
        "Større lufthavne": "stoej:lufthavne_st_e1_2017",
    }

    @staticmethod
    def _baand(r: dict[str, Any]) -> tuple[int, str] | None:
        """Lagene bruger forskellige felter (verificeret 8/11-2026):
        db_low/db_high, lden_min/lden_max eller kun klasseindeks noise_in.
        noise_in afledes ud fra lag med begge felter: 5=55-59, 4=60-64, 3=65-69, 2=70-74, 1=75+."""
        for lo, hi in (("db_low", "db_high"), ("lden_min", "lden_max")):
            if r.get(lo) not in (None, ""):
                lav = int(float(r[lo]))
                return lav, (f"{lav}-{int(float(r[hi]))} dB" if r.get(hi) not in (None, "") else f"{lav}+ dB")
        if r.get("noise_in") not in (None, "", 0):
            i = int(r["noise_in"])
            lav = 55 + 5 * (5 - i)
            return lav, (f"{lav}-{lav + 4} dB (afledt af støjklasse)" if i > 1 else f"{lav}+ dB (afledt af støjklasse)")
        return None

    async def ved_punkt(self, x: float, y: float) -> dict[str, Any]:
        res = await asyncio.gather(
            *(self.wfs_ved_punkt(STOEJ_WFS, t, "wkb_geometry", x, y) for t in self._LAG.values()),
            return_exceptions=True,
        )
        fundet: dict[str, str] = {}
        fejl: dict[str, str] = {}
        for kilde, rows in zip(self._LAG, res):
            if isinstance(rows, Exception):
                fejl[kilde] = type(rows).__name__
                continue
            baand = [(b, r) for r in rows if (b := self._baand(r))]
            if baand:
                (_, tekst), r = max(baand, key=lambda t: t[0][0])
                aar = re.search(r"(19|20)\d\d", str(r.get("date") or r.get("date_1") or ""))
                fundet[kilde] = tekst + (f", kortlagt {aar.group(0)}" if aar and aar.group(0) != "1899" else "")
        out: dict[str, Any] = {
            "lden_1_5m": fundet or "under kortlægningens nedre grænse (typisk 55 dB) eller uden for kortlagt område",
            "note": "Strategisk støjkortlægning, Lden i 1,5 m. Erstatter ikke en konkret støjberegning.",
        }
        if fejl:
            out["fejl"] = fejl
        return out

    async def status(self) -> str:
        await self.wfs_ved_punkt(STOEJ_WFS, self._LAG["Veje i by"], "wkb_geometry", 724380, 6175700, ttl=0)
        return "ok"


class FortidsmindeAdapter(Adapter):
    kilde = Kilde(
        id="G03",
        navn="Fund og Fortidsminder",
        udbyder="Slots- og Kulturstyrelsen",
        url="https://www.kulturarv.dk/fundogfortidsminder",
        licens="Frie data - kildeangivelse: Slots- og Kulturstyrelsen",
    )
    _FELTER = {"anlaegstype": "anlaegstype", "datering": "datering", "frednr": "frednr", "url": "url"}

    async def ved_punkt(self, x: float, y: float, radius: float = 0) -> dict[str, list[dict[str, Any]]]:
        fredet, beskyt = await asyncio.gather(
            self.wfs_ved_punkt(FF_WFS, "public:fundogfortidsminder_areal_fredet", "geom", x, y, radius),
            self.wfs_ved_punkt(FF_WFS, "public:fundogfortidsminder_areal_beskyttelse", "geom", x, y, radius),
        )

        def rens(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{ny: r[gl] for gl, ny in self._FELTER.items() if r.get(gl)} for r in rows]

        out: dict[str, list[dict[str, Any]]] = {}
        if fredet:
            out["fredet_fortidsminde_areal"] = rens(fredet)
        if beskyt:
            out["fortidsmindebeskyttelseslinje"] = rens(beskyt)
        return out

    async def status(self) -> str:
        await self.wfs_ved_punkt(FF_WFS, "public:fundogfortidsminder_areal_fredet", "geom", 555882, 6323238, ttl=0)
        return "ok"

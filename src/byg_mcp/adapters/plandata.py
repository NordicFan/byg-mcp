"""Plandata.dk via GeoServer WFS (nøglefri). Verificeret i M0, 7/11-2026."""

from __future__ import annotations

import asyncio
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

WFS_URL = "https://geoserver.plandata.dk/geoserver/wfs"

# Lagnavne verificeret mod GetCapabilities. Geometrifeltet hedder 'geometri'.
LAG = {
    "lokalplaner": "pdk:theme_pdk_lokalplan_vedtaget",
    "lokalplan_delomraader": "pdk:theme_pdk_lokalplandelomraade_vedtaget",
    "lokalplanforslag": "pdk:theme_pdk_lokalplan_forslag",
    # '_alle_' medtager rammer fra kommuneplantillæg. Uden den manglede fx 1.1.C1 i Aalborg Midtby.
    "kommuneplanrammer": "pdk:theme_pdk_kommuneplanramme_alle_vedtaget_v",
    "zonestatus": "pdk:theme_pdk_zonekort_v",
    "byggefelter": "pdk:theme_pdk_byggefelt_vedtaget",
}

# Tekniske felter uden værdi for brugeren.
_SKJUL = {"oid", "id", "objektkode", "datooprt", "datoopdt", "datoattr", "datogeom", "datogstart", "komplan_id"}


def _rens(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if v not in (None, "") and k not in _SKJUL}


class PlandataAdapter(Adapter):
    kilde = Kilde(
        id="C01",
        navn="Plandata.dk",
        udbyder="Bolig- og Planstyrelsen",
        url="https://www.plandata.dk",
        licens="Frie data - kildeangivelse: Plandata.dk",
    )

    async def lag_ved_punkt(self, lag: str, x: float, y: float) -> list[dict[str, Any]]:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": lag,
            "outputFormat": "application/json",
            "srsName": "EPSG:25832",
            "CQL_FILTER": f"INTERSECTS(geometri,POINT({x:.2f} {y:.2f}))",
        }
        data = await self.get_json(WFS_URL, params, ttl=7 * 24 * 3600)
        return [_rens(f.get("properties", {})) for f in data.get("features", [])]

    async def plan_ved_punkt(self, x: float, y: float) -> dict[str, Any]:
        navne = list(LAG)
        results = await asyncio.gather(*(self.lag_ved_punkt(LAG[n], x, y) for n in navne), return_exceptions=True)
        out: dict[str, Any] = {}
        fejl: dict[str, str] = {}
        for navn, res in zip(navne, results):
            if isinstance(res, Exception):
                fejl[navn] = f"{type(res).__name__}: {res}"
            else:
                out[navn] = res
        if fejl:
            out["fejl"] = fejl
        return out

    async def plan_efter_id(self, planid: int) -> dict[str, Any] | None:
        """Slå en vedtaget lokalplan op på Plandatas planid (fra plan_gaeldende)."""
        for lag in (LAG["lokalplaner"], LAG["lokalplanforslag"]):
            params = {
                "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": lag,
                "outputFormat": "application/json", "count": "1", "CQL_FILTER": f"planid={int(planid)}",
                "propertyName": "planid,plannr,plannavn,doklink,status,datovedt,kommunenavn",
            }
            data = await self.get_json(WFS_URL, params, ttl=7 * 24 * 3600)
            if data.get("features"):
                return _rens(data["features"][0]["properties"])
        return None

    async def hent_pdf(self, doklink: str, maks_mb: int = 60) -> bytes:
        """Hent planens PDF. Kun dokument.plandata.dk er tilladt (ingen vilkårlige URL'er)."""
        from urllib.parse import urlparse

        u = urlparse(doklink)
        if u.scheme != "https" or u.hostname != "dokument.plandata.dk":
            raise ValueError("Kun PDF'er fra https://dokument.plandata.dk kan hentes")
        resp = await self.client.get(doklink, timeout=120)
        resp.raise_for_status()
        if len(resp.content) > maks_mb * 1024 * 1024:
            raise ValueError(f"PDF'en er større end {maks_mb} MB")
        return resp.content

    async def status(self) -> str:
        await self.lag_ved_punkt(LAG["zonestatus"], 724459, 6175810)
        return "ok"

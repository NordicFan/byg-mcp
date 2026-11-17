"""Oversvømmelse: Havvand på Land og Bluespot fra Danmarks Hydrologiske Højdemodel (Klimadatastyrelsen).

Kilde: Dataforsyningen WMS `wms/dhm` (kræver DATAFORSYNINGEN_TOKEN), lagene
- `dhm_havvandpaaland`: hver celle angiver det havniveau over middelvandstand (m), der oversvømmer cellen.
- `dhm_bluespot_ekstremregn`: lavninger; cellens værdi er den regnmængde (m), der skal til at fylde den.
  Der regnes uden kloak og nedsivning.
Værdien aflæses med GetFeatureInfo som for HIP-grundvandet. Lagnavne og betydning er fra Dataforsyningens
produktsider. Verificeret live 17/11-2026 i Aalborg: værdierne er i meter (Havvand på Land følger terrænkoten,
fx 1,41 m ved havnefronten og 14,94 m på et terræn i kote 14,92). Havvand på Land returnerer 300 for celler
uden gyldig tærskel. Det sås på et sted i kote 2,8 m midt i en bebyggelse og ved UCN i kote 20 m; det tolkes
som "ingen forbindelse til havet i modellen, fx under bygninger", ikke som et havniveau på 300 m.
"""

from __future__ import annotations

import asyncio
import math
import re
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

DHM_HYDRO_WMS = "https://api.dataforsyningen.dk/wms/dhm"
LAG = {"havvand": "dhm_havvandpaaland", "bluespot": "dhm_bluespot_ekstremregn"}
HAVVAND_KODE_INGEN_FORBINDELSE = 299.0  # værdier herover (set: 300) er en kode, ikke et havniveau

_TAL = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"


def feature_info_vaerdi(tekst: str) -> float | None:
    """Første pixelværdi i et GetFeatureInfo-svar (text/plain). Ingen værdi eller nodata → None."""
    for mønster in (
        rf"value_0\s*=\s*'?{_TAL}",                      # MapServer raster
        rf"(?:GRAY_INDEX|Band1|band_1|pixel)\s*=\s*'?{_TAL}",  # GeoServer m.fl.
        rf"\bvalue\s*[=:]\s*'?{_TAL}",
    ):
        if m := re.search(mønster, tekst, flags=re.IGNORECASE):
            v = float(m.group(1))
            if math.isnan(v) or v <= -9000 or abs(v) > 1e20:  # nodata
                return None
            return v
    return None


def ring(x: float, y: float, r: float) -> list[tuple[float, float]]:
    """Punktet selv + 8 punkter på en cirkel med radius r (til 'laveste værdi i nærheden')."""
    if r <= 0:
        return [(x, y)]
    return [(x, y)] + [(x + r * math.cos(a), y + r * math.sin(a)) for a in (i * math.pi / 4 for i in range(8))]


class HydroAdapter(Adapter):
    kilde = Kilde(
        id="E06",
        navn="Havvand på Land og Bluespot (DHM)",
        udbyder="Klimadatastyrelsen",
        url="https://dataforsyningen.dk/data/2695",
        licens="Frie data (CC BY 4.0) - kildeangivelse: Klimadatastyrelsen",
    )

    async def _vaerdi(self, lag: str, x: float, y: float) -> float | None:
        key = f"dhmhydro:{lag}:{round(x)}:{round(y)}"
        if (hit := self.cache.get(key)) is not None:
            return hit if hit != "ingen" else None
        resp = await self.client.get(
            DHM_HYDRO_WMS,
            params={
                "service": "WMS", "version": "1.3.0", "request": "GetFeatureInfo", "layers": lag, "query_layers": lag,
                "crs": "EPSG:25832", "bbox": f"{x - 5},{y - 5},{x + 5},{y + 5}", "width": 25, "height": 25,
                "i": 12, "j": 12, "info_format": "text/plain", "token": self.config.dataforsyningen_token,
            },
        )
        resp.raise_for_status()
        v = feature_info_vaerdi(resp.text)
        self.cache.set(key, v if v is not None else "ingen", 90 * 24 * 3600)
        return v

    async def lag_ved_punkt(self, lag: str, x: float, y: float, radius: float) -> dict[str, Any]:
        sem = asyncio.Semaphore(4)

        async def one(p: tuple[float, float]) -> float | None:
            async with sem:
                return await self._vaerdi(LAG[lag], *p)

        vals = list(await asyncio.gather(*(one(p) for p in ring(x, y, radius))))
        kodede = 0
        if lag == "havvand":
            kodede = sum(1 for v in vals if v is not None and v >= HAVVAND_KODE_INGEN_FORBINDELSE)
            vals = [None if v is not None and v >= HAVVAND_KODE_INGEN_FORBINDELSE else v for v in vals]
        fundne = [v for v in vals if v is not None]
        ud: dict[str, Any] = {"i_punktet": vals[0], "laveste_i_radius": min(fundne) if fundne else None,
                              "antal_punkter": len(vals)}
        if kodede:
            ud["punkter_uden_forbindelse_til_havet"] = kodede
        return ud

    async def status(self) -> str:
        if not self.config.dataforsyningen_token:
            return "ikke konfigureret (DATAFORSYNINGEN_TOKEN mangler)"
        await self._vaerdi(LAG["havvand"], 556500, 6324500)
        return "ok"

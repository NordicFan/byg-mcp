"""Adressesøgning.

1. Dataforsyningen gsearch (officiel, kræver gratis token) - foretrukken.
2. OpenStreetMap Nominatim (nøglefri, fair use max 1 kald/sek) - reserve, så serveren virker uden nøgler.

DAWA er lukket (HTTP 410, verificeret 7/11-2026) og bruges ikke.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

GSEARCH_BASE = "https://api.dataforsyningen.dk/rest/gsearch/v2.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class GsearchAdapter(Adapter):
    kilde = Kilde(
        id="P02",
        navn="Dataforsyningen gsearch (adresser og matrikler)",
        udbyder="Klimadatastyrelsen",
        url="https://dataforsyningen.dk",
        licens="Frie data - kildeangivelse: Klimadatastyrelsen",
    )

    @property
    def aktiv(self) -> bool:
        return bool(self.config.dataforsyningen_token)

    async def _gsearch(self, ressource: str, tekst: str, limit: int, ttl: float = 30 * 24 * 3600) -> list[dict[str, Any]]:
        data = await self.get_json(
            f"{GSEARCH_BASE}/{ressource}",
            {"q": tekst, "limit": limit, "token": self.config.dataforsyningen_token},
            ttl=ttl,
        )
        return data if isinstance(data, list) else []

    async def soeg_husnummer(self, tekst: str, limit: int = 5) -> list[dict[str, Any]]:
        """Adresser på husnummerniveau (adgangsadresser). Verificeret 8/11-2026: `id` er DAR-husnummer-UUID,
        `geometri` er adgangspunktet som MultiPoint i EPSG:25832."""
        hits = []
        for item in await self._gsearch("husnummer", tekst, limit):
            coords = ((item.get("geometri") or {}).get("coordinates") or [[None, None]])[0]
            hits.append(
                {
                    "betegnelse": item.get("visningstekst"),
                    "x": coords[0],
                    "y": coords[1],
                    "husnummer_id": item.get("id"),
                    "kommunekode": item.get("kommunekode"),
                    "kommunenavn": item.get("kommunenavn"),
                    "postnummer": item.get("postnummer"),
                }
            )
        return [h for h in hits if h["x"] is not None]

    async def soeg_matrikel(self, tekst: str, limit: int = 5) -> list[dict[str, Any]]:
        """Matrikler, fx '220, Aalborg Bygrunde'. Verificeret 8/11-2026: giver jordstykke_id, bfenummer og centroide."""
        return [
            {
                "betegnelse": item.get("visningstekst"),
                "x": item.get("centroid_x"),
                "y": item.get("centroid_y"),
                "jordstykke_id": str(item["jordstykke_id"]) if item.get("jordstykke_id") else None,
                "bfe_nummer": item.get("bfenummer"),
                "kommunekode": item.get("kommunekode"),
                "kommunenavn": item.get("kommunenavn"),
            }
            for item in await self._gsearch("matrikel", tekst, limit)
            if item.get("centroid_x") is not None
        ]

    async def status(self) -> str:
        if not self.aktiv:
            return "ikke konfigureret (DATAFORSYNINGEN_TOKEN mangler)"
        await self._gsearch("husnummer", "Rådhuspladsen 1 København", 1, ttl=0)  # altid live: tester tokenet
        return "ok"


class NominatimAdapter(Adapter):
    kilde = Kilde(
        id="B09",
        navn="OpenStreetMap Nominatim",
        udbyder="OpenStreetMap Foundation",
        url="https://nominatim.openstreetmap.org",
        licens="ODbL - © OpenStreetMap-bidragydere",
    )
    _last_call = 0.0
    _lock = asyncio.Lock()

    async def soeg(self, tekst: str, limit: int = 5) -> list[dict[str, Any]]:
        async with self._lock:  # fair use: max 1 kald pr. sekund
            wait = 1.0 - (time.monotonic() - NominatimAdapter._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            NominatimAdapter._last_call = time.monotonic()
            data = await self.get_json(
                NOMINATIM_URL,
                {"q": tekst, "format": "jsonv2", "countrycodes": "dk", "limit": limit, "addressdetails": 1},
                ttl=30 * 24 * 3600,
            )
        return [
            {
                "betegnelse": d.get("display_name"),
                "lat": float(d["lat"]),
                "lon": float(d["lon"]),
                "type": d.get("type"),
                "postnr": (d.get("address") or {}).get("postcode"),
            }
            for d in data
        ]

    async def status(self) -> str:
        await self.soeg("Rådhuspladsen 1, København", 1)
        return "ok"

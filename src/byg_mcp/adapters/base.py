"""Fælles grundlag for kildeadaptere: kildeangivelse, HTTP-klient og simpel TTL-cache."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from byg_mcp.infra.config import Config


@dataclass(frozen=True)
class Kilde:
    """Statisk beskrivelse af en datakilde (svarer til en række i kildekataloget)."""

    id: str
    navn: str
    udbyder: str
    url: str
    licens: str


@dataclass
class Kildeangivelse:
    """Kildeangivelse, der følger med hvert svar."""

    navn: str
    udbyder: str
    url: str
    licens: str
    hentet: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    note: str | None = None

    @classmethod
    def fra(cls, kilde: Kilde, note: str | None = None) -> "Kildeangivelse":
        return cls(kilde.navn, kilde.udbyder, kilde.url, kilde.licens, note=note)

    def dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class KildeOverbelastet(RuntimeError):
    """Kilden svarer 429/503. Meldes til modellen som en forståelig fejl."""


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: float) -> None: ...


class TTLCache:
    """In-memory cache (bruges i tests). Serveren bruger infra.cache.SQLiteCache."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        expires, value = hit
        if time.monotonic() > expires:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._data[key] = (time.monotonic() + ttl, value)


class Adapter:
    """Basisklasse. Adaptere kender intet til MCP."""

    kilde: Kilde

    def __init__(self, config: Config, client: httpx.AsyncClient, cache: Cache) -> None:
        self.config = config
        self.client = client
        self.cache = cache

    async def get_json(self, url: str, params: dict[str, Any] | None = None, ttl: float = 0, **kw: Any) -> Any:
        # Hemmeligheder må aldrig indgå i cache-nøglen (den gemmes på disk).
        key = f"{url}?{sorted((k, v) for k, v in (params or {}).items() if k.lower() not in {'token', 'apikey'})}"
        if ttl and (cached := self.cache.get(key)) is not None:
            return cached
        resp = await self.client.get(url, params=params, **kw)
        if resp.status_code in (429, 503):  # overbelastet kilde: ét genforsøg efter kort pause
            import asyncio

            try:
                vent = min(5.0, float(resp.headers.get("Retry-After", "2")))
            except ValueError:
                vent = 2.0
            await asyncio.sleep(vent)
            resp = await self.client.get(url, params=params, **kw)
            if resp.status_code in (429, 503):
                raise KildeOverbelastet(f"{self.kilde.navn} er midlertidigt overbelastet (HTTP {resp.status_code}). Prøv igen om lidt.")
        resp.raise_for_status()
        data = resp.json()
        if ttl:
            self.cache.set(key, data, ttl)
        return data

    async def wfs_ved_punkt(
        self,
        url: str,
        typ: str,
        geom: str,
        x: float,
        y: float,
        radius: float = 0,
        felter: list[str] | None = None,
        count: int = 20,
        ttl: float = 7 * 24 * 3600,
    ) -> list[dict[str, Any]]:
        """Præcist punktopslag i en GeoServer-WFS (EPSG:25832). BBOX bruges ikke, fordi flere servere
        har 'loose bbox' slået til og returnerer objekter, hvis omsluttende rektangel rammer punktet."""
        punkt = f"POINT({x:.2f} {y:.2f})"
        cql = f"INTERSECTS({geom},{punkt})" if radius <= 0 else f"DWITHIN({geom},{punkt},{radius},meters)"
        params: dict[str, Any] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": typ,
            "outputFormat": "application/json",
            "count": str(count),
            "srsName": "EPSG:25832",
            "CQL_FILTER": cql,
        }
        if felter:
            params["propertyName"] = ",".join(felter)
        data = await self.get_json(url, params, ttl=ttl)
        return [
            {k: v for k, v in (f.get("properties") or {}).items() if v not in (None, "") and not k.startswith("_")}
            for f in data.get("features", [])
        ]

    def angivelse(self, note: str | None = None) -> Kildeangivelse:
        return Kildeangivelse.fra(self.kilde, note)


def make_client(config: Config) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=config.http_timeout,
        headers={"User-Agent": config.user_agent},
        follow_redirects=True,
    )

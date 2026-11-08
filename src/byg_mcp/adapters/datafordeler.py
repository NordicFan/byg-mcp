"""Datafordeleren - moderniserede GraphQL-tjenester.

Verificeret 7-8/11-2026:
- Endepunkt: https://graphql.datafordeler.dk/<tjeneste>/<version>, skema på .../schema
- Auth: ?apiKey=<nøgle> fra et IT-system på portal.datafordeler.dk. Nye nøgler er aktive efter ca. 15 min.
- Registerspecifikke tjenester (DAR/v3, BBR/v3, MAT/v3, DAGI/v2, EBR/v1) kræver filter på id_lokalId.
- **FlexibleCurrent/v3** kræver kun `virkningstid` og tillader filtre på relationer (fx BBR_Bygning.jordstykke)
  og geografi (intersects/within med WKT + crs). Det er den, vi bruger.
- ID-filtre understøtter `eq` og `in` (maks. 100 værdier).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

GRAPHQL_BASE = "https://graphql.datafordeler.dk"
FLEX = ("FlexibleCurrent", "v3")


class DatafordelerError(RuntimeError):
    pass


def _nu() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DatafordelerAdapter(Adapter):
    kilde = Kilde(
        id="P01",
        navn="Datafordeleren (DAR, MAT, BBR)",
        udbyder="Klimadatastyrelsen / Bolig- og Planstyrelsen",
        url="https://datafordeler.dk",
        licens="Frie grunddata - kildeangivelse: Klimadatastyrelsen (DAR, MAT) og Bolig- og Planstyrelsen (BBR)",
    )

    @property
    def aktiv(self) -> bool:
        return bool(self.config.datafordeler_api_key)

    def _tjek(self, resp: Any, hvad: str) -> None:
        """Rejs fejl UDEN URL: URL'en indeholder API-nøglen og må aldrig logges eller returneres."""
        if resp.status_code >= 400:
            detalje = resp.text[:300].replace(self.config.datafordeler_api_key or "\0", "***")
            raise DatafordelerError(f"{hvad}: HTTP {resp.status_code} {detalje}".strip())

    async def query(self, tjeneste: str, version: str, query: str, variables: dict[str, Any] | None = None) -> Any:
        if not self.aktiv:
            raise DatafordelerError("DATAFORDELER_API_KEY er ikke sat")
        resp = await self.client.post(
            f"{GRAPHQL_BASE}/{tjeneste}/{version}",
            params={"apiKey": self.config.datafordeler_api_key},
            json={"query": query, "variables": variables or {}},
        )
        self._tjek(resp, f"{tjeneste}/{version} query")
        data = resp.json()
        if data.get("errors"):
            raise DatafordelerError(str(data["errors"])[:500])
        return data.get("data")

    async def aktuel(self, entitet: str, felter: str, where: dict[str, Any], first: int = 100, ttl: float = 24 * 3600) -> list[dict]:
        """Hent aktuelle (gældende nu) objekter af en entitet fra FlexibleCurrent. Resultatet caches."""
        key = "df:" + hashlib.sha1(json.dumps([entitet, felter, where, first], sort_keys=True).encode()).hexdigest()
        if ttl and (hit := self.cache.get(key)) is not None:
            return hit
        q = (
            f"query($t: DafDateTime!, $w: {entitet}FilterInput) "
            f"{{ {entitet}(first: {first}, virkningstid: $t, where: $w) {{ nodes {{ {felter} }} }} }}"
        )
        data = await self.query(*FLEX, q, {"t": _nu(), "w": where})
        nodes = (data or {}).get(entitet, {}).get("nodes", [])
        if ttl:
            self.cache.set(key, nodes, ttl)
        return nodes

    async def schema(self, tjeneste: str, version: str = "v1") -> str:
        resp = await self.client.get(
            f"{GRAPHQL_BASE}/{tjeneste}/{version}/schema", params={"apiKey": self.config.datafordeler_api_key}
        )
        self._tjek(resp, f"{tjeneste}/{version} schema")
        return resp.text

    async def status(self) -> str:
        if not self.aktiv:
            return "ikke konfigureret (DATAFORDELER_API_KEY mangler)"
        await self.aktuel("MAT_Ejerlav", "ejerlavsnavn", {"ejerlavskode": {"eq": 2005051}}, first=1, ttl=0)
        return "ok"

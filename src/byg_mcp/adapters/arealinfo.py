"""Danmarks Arealinformation (Danmarks Miljøportal) via GeoServer WFS (nøglefri).

Verificeret i M0, 7/11-2026: workspace 'dai' med 25 lag. BBOX-filter i EPSG:25832 virker.
Jordforurening (V1/V2), støj, strandbeskyttelse og fortidsminder ligger IKKE i dette workspace
og skal findes i M2 (datakatalog.miljoeportal.dk/api lister 1500+ datasæt).
"""

from __future__ import annotations

import asyncio
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

WFS_URL = "https://arealeditering-dist-geo.miljoeportal.dk/geoserver/wfs"

LAG = {
    "dai:soe_bes_linjer": "Søbeskyttelseslinjer",
    "dai:aa_bes_linjer": "Åbeskyttelseslinjer",
    "dai:skovbyggelinjer": "Skovbyggelinjer",
    "dai:kirkebyggelinjer": "Kirkebyggelinjer",
    "dai:fredede_omr": "Fredede områder",
    "dai:fredede_omr_forslag": "Fredede områder, forslag",
    "dai:fredede_omr_bk": "Bekendtgørelsesfredninger",
    "dai:bes_naturtyper": "Beskyttede naturtyper (§ 3)",
    "dai:bes_vandloeb": "Beskyttede vandløb (§ 3)",
    "dai:bes_sten_jorddiger_2022": "Beskyttede sten- og jorddiger",
    "dai:fugle_bes_omr": "Natura 2000 - fuglebeskyttelsesområder",
    "dai:habitat_omr": "Natura 2000 - habitatområder",
    "dai:ramsar_omr": "Ramsarområder",
    "dai:natur_vildt_reservat": "Natur- og vildtreservater",
    "dai:omr_klassificering": "Områdeklassificering (lettere forurenet byjord)",
    "dai:raastofomr": "Råstofområder",
    "dai:indsatsplaner": "Indsatsplaner for grundvandsbeskyttelse",
    "dai:aftarea_grvbes": "Aftaleområder for grundvand",
    "dai:status_bnbo": "Boringsnære beskyttelsesområder (BNBO)",
}

_SKJUL_PREFIX = (
    "Systid", "Version_id", "Oprettet", "Oprindkode", "Statuskode", "Off_kode", "CVR_kode", "Bruger_id",
    "Shape_", "Objekt_id", "Offentlig", "Temakode", "Komtlf", "Komemailad", "Komurl_link", "Oprindelse",
)
_UGYLDIGE = ("Ukendt ved migrering", "Ikke udfyldt")


def _rens(props: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in props.items()
        if v not in (None, "", 0)
        and not k.startswith(_SKJUL_PREFIX)
        and not (isinstance(v, str) and v.startswith(_UGYLDIGE))
    }


class ArealinfoAdapter(Adapter):
    kilde = Kilde(
        id="D01",
        navn="Danmarks Arealinformation",
        udbyder="Danmarks Miljøportal / Miljøstyrelsen",
        url="https://danmarksarealinformation.miljoeportal.dk",
        licens="Frie data - kildeangivelse: Danmarks Miljøportal",
    )

    async def lag_ved_punkt(self, lag: str, x: float, y: float, radius: float) -> list[dict[str, Any]]:
        # Geometrifeltet hedder 'Shape' i alle dai-lag (verificeret 8/11-2026).
        return [_rens(p) for p in await self.wfs_ved_punkt(WFS_URL, lag, "Shape", x, y, radius)]

    async def restriktioner(self, x: float, y: float, radius: float = 0) -> dict[str, Any]:
        sem = asyncio.Semaphore(8)

        async def one(lag: str) -> list[dict[str, Any]]:
            async with sem:
                return await self.lag_ved_punkt(lag, x, y, radius)

        results = await asyncio.gather(*(one(lag) for lag in LAG), return_exceptions=True)
        fundet: dict[str, Any] = {}
        ikke_fundet: list[str] = []
        fejl: dict[str, str] = {}
        for lag, res in zip(LAG, results):
            titel = LAG[lag]
            if isinstance(res, Exception):
                fejl[titel] = f"{type(res).__name__}: {res}"
            elif res:
                fundet[titel] = res
            else:
                ikke_fundet.append(titel)
        out: dict[str, Any] = {"fundet": fundet, "ikke_fundet": ikke_fundet}
        if fejl:
            out["fejl"] = fejl
        return out

    async def status(self) -> str:
        await self.wfs_ved_punkt(WFS_URL, "dai:omr_klassificering", "Shape", 555882, 6323238, ttl=0)
        return "ok"

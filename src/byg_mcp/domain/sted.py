"""Sted: det centrale objekt, som alle andre værktøjer tager udgangspunkt i.

M0: koordinater og adressetekst. M1 tilføjer DAR-ID, BFE-nummer, jordstykker og BBR-ID'er via Datafordeleren.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pyproj import Transformer

_TIL_UTM = Transformer.from_crs(4326, 25832, always_xy=True)
_TIL_WGS = Transformer.from_crs(25832, 4326, always_xy=True)

# Groft Danmark-vindue i EPSG:25832 - fanger ombyttede eller forkerte koordinater.
_DK_X = (400_000, 900_000)
_DK_Y = (6_000_000, 6_420_000)


@dataclass
class Sted:
    x: float  # EPSG:25832 (ETRS89 / UTM 32N)
    y: float
    lat: float  # WGS84
    lon: float
    betegnelse: str | None = None
    kilde: str | None = None
    noter: list[str] = field(default_factory=list)

    @classmethod
    def fra_utm(cls, x: float, y: float, **kw: Any) -> "Sted":
        if not (_DK_X[0] <= x <= _DK_X[1] and _DK_Y[0] <= y <= _DK_Y[1]):
            raise ValueError(f"Koordinaten ({x}, {y}) ligger ikke i Danmark (forventer EPSG:25832, x≈400-900k, y≈6.0-6.4M)")
        lon, lat = _TIL_WGS.transform(x, y)
        return cls(x=round(x, 2), y=round(y, 2), lat=round(lat, 7), lon=round(lon, 7), **kw)

    @classmethod
    def fra_wgs84(cls, lat: float, lon: float, **kw: Any) -> "Sted":
        x, y = _TIL_UTM.transform(lon, lat)
        return cls.fra_utm(x, y, **kw)

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d["noter"]:
            d.pop("noter")
        return {k: v for k, v in d.items() if v is not None}

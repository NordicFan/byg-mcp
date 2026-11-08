"""Terrænanalyse af en grund ud fra Danmarks Højdemodel (terræn = DTM, overflade = DSM)."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import shapely
from shapely import wkt as shapely_wkt
from shapely.geometry import Point

from byg_mcp.adapters.geo import HoejdemodelAdapter


def _r(v: float | None, n: int = 2) -> float | None:
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), n)


async def analyse(
    dhm: HoejdemodelAdapter,
    x: float,
    y: float,
    grund_wkt: str | None = None,
    omgivelser_m: float = 30,
) -> dict[str, Any]:
    grund = shapely_wkt.loads(grund_wkt) if grund_wkt else Point(x, y).buffer(10)
    zone = grund.buffer(omgivelser_m)
    x0, y0, x1, y1 = zone.bounds
    dtm, dsm = await asyncio.gather(
        dhm.raster("dhm_terraen", (x0, y0, x1, y1)), dhm.raster("dhm_overflade", (x0, y0, x1, y1))
    )
    rows, cols = dtm.shape
    dx, dy = (x1 - x0) / cols, (y1 - y0) / rows
    xs = x0 + (np.arange(cols) + 0.5) * dx
    ys = y1 - (np.arange(rows) + 0.5) * dy
    X, Y = np.meshgrid(xs, ys)
    m_grund = shapely.contains_xy(grund, X, Y)
    m_omg = shapely.contains_xy(zone, X, Y) & ~m_grund
    ndsm = dsm - dtm  # højde over terræn: bygninger, træer m.m.

    i = int(np.clip((y1 - y) / dy, 0, rows - 1))
    j = int(np.clip((x - x0) / dx, 0, cols - 1))
    gy, gx = np.gradient(dtm, dy, dx)
    haeldning_pct = np.hypot(gx, gy) * 100

    g = dtm[m_grund]
    out: dict[str, Any] = {
        "kote_i_punktet_m": _r(dtm[i, j]),
        "grund": {
            "grundlag": "matrikelgrænse" if grund_wkt else "cirkel med radius 10 m (ingen matrikelgrænse)",
            "areal_m2": round(grund.area),
            "terraen_min_m": _r(np.nanmin(g)) if g.size else None,
            "terraen_max_m": _r(np.nanmax(g)) if g.size else None,
            "terraen_middel_m": _r(np.nanmean(g)) if g.size else None,
            "hoejdeforskel_m": _r(np.nanmax(g) - np.nanmin(g)) if g.size else None,
            "middel_haeldning_pct": _r(np.nanmean(haeldning_pct[m_grund]), 1) if g.size else None,
            "maks_hoejde_over_terraen_m": _r(np.nanmax(ndsm[m_grund])) if g.size else None,
        },
        "omgivelser": {
            "zone": f"{omgivelser_m:g} m omkring grunden",
            "terraen_min_m": _r(np.nanmin(dtm[m_omg])),
            "terraen_max_m": _r(np.nanmax(dtm[m_omg])),
            "maks_hoejde_over_terraen_m": _r(np.nanmax(ndsm[m_omg])),
            "hoejde_over_terraen_p90_m": _r(np.nanpercentile(ndsm[m_omg], 90)),
        },
        "opløsning_m": round(max(dx, dy), 2),
        "note": "Koter i DVR90. 'Højde over terræn' er overflademodel minus terrænmodel og omfatter både bygninger "
        "og træer. Det er en indikator for nabobebyggelsens højde, ikke en opmåling.",
    }
    return out

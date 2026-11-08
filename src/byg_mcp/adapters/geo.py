"""Terræn (Danmarks Højdemodel), geologi og boringer (GEUS), terrænnært grundvand (HIP) og ortofoto.

Tjenester verificeret 8/11-2026:
- DHM: Dataforsyningen WCS 1.0 `dhm_wcs_DAF`, coverages `dhm_terraen` og `dhm_overflade`, kun GTiff, 0,4 m.
  (Datafordelerens DHMKoter-REST er udfaset og svarer 403.)
- GEUS Jupiter: MapServer WFS `data.geus.dk/geusmap/ows/25832.jsp` (nøglefri).
- GEUS jordartskort: ArcGIS REST `data.geus.dk/arcgis/rest/services/Denmark/Jordartskort_25000|_200000`.
- HIP: Dataforsyningen WMS `wms/hip_statistics`, GetFeatureInfo som text/plain.
- Ortofoto: Dataforsyningen WMS `orto_foraar_DAF`.
"""

from __future__ import annotations

import asyncio
import io
import math
import re
from typing import Any

import numpy as np

from byg_mcp.adapters.base import Adapter, Kilde

DHM_WCS = "https://api.dataforsyningen.dk/dhm_wcs_DAF"
GEUS_WFS = "https://data.geus.dk/geusmap/ows/25832.jsp"
GEUS_ARCGIS = "https://data.geus.dk/arcgis/rest/services/Denmark"
HIP_WMS = "https://api.dataforsyningen.dk/wms/hip_statistics"
ORTO_WMS = "https://api.dataforsyningen.dk/orto_foraar_DAF"
DHM_WMS = "https://api.dataforsyningen.dk/dhm_DAF"


class HoejdemodelAdapter(Adapter):
    kilde = Kilde(
        id="B02",
        navn="Danmarks Højdemodel (DHM)",
        udbyder="Klimadatastyrelsen",
        url="https://dataforsyningen.dk/data/930",
        licens="Frie data - kildeangivelse: Klimadatastyrelsen. Koter i DVR90.",
    )

    async def raster(self, coverage: str, bbox: tuple[float, float, float, float], maks_px: int = 600) -> np.ndarray:
        """Hent et udsnit af terræn- eller overflademodellen. Opløsning 0,4 m, men nedskaleret til maks_px."""
        import tifffile

        x0, y0, x1, y1 = bbox
        bredde = max(2, min(maks_px, math.ceil((x1 - x0) / 0.4)))
        hoejde = max(2, min(maks_px, math.ceil((y1 - y0) / 0.4)))
        resp = await self.client.get(
            DHM_WCS,
            params={
                "service": "WCS", "version": "1.0.0", "request": "GetCoverage", "coverage": coverage,
                "crs": "EPSG:25832", "bbox": f"{x0},{y0},{x1},{y1}", "width": bredde, "height": hoejde,
                "format": "GTiff", "token": self.config.dataforsyningen_token,
            },
            timeout=90,
        )
        resp.raise_for_status()
        if "tiff" not in resp.headers.get("content-type", ""):
            raise RuntimeError("Højdemodellen returnerede ikke et rasterbillede")
        a = tifffile.imread(io.BytesIO(resp.content)).astype("float64")
        return np.where(a < -1000, np.nan, a)

    async def status(self) -> str:
        if not self.config.dataforsyningen_token:
            return "ikke konfigureret (DATAFORSYNINGEN_TOKEN mangler)"
        await self.raster("dhm_terraen", (555880, 6323236, 555884, 6323240), 4)
        return "ok"


class GeusAdapter(Adapter):
    kilde = Kilde(
        id="D03",
        navn="GEUS - Jupiter og jordartskort",
        udbyder="De Nationale Geologiske Undersøgelser for Danmark og Grønland (GEUS)",
        url="https://www.geus.dk",
        licens="Frie data - kildeangivelse: GEUS (Jupiter-databasen, Danmarks digitale jordartskort)",
    )

    async def _wfs_bbox(self, typ: str, x: float, y: float, r: float, maks: int = 200) -> list[dict[str, Any]]:
        params = {
            "service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": typ,
            "maxFeatures": str(maks), "bbox": f"{x - r},{y - r},{x + r},{y + r},EPSG:25832", "outputFormat": "geojson",
        }
        data = await self.get_json(GEUS_WFS, params, ttl=30 * 24 * 3600)
        return [f.get("properties") or {} for f in data.get("features", [])]

    async def boringer(self, x: float, y: float, radius: float = 300, maks: int = 8) -> list[dict[str, Any]]:
        bor, lith, pejl = await asyncio.gather(
            self._wfs_bbox("ms:jupiter_boringer_ws", x, y, radius),
            self._wfs_bbox("ms:jupiter_lithologi_over_10m_dybe", x, y, radius),
            self._wfs_bbox("ms:jupiter_boringer_seneste_pejling", x, y, radius),
            return_exceptions=True,
        )
        if isinstance(bor, Exception):
            raise bor
        lith_map = {} if isinstance(lith, Exception) else {l.get("dgunr"): l.get("dgusymboler") for l in lith}
        pejl_map = {} if isinstance(pejl, Exception) else {p.get("dgunr"): p for p in pejl}
        ud = []
        for b in bor:
            try:
                afstand = math.hypot(float(b["xutm"]) - x, float(b["yutm"]) - y)
            except (KeyError, TypeError, ValueError):
                continue
            if afstand > radius:
                continue
            rec: dict[str, Any] = {
                "dgunr": (b.get("dgunr") or "").strip(),
                "afstand_m": round(afstand),
                "dybde_m": b.get("dybde_num"),
                "aar": b.get("aar_num"),
                "formaal": b.get("formaal_tekst"),
                "anvendelse": b.get("anvendelse_tekst"),
                "terraenkote_m": float(b["terraen_kote"]) if b.get("terraen_kote") not in (None, "") else None,
                "borerapport": b.get("url"),
            }
            if lith_map.get(b.get("dgunr")):
                rec["jordlag_dgu_symboler"] = lith_map[b["dgunr"]]
            if (p := pejl_map.get(b.get("dgunr"))) and p.get("vandstandterraen_num") not in (None, ""):
                rec["seneste_vandstand_under_terraen_m"] = float(p["vandstandterraen_num"])
                rec["pejledato"] = p.get("pejletidspunkt")
            # 0 i dybde/år betyder 'ikke registreret' i Jupiter.
            ud.append({k: v for k, v in rec.items() if v not in (None, "") and not (k in ("dybde_m", "aar") and not v)})
        ud.sort(key=lambda r: (r["afstand_m"], -(r.get("dybde_m") or 0)))
        return ud[:maks]

    async def jordart(self, x: float, y: float) -> dict[str, Any]:
        async def query(tjeneste: str, lag: int) -> list[dict[str, Any]]:
            data = await self.get_json(
                f"{GEUS_ARCGIS}/{tjeneste}/MapServer/{lag}/query",
                {"geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "inSR": 25832,
                 "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false", "f": "json"},
                ttl=90 * 24 * 3600,
            )
            return [f.get("attributes") or {} for f in data.get("features", [])]

        d25, d200 = await asyncio.gather(query("Jordartskort_25000", 1), query("Jordartskort_200000", 1), return_exceptions=True)
        out: dict[str, Any] = {}
        if not isinstance(d25, Exception) and d25:
            a = d25[0]
            out["jordartskort_25000"] = {
                "jordart": (a.get("Jordart") or "").strip(),
                "tidsalder": (a.get("Tidsalder") or "").strip(),
                "symbol": a.get("tsym"),
                "version": a.get("Version"),
            }
        if not isinstance(d200, Exception) and d200:
            out["jordartskort_200000"] = {"symbol": d200[0].get("tsym")}
        if out.get("jordartskort_25000", {}).get("symbol") == "BY":
            out["note"] = "Byområde er ikke kortlagt på jordartskortet. Brug boringer til at vurdere jordbunden."
        return out

    async def status(self) -> str:
        await self._wfs_bbox("ms:jupiter_boringer_ws", 555882, 6323238, 50, 1)
        return "ok"


class GrundvandAdapter(Adapter):
    kilde = Kilde(
        id="D05",
        navn="HIP - terrænnært grundvand",
        udbyder="Klimadatastyrelsen / GEUS (Hydrologisk Informations- og Prognosesystem)",
        url="https://hip.dataforsyningen.dk",
        licens="Frie data - kildeangivelse: Klimadatastyrelsen (HIP)",
    )
    _LAG = {
        "vinter": "shallow_groundwater_depth_statistics_10m_winter_p50_1991_2025",
        "sommer": "shallow_groundwater_depth_statistics_10m_summer_p50_1991_2025",
    }

    async def _vaerdi(self, lag: str, x: float, y: float) -> float | None:
        key = f"hip:{lag}:{round(x)}:{round(y)}"
        if (hit := self.cache.get(key)) is not None:
            return hit if hit != "ingen" else None
        resp = await self.client.get(
            HIP_WMS,
            params={
                "service": "WMS", "version": "1.3.0", "request": "GetFeatureInfo", "layers": lag, "query_layers": lag,
                "crs": "EPSG:25832", "bbox": f"{x - 50},{y - 50},{x + 50},{y + 50}", "width": 101, "height": 101,
                "i": 50, "j": 50, "info_format": "text/plain", "token": self.config.dataforsyningen_token,
            },
        )
        resp.raise_for_status()
        m = re.search(r"value_0\s*=\s*'(-?[\d.]+)'", resp.text)
        v = float(m.group(1)) if m else None
        self.cache.set(key, v if v is not None else "ingen", 90 * 24 * 3600)
        return v

    async def ved_punkt(self, x: float, y: float) -> dict[str, Any]:
        vinter, sommer = await asyncio.gather(*(self._vaerdi(l, x, y) for l in self._LAG.values()))
        # Værdierne er i centimeter (fx 145 ved Aalborg havnefront, 2,8 m over havet).
        out = {
            k: round(v / 100, 2)
            for k, v in (("dybde_vinter_m", vinter), ("dybde_sommer_m", sommer))
            if v is not None
        }
        if not out:
            return {"note": "Ingen værdi i punktet"}
        return {
            **out,
            "forklaring": "Mest sandsynlige dybde (50. percentil) til terrænnært grundvand, 10 m-grid, 1991-2025. "
            "Vinter er typisk det højeste grundvandsspejl og bruges ved kældre, dræn og LAR.",
        }

    async def status(self) -> str:
        if not self.config.dataforsyningen_token:
            return "ikke konfigureret (DATAFORSYNINGEN_TOKEN mangler)"
        await self._vaerdi(self._LAG["vinter"], 555882, 6323238)
        return "ok"


class KortAdapter(Adapter):
    kilde = Kilde(
        id="B03",
        navn="Ortofoto og skyggekort",
        udbyder="Klimadatastyrelsen / GeoDanmark",
        url="https://dataforsyningen.dk",
        licens="Frie data - kildeangivelse: Klimadatastyrelsen, GeoDanmark",
    )
    LAG = {
        "ortofoto": (ORTO_WMS, "orto_foraar", "image/jpeg"),
        "terraen_skyggekort": (DHM_WMS, "dhm_terraen_skyggekort", "image/png"),
        "overflade_skyggekort": (DHM_WMS, "dhm_overflade_skyggekort", "image/png"),
    }

    async def billede(self, lag: str, x: float, y: float, side_m: float, px: int = 800) -> tuple[bytes, str]:
        url, wms_lag, fmt = self.LAG[lag]
        h = side_m / 2
        resp = await self.client.get(
            url,
            params={
                "service": "WMS", "version": "1.3.0", "request": "GetMap", "layers": wms_lag, "styles": "",
                "crs": "EPSG:25832", "bbox": f"{x - h},{y - h},{x + h},{y + h}", "width": px, "height": px,
                "format": fmt, "token": self.config.dataforsyningen_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        if not resp.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError("Korttjenesten returnerede ikke et billede")
        return resp.content, fmt.split("/")[1]

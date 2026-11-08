"""Klima og energi: DMI klimadata, PVGIS (sol/PV og vejrfiler) og Energi Data Service (CO2 for el).

Verificeret 8/11-2026 (alle nøglefri):
- DMI: https://opendataapi.dmi.dk/v2/climateData/collections/municipalityValue/items
  (parameterId, municipalityId, timeResolution=year). Nøglefri siden 2/12-2025.
- PVGIS 5.3: https://re.jrc.ec.europa.eu/api/v5_3/PVcalc og /tmy (outputformat=epw)
- Energinet: https://api.energidataservice.dk/dataset/CO2Emis (5-min, DK1/DK2)
"""

from __future__ import annotations

import asyncio
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any

from byg_mcp.adapters.base import Adapter, Kilde

DMI = "https://opendataapi.dmi.dk/v2/climateData/collections/municipalityValue/items"
PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3"
EDS = "https://api.energidataservice.dk/dataset"

# DMI-parametre der er relevante for bygningsdesign → (dansk navn, enhed, aggregering over år)
DMI_PARAMETRE = {
    "mean_temp": ("Middeltemperatur", "°C", "middel"),
    "mean_daily_max_temp": ("Middel af døgnets maks.-temperatur", "°C", "middel"),
    "min_temp": ("Laveste temperatur", "°C", "min"),
    "max_temp_w_date": ("Højeste temperatur", "°C", "maks"),
    "acc_heating_degree_days_17": ("Graddage (basis 17 °C)", "graddage", "middel"),
    "acc_precip": ("Årsnedbør", "mm", "middel"),
    "max_precip_30m": ("Største 30-min. nedbør", "mm", "maks"),
    "no_days_acc_precip_10": ("Dage med mindst 10 mm nedbør", "dage", "middel"),
    "mean_wind_speed": ("Middelvindhastighed", "m/s", "middel"),
    "max_wind_speed_3sec": ("Største vindstød (3 sek.)", "m/s", "maks"),
    "mean_wind_dir": ("Fremherskende vindretning (middel)", "grader", "middel"),
    "bright_sunshine": ("Solskinstimer", "timer", "middel"),
    "mean_radiation": ("Globalstråling (middel)", "W/m²", "middel"),
    "mean_relative_hum": ("Relativ luftfugtighed", "%", "middel"),
    "no_summer_days": ("Sommerdage (> 25 °C)", "dage", "middel"),
    "no_tropical_nights": ("Tropenætter (> 20 °C)", "dage", "middel"),
    "no_frost_days": ("Frostdøgn", "dage", "middel"),
    "snow_depth": ("Største snedybde", "cm", "maks"),
}


class DmiAdapter(Adapter):
    kilde = Kilde(
        id="E01",
        navn="DMI klimadata (kommuneværdier)",
        udbyder="Danmarks Meteorologiske Institut",
        url="https://opendatadocs.dmi.govcloud.dk",
        licens="Frie data - kildeangivelse: DMI",
    )

    async def _parameter(self, kommunekode: str, param: str, aar_fra: int, aar_til: int) -> dict[int, float]:
        data = await self.get_json(
            DMI,
            {
                "municipalityId": kommunekode, "parameterId": param, "timeResolution": "year",
                "datetime": f"{aar_fra}-01-01T00:00:00Z/{aar_til}-12-31T23:59:59Z", "limit": 200,
            },
            ttl=30 * 24 * 3600,
        )
        pr_aar: dict[int, tuple[int, float]] = {}
        for f in data.get("features", []):
            p = f["properties"]
            aar = int(p["from"][:4])
            if not aar_fra <= aar <= aar_til:  # tidszone-forskydning kan give et år for meget
                continue
            prioritet = 1 if p.get("qcStatus") == "manual" else 0  # kvalitetskontrollerede værdier foretrækkes
            if aar not in pr_aar or prioritet > pr_aar[aar][0]:
                pr_aar[aar] = (prioritet, p["value"])
        return {a: v for a, (_, v) in sorted(pr_aar.items())}

    async def klima(self, kommunekode: str, aar: int = 10) -> dict[str, Any]:
        til = date.today().year - 1  # seneste hele år
        fra = til - aar + 1
        sem = asyncio.Semaphore(6)

        async def one(p: str) -> dict[int, float]:
            async with sem:
                return await self._parameter(kommunekode, p, fra, til)

        res = await asyncio.gather(*(one(p) for p in DMI_PARAMETRE), return_exceptions=True)
        ud: dict[str, Any] = {}
        for p, r in zip(DMI_PARAMETRE, res):
            if isinstance(r, Exception) or not r:
                continue
            navn, enhed, agg = DMI_PARAMETRE[p]
            vals = list(r.values())
            v = {"middel": statistics.fmean(vals), "min": min(vals), "maks": max(vals)}[agg]
            ud[navn] = {"vaerdi": round(v, 1), "enhed": enhed, "grundlag": f"{agg} af {len(vals)} år",
                        "seneste_aar": {str(max(r)): r[max(r)]}}
        return {"periode": f"{fra}-{til}", "kommunekode": kommunekode, "parametre": ud}

    async def status(self) -> str:
        await self._parameter("0101", "mean_temp", 2024, 2024)
        return "ok"


class PvgisAdapter(Adapter):
    kilde = Kilde(
        id="E05",
        navn="PVGIS 5.3",
        udbyder="EU-Kommissionens Joint Research Centre",
        url="https://re.jrc.ec.europa.eu/pvg_tools/en/",
        licens="Frie data - kildeangivelse: PVGIS © European Union",
    )

    async def pv(self, lat: float, lon: float, hældning: float | None, orientering: float | None, kwp: float, tab_pct: float) -> dict[str, Any]:
        params: dict[str, Any] = {"lat": round(lat, 5), "lon": round(lon, 5), "peakpower": kwp, "loss": tab_pct, "outputformat": "json"}
        if hældning is None or orientering is None:
            params["optimalangles"] = 1
        else:
            params["angle"], params["aspect"] = hældning, orientering
        d = await self.get_json(f"{PVGIS}/PVcalc", params, ttl=90 * 24 * 3600)
        fx = d["inputs"]["mounting_system"]["fixed"]
        tot = d["outputs"]["totals"]["fixed"]
        md = d["outputs"]["monthly"]["fixed"]
        return {
            "anlaeg": {"kwp": kwp, "systemtab_pct": tab_pct,
                       "haeldning_grader": fx["slope"]["value"], "haeldning_optimal": fx["slope"].get("optimal"),
                       "orientering_grader": fx["azimuth"]["value"], "orientering_optimal": fx["azimuth"].get("optimal")},
            "aarsproduktion_kwh": round(tot["E_y"]),
            "aarsproduktion_kwh_pr_kwp": round(tot["E_y"] / kwp),
            "indstraaling_paa_flade_kwh_m2_aar": round(tot["H(i)_y"]),
            "variation_mellem_aar_kwh": round(tot.get("SD_y", 0)),
            "maanedlig_produktion_kwh": {m["month"]: round(m["E_m"]) for m in md},
            "data": f"{d['inputs']['meteo_data']['radiation_db']}, {d['inputs']['meteo_data']['year_min']}-{d['inputs']['meteo_data']['year_max']}, horisont fra terrænmodel",
        }

    def tmy_url(self, lat: float, lon: float) -> str:
        return f"{PVGIS}/tmy?lat={lat:.4f}&lon={lon:.4f}&outputformat=epw"

    async def tmy_epw(self, lat: float, lon: float) -> str:
        resp = await self.client.get(self.tmy_url(lat, lon), timeout=120)
        resp.raise_for_status()
        if not resp.text.startswith("LOCATION"):
            raise RuntimeError("PVGIS returnerede ikke en EPW-fil")
        return resp.text

    async def status(self) -> str:
        await self.get_json(f"{PVGIS}/PVcalc", {"lat": 55.68, "lon": 12.57, "peakpower": 1, "loss": 14, "angle": 35, "aspect": 0, "outputformat": "json"}, ttl=0)
        return "ok"


class EnerginetAdapter(Adapter):
    kilde = Kilde(
        id="F02",
        navn="Energi Data Service (CO2Emis)",
        udbyder="Energinet",
        url="https://www.energidataservice.dk",
        licens="Frie data - kildeangivelse: Energinet",
    )

    async def co2(self, prisomraade: str, dage: int = 7) -> dict[str, Any]:
        # Rundet til hel time, så gentagne kald inden for samme time genbruger cachen (Energinet rate-limiter).
        start = (datetime.now(timezone.utc) - timedelta(days=dage)).strftime("%Y-%m-%dT%H:00")
        d = await self.get_json(
            f"{EDS}/CO2Emis",
            {"start": start, "filter": f'{{"PriceArea":["{prisomraade}"]}}', "sort": "Minutes5UTC desc", "limit": 0},
            ttl=900,
        )
        vals = [r["CO2Emission"] for r in d.get("records", []) if r.get("CO2Emission") is not None]
        if not vals:
            return {"note": "Ingen data"}
        seneste = d["records"][0]
        return {
            "prisomraade": prisomraade,
            "seneste_g_pr_kwh": round(seneste["CO2Emission"]),
            "seneste_tidspunkt_dk": seneste.get("Minutes5DK"),
            f"middel_{dage}_dage_g_pr_kwh": round(statistics.fmean(vals)),
            f"min_{dage}_dage_g_pr_kwh": round(min(vals)),
            f"maks_{dage}_dage_g_pr_kwh": round(max(vals)),
        }

    async def status(self) -> str:
        await self.get_json(f"{EDS}/CO2Emis", {"limit": 1}, ttl=0)
        return "ok"

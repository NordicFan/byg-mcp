"""Energimærker fra Energistyrelsens EMOData-service.

Verificeret 17/11-2026 mod tjenestens swagger (https://emoweb.dk/EMOData/api-docs/swagger.json):
- Base: https://emoweb.dk/EMOData/EMOData.svc
- Adgang: HTTP Basic med brugernavn og adgangskode fra Energistyrelsen. Uden adgang svarer tjenesten
  HTTP 200 med status "ACCESS_DENIED" eller HTTP 401.
- SearchEnergyLabelBFE/{bfe}: alle mærker på ejendommen (EnergyLabels[]).
- GetEnergyLabelFromCoordinates?coordinateX=<breddegrad>&coordinateY=<længdegrad> (WGS84).
- GetEnergyLabelImprovementSuggestionsByNumber/{nr}: forbedringsforslag med investering, besparelse og levetid.
Ikke live-testet endnu: kræver adgang fra Energistyrelsen.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from byg_mcp.adapters.base import Adapter, Kilde

EMO = "https://emoweb.dk/EMOData/EMOData.svc"
GYLDIGE_STATUSSER = {"VALID", "GYLDIG", "ACTIVE", "AKTIV"}


def emo_dato(v: Any) -> str | None:
    """EMOData (WCF) leverer datoer som ISO-tekst eller som '/Date(1719352800000+0200)/'. Returnerer ÅÅÅÅ-MM-DD."""
    if v in (None, ""):
        return None
    s = str(v)
    if m := re.match(r"/Date\((-?\d+)([+-]\d{2})?(\d{2})?", s):
        t = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)
        if m.group(2):  # WCF angiver den lokale tidszone efter tallet, fx +0200
            fortegn = -1 if m.group(2).startswith("-") else 1
            t += timedelta(hours=int(m.group(2)), minutes=fortegn * int(m.group(3) or 0))
        return t.date().isoformat()
    if m := re.match(r"(\d{4}-\d{2}-\d{2})", s):
        return m.group(1)
    if m := re.match(r"(\d{2})-(\d{2})-(\d{4})", s):
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return s


def adgang_naegtet(data: Any) -> str | None:
    """Find EMOData's fejlstatus, uanset hvilket svarobjekt den ligger i."""
    if not isinstance(data, dict):
        return None
    for v in data.values():
        if isinstance(v, dict):
            status = str(v.get("Status") or "")
            if status.upper() in {"ACCESS_DENIED", "ERROR", "FAILED"}:
                return v.get("StatusMessage") or v.get("Message") or status
            if indre := adgang_naegtet(v):
                return indre
    return None


def normaliser_maerke(m: dict[str, Any]) -> dict[str, Any]:
    """Fælles form for EnergyLabelsResponse (BFE-søgning) og EnergyLabelItem (koordinatsøgning)."""
    bygninger = [
        {k2: v for k2, v in (
            ("bygningsnr", b.get("BuildingNumber")),
            ("opfoerelsesaar", b.get("YearOfConstruction")),
            ("varmeforsyning", b.get("HeatSupply")),
            ("bbr_anvendelseskode", b.get("BBRUseCode")),
        ) if v not in (None, "")}
        for b in m.get("Buildings") or []
    ]
    if not bygninger and (m.get("BuildingNumber") or m.get("YearOfConstruction")):
        bygninger = [{k2: v for k2, v in (
            ("bygningsnr", m.get("BuildingNumber")),
            ("opfoerelsesaar", m.get("YearOfConstruction")),
            ("varmeforsyning", m.get("HeatSupply")),
            ("bbr_anvendelseskode", m.get("BBRUseCode")),
        ) if v not in (None, "")}]
    ud = {
        "nummer": str(m.get("EnergyLabelSerialIdentifier") or m.get("EnergyLabelNumber") or ""),
        "klasse": m.get("EnergyLabelClassification") or m.get("CurrentEnergyLabel"),
        "status": m.get("LabelStatus"),
        "gyldig_fra": emo_dato(m.get("ValidFrom")),
        "gyldig_til": emo_dato(m.get("ValidTo")),
        "grundlag": m.get("EnergyLabelTypeBasedOn"),
        "anvendelse": m.get("EnergyLabelTypeUsage"),
        "adresse": " ".join(str(x) for x in (m.get("StreetName"), m.get("HouseNumber")) if x) or None,
        "postnr_by": " ".join(str(x) for x in (m.get("ZipCode"), m.get("CityName")) if x) or None,
        "bfe_nummer": m.get("BFENumber"),
        "bygninger": bygninger or None,
        "erstatter_nummer": m.get("FormerEnergyLabelSerialIdentifier") or None,
        "firma": m.get("SubmitterCompanyName"),
    }
    return {k: v for k, v in ud.items() if v not in (None, "", [])}


def vaelg_gaeldende(maerker: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Nyeste gyldige mærke; findes intet gyldigt, det nyeste."""
    if not maerker:
        return None
    gyldige = [m for m in maerker if str(m.get("status") or "").upper() in GYLDIGE_STATUSSER]
    kandidater = gyldige or maerker
    return max(kandidater, key=lambda m: m.get("gyldig_fra") or "")


def _tal(v: Any) -> float | None:
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except ValueError:
        return None


def normaliser_forbedringer(label: dict[str, Any]) -> dict[str, Any]:
    forslag = []
    for p in label.get("Proposals") or []:
        f = {
            "overskrift": p.get("ProposalHeadline"),
            "bygningsnr": p.get("BuildingNumber"),
            "investering_kr": _tal(p.get("Investment")),
            "aarlig_besparelse": p.get("Savings"),
            "energibesparelse": " ".join(str(x) for x in (p.get("EnergySaved"), p.get("EnergySavedUnit")) if x) or None,
            "levetid_aar": p.get("LifeTime"),
            "rentabelt": p.get("Profitable"),
            "co2_besparelse": p.get("SavingsInEmission"),
            "beskrivelse": (p.get("ProposalText") or "")[:300] or None,
        }
        forslag.append({k: v for k, v in f.items() if v not in (None, "")})
    beregning = (label.get("ProposalsCalculations") or [{}])[0]
    samlet = {k: v for k, v in (
        ("investering_rentable_kr", _tal(beregning.get("TotalInvestmentProfitable"))),
        ("investering_anbefalede_kr", _tal(beregning.get("TotalInvestmentRecommended"))),
        ("investering_alle_kr", _tal(beregning.get("TotalInvestmentAll"))),
    ) if v is not None}
    ud = {
        "nuvaerende_klasse": label.get("CurrentEnergyLabel"),
        "klasse_efter_rentable_forslag": label.get("PossibleEnergyLabelForAllProfitableProposals"),
        "klasse_efter_alle_forslag": label.get("PossibleEnergyLabelForAllProposals"),
        "samlet": samlet or None,
        "antal_forslag": len(forslag),
        "forslag": forslag,
        "rapport_pdf": label.get("PDF") or None,
    }
    return {k: v for k, v in ud.items() if v not in (None, "")}


class EmoAdapter(Adapter):
    kilde = Kilde(
        id="J01",
        navn="Energimærker (EMOData)",
        udbyder="Energistyrelsen",
        url="https://ens.dk/analyser-og-statistik/energimaerkningsdata",
        licens="Data fra Energimærkningsordningen - kildeangivelse: Energistyrelsen. Kræver adgang til EMOData",
    )

    @property
    def aktiv(self) -> bool:
        return bool(self.config.emo_brugernavn and self.config.emo_adgangskode)

    async def _hent(self, sti: str, params: dict[str, Any] | None = None, ttl: float = 7 * 24 * 3600) -> Any:
        if not self.aktiv:
            raise ValueError(
                "Energimærker kræver adgang til Energistyrelsens EMOData-service. Sæt EMO_BRUGERNAVN og "
                "EMO_ADGANGSKODE i .env. Adgang fås ved henvendelse til Energistyrelsen."
            )
        key = f"emo:{sti}?{sorted((params or {}).items())}"
        if (hit := self.cache.get(key)) is not None:
            return hit
        auth = httpx.BasicAuth(self.config.emo_brugernavn or "", self.config.emo_adgangskode or "")
        try:
            data = await self.get_json(f"{EMO}/{sti}", params, ttl=0, auth=auth)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise ValueError("EMOData afviste brugernavn eller adgangskode (HTTP 401/403)") from e
            raise
        if fejl := adgang_naegtet(data):
            raise ValueError(f"EMOData afviste forespørgslen: {fejl}")
        self.cache.set(key, data, ttl)  # først efter tjek, så afviste svar aldrig caches
        return data

    async def maerker_for_bfe(self, bfe: int | str) -> list[dict[str, Any]]:
        data = await self._hent(f"SearchEnergyLabelBFE/{bfe}")
        return [normaliser_maerke(m) for m in (data.get("EnergyLabels") or [])]

    async def maerker_ved_koordinat(self, lat: float, lon: float) -> list[dict[str, Any]]:
        data = await self._hent(
            "GetEnergyLabelFromCoordinates", {"coordinateX": round(lat, 6), "coordinateY": round(lon, 6)}
        )
        return [normaliser_maerke(m) for m in (data.get("SearchResults") or [])]

    async def forbedringer(self, nummer: str) -> dict[str, Any] | None:
        data = await self._hent(f"GetEnergyLabelImprovementSuggestionsByNumber/{nummer}")
        res = data.get("GetEnergyLabelImprovementSuggestionsByNumberResult") or {}
        labels = res.get("EnergyLabels") or []
        return normaliser_forbedringer(labels[0]) if labels else None

    async def status(self) -> str:
        if not self.aktiv:
            return "ikke konfigureret (EMO_BRUGERNAVN/EMO_ADGANGSKODE mangler; adgang via Energistyrelsen)"
        await self._hent("Ping", ttl=60)
        return "ok"

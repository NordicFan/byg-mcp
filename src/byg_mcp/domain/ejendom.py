"""Ejendomskæden: husnummer / jordstykke / BFE / punkt → samlet fast ejendom med alle jordstykker.

Verificeret mod FlexibleCurrent/v3 8/11-2026 (Bispensgade 3, Aalborg → matr. 220 Aalborg Bygrunde, BFE 5539730).
"""

from __future__ import annotations

import asyncio
from typing import Any

from byg_mcp.adapters.datafordeler import DatafordelerAdapter

_JS_FELTER = (
    "id_lokalId matrikelnummer ejerlavLokalId registreretAreal vejareal samletFastEjendomLokalId status "
    "fredskov_omfang fredskov_areal strandbeskyttelse_omfang strandbeskyttelse_areal "
    "klitfredning_omfang klitfredning_areal majoratsskov_omfang jordrente_omfang"
)
_NOTERINGER = {
    "fredskov": ("fredskov_omfang", "fredskov_areal"),
    "strandbeskyttelse": ("strandbeskyttelse_omfang", "strandbeskyttelse_areal"),
    "klitfredning": ("klitfredning_omfang", "klitfredning_areal"),
}


class EjendomIkkeFundet(LookupError):
    pass


async def husnummer(df: DatafordelerAdapter, husnummer_id: str) -> dict[str, Any] | None:
    nodes = await df.aktuel(
        "DAR_Husnummer",
        "id_lokalId adgangsadressebetegnelse jordstykke adgangTilBygning status",
        {"id_lokalId": {"eq": husnummer_id}},
        first=1,
    )
    return nodes[0] if nodes else None


async def sfe_ved_punkt(df: DatafordelerAdapter, x: float, y: float) -> str | None:
    nodes = await df.aktuel(
        "MAT_SamletFastEjendom",
        "id_lokalId",
        {"geometri": {"intersects": {"wkt": f"POINT({x:.2f} {y:.2f})", "crs": 25832}}},
        first=2,
    )
    return nodes[0]["id_lokalId"] if nodes else None


async def ejendom(
    df: DatafordelerAdapter,
    *,
    husnummer_id: str | None = None,
    jordstykke_id: str | None = None,
    bfe_nummer: int | None = None,
    punkt: tuple[float, float] | None = None,
    med_geometri: bool = False,
) -> dict[str, Any]:
    """Find den samlede faste ejendom (BFE) og alle dens jordstykker ud fra den bedste nøgle, der er givet."""
    out: dict[str, Any] = {}
    sfe_id: str | None = None
    if bfe_nummer:
        hit = await df.aktuel("MAT_SamletFastEjendom", "id_lokalId", {"BFEnummer": {"eq": int(bfe_nummer)}}, first=1)
        sfe_id = hit[0]["id_lokalId"] if hit else None

    if husnummer_id and not jordstykke_id:
        hn = await husnummer(df, husnummer_id)
        if hn:
            out["husnummer_id"] = hn["id_lokalId"]
            out["adgangsadresse"] = hn.get("adgangsadressebetegnelse")
            if hn.get("adgangTilBygning"):
                out["adgang_til_bygning_id"] = hn["adgangTilBygning"]
            jordstykke_id = hn.get("jordstykke")

    if jordstykke_id and not sfe_id:
        js = await df.aktuel("MAT_Jordstykke", "samletFastEjendomLokalId", {"id_lokalId": {"eq": str(jordstykke_id)}}, first=1)
        if js:
            sfe_id = js[0]["samletFastEjendomLokalId"]

    if not sfe_id and punkt:
        sfe_id = await sfe_ved_punkt(df, *punkt)

    if not sfe_id:
        raise EjendomIkkeFundet("Kunne ikke finde en samlet fast ejendom ud fra de givne oplysninger")

    sfe_felter = "id_lokalId BFEnummer hovedejendomOpdeltIEjerlejligh udskiltVej arbejderbolig landbrugsnotering status"
    if med_geometri:
        sfe_felter += " geometri { wkt }"
    sfe_nodes, jordstykker = await asyncio.gather(
        df.aktuel("MAT_SamletFastEjendom", sfe_felter, {"id_lokalId": {"eq": sfe_id}}, first=1),
        df.aktuel("MAT_Jordstykke", _JS_FELTER, {"samletFastEjendomLokalId": {"eq": sfe_id}}, first=100),
    )
    if not sfe_nodes:
        raise EjendomIkkeFundet(f"Samlet fast ejendom {sfe_id} findes ikke (eller er ikke gældende)")
    sfe = sfe_nodes[0]

    ejerlav_ids = sorted({j["ejerlavLokalId"] for j in jordstykker if j.get("ejerlavLokalId")})
    ejerlav = {
        e["id_lokalId"]: e
        for e in await df.aktuel("MAT_Ejerlav", "id_lokalId ejerlavskode ejerlavsnavn", {"id_lokalId": {"in": ejerlav_ids}})
    } if ejerlav_ids else {}

    js_ud = []
    for j in jordstykker:
        el = ejerlav.get(j.get("ejerlavLokalId"), {})
        rec: dict[str, Any] = {
            "jordstykke_id": j["id_lokalId"],
            "matrikelnummer": j.get("matrikelnummer"),
            "ejerlavskode": el.get("ejerlavskode"),
            "ejerlavsnavn": el.get("ejerlavsnavn"),
            "betegnelse": f"{j.get('matrikelnummer')}, {el.get('ejerlavsnavn')}" if el else j.get("matrikelnummer"),
            "registreret_areal_m2": j.get("registreretAreal"),
            "vejareal_m2": j.get("vejareal"),
        }
        noter = {
            navn: {"omfang": j[o], **({"areal_m2": j[a]} if j.get(a) else {})}
            for navn, (o, a) in _NOTERINGER.items()
            if j.get(o)
        }
        if noter:
            rec["noteringer"] = noter
        js_ud.append(rec)

    out.update(
        {
            "bfe_nummer": sfe["BFEnummer"],
            "opdelt_i_ejerlejligheder": sfe.get("hovedejendomOpdeltIEjerlejligh"),
            "jordstykker": js_ud,
            "grundareal_registreret_m2": sum(j.get("registreretAreal") or 0 for j in jordstykker),
            "heraf_vejareal_m2": sum(j.get("vejareal") or 0 for j in jordstykker),
        }
    )
    if sfe.get("landbrugsnotering"):
        out["landbrugsnotering"] = sfe["landbrugsnotering"]
    if med_geometri and sfe.get("geometri"):
        out["grundgeometri_wkt"] = sfe["geometri"]["wkt"]
    return out

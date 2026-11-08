"""BBR-bygninger på en ejendom, med koder oversat via BBR's officielle kodelister."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from byg_mcp.adapters.datafordeler import DatafordelerAdapter

# Livscyklus-koder, der ikke længere beskriver en eksisterende/planlagt bygning.
_INAKTIVE = {"9", "10", "11", "14"}  # Afsluttet, Historisk, Fejlregistreret, Henlagt

# (BBR-felt, visningsnavn, kodeliste eller None)
_BYG = [
    ("byg007Bygningsnummer", "bygningsnummer", None),
    ("byg021BygningensAnvendelse", "anvendelse", "BygAnvendelse"),
    ("byg026Opfoerelsesaar", "opfoerelsesaar", None),
    ("byg027OmTilbygningsaar", "om_tilbygningsaar", None),
    ("byg038SamletBygningsareal", "samlet_bygningsareal_m2", None),
    ("byg039BygningensSamledeBoligAreal", "boligareal_m2", None),
    ("byg040BygningensSamledeErhvervsAreal", "erhvervsareal_m2", None),
    ("byg041BebyggetAreal", "bebygget_areal_m2", None),
    ("byg054AntalEtager", "antal_etager", None),
    ("byg055AfvigendeEtager", "afvigende_etager", "AfvigendeEtager"),
    ("byg024AntalLejlighederMedKoekken", "lejligheder_med_koekken", None),
    ("byg032YdervaeggensMateriale", "ydervaeg", "YdervaeggenesMateriale"),
    ("byg034SupplerendeYdervaeggensMateriale", "ydervaeg_supplerende", "YdervaeggenesMateriale"),
    ("byg033Tagdaekningsmateriale", "tagdaekning", "Tagdaekningsmateriale"),
    ("byg036AsbestholdigtMateriale", "asbestholdigt_materiale", "AsbestholdigtMateriale"),
    ("byg056Varmeinstallation", "varmeinstallation", "BygVarmeinstallation"),
    ("byg057Opvarmningsmiddel", "opvarmningsmiddel", "Opvarmningsmiddel"),
    ("byg058SupplerendeVarme", "supplerende_varme", "BygSupplerendeVarme"),
    ("byg030Vandforsyning", "vandforsyning", "BygVandforsyning"),
    ("byg031Afloebsforhold", "afloebsforhold", "BygAfloebsforhold"),
    ("byg070Fredning", "fredning", "Fredning"),
    ("byg071BevaringsvaerdighedReference", "bevaringsvaerdighed_reference", None),
    ("byg130ArealAfUdvendigEfterisolering", "udvendig_efterisolering_m2", None),
    ("byg151Frihoejde", "frihoejde_m", None),
    ("byg153Konstruktionsforhold", "konstruktionsforhold", "Konstruktionsforhold"),
    ("byg069Sikringsrumpladser", "sikringsrumpladser", None),
    ("status", "status", "Livscyklus"),
]
_ETA = [
    ("eta006BygningensEtagebetegnelse", "etage", None),
    ("eta020SamletArealAfEtage", "areal_m2", None),
    ("eta021ArealAfUdnyttetDelAfTagetage", "udnyttet_tagetage_m2", None),
    ("eta022Kaelderareal", "kaelderareal_m2", None),
    ("eta025Etagetype", "etagetype", "EtageType"),
]


@lru_cache(maxsize=1)
def kodelister() -> dict[str, Any]:
    return json.loads(resources.files("byg_mcp.data").joinpath("bbr_kodelister.json").read_text(encoding="utf-8"))


def _oversaet(node: dict[str, Any], felter: list[tuple[str, str, str | None]]) -> dict[str, Any]:
    kl = kodelister()
    out: dict[str, Any] = {}
    for felt, navn, liste in felter:
        v = node.get(felt)
        if v in (None, ""):
            continue
        out[navn] = {"kode": v, "tekst": kl.get(liste, {}).get(str(v), "ukendt kode")} if liste else v
    return out


async def bygninger(
    df: DatafordelerAdapter,
    jordstykke_ids: list[str],
    *,
    husnummer_id: str | None = None,
    med_etager: bool = False,
    med_inaktive: bool = False,
) -> dict[str, Any]:
    felter = " ".join(f for f, _, _ in _BYG) + " id_lokalId byg404Koordinat { wkt }"
    where: dict[str, Any] = {"jordstykke": {"in": jordstykke_ids[:100]}}
    nodes = await df.aktuel("BBR_Bygning", felter, where, first=200) if jordstykke_ids else []
    if not nodes and husnummer_id:  # fx bygninger uden jordstykkereference
        nodes = await df.aktuel("BBR_Bygning", felter, {"husnummer": {"eq": husnummer_id}}, first=200)

    aktive = [n for n in nodes if med_inaktive or str(n.get("status")) not in _INAKTIVE]
    udeladt = len(nodes) - len(aktive)

    etager: dict[str, list[dict]] = {}
    if med_etager and aktive:
        eta_felter = "bygning " + " ".join(f for f, _, _ in _ETA)
        ids = [n["id_lokalId"] for n in aktive][:100]
        for e in await df.aktuel("BBR_Etage", eta_felter, {"bygning": {"in": ids}}, first=500):
            etager.setdefault(e["bygning"], []).append(_oversaet(e, _ETA))

    ud = []
    for n in sorted(aktive, key=lambda n: (n.get("byg007Bygningsnummer") or 0)):
        rec = {"bbr_bygning_id": n["id_lokalId"], **_oversaet(n, _BYG)}
        if (n.get("byg404Koordinat") or {}).get("wkt"):
            rec["koordinat_wkt"] = n["byg404Koordinat"]["wkt"]
        if med_etager:
            rec["etager"] = etager.get(n["id_lokalId"], [])
        ud.append(rec)

    resultat: dict[str, Any] = {
        "antal_bygninger": len(ud),
        "bygninger": ud,
        "samlet_bebygget_areal_m2": sum(b.get("bebygget_areal_m2") or 0 for b in ud),
        "samlet_bygningsareal_m2": sum(b.get("samlet_bygningsareal_m2") or 0 for b in ud),
    }
    if udeladt:
        resultat["udeladt_inaktive"] = f"{udeladt} bygning(er) med status afsluttet/historisk/fejlregistreret/henlagt er udeladt"
    return resultat


def noegletal(bygn: dict[str, Any], grundareal: float, vejareal: float = 0) -> dict[str, Any]:
    """Indikatorer ud fra BBR-arealer. Bebyggelsesprocent = etageareal i % af grundarealet (BR18's definition).
    BBR's samlede bygningsareal bruges som tilnærmelse til etagearealet. BR18's beregningsregler
    (fx fradrag for kælder, tagetage, parkering) er ikke anvendt, så tallene er indikatorer."""
    netto = grundareal - vejareal
    if netto <= 0:
        return {}
    return {
        "bebyggelsesprocent_indikator": round(100 * bygn["samlet_bygningsareal_m2"] / netto, 1),
        "bebygget_andel_af_grund_pct": round(100 * bygn["samlet_bebygget_areal_m2"] / netto, 1),
        "grundlag": "BBR-arealer og registreret grundareal minus vejareal. Ikke beregnet efter BR18's regler.",
    }

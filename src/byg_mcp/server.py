"""MCP-server for bygningsdesign i Danmark (M0-spike).

Kør lokalt:  uv run byg-mcp
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from byg_mcp.adapters.arealinfo import ArealinfoAdapter
from byg_mcp.adapters.base import KildeOverbelastet, make_client
from byg_mcp.adapters.datafordeler import DatafordelerAdapter, DatafordelerError
from byg_mcp.adapters.geokodning import GsearchAdapter, NominatimAdapter
from byg_mcp.adapters.miljoe import FortidsmindeAdapter, JordforureningAdapter, StoejAdapter
from byg_mcp.adapters.geo import GeusAdapter, GrundvandAdapter, HoejdemodelAdapter, KortAdapter
from byg_mcp.adapters.retsinformation import RetsinformationAdapter
from byg_mcp.adapters.energimaerke import EmoAdapter, vaelg_gaeldende
from byg_mcp.adapters.klima import DmiAdapter, EnerginetAdapter, PvgisAdapter
from byg_mcp.adapters.klimaatlas import AARSTIDER, PERIODER, SCENARIER_KOMMUNE, KlimaatlasAdapter
from byg_mcp.adapters.oversvoemmelse import HydroAdapter
from byg_mcp.adapters.lca_bim import BsddAdapter, OekobaudatAdapter
from byg_mcp.adapters.plandata import PlandataAdapter
from byg_mcp.domain import bygning as bygning_domain
from byg_mcp.domain import ejendom as ejendom_domain
from byg_mcp.domain.sted import Sted
from byg_mcp.infra.cache import SQLiteCache
from byg_mcp.infra.config import load_config
from byg_mcp.infra.logging import sikr_logning

sikr_logning()

INSTRUKTIONER = """\
Værktøjer til bygningsdesignere (arkitekter, ingeniører, bygningskonstruktører) i Danmark.
Til regler: `br18_soeg` / `br18_paragraf` (bygningsreglementet, aktuel version) og `lov_paragraf` (øvrige love).
Til steder: start med `sted_find` (adresse, matrikel eller koordinat) eller `grundrapport`. Den giver koordinater, matrikel, BFE-nummer
og grundareal. Brug derefter `bygning_bbr`, `plan_gaeldende` og `restriktioner`.
Til klima og risiko: `klima_data` (målt), `klima_fremskrivning` (DMI Klimaatlas), `oversvoemmelse` og `energimaerke`. Alle svar har en
`kilder`-liste. Angiv altid kilderne i dit svar. Data er grundlag for faglig vurdering, ikke
myndighedsafgørelser.
"""


@dataclass
class Adaptere:
    plandata: PlandataAdapter
    arealinfo: ArealinfoAdapter
    gsearch: GsearchAdapter
    nominatim: NominatimAdapter
    datafordeler: DatafordelerAdapter
    jord: JordforureningAdapter
    stoej: StoejAdapter
    fortidsminder: FortidsmindeAdapter
    dhm: HoejdemodelAdapter
    geus: GeusAdapter
    grundvand: GrundvandAdapter
    kort: KortAdapter
    retsinfo: RetsinformationAdapter
    dmi: DmiAdapter
    pvgis: PvgisAdapter
    energinet: EnerginetAdapter
    oekobaudat: OekobaudatAdapter
    bsdd: BsddAdapter
    emo: EmoAdapter
    klimaatlas: KlimaatlasAdapter
    hydro: HydroAdapter


@asynccontextmanager
async def lifespan(_server: MCPServer) -> AsyncIterator[Adaptere]:
    sikr_logning()  # igen her: SDK'et kan have tilføjet handlers efter import
    config = load_config()
    cache = SQLiteCache(config.cache_path)
    async with make_client(config) as client:
        args = (config, client, cache)
        yield Adaptere(
            plandata=PlandataAdapter(*args),
            arealinfo=ArealinfoAdapter(*args),
            gsearch=GsearchAdapter(*args),
            nominatim=NominatimAdapter(*args),
            datafordeler=DatafordelerAdapter(*args),
            jord=JordforureningAdapter(*args),
            stoej=StoejAdapter(*args),
            fortidsminder=FortidsmindeAdapter(*args),
            dhm=HoejdemodelAdapter(*args),
            geus=GeusAdapter(*args),
            grundvand=GrundvandAdapter(*args),
            kort=KortAdapter(*args),
            retsinfo=RetsinformationAdapter(*args),
            dmi=DmiAdapter(*args),
            pvgis=PvgisAdapter(*args),
            energinet=EnerginetAdapter(*args),
            oekobaudat=OekobaudatAdapter(*args),
            bsdd=BsddAdapter(*args),
            emo=EmoAdapter(*args),
            klimaatlas=KlimaatlasAdapter(*args),
            hydro=HydroAdapter(*args),
        )


mcp = MCPServer(name="byg-dk", instructions=INSTRUKTIONER, lifespan=lifespan)


def brugerfejl(fn):
    """Omsæt forventede fejl til ToolError, så modellen ser fejlteksten (andre undtagelser skjules af SDK'et)."""
    import functools

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ToolError:
            raise
        except (ValueError, LookupError, DatafordelerError, KildeOverbelastet) as e:
            raise ToolError(str(e)) from e

    return wrapper



def _a(ctx: Context) -> Adaptere:
    return ctx.request_context.lifespan_context


def _sted_fra_input(
    x: float | None, y: float | None, lat: float | None, lon: float | None
) -> Sted:
    if x is not None and y is not None:
        return Sted.fra_utm(x, y)
    if lat is not None and lon is not None:
        return Sted.fra_wgs84(lat, lon)
    raise ValueError("Angiv enten x og y (EPSG:25832) eller lat og lon (WGS84). Brug sted_find til at slå en adresse op.")


@mcp.tool()
@brugerfejl
async def kilde_status(ctx: Context) -> dict[str, Any]:
    """Tjek hvilke datakilder serveren kan nå lige nu, og hvilke der mangler nøgler."""
    a = _a(ctx)
    out: dict[str, Any] = {}
    for navn in (
        "plandata", "arealinfo", "jord", "stoej", "fortidsminder", "dhm", "geus", "grundvand",
        "retsinfo", "dmi", "pvgis", "energinet", "oekobaudat", "bsdd", "gsearch", "nominatim", "datafordeler",
        "emo", "klimaatlas", "hydro",
    ):
        adapter = getattr(a, navn)
        try:
            out[adapter.kilde.navn] = await adapter.status()
        except Exception as e:  # noqa: BLE001 - statusværktøj skal aldrig fejle
            out[adapter.kilde.navn] = f"fejl: {type(e).__name__}: {e}"
    return out


async def _kandidater(
    a: Adaptere, adresse: str | None, matrikel: str | None, maks: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fritekst → kandidatliste (dicts med x, y og evt. husnummer_id/jordstykke_id/bfe_nummer) + kilder."""
    if matrikel:
        if not a.gsearch.aktiv:
            raise ValueError("Matrikelsøgning kræver DATAFORSYNINGEN_TOKEN")
        return await a.gsearch.soeg_matrikel(matrikel, maks), [a.gsearch.angivelse().dict()]
    if adresse and a.gsearch.aktiv:
        return await a.gsearch.soeg_husnummer(adresse, maks), [a.gsearch.angivelse().dict()]
    if adresse:
        hits = await a.nominatim.soeg(adresse, maks)
        for h in hits:
            s = Sted.fra_wgs84(h["lat"], h["lon"])
            h["x"], h["y"] = s.x, s.y
        note = "Reserve-geokoder: OpenStreetMap er ikke det officielle adresseregister. Sæt DATAFORSYNINGEN_TOKEN."
        return hits, [a.nominatim.angivelse(note).dict()]
    return [], []


def _tokens(s: str) -> set[str]:
    import re

    return set(re.findall(r"[0-9a-zæøåé]+", s.lower()))


def _match_kvalitet(soegt: str, fundet: str | None) -> str:
    """gsearch er fuzzy og returnerer nærmeste adresse, hvis den søgte ikke findes (fx 'Nørre Allé 1' →
    'Nørre Allé 11'). Et match er kun 'eksakt', hvis alle søgte ord/tal indgår i resultatet."""
    if not fundet:
        return "usikkert"
    mangler = _tokens(soegt) - _tokens(fundet)
    return "eksakt" if not mangler else "usikkert"


async def _ejendom_for(a: Adaptere, k: dict[str, Any]) -> dict[str, Any]:
    return await ejendom_domain.ejendom(
        a.datafordeler,
        husnummer_id=k.get("husnummer_id"),
        jordstykke_id=k.get("jordstykke_id"),
        bfe_nummer=k.get("bfe_nummer"),
        punkt=(k["x"], k["y"]),
    )


@mcp.tool()
@brugerfejl
async def sted_find(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    maks_resultater: int = 5,
) -> dict[str, Any]:
    """Find et sted i Danmark og dets ejendom ud fra adresse, matrikel (fx "220, Aalborg Bygrunde"),
    BFE-nummer eller koordinater (x/y i EPSG:25832 eller lat/lon).

    Returnerer det bedste match (`valgt`) med koordinater, husnummer-ID, BFE-nummer, jordstykker
    (matrikelnr., ejerlav, registreret areal, vejareal, noteringer om fredskov/strandbeskyttelse/klitfredning)
    og samlet grundareal, plus `andre_kandidater`. Spørg brugeren, hvis matchet er tvetydigt.
    """
    a = _a(ctx)
    kilder: list[dict[str, Any]] = []
    if adresse or matrikel:
        kandidater, kilder = await _kandidater(a, adresse, matrikel, maks_resultater)
        if not kandidater:
            return {"valgt": None, "andre_kandidater": [], "besked": "Ingen match", "kilder": kilder}
    elif bfe_nummer:
        kandidater = [{"bfe_nummer": bfe_nummer}]
    else:
        s = _sted_fra_input(x, y, lat, lon)
        kandidater = [{"x": s.x, "y": s.y}]

    valgt = dict(kandidater[0])
    noter: list[str] = []
    ejendom: dict[str, Any] | None = None
    if a.datafordeler.aktiv:
        try:
            if "x" not in valgt:  # kun BFE givet
                ejendom = await ejendom_domain.ejendom(a.datafordeler, bfe_nummer=bfe_nummer, med_geometri=True)
                wkt = ejendom.pop("grundgeometri_wkt", "")
                valgt.update(_centroide(wkt))
            else:
                ejendom = await _ejendom_for(a, valgt)
            kilder.append(a.datafordeler.angivelse().dict())
        except ejendom_domain.EjendomIkkeFundet as e:
            noter.append(str(e))
    else:
        noter.append("Ejendomsoplysninger kræver DATAFORDELER_API_KEY")

    if "x" not in valgt:
        return {"valgt": None, "besked": "; ".join(noter) or "Ingen match", "kilder": kilder}
    sted = Sted.fra_utm(valgt["x"], valgt["y"], betegnelse=valgt.get("betegnelse"), noter=noter).dict()
    sted.update({k: valgt[k] for k in ("husnummer_id", "kommunekode", "kommunenavn", "postnummer") if valgt.get(k)})
    if ejendom:
        sted["ejendom"] = ejendom
    andre = [{k: v for k, v in c.items() if k in ("betegnelse", "x", "y")} for c in kandidater[1:]]
    svar: dict[str, Any] = {"valgt": sted, "andre_kandidater": andre, "kilder": kilder}
    if adresse or matrikel:
        svar["match"] = _match_kvalitet(adresse or matrikel or "", valgt.get("betegnelse"))
        if svar["match"] == "usikkert":
            svar["advarsel"] = (
                f"Den søgte '{adresse or matrikel}' blev ikke fundet præcist. Nærmeste match er "
                f"'{valgt.get('betegnelse')}'. Bekræft med brugeren, før resultatet bruges."
            )
    return svar


def _centroide(wkt: str) -> dict[str, float]:
    """Grov centroide (gennemsnit af hjørnepunkter) af en WKT-multipolygon - nok til kortopslag."""
    import re

    tal = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", wkt)]
    if len(tal) < 2:
        return {}
    xs, ys = tal[0::2], tal[1::2]
    return {"x": round(sum(xs) / len(xs), 2), "y": round(sum(ys) / len(ys), 2)}


@mcp.tool()
@brugerfejl
async def bygning_bbr(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    med_etager: bool = False,
    med_inaktive: bool = False,
) -> dict[str, Any]:
    """Bygninger på ejendommen fra BBR: anvendelse, opførelses- og ombygningsår, arealer, etager,
    ydervæg- og tagmateriale, asbest, varmeinstallation, fredning m.m. Koder er oversat til tekst.

    Ejendommen findes som i `sted_find`. Svaret indeholder også indikatorer for bebyggelsesprocent
    ud fra BBR-arealer (ikke beregnet efter BR18's regler). `med_etager` giver areal pr. etage.
    `med_inaktive` medtager nedrevne/historiske bygninger.
    """
    a = _a(ctx)
    if not a.datafordeler.aktiv:
        raise ValueError("bygning_bbr kræver DATAFORDELER_API_KEY")
    kilder: list[dict[str, Any]] = []
    if adresse or matrikel:
        kandidater, kilder = await _kandidater(a, adresse, matrikel, 1)
        if not kandidater:
            return {"besked": "Ingen match på adresse/matrikel", "kilder": kilder}
        k = kandidater[0]
    elif bfe_nummer:
        k = {"bfe_nummer": bfe_nummer, "x": None, "y": None}
    else:
        s = _sted_fra_input(x, y, lat, lon)
        k = {"x": s.x, "y": s.y}

    ejendom = await ejendom_domain.ejendom(
        a.datafordeler,
        husnummer_id=k.get("husnummer_id"),
        jordstykke_id=k.get("jordstykke_id"),
        bfe_nummer=k.get("bfe_nummer"),
        punkt=(k["x"], k["y"]) if k.get("x") is not None else None,
    )
    js_ids = [j["jordstykke_id"] for j in ejendom["jordstykker"]]
    byg = await bygning_domain.bygninger(
        a.datafordeler, js_ids, husnummer_id=ejendom.get("husnummer_id"), med_etager=med_etager, med_inaktive=med_inaktive
    )
    kilder.append(a.datafordeler.angivelse().dict())
    match: dict[str, Any] = {}
    if adresse or matrikel:
        kval = _match_kvalitet(adresse or matrikel or "", k.get("betegnelse"))
        match = {"match": kval}
        if kval == "usikkert":
            match["advarsel"] = (
                f"Den søgte '{adresse or matrikel}' blev ikke fundet præcist. Data gælder '{k.get('betegnelse')}'. "
                "Bekræft med brugeren."
            )
    return {
        **match,
        "ejendom": {
            "betegnelse": k.get("betegnelse"),
            "bfe_nummer": ejendom["bfe_nummer"],
            "matrikler": [j["betegnelse"] for j in ejendom["jordstykker"]],
            "grundareal_registreret_m2": ejendom["grundareal_registreret_m2"],
            "heraf_vejareal_m2": ejendom["heraf_vejareal_m2"],
            "opdelt_i_ejerlejligheder": ejendom.get("opdelt_i_ejerlejligheder"),
        },
        **byg,
        "noegletal": bygning_domain.noegletal(byg, ejendom["grundareal_registreret_m2"], ejendom["heraf_vejareal_m2"]),
        "kilder": kilder,
    }


@mcp.tool()
@brugerfejl
async def plan_gaeldende(
    ctx: Context,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Gældende planer i et punkt: lokalplaner og delområder, lokalplanforslag, kommuneplanramme,
    zonestatus og byggefelter fra Plandata.dk.

    Kommuneplanrammen indeholder ofte maks. bebyggelsesprocent, etager og højde. Lokalplanens
    bestemmelser står i PDF'en (feltet `doklink`), som skal læses for de præcise krav.
    """
    a = _a(ctx)
    sted = _sted_fra_input(x, y, lat, lon)
    planer = await a.plandata.plan_ved_punkt(sted.x, sted.y)
    return {"sted": sted.dict(), **planer, "kilder": [a.plandata.angivelse().dict()]}


@mcp.tool()
@brugerfejl
async def plan_laes_lokalplan(
    ctx: Context,
    planid: int | None = None,
    doklink: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    emne: str | None = None,
    maks_tegn_pr_bestemmelse: int = 4000,
) -> dict[str, Any]:
    """Læs en lokalplans bestemmelser fra PDF'en, opdelt i nummererede bestemmelser med side og underpunkter.

    Angiv `planid` eller `doklink` fra `plan_gaeldende`, eller et punkt (x/y eller lat/lon), så læses den
    gældende lokalplan der. `emne` filtrerer til relevante bestemmelser. Mulige emner: anvendelse,
    bebyggelsesprocent, hoejde, placering, facade_og_materialer, parkering, ubebyggede_arealer,
    veje_og_adgang, miljoe_og_stoej, klima_og_regnvand, bevaring, energi_og_teknik, ibrugtagning
    (eller et frit søgeord). Citér altid bestemmelsens nummer og side. Kortbilag kan ikke læses.
    """
    from byg_mcp.domain import lokalplan as lp

    a = _a(ctx)
    plan: dict[str, Any] = {}
    andre: list[dict[str, Any]] = []
    if planid:
        plan = await a.plandata.plan_efter_id(planid) or {}
        if not plan:
            raise ValueError(f"Ingen lokalplan med planid {planid}")
    elif doklink:
        plan = {"doklink": doklink}
    else:
        sted = _sted_fra_input(x, y, lat, lon)
        planer = await a.plandata.lag_ved_punkt("pdk:theme_pdk_lokalplan_vedtaget", sted.x, sted.y)
        if not planer:
            return {"besked": "Ingen vedtaget lokalplan i punktet", "kilder": [a.plandata.angivelse().dict()]}
        planer.sort(key=lambda p: p.get("datovedt") or 0, reverse=True)
        plan, andre = planer[0], [{k: p.get(k) for k in ("planid", "plannr", "plannavn")} for p in planer[1:]]

    link = plan.get("doklink")
    if not link:
        raise ValueError("Planen har ikke noget dokumentlink")
    cache_key = f"lokalplan:v1:{link}"
    parsed = a.plandata.cache.get(cache_key)
    if parsed is None:
        sider = lp.udtraek_tekst(await a.plandata.hent_pdf(link))
        fmt, best = lp.parse_bestemmelser(sider)
        parsed = {"format": fmt, "sider": len(sider), "bestemmelser": [b.dict() for b in best]}
        a.plandata.cache.set(cache_key, parsed, 30 * 24 * 3600)

    bestemmelser = [lp.Bestemmelse(**b) for b in parsed["bestemmelser"]]
    valgte = lp.filtrer(bestemmelser, emne)
    svar: dict[str, Any] = {
        "plan": {k: plan.get(k) for k in ("planid", "plannr", "plannavn", "kommunenavn", "datovedt", "doklink") if plan.get(k)},
        "pdf_sider": parsed["sider"],
        "format": parsed["format"],
        "emne": emne,
        "bestemmelser": [b.dict(maks_tegn_pr_bestemmelse) for b in valgte],
        "oversigt": [f"{b.nr}. {b.overskrift} (s. {b.side})" for b in bestemmelser],
        "note": "Tekst udtrukket automatisk fra PDF. Kortbilag og illustrationer er ikke med. "
        "Kontrollér altid mod den originale PDF (doklink).",
        "kilder": [a.plandata.angivelse().dict()],
    }
    if not bestemmelser:
        svar["advarsel"] = "Bestemmelserne kunne ikke genkendes i PDF'en. Læs den originale PDF."
    if andre:
        svar["andre_lokalplaner_i_punktet"] = andre
    return svar


@mcp.tool()
@brugerfejl
async def restriktioner(
    ctx: Context,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_m: float = 0,
) -> dict[str, Any]:
    """Restriktioner og miljøforhold i et punkt, samlet fra flere kilder:

    - `natur_og_planlinjer` (Danmarks Arealinformation): sø-, å-, skov- og kirkebyggelinjer, fredninger,
      § 3-natur, Natura 2000, områdeklassificering, råstof, grundvandsbeskyttelse (BNBO, indsatsplaner).
    - `jordforurening` (DKjord): V1-/V2-kortlagte arealer med lokalitet og link til jordforureningsattest.
    - `stoej` (Miljøstyrelsen): Lden i 1,5 m fra vej, jernbane, virksomheder og lufthavne (dB-interval).
    - `fortidsminder` (Slots- og Kulturstyrelsen): fredede fortidsminder og 100 m-beskyttelseslinjer.
    - `matrikelnoteringer` (Matriklen): strandbeskyttelse, klitfredning og fredskov på ejendommens
      jordstykker (kræver Datafordeler-nøgle).

    `radius_m` = 0 betyder præcis punkt. Sæt fx 50 for at se restriktioner tæt på punktet.
    Data er screening, ikke en juridisk afklaring.
    """
    a = _a(ctx)
    sted = _sted_fra_input(x, y, lat, lon)
    kilder: list[dict[str, Any]] = []

    async def matrikel() -> dict[str, Any]:
        if not a.datafordeler.aktiv:
            return {"note": "kræver DATAFORDELER_API_KEY"}
        e = await ejendom_domain.ejendom(a.datafordeler, punkt=(sted.x, sted.y))
        noter = {j["betegnelse"]: j["noteringer"] for j in e["jordstykker"] if j.get("noteringer")}
        return {"bfe_nummer": e["bfe_nummer"], "noteringer": noter or "ingen"}

    opgaver = {
        "natur_og_planlinjer": (a.arealinfo, a.arealinfo.restriktioner(sted.x, sted.y, radius_m)),
        "jordforurening": (a.jord, a.jord.ved_punkt(sted.x, sted.y, radius_m)),
        "stoej": (a.stoej, a.stoej.ved_punkt(sted.x, sted.y)),
        "fortidsminder": (a.fortidsminder, a.fortidsminder.ved_punkt(sted.x, sted.y, radius_m)),
        "matrikelnoteringer": (a.datafordeler, matrikel()),
    }
    res = await asyncio.gather(*(c for _, c in opgaver.values()), return_exceptions=True)
    out: dict[str, Any] = {"sted": sted.dict()}
    for (navn, (adapter, _)), r in zip(opgaver.items(), res):
        if isinstance(r, Exception):
            out[navn] = {"fejl": f"{type(r).__name__}: {str(r)[:200]}"}
        else:
            out[navn] = r if r else "intet fundet"
            kilder.append(adapter.angivelse().dict())
    out["kilder"] = kilder
    return out


# ---------------------------------------------------------------- M3: grund, terræn, geologi, kort


async def _find(
    a: Adaptere,
    adresse: str | None,
    matrikel: str | None,
    bfe_nummer: int | None,
    x: float | None,
    y: float | None,
    lat: float | None,
    lon: float | None,
    med_geometri: bool = False,
) -> dict[str, Any]:
    """Fælles stedsopslag: returnerer punkt (x, y), evt. ejendom (med grundgeometri), betegnelse, match og kilder."""
    kilder: list[dict[str, Any]] = []
    k: dict[str, Any]
    if adresse or matrikel:
        kandidater, kilder = await _kandidater(a, adresse, matrikel, 1)
        if not kandidater:
            raise LookupError(f"Ingen match på '{adresse or matrikel}'")
        k = kandidater[0]
    elif bfe_nummer:
        k = {"bfe_nummer": bfe_nummer}
    else:
        s = _sted_fra_input(x, y, lat, lon)
        k = {"x": s.x, "y": s.y}

    ejendom = None
    if a.datafordeler.aktiv:
        try:
            ejendom = await ejendom_domain.ejendom(
                a.datafordeler,
                husnummer_id=k.get("husnummer_id"),
                jordstykke_id=k.get("jordstykke_id"),
                bfe_nummer=k.get("bfe_nummer"),
                punkt=(k["x"], k["y"]) if k.get("x") is not None else None,
                med_geometri=med_geometri or "x" not in k,
            )
            kilder.append(a.datafordeler.angivelse().dict())
        except ejendom_domain.EjendomIkkeFundet:
            ejendom = None
    if "x" not in k:
        if not ejendom or not ejendom.get("grundgeometri_wkt"):
            raise LookupError("Kunne ikke bestemme et punkt for ejendommen")
        c = shapely_wkt_loads(ejendom["grundgeometri_wkt"]).representative_point()
        k["x"], k["y"] = round(c.x, 2), round(c.y, 2)
    res = {"x": k["x"], "y": k["y"], "betegnelse": k.get("betegnelse"), "ejendom": ejendom, "kilder": kilder}
    if adresse or matrikel:
        res["match"] = _match_kvalitet(adresse or matrikel or "", k.get("betegnelse"))
    return res


def shapely_wkt_loads(w: str):  # lille indirektion, så shapely kun importeres ved behov
    from shapely import wkt

    return wkt.loads(w)


@mcp.tool()
@brugerfejl
async def terraen(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    omgivelser_m: float = 30,
) -> dict[str, Any]:
    """Terrænforhold på grunden fra Danmarks Højdemodel (DVR90): kote i punktet, min/maks/middel-terræn og
    højdeforskel inden for matrikelgrænsen, middelhældning samt højde over terræn (bygninger/træer) på grunden
    og i en zone omkring den. Bruges til niveaufri adgang, sokkelkoter, terrænregulering, skygge- og nabohøjder.
    """
    from byg_mcp.domain import terraen as terraen_domain

    a = _a(ctx)
    f = await _find(a, adresse, matrikel, bfe_nummer, x, y, lat, lon, med_geometri=True)
    grund_wkt = (f["ejendom"] or {}).get("grundgeometri_wkt")
    analyse = await terraen_domain.analyse(a.dhm, f["x"], f["y"], grund_wkt, omgivelser_m)
    svar = {
        "sted": {"betegnelse": f["betegnelse"], "x": f["x"], "y": f["y"],
                 "bfe_nummer": (f["ejendom"] or {}).get("bfe_nummer")},
        **analyse,
        "kilder": f["kilder"] + [a.dhm.angivelse().dict()],
    }
    if f.get("match") == "usikkert":
        svar["advarsel"] = f"Usikkert adressematch: data gælder '{f['betegnelse']}'."
    return svar


@mcp.tool()
@brugerfejl
async def jord_geologi(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_m: float = 300,
    maks_boringer: int = 8,
) -> dict[str, Any]:
    """Jordbund og grundvand til tidlig geoteknisk vurdering: jordart fra GEUS' jordartskort (1:25.000 og
    1:200.000), nærmeste boringer i Jupiter med dybde, formål, år, terrænkote, jordlagssymboler, seneste
    vandstand og link til borerapport, samt dybde til terrænnært grundvand (HIP, vinter og sommer).
    Erstatter ikke en geoteknisk undersøgelse.
    """
    a = _a(ctx)
    f = await _find(a, adresse, matrikel, bfe_nummer, x, y, lat, lon)
    jordart, boringer, grundvand = await asyncio.gather(
        a.geus.jordart(f["x"], f["y"]),
        a.geus.boringer(f["x"], f["y"], radius_m, maks_boringer),
        a.grundvand.ved_punkt(f["x"], f["y"]),
        return_exceptions=True,
    )

    def ok(v: Any) -> Any:
        return {"fejl": f"{type(v).__name__}: {str(v)[:150]}"} if isinstance(v, Exception) else v

    return {
        "sted": {"betegnelse": f["betegnelse"], "x": f["x"], "y": f["y"]},
        "jordart": ok(jordart),
        "boringer": ok(boringer) if boringer else f"Ingen boringer inden for {radius_m:g} m",
        "terraennaert_grundvand": ok(grundvand),
        "note": "Jordlagssymboler følger GEUS' DGU-nomenklatur (fx ml = moræneler, ds = smeltevandssand, "
        "f = fyld). Læs borerapporten for den fulde lagfølge.",
        "kilder": f["kilder"] + [a.geus.angivelse().dict(), a.grundvand.angivelse().dict()],
    }


@mcp.tool()
@brugerfejl
async def kort_udsnit(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    lag: str = "ortofoto",
    side_m: float = 150,
) -> list:
    """Kortudsnit som billede centreret om stedet. `lag`: ortofoto (luftfoto, forår), terraen_skyggekort
    eller overflade_skyggekort (viser bygninger og træer i relief). `side_m` er udsnittets sidelængde i meter
    (30-1000). Svaret indeholder også et link til skråfoto af stedet.
    """
    from mcp.server.mcpserver import Image

    a = _a(ctx)
    if lag not in a.kort.LAG:
        raise ValueError(f"Ukendt lag '{lag}'. Vælg mellem: {', '.join(a.kort.LAG)}")
    side_m = max(30, min(1000, side_m))
    f = await _find(a, adresse, matrikel, bfe_nummer, x, y, lat, lon)
    data, fmt = await a.kort.billede(lag, f["x"], f["y"], side_m)
    info = {
        "sted": f["betegnelse"] or f"{f['x']:.0f}, {f['y']:.0f}",
        "lag": lag,
        "udsnit": f"{side_m:g} x {side_m:g} m, nord opad, centreret om stedet",
        "skraafoto": f"https://skraafoto.dataforsyningen.dk/?center={f['x']:.0f},{f['y']:.0f}",
        "kilde": a.kort.angivelse().dict(),
    }
    import json as _json

    return [Image(data=data, format=fmt), _json.dumps(info, ensure_ascii=False)]


@mcp.tool()
@brugerfejl
async def grundrapport(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Samlet grundrapport for tidlig fase. Kører alle kilder parallelt og samler: ejendom (matrikler, BFE,
    grundareal), eksisterende bygninger (BBR), plangrundlag (zone, lokalplaner med nøgletal, kommuneplanramme),
    restriktioner (natur, jordforurening, støj, fortidsminder, matrikelnoteringer), terræn og jordbund/grundvand.
    Brug derefter de enkelte værktøjer (fx `plan_laes_lokalplan`) til detaljer.
    """
    from byg_mcp.domain import terraen as terraen_domain

    a = _a(ctx)
    f = await _find(a, adresse, matrikel, bfe_nummer, x, y, lat, lon, med_geometri=True)
    X, Y, ejd = f["x"], f["y"], f["ejendom"] or {}
    js_ids = [j["jordstykke_id"] for j in ejd.get("jordstykker", [])]

    async def bygninger() -> Any:
        if not js_ids:
            return "kræver ejendomsopslag (DATAFORDELER_API_KEY)"
        b = await bygning_domain.bygninger(a.datafordeler, js_ids, husnummer_id=ejd.get("husnummer_id"))
        kort = [
            {k: v for k, v in {
                "anvendelse": (x_.get("anvendelse") or {}).get("tekst"),
                "opfoerelsesaar": x_.get("opfoerelsesaar"),
                "om_tilbygningsaar": x_.get("om_tilbygningsaar"),
                "samlet_bygningsareal_m2": x_.get("samlet_bygningsareal_m2"),
                "bebygget_areal_m2": x_.get("bebygget_areal_m2"),
                "antal_etager": x_.get("antal_etager"),
                "ydervaeg": (x_.get("ydervaeg") or {}).get("tekst"),
                "tagdaekning": (x_.get("tagdaekning") or {}).get("tekst"),
                "varmeinstallation": (x_.get("varmeinstallation") or {}).get("tekst"),
                "fredning": (x_.get("fredning") or {}).get("tekst"),
            }.items() if v not in (None, "")}
            for x_ in b["bygninger"]
        ]
        return {
            "antal": b["antal_bygninger"], "bygninger": kort,
            "noegletal": bygning_domain.noegletal(b, ejd.get("grundareal_registreret_m2", 0), ejd.get("heraf_vejareal_m2", 0)),
        }

    async def plan() -> Any:
        p = await a.plandata.plan_ved_punkt(X, Y)
        noegle = ("plannr", "plannavn", "anvendelsegenerel", "bebygpct", "maxetager", "maxbygnhjd", "minuds",
                  "maxbebygpct", "doklink", "planid", "datovedt", "zonestatus")

        def pluk(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{k: r[k] for k in noegle if r.get(k) not in (None, "")} for r in rows]

        return {
            "zonestatus": [z.get("zonestatus") for z in p.get("zonestatus", [])],
            "lokalplaner": pluk(p.get("lokalplaner", [])),
            "lokalplan_delomraader": pluk(p.get("lokalplan_delomraader", [])),
            "lokalplanforslag": pluk(p.get("lokalplanforslag", [])),
            "kommuneplanrammer": pluk(p.get("kommuneplanrammer", [])),
        }

    async def restr() -> Any:
        r = await restriktioner(ctx, x=X, y=Y)
        r.pop("sted", None)
        r.pop("kilder", None)
        if isinstance(r.get("natur_og_planlinjer"), dict):
            r["natur_og_planlinjer"] = list(r["natur_og_planlinjer"].get("fundet", {})) or "intet fundet"
        return r

    async def terr() -> Any:
        t = await terraen_domain.analyse(a.dhm, X, Y, ejd.get("grundgeometri_wkt"))
        t.pop("note", None)
        return t

    async def geo() -> Any:
        jordart, bor, gv = await asyncio.gather(
            a.geus.jordart(X, Y), a.geus.boringer(X, Y, 300, 5), a.grundvand.ved_punkt(X, Y), return_exceptions=True
        )
        return {
            "jordart": jordart if not isinstance(jordart, Exception) else str(jordart)[:120],
            "naermeste_boringer": bor if not isinstance(bor, Exception) else str(bor)[:120],
            "terraennaert_grundvand": gv if not isinstance(gv, Exception) else str(gv)[:120],
        }

    navne = ["bygninger", "plangrundlag", "restriktioner", "terraen", "jord_og_grundvand"]
    res = await asyncio.gather(bygninger(), plan(), restr(), terr(), geo(), return_exceptions=True)
    rapport: dict[str, Any] = {
        "sted": {"betegnelse": f["betegnelse"], "x": X, "y": Y},
        "ejendom": {k: v for k, v in ejd.items() if k != "grundgeometri_wkt"} or "ikke fundet",
    }
    if f.get("match") == "usikkert":
        rapport["advarsel"] = f"Usikkert adressematch: rapporten gælder '{f['betegnelse']}'. Bekræft med brugeren."
    for n, r in zip(navne, res):
        rapport[n] = {"fejl": f"{type(r).__name__}: {str(r)[:200]}"} if isinstance(r, Exception) else r
    rapport["links"] = {
        "skraafoto": f"https://skraafoto.dataforsyningen.dk/?center={X:.0f},{Y:.0f}",
        "arealinformation": f"https://danmarksarealinformation.miljoeportal.dk/?center={X:.0f},{Y:.0f}&zoom=12",
    }
    rapport["kilder"] = f["kilder"] + [
        ad.angivelse().dict()
        for ad in (a.datafordeler, a.plandata, a.arealinfo, a.jord, a.stoej, a.fortidsminder, a.dhm, a.geus, a.grundvand)
    ]
    rapport["forbehold"] = (
        "Automatisk screening af offentlige registre. Erstatter ikke servitutgennemgang (tingbog), "
        "geoteknisk undersøgelse, myndighedsdialog eller læsning af lokalplanens fulde tekst og kortbilag."
    )
    return rapport


# ---------------------------------------------------------------- M5: klima, energi, LCA og BIM


async def _kommunekode(a: Adaptere, x: float, y: float) -> str:
    zoner = await a.plandata.lag_ved_punkt("pdk:theme_pdk_zonekort_v", x, y)
    if zoner and zoner[0].get("komnr"):
        return f"{int(zoner[0]['komnr']):04d}"
    raise LookupError("Kunne ikke bestemme kommunen for punktet")


def _prisomraade(lon: float, x: float) -> str:
    """DK1 = Jylland og Fyn, DK2 = Sjælland, øerne og Bornholm. Grænsen følger Storebælt (ca. 11° Ø)."""
    return "DK2" if lon >= 11.0 or x > 850_000 else "DK1"


@mcp.tool()
@brugerfejl
async def klima_data(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    antal_aar: int = 10,
) -> dict[str, Any]:
    """Observeret klima for kommunen fra DMI (seneste hele år): temperatur, graddage, nedbør inkl. største
    30-min.-regn (skybrud), vind og vindstød, solskin, stråling, fugt, sommerdage, tropenætter, frost og sne.
    Bruges til LAR, energi, termisk indeklima og konstruktioner. `antal_aar` (1-30) styrer perioden.
    Det er målte værdier, ikke klimafremskrivninger. Dimensionering sker efter gældende normer og DMI's
    klimaatlas.
    """
    a = _a(ctx)
    f = await _find(a, adresse, matrikel, None, x, y, lat, lon)
    kode = await _kommunekode(a, f["x"], f["y"])
    k = await a.dmi.klima(kode, max(1, min(30, antal_aar)))
    return {"sted": {"betegnelse": f["betegnelse"], "x": f["x"], "y": f["y"]}, **k,
            "kilder": f["kilder"] + [a.dmi.angivelse("Kommunegennemsnit (interpoleret grid), ikke en enkelt station").dict()]}


def _liste(tekst: str, gyldige: dict[str, Any], navn: str) -> list[str]:
    valgt = list(gyldige) if tekst.strip().lower() == "alle" else [t.strip().lower() for t in tekst.split(",") if t.strip()]
    ukendte = [t for t in valgt if t not in gyldige]
    if ukendte or not valgt:
        raise ValueError(f"Ukendt {navn}: {', '.join(ukendte) or tekst}. Brug {', '.join(gyldige)} eller 'alle'.")
    return valgt


@mcp.tool()
@brugerfejl
async def klima_fremskrivning(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    scenarier: str = "mellem",
    perioder: str = "midt,slut",
    aarstid: str = "hele_aaret",
    med_kyst: bool = True,
    kyst_maks_afstand_m: float = 5000,
) -> dict[str, Any]:
    """Klimafremskrivninger fra DMI's Klimaatlas for stedets kommune: nedbør (gennemsnit, skybrud, 10- og
    100-årshændelser for time- og døgnnedbør), temperatur, hedebølger, frost og frysepunktspassager. Ligger
    stedet tæt på kysten, også middelvandstand og stormflod (20- og 100-årshændelse) for kyststrækningen.

    `scenarier`: lav, mellem, hoej eller alle (kommune: RCP2,6/4,5/8,5; kyst: SSP1-2,6/2-4,5/5-8,5).
    `perioder`: start (2011-2040), midt (2041-2070), slut (2071-2100) eller alle.
    `aarstid`: hele_aaret, vinter, foraar, sommer, efteraar (gælder kommunedata).
    Hver værdi er median med 10-90 %-interval; reference er 1981-2010. Til dimensionering bruges gældende
    normer og vejledning om valg af udledningsscenarie.
    """
    a = _a(ctx)
    scen = _liste(scenarier, SCENARIER_KOMMUNE, "scenarie")
    per = [PERIODER[p] for p in _liste(perioder, PERIODER, "periode")]
    if aarstid not in AARSTIDER:
        raise ValueError(f"Ukendt årstid '{aarstid}'. Brug {', '.join(AARSTIDER)}.")
    f = await _find(a, adresse, matrikel, None, x, y, lat, lon)
    kode = await _kommunekode(a, f["x"], f["y"])
    kommune = await a.klimaatlas.kommune(kode, scen, per, AARSTIDER[aarstid])
    ud: dict[str, Any] = {"sted": {"betegnelse": f["betegnelse"], "x": f["x"], "y": f["y"]}, "kommunekode": kode,
                          "aarstid": aarstid, "kommune": kommune}
    if med_kyst:
        k = await a.klimaatlas.kyststraekning(f["x"], f["y"], kyst_maks_afstand_m)
        if k:
            ud["kyst"] = {**k, **await a.klimaatlas.kyst(k["kystkode"], scen, per)}
        else:
            ud["kyst"] = {"note": f"Ingen kyststrækning inden for {kyst_maks_afstand_m:.0f} m"}
    ud["forbehold"] = ("Kommunegennemsnit og kyststrækning, ikke punktværdier. Stormflod er uden bølgebidrag. "
                       "Klimaatlas siger intet om effekter som grundvand, kloak og lokale forhold.")
    ud["kilder"] = f["kilder"] + [a.klimaatlas.angivelse(f"Klimaatlas {kommune.get('version') or ''}".strip()).dict()]
    return ud


@mcp.tool()
@brugerfejl
async def oversvoemmelse(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_m: float = 15,
    kyst_maks_afstand_m: float = 5000,
) -> dict[str, Any]:
    """Screening for oversvømmelse på stedet: havvand (hvor højt havet skal stige, før stedet oversvømmes,
    sammenholdt med DMI's stormflodshøjder for kyststrækningen), lavninger ved ekstremregn (Bluespot: hvor
    meget regn der skal til at fylde lavningen) og terrænnært grundvand.

    `radius_m` (standard 15 m) giver også den laveste værdi i en ring omkring punktet, fx bygningens hjørner.
    Screening uden kloak, nedsivning og bølger. Erstatter ikke en hydraulisk analyse eller kommunens
    risikokortlægning.
    """
    a = _a(ctx)
    if not a.hydro.config.dataforsyningen_token:
        raise ValueError("Oversvømmelsesdata kræver DATAFORSYNINGEN_TOKEN")
    f = await _find(a, adresse, matrikel, None, x, y, lat, lon)
    r = max(0.0, min(100.0, radius_m))
    havvand, bluespot, grundvand, kyst = await asyncio.gather(
        a.hydro.lag_ved_punkt("havvand", f["x"], f["y"], r),
        a.hydro.lag_ved_punkt("bluespot", f["x"], f["y"], r),
        a.grundvand.ved_punkt(f["x"], f["y"]),
        a.klimaatlas.kyststraekning(f["x"], f["y"], kyst_maks_afstand_m),
        return_exceptions=True,
    )
    noter: list[str] = []
    ud: dict[str, Any] = {"sted": {"betegnelse": f["betegnelse"], "x": f["x"], "y": f["y"]}, "radius_m": r}

    if isinstance(havvand, Exception):
        noter.append(f"Havvand på Land: {type(havvand).__name__}: {havvand}")
    else:
        taerskel = havvand["laveste_i_radius"]
        rund = lambda v: None if v is None else round(v, 2)  # noqa: E731
        hv: dict[str, Any] = {
            "oversvoemmes_ved_havniveau_m": rund(havvand["i_punktet"]),
            "laveste_taerskel_i_radius_m": rund(taerskel),
            "forklaring": "Havniveau over middelvandstand (m, DVR90), der oversvømmer stedet via åben forbindelse til havet. "
                          "Ingen værdi i punktet betyder, at modellen ikke har en tærskel dér (fx under en bygning eller "
                          "uden forbindelse til havet); se så den laveste værdi i radius.",
        }
        if havvand.get("punkter_uden_forbindelse_til_havet"):
            hv["punkter_uden_forbindelse_til_havet"] = havvand["punkter_uden_forbindelse_til_havet"]
        if taerskel is not None and not isinstance(kyst, Exception) and kyst:
            try:
                storm = await a.klimaatlas.stormflod_m(kyst["kystkode"])
                hv["kyststraekning"] = kyst
                hv["stormflod_der_naar_stedet"] = [s for s in storm if s["hoejde_m"] >= taerskel]
                hv["stormflod_alle"] = storm
            except Exception as e:  # noqa: BLE001 - delvise svar frem for fejl
                noter.append(f"Klimaatlas stormflod: {e}")
        ud["havvand"] = hv
    if isinstance(bluespot, Exception):
        noter.append(f"Bluespot: {type(bluespot).__name__}: {bluespot}")
    else:
        mm = lambda v: None if v is None else round(v * 1000)  # noqa: E731 - meter regn → mm
        ud["ekstremregn_bluespot"] = {
            "regn_til_at_fylde_lavning_mm": mm(bluespot["i_punktet"]),
            "laveste_i_radius_mm": mm(bluespot["laveste_i_radius"]),
            "forklaring": "Regnmængde, der skal til at fylde terrænlavningen, uden kloak og nedsivning. "
                          "Ingen værdi betyder, at punktet ikke ligger i en lavning.",
        }
    ud["terraennaert_grundvand"] = (
        {"note": f"{type(grundvand).__name__}: {grundvand}"} if isinstance(grundvand, Exception) else grundvand
    )
    if noter:
        ud["noter"] = noter
    ud["forbehold"] = "Screening. Erstatter ikke hydraulisk analyse, kommunens risikokortlægning eller forsikringsvurdering."
    ud["kilder"] = f["kilder"] + [a.hydro.angivelse().dict(), a.grundvand.angivelse().dict(), a.klimaatlas.angivelse().dict()]
    return ud


@mcp.tool()
@brugerfejl
async def energimaerke(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    bfe_nummer: int | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    med_forslag: bool = True,
) -> dict[str, Any]:
    """Energimærker for ejendommen fra Energistyrelsen: klasse, gyldighed, grundlag og bygninger, samt for det
    gældende mærke forbedringsforslagene med investering, årlig besparelse, levetid og om de er rentable, og den
    klasse bygningen kan opnå. Kræver adgang til EMOData (EMO_BRUGERNAVN og EMO_ADGANGSKODE).
    """
    a = _a(ctx)
    if not a.emo.aktiv:
        raise ValueError("Energimærker kræver adgang til Energistyrelsens EMOData-service. Sæt EMO_BRUGERNAVN og "
                         "EMO_ADGANGSKODE i .env. Adgang fås ved henvendelse til Energistyrelsen.")
    f = await _find(a, adresse, matrikel, bfe_nummer, x, y, lat, lon)
    bfe = bfe_nummer or (f.get("ejendom") or {}).get("bfe_nummer")
    maerker = await a.emo.maerker_for_bfe(bfe) if bfe else []
    grundlag = "BFE-nummer"
    if not maerker:
        s = Sted.fra_utm(f["x"], f["y"])
        maerker = await a.emo.maerker_ved_koordinat(s.lat, s.lon)
        grundlag = "koordinat (ingen mærker fundet på BFE-nummer)"
    gaeldende = vaelg_gaeldende(maerker)
    ud: dict[str, Any] = {"sted": {"betegnelse": f["betegnelse"], "bfe_nummer": bfe}, "soegt_paa": grundlag,
                          "antal_maerker": len(maerker), "gaeldende": gaeldende,
                          "oevrige": [m for m in maerker if m is not gaeldende]}
    if med_forslag and gaeldende and gaeldende.get("nummer"):
        ud["forbedringer"] = await a.emo.forbedringer(gaeldende["nummer"])
    if not maerker:
        ud["note"] = "Ingen energimærker fundet. Mange bygninger er ikke energimærket (fx fredede eller små bygninger)."
    ud["kilder"] = f["kilder"] + [a.emo.angivelse().dict()]
    return ud


@mcp.tool()
@brugerfejl
async def sol_og_pv(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    haeldning_grader: float | None = None,
    orientering_grader: float | None = None,
    kwp: float = 1.0,
    systemtab_pct: float = 14.0,
) -> dict[str, Any]:
    """Solcelleydelse og solindstråling fra PVGIS for stedet, inkl. horisont fra terrænmodel.
    `orientering_grader`: 0 = syd, -90 = øst, 90 = vest. `haeldning_grader`: 0 = vandret. Udelades begge,
    beregnes den optimale hældning og orientering. Giver årsproduktion, kWh pr. kWp og månedsfordeling.
    Nabobygningers og træers skygge indgår ikke.
    """
    a = _a(ctx)
    f = await _find(a, adresse, matrikel, None, x, y, lat, lon)
    s = Sted.fra_utm(f["x"], f["y"])
    r = await a.pvgis.pv(s.lat, s.lon, haeldning_grader, orientering_grader, kwp, systemtab_pct)
    return {"sted": {"betegnelse": f["betegnelse"], "lat": s.lat, "lon": s.lon}, **r,
            "kilder": f["kilder"] + [a.pvgis.angivelse().dict()]}


@mcp.tool()
@brugerfejl
async def vejrfil(
    ctx: Context,
    adresse: str | None = None,
    matrikel: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    gem_lokalt: bool = True,
) -> dict[str, Any]:
    """Typisk meteorologisk år (TMY) i EPW-format for stedet fra PVGIS, til termisk simulering, dagslys- og
    energiværktøjer (fx IDA ICE, EnergyPlus, Ladybug). Giver et direkte downloadlink og gemmer evt. filen
    lokalt. Bemærk: Be18-beregninger efter BR18 bruger DMI's Design Reference Year (DRY), ikke denne fil.
    """
    from pathlib import Path

    a = _a(ctx)
    f = await _find(a, adresse, matrikel, None, x, y, lat, lon)
    s = Sted.fra_utm(f["x"], f["y"])
    svar: dict[str, Any] = {
        "sted": {"betegnelse": f["betegnelse"], "lat": s.lat, "lon": s.lon},
        "download_url": a.pvgis.tmy_url(s.lat, s.lon),
        "format": "EnergyPlus Weather (EPW), 8760 timer",
        "note": "TMY fra PVGIS (ERA5/SARAH). Til lovpligtige energirammeberegninger (Be18) bruges DMI's DRY.",
    }
    if gem_lokalt:
        epw = await a.pvgis.tmy_epw(s.lat, s.lon)
        mappe = a.pvgis.config.cache_path.parent / "vejrfiler"
        mappe.mkdir(parents=True, exist_ok=True)
        fil = mappe / f"tmy_{s.lat:.3f}_{s.lon:.3f}.epw"
        fil.write_text(epw, encoding="utf-8")
        svar["lokal_fil"] = str(Path(fil).resolve())
        svar["epw_hoved"] = epw.splitlines()[0][:200]
    svar["kilder"] = f["kilder"] + [a.pvgis.angivelse().dict()]
    return svar


@mcp.tool()
@brugerfejl
async def el_co2(
    ctx: Context,
    adresse: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    prisomraade: str | None = None,
    dage: int = 7,
    byggeaar: int | None = None,
) -> dict[str, Any]:
    """CO2-udledning fra elforbruget: aktuel og seneste dages værdier fra Energinet (DK1 eller DK2, findes ud
    fra stedet) samt BR18's emissionsfaktorer (bilag 2, tabel 8.1) for el, fjernvarme og gas, inkl. en
    50-års middelværdi fra `byggeaar` (standard i år) til brug i tidlig LCA (modul B6).
    """
    from datetime import date as _date

    from byg_mcp.domain import lca as lca_domain

    a = _a(ctx)
    if not prisomraade:
        if adresse or (x is not None) or (lat is not None):
            f = await _find(a, adresse, None, None, x, y, lat, lon)
            s = Sted.fra_utm(f["x"], f["y"])
            prisomraade = _prisomraade(s.lon, s.x)
        else:
            prisomraade = "DK1"
    prisomraade = prisomraade.upper()
    if prisomraade not in ("DK1", "DK2"):
        raise ValueError("prisomraade skal være DK1 (Jylland/Fyn) eller DK2 (Sjælland/øerne/Bornholm)")
    aar = byggeaar or _date.today().year
    return {
        "energinet_aktuelt": await a.energinet.co2(prisomraade, max(1, min(31, dage))),
        "br18_tabel_8_1": {
            "dette_aar": lca_domain.emissionsfaktor(aar),
            "middel_50_aar_fra_byggeaar": {"fra": aar, **lca_domain.b6_middel(aar)},
            "enhed": "kg CO2e/kWh",
            "note": "BR18's fremskrevne faktorer skal bruges i LCA. 50-års middel er en forenkling til tidlig fase. "
            "År efter tabellens sidste år er sat til den sidste værdi.",
        },
        "kilder": [a.energinet.angivelse().dict(), {"navn": "BR18 bilag 2, tabel 8.1", "url": "https://www.bygningsreglementet.dk/bilag/b2/bilag_2/"}],
    }


@mcp.tool()
@brugerfejl
async def lca_materiale(
    ctx: Context,
    materiale: str,
    kilde: str = "br18",
    maks_resultater: int = 8,
) -> dict[str, Any]:
    """Klimadata (GWP, kg CO2e) for byggematerialer.

    `kilde`:
    - "br18" (standard): BR18's generiske datagrundlag (bilag 2, tabel 7), de værdier der må bruges i LCA
      efter BR18 uden produkt-EPD. Danske navne, fx "beton c25", "limtræ", "mineraluld murbatts", "gipsplade".
    - "oekobaudat": produkt-EPD'er og generiske datasæt fra ÖKOBAUDAT med GWP pr. modul.
    - "begge".
    Værdierne gælder pr. deklareret enhed (m³, m², ton, m² med R=1 …). Angiv altid enheden.
    """
    from byg_mcp.domain import lca as lca_domain

    a = _a(ctx)
    kilde = kilde.lower()
    svar: dict[str, Any] = {"materiale": materiale}
    kilder: list[dict[str, Any]] = []
    if kilde in ("br18", "begge"):
        rows = lca_domain.soeg_tabel7(materiale, maks_resultater)
        svar["br18_generiske_data"] = [
            {k: r[k] for k in ("id", "navn", "datatype", "gwp_a1_a3", "gwp_c3", "gwp_c4", "gwp_d",
                               "deklareret_faktor", "deklareret_enhed", "masse_faktor", "masse_enhed", "kilde_url") if r.get(k) is not None}
            for r in rows
        ] or "Ingen match i tabel 7. Prøv et andet ord eller kilde='oekobaudat'."
        kilder.append({"navn": "BR18 bilag 2, tabel 7 - generisk datagrundlag", "url": "https://www.bygningsreglementet.dk/bilag/b2/bilag_2/",
                       "hentet": lca_domain.data()["_hentet"]})
    if kilde in ("oekobaudat", "begge"):
        hits = await a.oekobaudat.soeg(materiale, maks_resultater)
        detaljer = await asyncio.gather(*(a.oekobaudat.gwp(h["uuid"]) for h in hits[:5]), return_exceptions=True)
        for h, d in zip(hits, detaljer):
            if not isinstance(d, Exception):
                h.update(d)
        svar["oekobaudat"] = hits or "Ingen match. ÖKOBAUDAT søger på tysk/engelsk navn."
        kilder.append(a.oekobaudat.angivelse().dict())
    if kilde not in ("br18", "oekobaudat", "begge"):
        raise ValueError("kilde skal være 'br18', 'oekobaudat' eller 'begge'")
    svar["moduler"] = "A1-A3 = produktion, C3-C4 = affaldsbehandling/bortskaffelse, D = potentiale uden for systemgrænsen"
    svar["kilder"] = kilder
    return svar


@mcp.tool()
@brugerfejl
async def bim_klassifikation(
    ctx: Context,
    begreb: str | None = None,
    ordbog: str = "cci",
    klasse_uri: str | None = None,
    maks_resultater: int = 10,
) -> dict[str, Any]:
    """Klassifikation og egenskaber fra buildingSMART Data Dictionary (bSDD).

    Søg med `begreb` i `ordbog`: "cci" (CCI Construction fra Molio, engelske navne, fx "window", "wall"),
    "ifc" (IFC 4.3), "br18" (DTU's ordbog over BR18 bilag 2, tabel 6, bygningsdele til LCA, dansk) eller
    "alle". Angiv `klasse_uri` fra et søgeresultat for at få klassens egenskabssæt (fx til IDS-krav).
    """
    from byg_mcp.adapters.lca_bim import CCI_URI, IFC_URI

    a = _a(ctx)
    if klasse_uri:
        return {"klasse": await a.bsdd.klasse(klasse_uri), "kilder": [a.bsdd.angivelse().dict()]}
    if not begreb:
        raise ValueError("Angiv enten `begreb` (søgning) eller `klasse_uri` (detaljer)")
    ordboeger = {
        "cci": CCI_URI, "ifc": IFC_URI,
        "br18": "https://identifier.buildingsmart.org/uri/dtu.construct/br18B2T6/1.1.1", "alle": None,
    }
    if ordbog.lower() not in ordboeger:
        raise ValueError(f"ordbog skal være en af: {', '.join(ordboeger)}")
    res = await a.bsdd.soeg(begreb, ordboeger[ordbog.lower()], maks_resultater)
    svar: dict[str, Any] = {"begreb": begreb, "ordbog": ordbog, "resultater": res or "Ingen klasser fundet"}
    if not res and ordbog.lower() == "cci":
        svar["tip"] = "CCI i bSDD har kun engelske navne. Prøv fx 'window' i stedet for 'vindue'."
    svar["kilder"] = [a.bsdd.angivelse().dict()]
    return svar


# ---------------------------------------------------------------- M4: regler


def _br18_kilde(note: str | None = None) -> dict[str, Any]:
    from byg_mcp.adapters.base import Kildeangivelse
    from byg_mcp.domain import vidensbase as vb

    m = vb.meta()
    k = Kildeangivelse(
        navn=f"Bygningsreglementet - {m['version']}",
        udbyder="Bolig- og Planstyrelsen (bygningsreglementet.dk)",
        url=m["kilde"],
        licens="Offentlig retsforskrift",
        note=note or f"Lokal kopi hentet {m['hentet']}. Seneste historiske version sluttede {m.get('seneste_historiske_version_slutter')}.",
    )
    k.hentet = m["hentet"]
    return k.dict()


@mcp.tool()
@brugerfejl
async def br18_soeg(
    tekst: str, kapitel: str | None = None, maks_resultater: int = 8, inkl_vejledninger: bool = True
) -> dict[str, Any]:
    """Søg i bygningsreglementet (BR18, aktuel konsolideret version) med fritekst, fx "værn højde altan",
    "grænseværdi klimapåvirkning", "radon", "dagslys". Returnerer relevante paragraffer med uddrag og
    (som standard) de mest relevante steder i BR-vejledningerne, hvor de konkrete løsninger og tal ofte står.
    Hent den fulde paragraf med `br18_paragraf` og vejledningsteksten med `br18_vejledning_hent`.
    `kapitel` kan begrænse søgningen (fx "11").
    """
    from byg_mcp.domain import vidensbase as vb

    hits = vb.soeg(tekst, kapitel, maks_resultater)
    svar: dict[str, Any] = {
        "soegning": tekst,
        "resultater": hits or "Ingen paragraffer fundet. Prøv andre ord eller se `br18_kapitel`.",
    }
    if inkl_vejledninger:
        svar["vejledninger"] = vb.soeg_vejledninger(tekst, kapitel, 4) or "Ingen vejledningstekst fundet"
    svar["kilder"] = [_br18_kilde()] + ([_vejledning_kilde()] if inkl_vejledninger else [])
    return svar


def _vejledning_kilde() -> dict[str, Any]:
    from byg_mcp.domain import vidensbase as vb

    m = vb.vejledning_meta()
    return {
        "navn": "Bygningsreglementets vejledninger",
        "udbyder": "Bolig- og Planstyrelsen (bygningsreglementet.dk)",
        "url": "https://www.bygningsreglementet.dk/vejledninger/bygningsreglementets-vejledninger/oversigt_br_vejledninger/",
        "licens": "Offentlig vejledning",
        "hentet": m.get("hentet"),
        "note": "Vejledninger er ikke bindende, men beskriver præ-accepterede løsninger og fortolkninger. "
        "Tekst fra PDF'er er udtrukket automatisk. Tabeller og figurer kan være ufuldstændige.",
    }


@mcp.tool()
@brugerfejl
async def br18_vejledning_soeg(tekst: str, kapitel: str | None = None, maks_resultater: int = 8) -> dict[str, Any]:
    """Søg i Bygningsreglementets vejledninger: præ-accepterede løsninger (fx brand for enfamiliehuse,
    etageboliger, kontorer), spørgsmål og svar samt uddybende vejledning til hvert kapitel. Fx "flugtvej
    afstand etagebolig", "dagslys glasareal 10 procent", "brandklasse 2 tagdækning". Returnerer dokument,
    side og uddrag. Hent hele teksten med `br18_vejledning_hent` (id).
    """
    from byg_mcp.domain import vidensbase as vb

    if not vb.vejledninger():
        raise LookupError("Vejledningerne er ikke indsamlet. Kør scripts/indsaml_vejledninger.py")
    hits = vb.soeg_vejledninger(tekst, kapitel, maks_resultater)
    return {"soegning": tekst, "resultater": hits or "Ingen vejledningstekst fundet. Prøv andre ord.",
            "kilder": [_vejledning_kilde()]}


@mcp.tool()
@brugerfejl
async def br18_vejledning_hent(id: int, naboer: int = 1) -> dict[str, Any]:
    """Hent den fulde tekst af et stykke vejledning (id fra `br18_vejledning_soeg` eller `br18_soeg`) samt
    `naboer` stykker før og efter fra samme dokument (fx forrige og næste side i en PDF). Citér dokument og side."""
    from byg_mcp.domain import vidensbase as vb

    return {**vb.hent_vejledning(id, max(0, min(3, naboer))), "kilder": [_vejledning_kilde()]}


@mcp.tool()
@brugerfejl
async def br18_paragraf(paragraffer: str) -> dict[str, Any]:
    """Hent den fulde ordlyd af paragraffer i bygningsreglementet (aktuel version). Eksempler: "58",
    "251-256", "297 og 298", "6a", "Bilag 2". Svaret indeholder kapitel, afsnit, tekst, link og eventuelle
    links til BR-vejledninger og henvisninger til standarder. Citér paragrafnummeret i dit svar.
    """
    from byg_mcp.domain import vidensbase as vb

    ps = vb.paragraffer(paragraffer)
    if not ps:
        raise LookupError(f"Ingen paragraf(fer) fundet for '{paragraffer}'. BR18 har §§ 1-565 og bilag 1-6.")
    if len(ps) > 25:
        raise ValueError(f"'{paragraffer}' giver {len(ps)} paragraffer. Begræns til højst 25 ad gangen.")
    return {
        "paragraffer": [
            {k: p[k] for k in ("nr", "kapitel", "kapitel_titel", "afsnit", "tekst", "url", "vejledninger", "henvisninger") if p.get(k)}
            for p in ps
        ],
        "kilder": [_br18_kilde()],
    }


@mcp.tool()
@brugerfejl
async def br18_kapitel(kapitel: str | None = None) -> dict[str, Any]:
    """Oversigt over bygningsreglementet. Uden argument: alle kapitler og bilag. Med `kapitel` (fx "5" for
    brand eller "B2" for bilag 2): kapitlets afsnit og paragrafnumre."""
    from byg_mcp.domain import vidensbase as vb

    if not kapitel:
        return {"kapitler": vb.kapitler(), "kilder": [_br18_kilde()]}
    o = vb.kapitel_oversigt(kapitel)
    if not o:
        raise LookupError(f"Kapitel '{kapitel}' findes ikke. Kald uden argument for at se oversigten.")
    return {**o, "kilder": [_br18_kilde()]}


@mcp.tool()
@brugerfejl
async def lov_soeg(ctx: Context, tekst: str, maks_resultater: int = 10) -> dict[str, Any]:
    """Søg efter gældende love og bekendtgørelser i Retsinformation (fx "byggeloven", "bygningsfredning",
    "energimærkning af bygninger", "jordflytning"). Returnerer titel, nummer, ministerium og link."""
    a = _a(ctx)
    return {"resultater": await a.retsinfo.soeg(tekst, maks=maks_resultater), "kilder": [a.retsinfo.angivelse().dict()]}


@mcp.tool()
@brugerfejl
async def lov_paragraf(ctx: Context, lov: str, paragraf: str) -> dict[str, Any]:
    """Hent en paragraf fra en gældende lov eller bekendtgørelse i Retsinformation. `lov` kan være et
    almindeligt navn (byggeloven, planloven, naturbeskyttelsesloven, miljøbeskyttelsesloven,
    jordforureningsloven, bygningsfredningsloven, museumsloven, arbejdsmiljøloven, vejloven, privatvejsloven,
    skovloven, kystbeskyttelsesloven) eller et ELI-link (fx "/eli/lta/2024/572"). `paragraf` fx "15" eller "3a".

    Til bygningsreglementet: brug `br18_paragraf`. Retsinformation indeholder kun den oprindelige
    BR18-bekendtgørelse uden senere ændringer indarbejdet.
    """
    a = _a(ctx)
    if lov.lower().strip() in ("br18", "bygningsreglementet", "bygningsreglement"):
        return {
            "omdirigeret": "BR18 hentes fra bygningsreglementet.dk (konsolideret). Retsinformations BEK nr. 1399 af "
            "12/12/2019 er den oprindelige tekst, og fx § 298 har her et andet indhold end i dag.",
            **(await br18_paragraf(paragraf)),
        }
    if lov.startswith("/eli/"):
        dok = {"eli": lov, **(await a.retsinfo.titel(lov))}
    else:
        dok = await a.retsinfo.find_lov(lov)
        if not dok:
            raise LookupError(f"Fandt ingen gældende lov for '{lov}'. Prøv `lov_soeg`.")
    p = await a.retsinfo.paragraf(dok["eli"], paragraf)
    if not p:
        raise LookupError(f"§ {paragraf} findes ikke i {dok.get('betegnelse') or dok['eli']}")
    return {
        "lov": {k: dok.get(k) for k in ("titel", "populaertitel", "betegnelse", "eli") if dok.get(k)},
        **p,
        "url": f"https://www.retsinformation.dk{dok['eli']}",
        "kilder": [a.retsinfo.angivelse().dict()],
    }


@mcp.resource("br18://oversigt", name="BR18-oversigt", mime_type="application/json")
def br18_oversigt_resource() -> str:
    """Bygningsreglementets kapitler og version."""
    import json as _json

    from byg_mcp.domain import vidensbase as vb

    return _json.dumps({"meta": vb.meta(), "kapitler": vb.kapitler()}, ensure_ascii=False)


@mcp.resource("br18://paragraf/{nr}", name="BR18-paragraf", mime_type="text/plain")
def br18_paragraf_resource(nr: str) -> str:
    """Ordlyden af én BR18-paragraf (aktuel version)."""
    from byg_mcp.domain import vidensbase as vb

    ps = vb.paragraffer(nr)
    if not ps:
        from mcp.server.mcpserver.exceptions import ResourceNotFoundError

        raise ResourceNotFoundError(f"BR18 § {nr} findes ikke")
    return "\n\n".join(f"{p['tekst']}\n[{p['kapitel']}. {p['kapitel_titel']} – {p['afsnit']}] {p['url']}" for p in ps)


@mcp.prompt()
def br18_tjek(projekt: str, emner: str = "") -> str:
    """Gennemgå et projekt mod relevante krav i bygningsreglementet."""
    return f"""Du hjælper en bygningsdesigner med at tjekke et projekt mod bygningsreglementet (BR18, aktuel version).

Projekt: {projekt}
{f'Fokusér på: {emner}' if emner else ''}

Fremgangsmåde:
1. Identificér de relevante emner (fx adgangsforhold, brand, energi/klima, lys, lyd, ventilation, konstruktioner).
2. Brug `br18_soeg` pr. emne og `br18_paragraf` til den fulde ordlyd. Brug `br18_kapitel` til at få overblik.
3. Brug `lov_paragraf` ved behov for byggeloven eller planloven.

Svar som en tabel: Emne | Krav (med §) | Projektets forhold | Vurdering (opfyldt / skal eftervises / uklart).
Citér paragrafnumre. Skeln mellem lovtekst og din fortolkning, og gør opmærksom på, at BR-vejledningerne og
eventuelle standarder (DS, Eurocodes) skal konsulteres for de konkrete eftervisningsmetoder.
"""


@mcp.prompt()
def grundscreening(adresse: str, projekt: str = "") -> str:
    """Tidlig-fase-screening af en grund: hvad må der bygges, og hvilke forhold skal undersøges nærmere?"""
    return f"""Du er rådgiver for en bygningsdesigner i tidlig fase. Lav en grundscreening af: {adresse}
{f'Projektidé: {projekt}' if projekt else ''}

Fremgangsmåde:
1. Kald `grundrapport` for adressen. Er adressematchet usikkert, så spørg brugeren først.
2. Kald `plan_laes_lokalplan` med emnerne hoejde, bebyggelsesprocent og parkering for den gældende lokalplan.
3. Kald evt. `kort_udsnit` (ortofoto) for at forstå konteksten.

Skriv derefter en kort screening på dansk med disse afsnit:
- **Ejendom og eksisterende forhold:** matrikel, grundareal, bygninger.
- **Byggemuligheder:** zone, anvendelse, bebyggelsesprocent, højder og etager med henvisning til
  lokalplanens bestemmelse og side eller kommuneplanrammen.
- **Restriktioner og risici:** bygge- og beskyttelseslinjer, fortidsminder, jordforurening, støj, grundvand,
  terræn og jordbund.
- **Skal afklares:** fx servitutter, dispensationer, geoteknik, myndighedsdialog.

Angiv kilde for hvert faktum. Skeln tydeligt mellem data fra registrene og din egen faglige vurdering.
"""


def _http_app(token: str, stateless: bool = False):
    """Streamable HTTP-app, hvor MCP-endpointet ligger på en hemmelig sti (/mcp/<token>).

    claude.ai's custom connectors kan ikke sende en fast Bearer-header, så den hemmelige sti er
    adgangskontrollen. Alle andre stier giver 404. Host-tjekket (DNS rebinding) er slået fra, fordi
    serveren kun lytter på localhost bag en tunnel med skiftende værtsnavn, og et angreb alligevel
    skulle kende stien.

    `stateless=True` bruges i containeren hos Cloudflare: den sover, når den ikke bruges, så sessioner
    i hukommelsen ville gå tabt. Uden tilstand kan hvert kald stå alene.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    return mcp.streamable_http_app(
        streamable_http_path=f"/mcp/{token}",
        stateless_http=stateless,
        json_response=stateless,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


def main() -> None:
    import argparse
    import os

    p = argparse.ArgumentParser(prog="byg-mcp", description="MCP-server med danske data for bygningsdesign.")
    p.add_argument("--http", action="store_true", help="Kør som HTTP-server (til tunnel/claude.ai) i stedet for stdio")
    p.add_argument("--port", type=int, default=int(os.environ.get("BYG_MCP_PORT", "8765")))
    p.add_argument("--host", default=os.environ.get("BYG_MCP_HOST", "127.0.0.1"),
                   help="Adresse at lytte på. 127.0.0.1 bag en tunnel, 0.0.0.0 i en container")
    p.add_argument("--stateless", action="store_true",
                   default=os.environ.get("BYG_MCP_STATELESS", "") == "1",
                   help="Uden sessioner (til containere, der kan sove mellem kald)")
    args = p.parse_args()

    if not args.http:
        mcp.run()
        return

    import secrets

    import uvicorn

    from byg_mcp.infra.config import _load_dotenv

    _load_dotenv()
    token = os.environ.get("BYG_MCP_HTTP_TOKEN", "").strip()
    if len(token) < 32:
        raise SystemExit(
            "BYG_MCP_HTTP_TOKEN mangler eller er for kort (mindst 32 tegn). Tilføj en linje i .env, fx:\n"
            f"BYG_MCP_HTTP_TOKEN={secrets.token_urlsafe(32)}"
        )
    print(f"byg-mcp lytter på http://{args.host}:{args.port}/mcp/<BYG_MCP_HTTP_TOKEN>"
          + (" (uden sessioner)" if args.stateless else ""), flush=True)
    # access_log=False: stien indeholder hemmeligheden og må ikke logges.
    uvicorn.run(_http_app(token, args.stateless), host=args.host, port=args.port,
                access_log=False, log_level="warning")


if __name__ == "__main__":
    main()

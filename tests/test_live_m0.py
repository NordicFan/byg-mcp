"""Live-test af M0 mod de rigtige kilder (kræver net). Kør: uv run pytest -m live -s"""

import json

import pytest
from mcp import Client

from byg_mcp.server import mcp

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

AALBORG_MIDTBY = {"x": 555882, "y": 6323238}  # Bispensgade 3, Aalborg (lokalplan 1-1-143)


async def _call(client: Client, tool: str, args: dict) -> dict:
    res = await client.call_tool(tool, args)
    assert not res.is_error, res.content
    return res.structured_content or json.loads(res.content[0].text)


async def test_tools_registreret():
    async with Client(mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert {"kilde_status", "sted_find", "plan_gaeldende", "restriktioner"} <= names


async def test_kilde_status():
    async with Client(mcp) as c:
        status = await _call(c, "kilde_status", {})
    print(json.dumps(status, ensure_ascii=False, indent=1))
    assert status["Plandata.dk"] == "ok"
    assert status["Danmarks Arealinformation"] == "ok"


async def test_sted_find_adresse():
    async with Client(mcp) as c:
        res = await _call(c, "sted_find", {"adresse": "Bispensgade 3, 9000 Aalborg"})
    print(json.dumps(res, ensure_ascii=False, indent=1)[:1200])
    k = res["valgt"]
    assert 550_000 < k["x"] < 560_000 and 6_320_000 < k["y"] < 6_326_000


async def test_plan_gaeldende_aalborg():
    async with Client(mcp) as c:
        res = await _call(c, "plan_gaeldende", AALBORG_MIDTBY)
    print(json.dumps({k: (v if k != "kommuneplanrammer" else v[:1]) for k, v in res.items()}, ensure_ascii=False, indent=1)[:2500])
    assert res["zonestatus"][0]["zonestatus"] == "Byzone"
    assert res["kommuneplanrammer"], "forventer mindst én kommuneplanramme"
    assert any(p["plannr"] == "1-1-143" for p in res["lokalplaner"])
    assert res["kilder"][0]["navn"] == "Plandata.dk"


async def test_restriktioner_aalborg():
    async with Client(mcp) as c:
        res = await _call(c, "restriktioner", AALBORG_MIDTBY)
    natur = res["natur_og_planlinjer"]
    assert "fejl" not in natur
    assert "Områdeklassificering (lettere forurenet byjord)" in natur["fundet"]
    # Bispensgade 3 ligger inden for fortidsmindebeskyttelseslinjen omkring Aalborghus (verificeret 8/11-2026)
    assert "fortidsmindebeskyttelseslinje" in res["fortidsminder"]
    assert "lden_1_5m" in res["stoej"]
    assert {k["navn"] for k in res["kilder"]} >= {"Danmarks Arealinformation", "DKjord - jordforurening", "Fund og Fortidsminder"}


async def test_restriktioner_stoej_og_jordforurening_kbh():
    async with Client(mcp) as c:
        stoej = await _call(c, "restriktioner", {"x": 724380, "y": 6175700})  # Rådhuspladsen
        jord = await _call(c, "restriktioner", {"x": 724459, "y": 6175810, "radius_m": 150})  # nær Politikens Hus
    assert stoej["stoej"]["lden_1_5m"]["Veje i by"].startswith("70-74")
    assert "V2" in jord["jordforurening"]


async def test_ugyldig_koordinat_giver_fejl():
    async with Client(mcp) as c:
        res = await c.call_tool("plan_gaeldende", {"x": 6323193, "y": 555735})  # ombyttet
    assert res.is_error

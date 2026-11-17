"""Live-test af M6 (Klimaatlas, oversvømmelse, energimærker). Kør: uv run pytest -m live tests/test_live_m6.py"""

import json

import pytest
from mcp import Client

from byg_mcp.infra.config import load_config
from byg_mcp.server import mcp

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

AALBORG_HAVN = {"x": 556500, "y": 6324500}  # tæt på Limfjorden
UCN = {"x": 553742, "y": 6320077}  # Sofiendalsvej 60, ca. 20 m over havet


async def _call(tool: str, args: dict) -> dict:
    async with Client(mcp) as c:
        res = await c.call_tool(tool, args)
    if res.is_error and "overbelastet" in res.content[0].text:
        pytest.skip(f"Kilden er midlertidigt overbelastet: {res.content[0].text[:120]}")
    assert not res.is_error, res.content
    return res.structured_content or json.loads(res.content[0].text)


async def test_klima_fremskrivning_aalborg():
    d = await _call("klima_fremskrivning", {**AALBORG_HAVN, "scenarier": "mellem", "perioder": "slut"})
    assert d["kommunekode"] == "0851"
    ind = {i["indikator"]: i for i in d["kommune"]["indikatorer"]}
    skybrud = ind["Skybrud (over 15 mm på 30 min.)"]
    assert skybrud["reference_1981_2010"]["median"] > 0
    assert "2071-2100" in skybrud["fremskrivning"]["mellem (RCP4,5)"]
    assert d["kyst"]["kystkode"] == "LF1"
    storm = {i["indikator"]: i for i in d["kyst"]["indikatorer"]}["Stormflod, 100-årshændelse"]
    assert 100 < storm["reference_1981_2010"]["median"] < 250


async def test_oversvoemmelse_havnefront_og_ucn():
    # Havnefronten i Aalborg (terræn ca. 1-3 m): oversvømmes ved ca. 1,4 m og rammes af 100-årsstormfloden.
    havn = await _call("oversvoemmelse", {"x": 555882, "y": 6323400, "radius_m": 0})
    hv = havn["havvand"]
    assert 0.5 < hv["oversvoemmes_ved_havniveau_m"] < 3, havn.get("noter")
    assert any(s["haendelse"] == "100-årsstormflod" for s in hv["stormflod_der_naar_stedet"])
    # UCN i kote ca. 20 m: ingen gyldig tærskel (kode 300 filtreres fra)
    ucn = await _call("oversvoemmelse", {**UCN, "radius_m": 0})
    assert ucn["havvand"]["oversvoemmes_ved_havniveau_m"] is None
    assert ucn["havvand"]["punkter_uden_forbindelse_til_havet"] == 1


@pytest.mark.skipif(not load_config().emo_brugernavn, reason="Kræver EMO_BRUGERNAVN/EMO_ADGANGSKODE")
async def test_energimaerke():
    d = await _call("energimaerke", {"adresse": "Fjelstrupvej 77, 6100 Haderslev"})
    assert d["antal_maerker"] >= 1 and d["gaeldende"]["klasse"]

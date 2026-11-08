"""Live-test af M5 (klima, sol, energi, LCA, BIM). Kør: uv run pytest -m live"""

import json

import pytest
from mcp import Client

from byg_mcp.server import mcp

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


async def _call(tool: str, args: dict) -> dict:
    async with Client(mcp) as c:
        res = await c.call_tool(tool, args)
    if res.is_error and "overbelastet" in res.content[0].text:
        pytest.skip(f"Kilden er midlertidigt overbelastet: {res.content[0].text[:120]}")
    assert not res.is_error, res.content
    return res.structured_content or json.loads(res.content[0].text)


async def test_klima_data_aalborg():
    d = await _call("klima_data", {"x": 555882, "y": 6323238, "antal_aar": 5})
    assert d["kommunekode"] == "0851"
    p = d["parametre"]
    assert 6 < p["Middeltemperatur"]["vaerdi"] < 12 and 400 < p["Årsnedbør"]["vaerdi"] < 1200
    assert "Største 30-min. nedbør" in p


async def test_sol_og_pv_optimal():
    d = await _call("sol_og_pv", {"x": 555882, "y": 6323238})
    assert d["anlaeg"]["haeldning_optimal"] and 850 < d["aarsproduktion_kwh_pr_kwp"] < 1200
    assert len(d["maanedlig_produktion_kwh"]) == 12


async def test_vejrfil_link_uden_download():
    d = await _call("vejrfil", {"x": 724380, "y": 6175700, "gem_lokalt": False})
    assert d["download_url"].startswith("https://re.jrc.ec.europa.eu/api/v5_3/tmy?") and "lokal_fil" not in d


async def test_el_co2_prisomraade_og_br18():
    d = await _call("el_co2", {"x": 724380, "y": 6175700})
    assert d["energinet_aktuelt"]["prisomraade"] == "DK2"
    assert d["br18_tabel_8_1"]["dette_aar"]["el"] > 0


async def test_lca_materiale_begge_kilder():
    d = await _call("lca_materiale", {"materiale": "gipsplade", "kilde": "begge", "maks_resultater": 3})
    assert d["br18_generiske_data"][0]["gwp_a1_a3"] > 0
    assert isinstance(d["oekobaudat"], list)


async def test_bim_cci_og_br18_ordbog():
    cci = await _call("bim_klassifikation", {"begreb": "window", "ordbog": "cci", "maks_resultater": 3})
    assert any(r.get("kode", "").startswith("L-") for r in cci["resultater"])
    br = await _call("bim_klassifikation", {"begreb": "ydervæg", "ordbog": "br18", "maks_resultater": 5})
    assert all(r["ordbog"] == "Tabel6" for r in br["resultater"])

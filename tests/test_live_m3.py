"""Live-test af M3 (terræn, geologi, kort, grundrapport). Kræver net og nøgler. Kør: uv run pytest -m live"""

import json

import pytest
from mcp import Client

from byg_mcp.infra.config import load_config
from byg_mcp.server import mcp

cfg = load_config()
pytestmark = [
    pytest.mark.live,
    pytest.mark.asyncio,
    pytest.mark.skipif(not (cfg.datafordeler_api_key and cfg.dataforsyningen_token), reason="nøgler mangler i .env"),
]


async def _call(tool: str, args: dict) -> dict:
    async with Client(mcp) as c:
        res = await c.call_tool(tool, args)
    assert not res.is_error, res.content
    return res.structured_content or json.loads(res.content[0].text)


async def test_terraen_paa_matrikel():
    d = await _call("terraen", {"adresse": "Bispensgade 3, 9000 Aalborg"})
    assert d["grund"]["grundlag"] == "matrikelgrænse"
    assert 1.5 < d["kote_i_punktet_m"] < 5  # havnenært, ca. 2,8 m DVR90
    assert d["omgivelser"]["maks_hoejde_over_terraen_m"] > 10  # bymidte


async def test_jord_geologi_loekken():
    d = await _call("jord_geologi", {"adresse": "Klitvej 10, 9480 Løkken"})
    assert d["jordart"]["jordartskort_25000"]["symbol"] == "HS"
    assert isinstance(d["boringer"], list) and d["boringer"][0]["borerapport"].startswith("https://data.geus.dk")
    assert "dybde_vinter_m" in d["terraennaert_grundvand"]


async def test_kort_udsnit_giver_billede():
    async with Client(mcp) as c:
        res = await c.call_tool("kort_udsnit", {"x": 555882, "y": 6323238, "side_m": 100})
    assert not res.is_error
    assert res.content[0].type == "image" and len(res.content[0].data) > 10_000
    assert "skraafoto" in json.loads(res.content[1].text)


async def test_grundrapport_snekkersten():
    d = await _call("grundrapport", {"adresse": "Strandvejen 200A, 3070 Snekkersten"})
    assert d["ejendom"]["bfe_nummer"] == 9177831
    assert any(o.get("bebygpct") == 30 for o in d["plangrundlag"]["lokalplan_delomraader"])
    assert "strandbeskyttelse" in json.dumps(d["restriktioner"]["matrikelnoteringer"])
    assert d["terraen"]["grund"]["hoejdeforskel_m"] > 3
    assert d["bygninger"]["antal"] >= 1
    assert not any(isinstance(v, dict) and "fejl" in v for v in d.values())


async def test_grundscreening_prompt():
    async with Client(mcp) as c:
        p = await c.get_prompt("grundscreening", {"adresse": "Bispensgade 3, 9000 Aalborg"})
    assert "grundrapport" in p.messages[0].content.text

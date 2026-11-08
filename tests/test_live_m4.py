"""Live-test af M4 (Retsinformation). Kør: uv run pytest -m live"""

import json

import pytest
from mcp import Client

from byg_mcp.server import mcp

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


async def _call(tool: str, args: dict) -> dict:
    async with Client(mcp) as c:
        res = await c.call_tool(tool, args)
    assert not res.is_error, res.content
    return res.structured_content or json.loads(res.content[0].text)


async def test_lov_paragraf_planloven():
    d = await _call("lov_paragraf", {"lov": "planloven", "paragraf": "15"})
    assert d["lov"]["populaertitel"] == "Planloven"
    assert "Lokalplan" in d["kapitel"] and "lokalplan" in d["tekst"].lower()


async def test_lov_paragraf_naturbeskyttelse_soebeskyttelse():
    d = await _call("lov_paragraf", {"lov": "naturbeskyttelsesloven", "paragraf": "16"})
    assert "150 m" in d["tekst"]


async def test_br18_omdirigeres_til_konsolideret_tekst():
    d = await _call("lov_paragraf", {"lov": "br18", "paragraf": "298"})
    assert "omdirigeret" in d and "CO2" in d["paragraffer"][0]["tekst"]


async def test_lov_soeg():
    d = await _call("lov_soeg", {"tekst": "byggeloven", "maks_resultater": 3})
    assert any("byggelov" in (r.get("titel", "") + r.get("populaertitel", "")).lower() for r in d["resultater"])


async def test_br18_ressource():
    async with Client(mcp) as c:
        r = await c.read_resource("br18://paragraf/58")
    assert "værn" in r.contents[0].text.lower()

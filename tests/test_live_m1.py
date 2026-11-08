"""Live-test af M1 (ejendomskæde og BBR). Kræver net og nøgler i .env. Kør: uv run pytest -m live

Testadresser er valgt 8/11-2026 og kan ændre sig, hvis registrene opdateres.
"""

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


async def test_adresse_til_ejendom():
    d = await _call("sted_find", {"adresse": "Bispensgade 3, 9000 Aalborg"})
    assert d["match"] == "eksakt"
    e = d["valgt"]["ejendom"]
    assert e["bfe_nummer"] == 5539730
    assert e["jordstykker"][0]["betegnelse"] == "220, Aalborg Bygrunde"
    assert e["grundareal_registreret_m2"] == 608


async def test_matrikel_til_ejendom():
    d = await _call("sted_find", {"matrikel": "220, Aalborg Bygrunde"})
    assert d["valgt"]["ejendom"]["bfe_nummer"] == 5539730


async def test_koordinat_til_ejendom():
    d = await _call("sted_find", {"x": 555882.14, "y": 6323238.25})
    assert d["valgt"]["ejendom"]["bfe_nummer"] == 5539730


async def test_bfe_til_ejendom():
    d = await _call("sted_find", {"bfe_nummer": 5539730})
    assert d["valgt"]["ejendom"]["jordstykker"][0]["matrikelnummer"] == "220"
    assert 555_800 < d["valgt"]["x"] < 555_950


async def test_flere_jordstykker_og_strandbeskyttelse():
    d = await _call("sted_find", {"adresse": "Strandvejen 200A, 3070 Snekkersten"})
    e = d["valgt"]["ejendom"]
    assert len(e["jordstykker"]) >= 2
    assert any("strandbeskyttelse" in (j.get("noteringer") or {}) for j in e["jordstykker"])


async def test_usikkert_match_markeres():
    d = await _call("sted_find", {"adresse": "Nørre Allé 1, 8000 Aarhus C"})
    assert d["match"] == "usikkert" and "advarsel" in d


async def test_bbr_bygninger_oversat():
    d = await _call("bygning_bbr", {"adresse": "Bispensgade 3, 9000 Aalborg", "med_etager": True})
    assert d["antal_bygninger"] >= 1
    b = next(b for b in d["bygninger"] if b["anvendelse"]["kode"] == "140")
    assert b["anvendelse"]["tekst"].startswith("Etagebolig")
    assert b["opfoerelsesaar"] == 2023
    assert b["status"]["tekst"] == "Opført"
    assert "etager" in b
    assert "bebyggelsesprocent_indikator" in d["noegletal"]


async def test_fredet_bygning():
    d = await _call("bygning_bbr", {"adresse": "Rådhuspladsen 1, 1550 København V"})
    assert any("fredet" in (b.get("fredning") or {}).get("tekst", "").lower() for b in d["bygninger"])


async def test_lokalplan_laes_emne():
    d = await _call("plan_laes_lokalplan", {"planid": 11020307, "emne": "hoejde"})
    assert d["plan"]["plannr"] == "1-1-143" and d["format"] == "digital"
    afsnit5 = next(b for b in d["bestemmelser"] if b["nr"] == "5")
    assert "5.4 Højder" in afsnit5["underpunkter"]
    assert len(d["oversigt"]) == 15


async def test_lokalplan_afviser_fremmed_domaene():
    async with Client(mcp) as c:
        res = await c.call_tool("plan_laes_lokalplan", {"doklink": "https://example.com/x.pdf"})
    assert res.is_error and "dokument.plandata.dk" in res.content[0].text

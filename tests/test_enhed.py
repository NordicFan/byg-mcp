"""Enhedstests uden netadgang. Kør: uv run pytest -m "not live" """

import logging

from byg_mcp.domain.bygning import kodelister, noegletal
from byg_mcp.infra.cache import SQLiteCache
from byg_mcp.infra.logging import maskér, sikr_logning
from byg_mcp.server import _match_kvalitet


def test_match_eksakt_og_usikkert():
    assert _match_kvalitet("Bispensgade 3, 9000 Aalborg", "Bispensgade 3, 9000 Aalborg") == "eksakt"
    assert _match_kvalitet("bispensgade 3 aalborg", "Bispensgade 3, 9000 Aalborg") == "eksakt"
    # gsearch returnerer nærmeste, når den søgte ikke findes
    assert _match_kvalitet("Nørre Allé 1, 8000 Aarhus C", "Nørre Allé 11, 8000 Aarhus C") == "usikkert"
    assert _match_kvalitet("Hovedgaden 1, 4000 Roskilde", "Hovedgaden 10A, Gundsømagle, 4000 Roskilde") == "usikkert"
    assert _match_kvalitet("220, Aalborg Bygrunde", "220, Aalborg Bygrunde") == "eksakt"


def test_maskering_af_hemmeligheder():
    url = "https://x.dk/a?q=1&apiKey=HEMMELIG123&token=abc&limit=5"
    assert "HEMMELIG123" not in maskér(url) and "abc" not in maskér(url)
    assert "apiKey=***" in maskér(url) and "limit=5" in maskér(url)


def test_httpx_logger_er_daempet_og_maskeret(caplog):
    sikr_logning()
    assert logging.getLogger("httpx").level >= logging.WARNING
    with caplog.at_level(logging.WARNING, logger="httpx"):
        logging.getLogger("httpx").warning("GET https://x.dk?apiKey=HEMMELIG")
    assert "HEMMELIG" not in caplog.text


def test_sqlite_cache(tmp_path):
    c = SQLiteCache(tmp_path / "c.sqlite")
    c.set("k", {"æ": [1, 2]}, ttl=60)
    assert c.get("k") == {"æ": [1, 2]}
    c.set("udloebet", 1, ttl=-1)
    assert c.get("udloebet") is None
    assert c.get("findes_ikke") is None


def test_kodelister_indlaest():
    kl = kodelister()
    assert kl["BygAnvendelse"]["140"].startswith("Etagebolig")
    assert kl["Livscyklus"]["6"] == "Opført"
    assert all(len(k) <= 6 for liste in kl.values() if isinstance(liste, dict) for k in liste)


def test_noegletal():
    n = noegletal({"samlet_bygningsareal_m2": 300, "samlet_bebygget_areal_m2": 150}, 1000, 0)
    assert n["bebyggelsesprocent_indikator"] == 30.0 and n["bebygget_andel_af_grund_pct"] == 15.0
    assert noegletal({"samlet_bygningsareal_m2": 1, "samlet_bebygget_areal_m2": 1}, 0) == {}


# --- Lokalplan-parser (M2) ---
from byg_mcp.domain.lokalplan import filtrer, parse_bestemmelser  # noqa: E402

_DIGITAL = [
    "Indhold\nBestemmelser\n1. Formål\n2. Anvendelse\n3. Bebyggelsens omfang\n4. Parkering",  # indholdsfortegnelse
    "1. Formål\n1.1 Formål\nAt sikre boliger.\nLokalplan 9-9-999Vedtaget\nSide 12",
    "2. Anvendelse\n2.1 Anvendelse\nOmrådet må kun anvendes til boliger.",
    "3. Bebyggelsens omfang\n3.1 Bebyggelsesprocent\nMaks. 40.\n3.2 Højder\nBebyggelse må opføres i maks. 3 etager.",
    "4. Parkering\n4.1 Bilparkering\n1 p-plads pr. bolig.\nVedtagelsespåtegning\nByrådet vedtog …",
]
_PARAGRAF = [
    "§ 1. Formål\nAt sikre boliger og stueetager.",
    "§ 2. Anvendelse\nStk. 1\nKun boliger.",
    "§ 3. Bebyggelsens omfang\nStk. 1\nBebyggelsesprocenten må ikke overstige 30.\nStk. 2\nMaks. 8,5 m højde.",
]


def test_parser_digital_springer_indholdsfortegnelse_over():
    fmt, b = parse_bestemmelser(_DIGITAL)
    assert fmt == "digital" and [x.nr for x in b] == ["1", "2", "3", "4"]
    assert b[0].side == 2  # ikke indholdsfortegnelsen på side 1
    assert "Side 12" not in b[0].tekst and "Vedtaget" not in b[0].tekst  # sidefod fjernet
    assert b[2].underpunkter == ["3.1 Bebyggelsesprocent", "3.2 Højder"]
    assert "Vedtagelsespåtegning" not in b[3].tekst


def test_parser_paragraf_format():
    fmt, b = parse_bestemmelser(_PARAGRAF)
    assert fmt == "paragraf" and len(b) == 3
    assert b[2].underpunkter == ["Stk. 1", "Stk. 2"]


def test_emnefilter_paa_underpunkt_og_ordstart():
    _, b = parse_bestemmelser(_DIGITAL)
    h = filtrer(b, "hoejde")
    assert [(x.nr, x.underpunkter) for x in h] == [("3", ["3.2 Højder"])]
    assert [x.nr for x in filtrer(b, "parkering")] == ["4"]
    _, p = parse_bestemmelser(_PARAGRAF)
    assert "1" not in [x.nr for x in filtrer(p, "hoejde")]  # 'stueetager' må ikke ramme 'etager'


# --- Terrænanalyse (M3) med syntetisk højdemodel ---
import asyncio  # noqa: E402

import numpy as np  # noqa: E402

from byg_mcp.adapters.miljoe import StoejAdapter  # noqa: E402
from byg_mcp.domain import terraen as terraen_domain  # noqa: E402


class _FakeDHM:
    """Terræn: skråplan med 10 % stigning mod øst. Overflade: 6 m højere i en 'bygning' midt på grunden."""

    async def raster(self, coverage, bbox, maks_px=600):
        x0, y0, x1, y1 = bbox
        n = 200
        xs = x0 + (np.arange(n) + 0.5) * (x1 - x0) / n
        ys = y1 - (np.arange(n) + 0.5) * (y1 - y0) / n
        X, Y = np.meshgrid(xs, ys)
        dtm = 10 + 0.10 * (X - x0)
        if coverage == "dhm_overflade":
            bygning = (abs(X - 600000) < 5) & (abs(Y - 6200000) < 5)
            return dtm + np.where(bygning, 6.0, 0.0)
        return dtm


def test_terraen_analyse_skraaplan():
    grund = "POLYGON((599980 6199980, 600020 6199980, 600020 6200020, 599980 6200020, 599980 6199980))"
    r = asyncio.run(terraen_domain.analyse(_FakeDHM(), 600000, 6200000, grund, omgivelser_m=10))
    g = r["grund"]
    assert abs(g["middel_haeldning_pct"] - 10) < 0.5
    assert abs(g["hoejdeforskel_m"] - 4.0) < 0.3  # 40 m bred grund x 10 %
    assert abs(g["maks_hoejde_over_terraen_m"] - 6.0) < 0.01
    assert g["grundlag"] == "matrikelgrænse"


def test_stoejbaand_fra_forskellige_felter():
    b = StoejAdapter._baand
    assert b({"db_low": "70", "db_high": "74"}) == (70, "70-74 dB")
    assert b({"lden_min": 55, "lden_max": 60})[1] == "55-60 dB"
    assert b({"noise_in": 4})[1].startswith("60-64 dB")
    assert b({"noise_in": 1})[1].startswith("75+ dB")
    assert b({"noise_in": 0}) is None


# --- BR18-vidensbase (M4) ---
import re as _re  # noqa: E402
import xml.etree.ElementTree as _ET  # noqa: E402

from byg_mcp.adapters.retsinformation import RetsinformationAdapter  # noqa: E402
from byg_mcp.domain import vidensbase as vb  # noqa: E402


def test_br18_daekning_og_tekstkvalitet():
    nrs = {int(_re.match(r"\d+", p["nr"]).group(0)) for p in vb.poster() if p["type"] == "paragraf"}
    assert len(nrs) >= 560 and max(nrs) == 565
    alt = "\n".join(p["tekst"] for p in vb.poster())
    assert "V arme" not in alt and "ener giforbrug" not in alt  # ord delt over <span>-elementer
    assert "\xa0" not in alt and "​" not in alt
    assert vb.meta()["version"].startswith("BR18")


def test_br18_soeg_finder_relevante_paragraffer():
    assert vb.soeg("værn højde altan", maks=3)[0]["nr"] == "58"
    assert vb.soeg("radon")[0]["nr"] == "332"
    assert "298" in [h["nr"] for h in vb.soeg("grænseværdi klimapåvirkning", maks=5)]
    assert "298" in [h["nr"] for h in vb.soeg("LCA", maks=8)]  # synonym → klimapåvirkning


def test_br18_paragraf_spec():
    assert [p["nr"] for p in vb.paragraffer("251-256")] == ["251", "252", "253", "254", "255", "256"]
    assert [p["nr"] for p in vb.paragraffer("§§ 297 og 298")] == ["297", "298"]
    assert vb.paragraffer("6a")[0]["nr"] == "6a"
    assert vb.paragraffer("Bilag 2") and vb.paragraffer("999") == []
    assert "1,9 for el" in vb.paragraffer("252")[0]["tekst"]


def test_retsinformation_tekstudtraek():
    xml = """<Paragraf localId="16"><Explicatus>§ 16.</Explicatus>
    <Stk><Exitus><Linea><Char>Arbejder må ikke påbegyndes</Char></Linea><Linea><Char>uden tilladelse.</Char></Linea></Exitus></Stk>
    <Stk><Explicatus>Stk. 2.</Explicatus><Exitus><Linea><Char>Ansøgning sker digitalt.</Char></Linea></Exitus></Stk></Paragraf>"""
    t = RetsinformationAdapter._tekst(_ET.fromstring(xml))
    assert t == "Arbejder må ikke påbegyndes uden tilladelse.\nStk. 2. Ansøgning sker digitalt."


# --- LCA og energi (M5) ---
from byg_mcp.domain import lca as lca_domain  # noqa: E402
from byg_mcp.server import _prisomraade  # noqa: E402


def test_br18_tabel7_indlaest_og_soegning():
    d = lca_domain.data()
    assert len(d["tabel7"]) > 400 and d["tabel81"]["2025"]["el"] > 0
    beton = lca_domain.soeg_tabel7("beton c25", 3)
    assert beton and "C25/30" in beton[0]["navn"] and beton[0]["deklareret_enhed"] == "m³"
    assert lca_domain.soeg_tabel7("gipsplade", 3)[0]["navn"].startswith("Gipsplade")
    assert all(r["datatype"] == "Standardværdi" for r in lca_domain.soeg_tabel7("etageboliger", 5, datatype="standard"))


def test_emissionsfaktorer():
    assert lca_domain.emissionsfaktor(2025)["el"] == 0.0801
    assert "note" in lca_domain.emissionsfaktor(2099)
    m = lca_domain.b6_middel(2026)
    assert 0 < m["el"] < lca_domain.emissionsfaktor(2026)["el"]  # faldende fremskrivning → lavere middel


def test_prisomraade():
    assert _prisomraade(9.92, 555882) == "DK1"   # Aalborg
    assert _prisomraade(10.39, 590000) == "DK1"  # Odense
    assert _prisomraade(12.57, 724380) == "DK2"  # København
    assert _prisomraade(14.9, 870000) == "DK2"   # Bornholm


# --- BR-vejledninger (M4b) ---
import importlib.util as _ilu  # noqa: E402
import pathlib as _pl  # noqa: E402

_spec = _ilu.spec_from_file_location("indsaml_vejledninger", _pl.Path(__file__).parents[1] / "scripts" / "indsaml_vejledninger.py")


def _vejl_script():
    import sys as _sys

    _sys.path.insert(0, str(_pl.Path(__file__).parents[1] / "scripts"))
    m = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(m)
    return m


def test_vejledning_rens_versioner_og_dubletter():
    m = _vejl_script()
    p = lambda titel, tekst, kilde="pdf": {"kapitel": "5", "titel": titel, "kilde": kilde, "url": "u", "pdf_url": titel, "tekst": tekst}  # noqa: E731
    alle = [
        p("Bilag 2: Etageboliger version 1.4", "ny tekst"),
        p("Bilag 2: Etageboliger version 1.4 med ændringsmarkeringer", "markeret tekst"),
        p("Bilag 2: Etageboliger version 1.1", "gammel tekst"),
        p("Bilag 8 version 1.1 med ændringsmarkeringer", "x"),
        p("Bilag 8 version 1.2", "bilag 8 ny"),
        p("Side A", "Samme  tekst", "html"),
        p("Side B", "samme tekst", "html"),
    ]
    tekster = [x["tekst"] for x in m.rens(alle)]
    assert tekster == ["ny tekst", "bilag 8 ny", "Samme  tekst"]


def test_vejledninger_indsamlet_og_soegbare():
    vj = vb.vejledninger()
    if not vj:
        import pytest

        pytest.skip("Vejledninger ikke indsamlet")
    assert len(vj) > 1000 and vb.vejledning_meta()["antal_pdf"] > 50
    assert not any("ændringsmarkering" in v["titel"].lower() for v in vj if v["kilde"] == "pdf")
    hits = vb.soeg_vejledninger("redningsåbning", maks=5)
    assert hits and any("Præ-accepterede" in h["dokument"] for h in hits)
    h = vb.hent_vejledning(hits[0]["id"], 1)
    assert "redningsåbning" in h["tekst"].lower() and len(h["stykker"]) >= 2

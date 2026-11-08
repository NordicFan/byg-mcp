"""BR18-vidensbase: paragraffer og bilag fra data/br18.jsonl, søgbare med SQLite FTS5 i hukommelsen.

Data bygges med scripts/indsaml_br18.py. Indekset bygges ved første opslag (~0,1 sek.).
"""

from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from importlib import resources
from typing import Any

# Synonymer og fagudtryk → ord, der faktisk står i BR18. Udvider søgningen (OR), erstatter den ikke.
SYNONYMER: dict[str, list[str]] = {
    "lca": ["klimapåvirkning", "livscyklusvurdering"],
    "co2": ["klimapåvirkning", "co2-ækvivalenter"],
    "u-værdi": ["transmissionskoefficient", "varmetab"],
    "uværdi": ["transmissionskoefficient", "varmetab"],
    "isolering": ["varmetab", "transmissionskoefficient"],
    "flugtvej": ["flugtveje", "redningsåbning"],
    "handicap": ["tilgængelighed", "niveaufri"],
    "tilgængelighed": ["niveaufri", "kørestolsbrugere"],
    "dagslys": ["dagslys", "glasareal"],
    "lyd": ["lydforhold", "lydisolation", "efterklangstid"],
    "støj": ["lydforhold", "støjbelastning"],
    "radon": ["radon"],
    "ventilation": ["ventilation", "luftskifte"],
    "trapper": ["trapper", "trappe"],
    "værn": ["værn", "rækværk"],
    "brandsikring": ["brand", "brandklasse"],
    "statik": ["konstruktioner", "konstruktionsklasse"],
    "energiramme": ["energiramme", "energibehov"],
    "overophedning": ["termisk indeklima", "temperatur"],
    "højde": ["højde", "højdegrænseplan"],
    "afstand": ["afstand", "skel"],
}


@lru_cache(maxsize=1)
def meta() -> dict[str, Any]:
    return json.loads(resources.files("byg_mcp.data").joinpath("br18_meta.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def poster() -> list[dict[str, Any]]:
    tekst = resources.files("byg_mcp.data").joinpath("br18.jsonl").read_text(encoding="utf-8")
    return [json.loads(l) for l in tekst.splitlines() if l.strip()]


@lru_cache(maxsize=1)
def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute(
        "CREATE VIRTUAL TABLE br USING fts5(nr UNINDEXED, idx UNINDEXED, kapitel_titel, afsnit, tekst, "
        "tokenize='unicode61 remove_diacritics 0')"
    )
    db.executemany(
        "INSERT INTO br (nr, idx, kapitel_titel, afsnit, tekst) VALUES (?, ?, ?, ?, ?)",
        [(p["nr"], i, p["kapitel_titel"], p["afsnit"], p["tekst"]) for i, p in enumerate(poster())],
    )
    return db


def _fts_query(tekst: str, operator: str) -> str:
    ord_ = [w for w in re.findall(r"[0-9a-zæøåé]+", tekst.lower()) if len(w) > 1]
    led = []
    for w in ord_:
        varianter = {w, *SYNONYMER.get(w, [])}
        led.append("(" + " OR ".join(f'"{v}"*' if " " not in v else f'"{v}"' for v in varianter) + ")")
    return f" {operator} ".join(led)


def soeg(tekst: str, kapitel: str | None = None, maks: int = 8) -> list[dict[str, Any]]:
    """Fuldtekstsøgning med præfiks-match og synonymer. Prøver AND først, derefter OR."""
    db = _db()
    for op in ("AND", "OR"):
        q = _fts_query(tekst, op)
        if not q:
            return []
        rows = db.execute(
            "SELECT idx, snippet(br, 4, '«', '»', ' … ', 24), bm25(br, 0, 0, 0.3, 5.0, 1.0) AS score "
            "FROM br WHERE br MATCH ? ORDER BY score LIMIT ?",
            (q, maks * 4),
        ).fetchall()
        hits = []
        for idx, uddrag, score in rows:
            p = poster()[idx]
            if kapitel and str(p["kapitel"]).lower() != str(kapitel).lstrip("0").lower():
                continue
            hits.append({
                "nr": p["nr"] if p["type"] == "paragraf" else p["nr"],
                "type": p["type"],
                "kapitel": f"{p['kapitel']}. {p['kapitel_titel']}",
                "afsnit": p["afsnit"],
                "uddrag": uddrag,
                "url": p["url"],
            })
            if len(hits) >= maks:
                break
        if hits:
            for h in hits:
                h["soegemetode"] = "alle ord" if op == "AND" else "mindst ét ord"
            return hits
    return []


def _nr_noegle(nr: str) -> tuple[int, str]:
    m = re.match(r"(\d+)\s*([a-z]?)", nr.lower())
    return (int(m.group(1)), m.group(2)) if m else (10**6, nr)


def paragraffer(spec: str) -> list[dict[str, Any]]:
    """Hent paragraffer ud fra '251', '251a', '251-256', '§§ 297 og 298' eller 'Bilag 2'."""
    spec = spec.strip()
    if spec.lower().startswith("bilag"):
        n = re.search(r"\d+", spec)
        return [p for p in poster() if p["type"] == "bilag" and n and p["nr"] == f"Bilag {n.group(0)}"]
    valgte: list[dict[str, Any]] = []
    for del_ in re.split(r",|\bog\b", spec.replace("§", "")):
        del_ = del_.strip()
        if not del_:
            continue
        if m := re.fullmatch(r"(\d+\s*[a-z]?)\s*-\s*(\d+\s*[a-z]?)", del_):
            lo, hi = _nr_noegle(m.group(1)), _nr_noegle(m.group(2))
            valgte += [p for p in poster() if p["type"] == "paragraf" and lo <= _nr_noegle(p["nr"]) <= hi]
        else:
            n = del_.replace(" ", "").lower()
            valgte += [p for p in poster() if p["type"] == "paragraf" and p["nr"].lower() == n]
    set_: set[int] = set()
    return [p for p in valgte if not (id(p) in set_ or set_.add(id(p)))]


def kapitel_oversigt(kapitel: str) -> dict[str, Any]:
    k = str(kapitel).lstrip("0").upper()
    ps = [p for p in poster() if str(p["kapitel"]).upper() == k]
    if not ps:
        return {}
    afsnit: dict[str, list[str]] = {}
    for p in ps:
        afsnit.setdefault(p["afsnit"], []).append(p["nr"])
    return {
        "kapitel": f"{k}. {ps[0]['kapitel_titel']}",
        "afsnit": [{"overskrift": a, "paragraffer": nrs} for a, nrs in afsnit.items()],
    }


def kapitler() -> list[str]:
    set_: dict[str, str] = {}
    for p in poster():
        set_.setdefault(str(p["kapitel"]), p["kapitel_titel"])
    return [f"{k}. {v}" for k, v in set_.items()]

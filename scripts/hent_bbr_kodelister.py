"""Henter udvalgte BBR-kodelister fra teknik.bbr.dk og gemmer dem som JSON i pakken.
Kør: uv run python scripts/hent_bbr_kodelister.py"""
import html
import json
import re
from datetime import date
from pathlib import Path

import httpx

LISTER = [
    "BygAnvendelse", "EnhAnvendelse", "Livscyklus", "YdervaeggenesMateriale", "Tagdaekningsmateriale",
    "BygVarmeinstallation", "Opvarmningsmiddel", "BygSupplerendeVarme", "Fredning", "BygVandforsyning",
    "BygAfloebsforhold", "AsbestholdigtMateriale", "Konstruktionsforhold", "EtageType", "Gulvbelaegning",
    "KildeTilOplysninger", "Energiforsyning", "Boligtype", "AfvigendeEtager",
]
URL = "https://teknik.bbr.dk/kodelister/0/1/0/{}"
UD = Path(__file__).resolve().parents[1] / "src" / "byg_mcp" / "data" / "bbr_kodelister.json"


def hent(navn: str, client: httpx.Client) -> dict[str, str]:
    t = client.get(URL.format(navn)).text
    out = {}
    for li in re.findall(r"<li[^>]*>(.*?)</li>", t, re.S):
        tekst = html.unescape(re.sub(r"<[^>]+>", "", li)).strip()
        if m := re.match(r"^([0-9A-Za-z]{1,6}) - (.+)$", tekst):
            out[m.group(1)] = m.group(2).strip()
    return out


def main() -> None:
    data = {"_kilde": "https://teknik.bbr.dk/kodelister", "_hentet": date.today().isoformat()}
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for navn in LISTER:
            data[navn] = hent(navn, c)
            print(f"{navn}: {len(data[navn])} koder")
    UD.parent.mkdir(parents=True, exist_ok=True)
    UD.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Gemt:", UD)


if __name__ == "__main__":
    main()

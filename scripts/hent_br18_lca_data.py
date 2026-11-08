"""Henter BR18 bilag 2, tabel 7 (generisk LCA-datagrundlag), 8.1 (emissionsfaktorer for energi) og
8.2 (brændstof) som Excel fra bygningsreglementet.dk og gemmer dem som JSON i pakken.

Kør:  uv run python scripts/hent_br18_lca_data.py
Linkene til Excel-filerne findes automatisk på bilag 2-siden (de skifter navn ved nye versioner).
"""

from __future__ import annotations

import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx
import openpyxl

SIDE = "https://www.bygningsreglementet.dk/bilag/b2/bilag_2/?Layout=ShowAll"
UD = Path(__file__).resolve().parents[1] / "src" / "byg_mcp" / "data" / "br18_lca.json"


def rows(data: bytes) -> list[tuple]:
    ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


def tal(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "byg-mcp/0.1"}) as c:
        html = c.get(SIDE).text
        links = sorted(set(re.findall(r'href="(/media/[^"]+\.xlsx)"', html)))
        print("Excel-filer:", links)

        def find(moenster: str) -> str:
            hit = [l for l in links if re.search(moenster, l)]
            if not hit:
                raise SystemExit(f"Fandt ikke {moenster} på bilag 2-siden")
            return "https://www.bygningsreglementet.dk" + hit[0]

        u7, u81, u82 = find(r"tabel-7"), find(r"tabel-81"), find(r"tabel-82")
        r7, r81, r82 = (rows(c.get(u).content) for u in (u7, u81, u82))

    hoved = [str(h).strip() if h else "" for h in r7[0]]
    idx = {h: i for i, h in enumerate(hoved)}

    def col(r, navn):
        return r[idx[navn]] if navn in idx and idx[navn] < len(r) else None

    tabel7 = []
    for r in r7[1:]:
        if not col(r, "Sorterings ID"):
            continue
        tabel7.append({k: v for k, v in {
            "id": col(r, "Sorterings ID"),
            "datatype": col(r, "Data type"),
            "navn": col(r, "Navn DK"),
            "navn_de_en": None if col(r, "Navn DE/ENG") in (None, "-") else col(r, "Navn DE/ENG"),
            "gwp_a1_a3": tal(col(r, "Global Opvarmning, modul A1-A3")),
            "gwp_c3": tal(col(r, "Global Opvarmning, modul C3")),
            "gwp_c4": tal(col(r, "Global Opvarmning, modul C4")),
            "gwp_d": tal(col(r, "Global Opvarmning, modul D")),
            "deklareret_faktor": tal(col(r, "Deklareret faktor (FU)")),
            "deklareret_enhed": col(r, "Deklareret enhed (FU)"),
            "masse_faktor": tal(col(r, "Masse faktor")),
            "masse_enhed": col(r, "Masse enhed"),
            "kilde_url": col(r, "Url (link)"),
            "kommentar": col(r, "Kommentar"),
        }.items() if v not in (None, "")})

    tabel81 = {}
    for r in r81:
        if isinstance(r[0], (int, float)) and 2000 < r[0] < 2200:
            tabel81[str(int(r[0]))] = {"el": tal(r[1]), "fjernvarme": tal(r[2]), "ledningsgas": tal(r[3])}

    tabel82 = []
    for r in r82[2:]:
        if r[0] and tal(r[1]) is not None:
            tabel82.append({"braendstof": str(r[0]).strip(), "gwp": tal(r[1]), "enhed": r[2], "gwp2": tal(r[3]), "enhed2": r[4]})

    data = {
        "_kilde": "BR18 bilag 2, tabel 7, 8.1 og 8.2 (bygningsreglementet.dk)",
        "_filer": [u7, u81, u82],
        "_hentet": date.today().isoformat(),
        "_enheder": "GWP i kg CO2e pr. deklareret enhed. Tabel 8.1 i kg CO2e/kWh.",
        "tabel7": tabel7,
        "tabel81": tabel81,
        "tabel82": tabel82,
    }
    UD.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tabel 7: {len(tabel7)} datasæt, tabel 8.1: {len(tabel81)} år ({min(tabel81)}-{max(tabel81)}), tabel 8.2: {len(tabel82)} brændstoffer")
    print("Gemt:", UD)


if __name__ == "__main__":
    main()

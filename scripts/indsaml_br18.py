"""Indsaml bygningsreglementet (BR18, aktuel version) fra bygningsreglementet.dk til JSONL.

Kør:  uv run python scripts/indsaml_br18.py
Output: src/byg_mcp/data/br18.jsonl (én linje pr. paragraf eller bilagsafsnit) + br18_meta.json

Struktur (verificeret 8/11-2026): forsiden linker til kapitlernes "krav"-sider. Med ?Layout=ShowAll er alle
afsnit foldet ud. Hvert afsnit (section.anchor-reference) har rækker:
  accordion__row--text           → lovtekst, én § pr. række
  accordion__row--footnote-list  → links til BR-vejledninger
  accordion__row--link           → henvisninger (standarder, anvisninger)
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

BASE = "https://www.bygningsreglementet.dk"
UD = Path(__file__).resolve().parents[1] / "src" / "byg_mcp" / "data"
UA = {"User-Agent": "byg-mcp/0.1 (forskningsprototype; indsamling af BR18 til lokal soegning)"}


def norm(t: str) -> str:
    t = t.replace("\xa0", " ").replace("​", "").replace("­", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s+([.,;:)])", r"\1", t)
    return t.strip()


_BLOK = ["p", "div", "li", "tr", "h2", "h3", "h4", "h5", "table", "ul", "ol"]


def blok_tekst(row: Tag) -> tuple[str | None, str]:
    """Returnér (paragrafnummer fra rækkens eget mærke, tekst).

    Inline-elementer (span) samles UDEN mellemrum, fordi kilden deler ord over flere spans
    (fx '<span>V</span><span>arme</span>'). Blokelementer giver linjeskift. Tabelceller adskilles med ' | '.
    """
    import copy

    row = copy.copy(row)
    tag = row.select_one(":scope > .accordion__tag")
    nr = None
    if tag:
        m = re.fullmatch(r"§ ?(\d+ ?[a-z]?)", norm(tag.get_text("", strip=True)))
        nr = m.group(1).replace(" ", "") if m else None
        tag.decompose()
    for br in row.find_all("br"):
        br.replace_with("\n")
    for td in row.find_all(["td", "th"]):
        td.insert_after(" | ")
    for el in row.find_all(_BLOK):
        el.insert_before("\n")
        el.insert_after("\n")
    raw = row.get_text("")
    linjer = [norm(l) for l in raw.split("\n")]
    linjer = [re.sub(r"\s*\|\s*$", "", l) for l in linjer if l and l != "|"]
    tekst = "\n".join(linjer)
    tekst = re.sub(r"Stk\. ?(\d+) ?\.", r"Stk. \1.", tekst)
    tekst = re.sub(r"\n(Stk\. \d+)\.?\n", r"\n\1. ", tekst)
    tekst = re.sub(r"^(\d+\))\n", r"\1 ", tekst, flags=re.M)  # '1)' alene på en linje
    return nr, tekst


def kapitel_links(client: httpx.Client) -> list[str]:
    s = BeautifulSoup(client.get(BASE + "/").text, "html.parser")
    links = []
    for a in s.select("a[href]"):
        h = a["href"]
        if re.search(r"bygningsreglementet\.dk/(administrative-bestemmelser|tekniske-bestemmelser|ovrige-bestemmelser|straf-og-ikrafttraedelse)/.*krav/$", h) or re.search(r"/bilag/b\d/bilag_\d/$", h):
            if "historisk" not in h and h not in links:
                links.append(h)
    return links


def parse_kapitel(url: str, html: str) -> list[dict]:
    s = BeautifulSoup(html, "html.parser")
    h1 = norm(s.find("h1").get_text(" ", strip=True)) if s.find("h1") else ""
    m = re.match(r"^(.*?)\s*\(§", h1)
    kap_titel = m.group(1) if m else h1
    kap_nr = (re.search(r"/(\d{2}|b\d)/", url) or re.search(r"(administrative)", url)).group(1)
    kap_nr = "1" if kap_nr == "administrative" else kap_nr.lstrip("0").upper()
    er_bilag = kap_nr.startswith("B")
    poster: list[dict] = []
    for sec in s.select("section.anchor-reference"):
        afsnit = norm(sec.select_one(".accordion__title").get_text(" ", strip=True)) if sec.select_one(".accordion__title") else ""
        anker = sec.select_one("a.accordion__trigger")
        afsnit_url = (anker["href"].split("#")[0] if anker else url)
        body = sec.select_one(".accordion__content")
        if body is None:
            continue
        seneste: dict | None = None
        bilagstekst: list[str] = []
        # Dækker afsnittet én enkelt §, står nummeret kun i overskriftsmærket ("§ 159"), ikke i teksten.
        tag = sec.select_one(".accordion__tag")
        tm = re.fullmatch(r"§ ?(\d+ ?[a-z]?)", norm(tag.get_text(" ", strip=True))) if tag else None
        enkelt_nr = tm.group(1).replace(" ", "") if tm else None
        for row in body.select(":scope > .accordion__row"):
            klasser = row.get("class") or []
            if "accordion__row--footnote-list" in klasser and seneste is not None:
                for a in row.select("a[href]"):
                    href = re.sub(r"/historisk/br18_version\d+", "", a["href"]).split("#")[0]
                    seneste.setdefault("vejledninger", []).append({"titel": norm(a.get_text(" ", strip=True)).removeprefix("Gå til "), "url": href})
            elif "accordion__row--link" in klasser and seneste is not None:
                titel = norm((row.find(["h3", "h4", "strong", "a"]) or row).get_text(" ", strip=True))[:150]
                seneste.setdefault("henvisninger", []).append(titel)
            elif "accordion__row--text" in klasser or "accordion__row--table" in klasser:
                row_nr, tekst = blok_tekst(row)
                pm = re.match(r"^§ ?(\d+\s?[a-z]?)\b\.?\s*", tekst)
                nr = row_nr or (pm.group(1).replace(" ", "") if pm else None)
                if not nr and enkelt_nr and seneste is None:
                    nr = enkelt_nr
                if nr and not er_bilag:
                    if not tekst.startswith("§"):
                        tekst = f"§ {nr}\n{tekst}"
                    seneste = {
                        "type": "paragraf", "nr": nr, "kapitel": kap_nr, "kapitel_titel": kap_titel,
                        "afsnit": afsnit, "tekst": tekst, "url": afsnit_url,
                    }
                    poster.append(seneste)
                elif seneste is not None and not er_bilag:
                    seneste["tekst"] += "\n" + tekst  # fortsættelse (fx tabel efter §-teksten)
                else:
                    bilagstekst.append(tekst)
        if er_bilag and bilagstekst:
            poster.append({
                "type": "bilag", "nr": f"Bilag {kap_nr[1:]}", "kapitel": kap_nr, "kapitel_titel": kap_titel,
                "afsnit": afsnit, "tekst": "\n".join(bilagstekst), "url": afsnit_url,
            })
    for p in poster:
        for k in ("vejledninger",):
            if k in p:  # fjern dubletter, bevar rækkefølge
                set_ = set()
                p[k] = [v for v in p[k] if not (v["url"] in set_ or set_.add(v["url"]))]
    return poster


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    alle: list[dict] = []
    with httpx.Client(timeout=60, follow_redirects=True, headers=UA) as c:
        forside = c.get(BASE + "/").text
        version = norm(BeautifulSoup(forside, "html.parser").select_one(".version-selector__current").get_text(" ", strip=True)) if "version-selector__current" in forside else "BR18"
        historiske = re.findall(r"BR18 \((\d{1,2}/\d{1,2}) ?- ?(\d{1,2}/\d{1,2}) (\d{4})\)", forside)
        for url in kapitel_links(c):
            html = c.get(url + "?Layout=ShowAll").text
            poster = parse_kapitel(url, html)
            print(f"{url.replace(BASE, ''):55s} {len(poster):4d} poster")
            alle.extend(poster)
            time.sleep(0.5)  # skån serveren
    UD.mkdir(parents=True, exist_ok=True)
    with (UD / "br18.jsonl").open("w", encoding="utf-8") as f:
        for p in alle:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    seneste_slut = f"{historiske[0][1]} {historiske[0][2]}" if historiske else None
    meta = {
        "kilde": BASE,
        "version": version,
        "hentet": date.today().isoformat(),
        "seneste_historiske_version_slutter": seneste_slut,
        "antal_paragraffer": sum(p["type"] == "paragraf" for p in alle),
        "antal_bilagsafsnit": sum(p["type"] == "bilag" for p in alle),
    }
    (UD / "br18_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()

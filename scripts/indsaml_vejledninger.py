"""Indsaml Bygningsreglementets vejledninger (HTML og PDF) fra bygningsreglementet.dk.

Kør:  uv run python scripts/indsaml_vejledninger.py            (alle kapitler, ca. 10-30 min.)
      uv run python scripts/indsaml_vejledninger.py 5 11       (udvalgte kapitler)
Output: src/byg_mcp/data/br18_vejledninger.jsonl.gz  (én linje pr. tekststykke)

Struktur (verificeret 8/11-2026):
- Hvert kapitels kravside har en "Vejledning"-fane (a.nav-tab__link), men URL-mønstret varierer
  (/vejledninger/, /brv/, /vejledning/). Derfra crawles alle undersider inden for kapitlets sti.
- Indholdet ligger ofte i accordion-sektioner, der hentes via data-href="...?ajax=1".
- Mange vejledninger (fx brandbilag med præ-accepterede løsninger) er PDF'er under /media/.
  Står samme dokument i flere versioner, er den nyeste først. Vi tager første forekomst pr. titel.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
import sys
import time
from collections import deque
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indsaml_br18 import blok_tekst, norm  # noqa: E402

BASE = "https://www.bygningsreglementet.dk"
UD = Path(__file__).resolve().parents[1] / "src" / "byg_mcp" / "data" / "br18_vejledninger.jsonl.gz"
META = UD.with_name("br18_vejledninger_meta.json")
UA = {"User-Agent": "byg-mcp/0.1 (forskningsprototype; indsamling af BR-vejledninger til lokal soegning)"}
MAKS_SIDER_PR_KAPITEL = 350
MAKS_PDF_MB = 40
PAUSE = 0.25


def kapitler(c: httpx.Client) -> list[tuple[str, str, str]]:
    """(kapitelnummer, kapiteltitel, vejlednings-URL) for alle kapitler med en vejledningsfane."""
    s = BeautifulSoup(c.get(BASE + "/").text, "html.parser")
    krav = list(dict.fromkeys(a["href"] for a in s.select("a[href]") if re.search(r"/krav/$", a["href"]) and "historisk" not in a["href"]))
    ud = []
    for k in krav:
        ss = BeautifulSoup(c.get(k).text, "html.parser")
        nr = "1" if "administrative" in k else re.search(r"/(\d{2})/krav", k).group(1).lstrip("0")
        h1 = norm(ss.find("h1").get_text(" ", strip=True)) if ss.find("h1") else ""
        titel = re.sub(r"\s*\(§.*$", "", h1)
        for a in ss.select("a.nav-tab__link"):
            if a.get_text(strip=True) != "Krav" and a.get("href"):
                ud.append((nr, titel, urljoin(BASE, a["href"])))
                break
        time.sleep(PAUSE)
    # Vejledningssider uden for kapitlerne (klimasikring, andre vejledninger)
    ud.append(("KS", "Vejledning om klimasikring", BASE + "/vejledninger/klimasikring/vejledning_klimasikring/"))
    return ud


def kapitel_prefix(url: str) -> str:
    p = urlparse(url).path
    m = re.match(r"^(/[^/]+/(?:\d{2}/)?)", p)
    if "/vejledninger/klimasikring/" in p:
        return "/vejledninger/klimasikring/"
    return m.group(1) if m else p


def side_tekst_og_links(html: str, url: str) -> tuple[str, list[tuple[str, str]], list[str], list[tuple[str, str]]]:
    """Returnér (sidetitel, tekstblokke som (overskrift, tekst), interne links, pdf-links som (titel, url))."""
    s = BeautifulSoup(html, "html.parser")
    # Links SKAL samles før navigation fjernes - undersiderne linkes fra sidemenuen (<nav>).
    alle_a = [(norm(a.get_text(" ", strip=True)), urljoin(url, a["href"]).split("#")[0]) for a in s.select("a[href]")]
    for el in s.select("header, footer, nav, .version-selector, script, style, .cookie, aside"):
        el.decompose()
    titel = ""
    h = s.select_one(".section-module--tabs h1, h1")
    if h:
        titel = norm(h.get_text(" ", strip=True))
    blokke: list[tuple[str, str]] = []
    for row in s.select(".accordion__row--text, .rich-text, .richtext, article"):
        if row.find_parent(class_="accordion__row--text") is not None:
            continue
        _, t = blok_tekst(row)
        if len(t) > 40:
            blokke.append(("", t))
    links, pdfs = [], []
    for tekst, href in alle_a:
        if href.lower().endswith(".pdf") and "/media/" in href:
            pdfs.append((tekst.removeprefix("Åbn ").strip() or href.rsplit("/", 1)[-1], href))
        elif href.startswith(BASE) and "historisk" not in href:
            links.append(href)
    ajax = [urljoin(url, x["data-href"]) for x in s.select("[data-href*='ajax=1']")]
    sektioner = []
    for x in s.select("section.anchor-reference"):
        t = x.select_one(".accordion__title")
        trig = x.select_one("[data-href*='ajax=1']")
        if t and trig:
            sektioner.append((norm(t.get_text(" ", strip=True)), urljoin(url, trig["data-href"])))
    return titel, blokke, links, pdfs + [("__AJAX__" + n, u) for n, u in sektioner] + [("__AJAX__", u) for u in ajax if u not in [s_[1] for s_ in sektioner]]


def pdf_sider(data: bytes) -> list[str]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    r = PdfReader(io.BytesIO(data))
    return [re.sub(r"[ \t]+", " ", (p.extract_text() or "")).strip() for p in r.pages]


def chunk(tekst: str, maks: int = 1800) -> list[str]:
    """Del lange tekster ved afsnit, så hvert stykke er søgbart og citerbart."""
    if len(tekst) <= maks:
        return [tekst]
    dele, cur = [], ""
    for afsnit in re.split(r"\n(?=\S)", tekst):
        if len(cur) + len(afsnit) > maks and cur:
            dele.append(cur.strip())
            cur = ""
        cur += afsnit + "\n"
    if cur.strip():
        dele.append(cur.strip())
    return dele


def crawl_kapitel(c: httpx.Client, nr: str, kap_titel: str, start: str, pdf_cache: dict[str, list[str]]) -> list[dict]:
    prefix = kapitel_prefix(start)
    koe, set_, poster = deque([start]), {start}, []
    set_titler: set[str] = set()
    sider = 0
    while koe and sider < MAKS_SIDER_PR_KAPITEL:
        url = koe.popleft()
        try:
            r = c.get(url)
        except httpx.HTTPError:
            continue
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            continue
        sider += 1
        titel, blokke, links, special = side_tekst_og_links(r.text, url)
        for _, t in blokke:
            for i, del_ in enumerate(chunk(t)):
                poster.append({"kapitel": nr, "kapitel_titel": kap_titel, "titel": titel, "kilde": "html", "url": url, "del": i, "tekst": del_})
        for navn, u in special:
            if navn.startswith("__AJAX__"):
                try:
                    a = c.get(u)
                except httpx.HTTPError:
                    continue
                if a.status_code != 200:
                    continue
                at, ablokke, alinks, apdfs = side_tekst_og_links(a.text, url)
                sektion = navn.removeprefix("__AJAX__") or at
                for _, t in ablokke:
                    for i, del_ in enumerate(chunk(t)):
                        poster.append({"kapitel": nr, "kapitel_titel": kap_titel, "titel": f"{titel} – {sektion}".strip(" –"),
                                       "kilde": "html", "url": url, "del": i, "tekst": del_})
                special += [p for p in apdfs if not p[0].startswith("__AJAX__")]
                links += alinks
                time.sleep(PAUSE)
            else:
                noegle = re.sub(r"\s+", " ", navn.lower())
                if noegle in set_titler:  # ældre version af samme dokument
                    continue
                set_titler.add(noegle)
                if u not in pdf_cache:
                    try:
                        pr = c.get(u, timeout=120)
                        if pr.status_code == 200 and len(pr.content) < MAKS_PDF_MB * 1024 * 1024:
                            pdf_cache[u] = pdf_sider(pr.content)
                        else:
                            pdf_cache[u] = []
                    except Exception as e:  # noqa: BLE001 - én defekt PDF må ikke stoppe indsamlingen
                        print(f"   PDF-fejl {u}: {type(e).__name__}")
                        pdf_cache[u] = []
                    time.sleep(PAUSE)
                for side_nr, t in enumerate(pdf_cache[u], start=1):
                    if len(t) < 80:
                        continue
                    for i, del_ in enumerate(chunk(t)):
                        poster.append({"kapitel": nr, "kapitel_titel": kap_titel, "titel": navn, "kilde": "pdf", "url": url,
                                       "pdf_url": u, "side": side_nr, "del": i, "tekst": del_})
        for l in links:
            p = urlparse(l).path
            if p.startswith(prefix) and "/krav" not in p and l not in set_ and not re.search(r"\.(pdf|xlsx?|docx?|zip|jpg|png)$", p, re.I):
                set_.add(l)
                koe.append(l)
        time.sleep(PAUSE)
    print(f"  kapitel {nr:>3}: {sider:3d} sider, {len(poster):5d} tekststykker")
    return poster


def _dokumentgruppe(titel: str) -> str:
    t = titel.lower().replace("‐", "-").replace("‑", "-")
    t = re.sub(r"-?\s*med ændringsmarkering(er)?", "", t)
    t = re.sub(r"version\s*[\d.]+", "", t)
    t = re.sub(r"\(?\d{1,2}[./]\d{1,2}[./]\d{2,4}\)?", "", t)
    return re.sub(r"[^a-zæøå0-9]+", " ", t).strip()


def _version(titel: str) -> tuple[int, ...]:
    m = re.search(r"version\s*([\d.]+)", titel.lower())
    return tuple(int(x) for x in m.group(1).strip(".").split(".") if x.isdigit()) if m else ()


def rens(alle: list[dict]) -> list[dict]:
    """Fjern (1) PDF'er 'med ændringsmarkeringer', (2) ældre versioner af samme dokument (højeste version beholdes,
    ellers første forekomst = nyeste på siden), (3) identisk tekst gentaget på flere sider."""
    pdf_titler: dict[str, str] = {}
    for p in alle:
        if p["kilde"] == "pdf":
            pdf_titler.setdefault(p["titel"], p["kapitel"])
    behold: dict[tuple[str, str], str] = {}
    for t, kap in pdf_titler.items():
        if "ændringsmarkering" in t.lower() or "ændringsvandmærke" in t.lower():
            continue
        g = (kap, _dokumentgruppe(t))
        if g not in behold or _version(t) > _version(behold[g]):
            behold[g] = t
    gyldige = set(behold.values())
    set_, ud = set(), []
    for p in alle:
        if p["kilde"] == "pdf" and p["titel"] not in gyldige:
            continue
        k = re.sub(r"\s+", " ", p["tekst"]).strip().lower()
        if k in set_:
            continue
        set_.add(k)
        ud.append(p)
    return ud


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if "--kun-rens" in sys.argv:  # rens en eksisterende fil uden at crawle igen
        with gzip.open(UD, "rt", encoding="utf-8") as f:
            alle = [json.loads(l) for l in f]
        pdf_cache = {p["pdf_url"]: [1] for p in alle if p.get("pdf_url")}
    else:
        valgte = set(a for a in sys.argv[1:] if not a.startswith("--"))
        alle = []
        pdf_cache = {}
        with httpx.Client(timeout=60, follow_redirects=True, headers=UA) as c:
            for nr, titel, start in kapitler(c):
                if valgte and nr not in valgte:
                    continue
                alle.extend(crawl_kapitel(c, nr, titel, start, pdf_cache))
    foer = len(alle)
    unikke = rens(alle)
    print(f"Rensning: {foer} → {len(unikke)} tekststykker")
    with gzip.open(UD, "wt", encoding="utf-8") as f:
        for p in unikke:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    meta = {
        "kilde": BASE, "hentet": date.today().isoformat(), "kapitler": sorted({p["kapitel"] for p in unikke}, key=lambda x: (len(x), x)),
        "antal_tekststykker": len(unikke), "antal_pdf": len([u for u, s in pdf_cache.items() if s]),
        "html_stykker": sum(p["kilde"] == "html" for p in unikke), "pdf_stykker": sum(p["kilde"] == "pdf" for p in unikke),
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    print(f"Gemt: {UD} ({UD.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

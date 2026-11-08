"""Lokalplan-PDF → struktureret liste af bestemmelser.

Understøtter to formater (verificeret 8/11-2026):
- Digitale planer fra Plandata/kommunernes plansystemer: "5. Bebyggelsens omfang og placering",
  underpunkter "5.1 Nedrivning …" og vejledende tekst "Ad 5.1".
- Ældre planer: "§ 5. Bebyggelsens omfang og placering" med "Stk. 1".

Tekst udtrækkes med pypdf (BSD-licens). Sprogmodellen fortolker selv indholdet. Her leveres kun
den relevante tekst med bestemmelsesnummer og side.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

EMNER: dict[str, list[str]] = {
    "anvendelse": ["anvendelse", "boliger", "erhverv", "detailhandel", "butik"],
    "bebyggelsesprocent": ["bebyggelsesprocent", "etageareal", "bebyggelsens omfang"],
    "hoejde": ["højde", "højder", "etager", "kote", "koter", "tagetage", "skrå højdegrænse", "bygningshøjde"],
    "placering": ["placering", "byggefelt", "byggelinje", "facadelinje", "afstand", "skel"],
    "facade_og_materialer": ["facade", "materiale", "udseende", "tag", "farve", "vindue", "tegl", "puds", "skilt"],
    "parkering": ["parkering", "p-plads", "bilparkering", "cykelparkering", "cykel"],
    "ubebyggede_arealer": ["ubebyggede", "opholdsareal", "friareal", "beplantning", "træ", "hegn"],
    "veje_og_adgang": ["vej", "sti", "adgang", "overkørsel"],
    "miljoe_og_stoej": ["støj", "miljø", "forurening", "vibration"],
    "klima_og_regnvand": ["regnvand", "lar", "nedsivning", "klimatilpasning", "oversvømmelse", "skybrud"],
    "bevaring": ["bevaring", "bevaringsværdig", "nedrivning", "nedrives"],
    "energi_og_teknik": ["energi", "solcelle", "solfanger", "varmeforsyning", "fjernvarme", "teknisk", "affald"],
    "ibrugtagning": ["ibrugtagning", "forudsætning", "betingelse"],
}

_TOP_DIGITAL = re.compile(r"^(\d{1,2})\.\s+([A-ZÆØÅ][^\n]{2,90})$")
_SUB_DIGITAL = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([^\n]{2,90})$")
_TOP_PARAGRAF = re.compile(r"^§\s*(\d{1,2})\.?\s*([^\n]{0,90})$")
_SIDEFOD = re.compile(
    r"^(Lokalplan\s+\S+.*Side\s+\d+|Side\s+\d+(\s+af\s+\d+)?|Lokalplan\s+[\w.\-]+\s*(Vedtaget|Forslag))$", re.I
)


@dataclass
class Bestemmelse:
    nr: str
    overskrift: str
    side: int
    tekst: str
    underpunkter: list[str] = field(default_factory=list)

    def dict(self, maks_tegn: int | None = None) -> dict[str, Any]:
        d = asdict(self)
        if maks_tegn and len(self.tekst) > maks_tegn:
            d["tekst"] = self.tekst[:maks_tegn].rstrip() + " … [afkortet]"
        if not d["underpunkter"]:
            d.pop("underpunkter")
        return d


def udtraek_tekst(pdf: bytes) -> list[str]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(pdf))
    return [(p.extract_text() or "") for p in reader.pages]


def _linjer(sider: list[str]) -> list[tuple[int, str]]:
    out = []
    for i, s in enumerate(sider, start=1):
        for linje in s.splitlines():
            linje = linje.strip()
            if not linje or _SIDEFOD.match(linje) or re.fullmatch(r"[.\s\d]+", linje):
                continue
            out.append((i, linje))
    return out


def parse_bestemmelser(sider: list[str]) -> tuple[str, list[Bestemmelse]]:
    """Returnér (format, bestemmelser). Indholdsfortegnelser springes over, fordi en overskrift kun
    tæller, hvis den efterfølges af tekst og nummereringen fortsætter fortløbende (1, 2, 3 …)."""
    linjer = _linjer(sider)
    for fmt, top_re in (("digital", _TOP_DIGITAL), ("paragraf", _TOP_PARAGRAF)):
        kandidater = [(idx, int(m.group(1)), m.group(2).strip()) for idx, (_, l) in enumerate(linjer) if (m := top_re.match(l))]
        # Find den længste fortløbende serie, der starter med 1 og har brødtekst mellem overskrifterne.
        bedste: list[tuple[int, int, str]] = []
        for start in [k for k in kandidater if k[1] == 1]:
            serie, forventet = [start], 2
            for k in kandidater:
                if k[0] <= serie[-1][0]:
                    continue
                if k[1] == forventet and k[0] - serie[-1][0] > 1:
                    serie.append(k)
                    forventet += 1
            # '>=' så en senere start vinder ved lige lange serier (indholdsfortegnelsen kommer først).
            if len(serie) >= len(bedste) and serie[1:2] and serie[1][0] - serie[0][0] > 1:
                bedste = serie
        if len(bedste) >= 3:
            return fmt, _byg(linjer, bedste, fmt)
    return "ukendt", []


def _byg(linjer: list[tuple[int, str]], serie: list[tuple[int, int, str]], fmt: str) -> list[Bestemmelse]:
    ud = []
    for i, (idx, nr, overskrift) in enumerate(serie):
        slut = serie[i + 1][0] if i + 1 < len(serie) else min(len(linjer), idx + 400)
        krop = [l for _, l in linjer[idx + 1 : slut]]
        # Sidste afsnit: stop ved typiske afslutninger af bestemmelsesdelen.
        if i + 1 == len(serie):
            for j, l in enumerate(krop):
                if re.match(r"^(Vedtagelsespåtegning|Forhold til anden planlægning|Redegørelse|Kortbilag|Bilag\s+\d)", l):
                    krop = krop[:j]
                    break
        under = [m.group(0) for l in krop if (m := _SUB_DIGITAL.match(l))] if fmt == "digital" else [
            l for l in krop if re.match(r"^Stk\.\s*\d+", l)
        ]
        ud.append(Bestemmelse(str(nr), overskrift, linjer[idx][0], "\n".join(krop).strip(), under))
    return ud


def _underafsnit(b: Bestemmelse) -> list[tuple[str, str]]:
    """Del en bestemmelses tekst op i (overskriftslinje, tekst) pr. underpunkt (5.1, 5.2 … eller Stk. 1 …)."""
    blokke: list[tuple[str, list[str]]] = [("", [])]
    for linje in b.tekst.splitlines():
        if _SUB_DIGITAL.match(linje) or re.match(r"^Stk\.\s*\d+", linje):
            blokke.append((linje, []))
        else:
            blokke[-1][1].append(linje)
    return [(h, "\n".join([h, *t]).strip()) for h, t in blokke if h or any(x.strip() for x in t)]


def filtrer(bestemmelser: list[Bestemmelse], emne: str | None) -> list[Bestemmelse]:
    """Returnér kun relevante bestemmelser. Matcher overskriften, returneres hele bestemmelsen.
    Ellers returneres kun de underpunkter, hvis tekst matcher."""
    if not emne:
        return bestemmelser
    noegler = EMNER.get(emne.lower().replace("ø", "oe").replace("æ", "ae").replace(" ", "_"), [emne.lower()])

    moenstre = [re.compile(r"(?<!\w)" + re.escape(n), re.I) for n in noegler]

    def rammer(t: str) -> bool:
        # Ordstart-match: 'etager' rammer ikke 'stueetagen', 'højde' rammer 'højdegrænse'.
        return any(m.search(t) for m in moenstre)

    ud = []
    for b in bestemmelser:
        if rammer(b.overskrift):
            ud.append(b)
            continue
        dele = [(h, t) for h, t in _underafsnit(b) if h and rammer(t)]
        if dele:
            ud.append(Bestemmelse(b.nr, b.overskrift, b.side, "\n\n".join(t for _, t in dele), [h for h, _ in dele]))
    return ud

"""BR18's generiske LCA-datagrundlag (bilag 2, tabel 7) og emissionsfaktorer (tabel 8.1/8.2)."""

from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    return json.loads(resources.files("byg_mcp.data").joinpath("br18_lca.json").read_text(encoding="utf-8"))


def _ord(s: str) -> list[str]:
    return re.findall(r"[0-9a-zæøåé]+", s.lower())


# Det man typisk mener → ord der står i tabellen (søgningen udvides, ikke erstattes).
_ALIAS = {"beton": ["fabriksbeton"], "isolering": ["mineraluld", "stenuld", "glasuld", "eps"], "clt": ["krydslamineret"],
          "spær": ["konstruktionstræ"], "stål": ["stål", "armering"], "mursten": ["tegl", "mursten"]}


def soeg_tabel7(tekst: str, maks: int = 10, datatype: str | None = None) -> list[dict[str, Any]]:
    """Find datasæt i tabel 7. Alle søgeord skal indgå. Ord der STARTER med søgeordet vægter højest.
    Uden fuldt match bruges fuzzy-match på navnet."""
    q = _ord(tekst)
    rows = [r for r in data()["tabel7"] if not datatype or datatype.lower() in r.get("datatype", "").lower()]

    def score(r: dict[str, Any]) -> int:
        navn_ord = _ord(r.get("navn", "") + " " + r.get("navn_de_en", ""))
        s = 0
        for w in q:
            varianter = [w, *_ALIAS.get(w, [])]
            if any(n == v for n in navn_ord for v in varianter):
                s += 3
            elif any(n.startswith(v) for n in navn_ord for v in varianter):
                s += 2
            elif any(v in n for n in navn_ord for v in varianter):
                s += 1
            else:
                return 0  # alle søgeord skal indgå
        return s

    scorede = [(score(r), r) for r in rows]
    fuld = [(s, r) for s, r in scorede if s > 0]
    if not fuld:
        navne = {r["navn"]: r for r in rows if r.get("navn")}
        fuld = [(1, navne[n]) for n in difflib.get_close_matches(tekst, list(navne), n=maks, cutoff=0.4)]
    orden = {"Dansk generisk data": 0, "Branche data": 1, "Generisk data": 2, "Standardværdi": 3}
    fuld.sort(key=lambda t: (-t[0], orden.get(t[1].get("datatype"), 9), len(t[1].get("navn", ""))))
    return [r for _, r in fuld[:maks]]


def emissionsfaktor(aar: int) -> dict[str, Any] | None:
    t = data()["tabel81"]
    if str(aar) in t:
        return {"aar": aar, **t[str(aar)]}
    if t:
        sidste = max(t, key=int)
        return {"aar": int(sidste), **t[sidste], "note": f"{aar} findes ikke i tabellen. Seneste år ({sidste}) vist."}
    return None


def b6_middel(start_aar: int, aar: int = 50) -> dict[str, float]:
    """Gennemsnitlig emissionsfaktor over bygningens betragtningsperiode (BR18: 50 år) fra tabel 8.1.
    År uden for tabellen sættes til tabellens sidste værdi."""
    t = data()["tabel81"]
    sidste = t[max(t, key=int)]
    serie = [t.get(str(a), sidste) for a in range(start_aar, start_aar + aar)]
    return {k: round(sum(s[k] for s in serie) / len(serie), 5) for k in ("el", "fjernvarme", "ledningsgas")}

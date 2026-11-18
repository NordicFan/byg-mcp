"""Personlige adgangstokens til den hostede byg-mcp (mcp.byg-mcp.dk).

Tokens gemmes i .env som BYG_MCP_BRUGERE="navn:token,navn:token". Samme værdi skal ligge som
secret BYG_MCP_BRUGERE på Workeren i Cloudflare. Adresserne til at sende ud skrives i
adgang.local.txt (ignoreres af git). Tokens skrives aldrig til skærmen.

  uv run python scripts/brugere.py tilfoej christian anders
  uv run python scripts/brugere.py fjern anders
  uv run python scripts/brugere.py vis          # kun navne
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

ROD = Path(__file__).resolve().parents[1]
ENV = ROD / ".env"
ADGANG = ROD / "adgang.local.txt"
NOEGLE = "BYG_MCP_BRUGERE"
BASIS = "https://mcp.byg-mcp.dk/mcp/"


def laes() -> tuple[list[str], dict[str, str]]:
    linjer = ENV.read_text(encoding="utf-8").splitlines()
    brugere: dict[str, str] = {}
    for linje in linjer:
        if linje.startswith(f"{NOEGLE}="):
            for par in filter(None, linje.split("=", 1)[1].strip().strip('"').split(",")):
                navn, token = par.split(":", 1)
                brugere[navn] = token
    return linjer, brugere


def gem(linjer: list[str], brugere: dict[str, str]) -> None:
    vaerdi = ",".join(f"{n}:{t}" for n, t in brugere.items())
    ny = f"{NOEGLE}={vaerdi}"
    linjer = [ny if l.startswith(f"{NOEGLE}=") else l for l in linjer]
    if ny not in linjer:
        linjer += ["# Personlige tokens til testere (scripts/brugere.py). Samme værdi som secret BYG_MCP_BRUGERE i Cloudflare.", ny]
    ENV.write_text("\n".join(linjer) + "\n", encoding="utf-8")
    ADGANG.write_text(
        "Personlige adresser til byg-mcp. Del kun med den enkelte. Må ikke committes.\n\n"
        + "".join(f"{n}: {BASIS}{t}\n" for n, t in brugere.items()),
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"tilfoej", "fjern", "vis"}:
        sys.exit(__doc__)
    handling, navne = sys.argv[1], [n.lower() for n in sys.argv[2:]]
    for n in navne:
        if not re.fullmatch(r"[a-z0-9æøå_-]+", n):
            sys.exit(f"Ugyldigt navn: {n!r} (brug små bogstaver, tal, - og _)")
    linjer, brugere = laes()
    if handling == "tilfoej":
        for n in navne:
            if n in brugere:
                print(f"{n} findes allerede, springer over")
            else:
                brugere[n] = secrets.token_urlsafe(32)
    elif handling == "fjern":
        for n in navne:
            brugere.pop(n, None)
    if handling != "vis":
        gem(linjer, brugere)
        print(f"Opdaterede {NOEGLE} i .env og adresserne i {ADGANG.name}")
    print(f"{len(brugere)} brugere: {', '.join(brugere) or '(ingen)'}")


if __name__ == "__main__":
    main()

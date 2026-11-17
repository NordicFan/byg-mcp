"""Bygger 12-hjemmeside/site/index.html (byg-mcp.dk) ud fra 12-hjemmeside/byg-mcp.html.

- Lægger siden ind i et komplet HTML-dokument (artifact-udgaven har intet <head>).
- Skifter Google Fonts ud med de selvhostede skrifttyper i site/fonts (ingen data til Google).

Kør: uv run python scripts/byg_site.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROD = Path(__file__).resolve().parents[1] / "12-hjemmeside"
KILDE = ROD / "byg-mcp.html"
MAAL = ROD / "site" / "index.html"

HOVED = (
    '<!doctype html>\n<html lang="da">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
    '<link rel="stylesheet" href="fonts/fonts.css">\n'
)


def main() -> None:
    s = KILDE.read_text(encoding="utf-8")
    # Fjern alle forbindelser til Google Fonts
    s = re.sub(r'<link rel="preconnect" href="https://fonts\.(googleapis|gstatic)\.com"[^>]*>\n?', "", s)
    s = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">\n?', "", s)
    assert "fonts.googleapis.com" not in s and "fonts.gstatic.com" not in s, "Google Fonts findes stadig"
    i, j = s.index("<style>"), s.index("</style>") + len("</style>")
    ud = HOVED + s[:j] + "\n</head>\n<body>\n" + s[j:] + "\n</body>\n</html>\n"
    MAAL.write_text(ud, encoding="utf-8")
    print(f"Skrev {MAAL} ({len(ud):,} tegn)")


if __name__ == "__main__":
    main()

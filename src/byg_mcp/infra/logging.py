"""Logning uden hemmeligheder.

httpx logger hver forespørgsel med fuld URL på INFO-niveau. Datafordeleren og Dataforsyningen kræver
nøglen i URL'en (?apiKey= / ?token=), så uden dette filter havner nøglerne i MCP-klientens logfiler.
"""

from __future__ import annotations

import logging
import re

_HEMMELIG = re.compile(r"(?i)\b(apikey|token|password|username)=([^&\s\"']+)")


def maskér(tekst: str) -> str:
    return _HEMMELIG.sub(lambda m: f"{m.group(1)}=***", tekst)


class _MaskeringsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            besked = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        renset = maskér(besked)
        if renset != besked:
            record.msg, record.args = renset, None
        return True


def sikr_logning() -> None:
    """Skru httpx/httpcore ned til WARNING og maskér hemmeligheder i alle logbeskeder."""
    for navn in ("httpx", "httpcore"):
        logging.getLogger(navn).setLevel(logging.WARNING)
    filt = _MaskeringsFilter()
    for navn in ("", "httpx", "httpcore", "mcp"):
        logger = logging.getLogger(navn)
        if not any(isinstance(f, _MaskeringsFilter) for f in logger.filters):
            logger.addFilter(filt)
        for h in logger.handlers:
            if not any(isinstance(f, _MaskeringsFilter) for f in h.filters):
                h.addFilter(filt)

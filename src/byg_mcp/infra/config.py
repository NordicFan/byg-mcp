"""Konfiguration fra miljøvariabler (eller en lokal .env, som aldrig committes)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env-indlæsning uden ekstra afhængighed. Eksisterende miljøvariabler vinder."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break


@dataclass(frozen=True)
class Config:
    datafordeler_api_key: str | None
    dataforsyningen_token: str | None
    emo_brugernavn: str | None
    emo_adgangskode: str | None
    http_timeout: float
    user_agent: str
    cache_path: Path


def load_config() -> Config:
    _load_dotenv()
    return Config(
        datafordeler_api_key=os.environ.get("DATAFORDELER_API_KEY") or None,
        dataforsyningen_token=os.environ.get("DATAFORSYNINGEN_TOKEN") or None,
        emo_brugernavn=os.environ.get("EMO_BRUGERNAVN") or None,
        emo_adgangskode=os.environ.get("EMO_ADGANGSKODE") or None,
        http_timeout=float(os.environ.get("BYG_MCP_HTTP_TIMEOUT", "30")),
        user_agent=os.environ.get("BYG_MCP_USER_AGENT", "byg-mcp/0.1 (forskningsprototype)"),
        cache_path=Path(
            os.environ.get("BYG_MCP_CACHE", str(Path(__file__).resolve().parents[3] / "data" / "cache.sqlite"))
        ),
    )

"""
Konfiguration für den Patent Intelligence MCP Server.
Lädt Umgebungsvariablen und stellt Einstellungen bereit.
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Server-Einstellungen."""

    # USPTO PatentsView API (kostenlos, kein Key nötig)
    PATENTSVIEW_API_URL: str = "https://api.patentsview.org"

    # Timeouts
    HTTP_TIMEOUT: int = 30

    # Standard-Limits
    DEFAULT_LIMIT: int = 10
    MAX_LIMIT: int = 50

    # Cache-Einstellungen
    CACHE_ENABLED: bool = True
    CACHE_MAX_SIZE: int = 256
    CACHE_TTL_SECONDS: int = 600  # 10 Minuten

    # Version
    VERSION: str = "0.2.0"


def load_settings() -> Settings:
    """Lädt Einstellungen aus Umgebungsvariablen."""
    return Settings(
        HTTP_TIMEOUT=int(os.getenv("PATENT_HTTP_TIMEOUT", "30")),
        DEFAULT_LIMIT=int(os.getenv("PATENT_DEFAULT_LIMIT", "10")),
        MAX_LIMIT=int(os.getenv("PATENT_MAX_LIMIT", "50")),
        CACHE_ENABLED=os.getenv("PATENT_CACHE_ENABLED", "true").lower() == "true",
        CACHE_TTL_SECONDS=int(os.getenv("PATENT_CACHE_TTL", "600")),
    )


# Globale Instanz
settings = load_settings()

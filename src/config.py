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

    # EPO Open Patent Services (kostenlos für geringe Nutzung)
    EPO_OPS_URL: str = "https://data.epo.org/linked-data"

    # Timeouts
    HTTP_TIMEOUT: int = 30

    # Standard-Limits
    DEFAULT_LIMIT: int = 10
    MAX_LIMIT: int = 50


def load_settings() -> Settings:
    """Lädt Einstellungen aus Umgebungsvariablen."""
    return Settings(
        HTTP_TIMEOUT=int(os.getenv("PATENT_HTTP_TIMEOUT", "30")),
        DEFAULT_LIMIT=int(os.getenv("PATENT_DEFAULT_LIMIT", "10")),
        MAX_LIMIT=int(os.getenv("PATENT_MAX_LIMIT", "50")),
    )


# Globale Instanz
settings = load_settings()

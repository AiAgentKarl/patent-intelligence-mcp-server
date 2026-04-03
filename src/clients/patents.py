"""
Async HTTP-Client für Patent-APIs.
Nutzt USPTO PatentsView API (kostenlos, kein Key) als Hauptquelle.
v0.3.0: 16 Tools — Patent-Familien, Claims, Top-Holder, erweiterte Landschaft,
Klassifikationssuche (IPC/CPC mit Subgroup), Kategorie-Filter.
"""

import asyncio
import hashlib
import json
import time
from typing import Any

import httpx

from src.config import settings


class SimpleCache:
    """Einfacher In-Memory-Cache mit TTL und Max-Size."""

    def __init__(self, max_size: int = 256, ttl: int = 600):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._max_size = max_size
        self._ttl = ttl

    def _make_key(self, method: str, payload: dict) -> str:
        """Erstellt einen deterministischen Cache-Key."""
        raw = f"{method}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, method: str, payload: dict) -> Any | None:
        """Holt einen Eintrag aus dem Cache. None wenn nicht vorhanden oder abgelaufen."""
        key = self._make_key(method, payload)
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def set(self, method: str, payload: dict, value: Any) -> None:
        """Speichert einen Eintrag im Cache."""
        # Aelteste Eintraege loeschen wenn Cache voll
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        key = self._make_key(method, payload)
        self._cache[key] = (time.time(), value)

    @property
    def size(self) -> int:
        return len(self._cache)


# Globaler Cache
_cache = SimpleCache(
    max_size=settings.CACHE_MAX_SIZE,
    ttl=settings.CACHE_TTL_SECONDS,
)


class PatentClient:
    """Client für USPTO PatentsView API mit Cache und parallelen Requests."""

    def __init__(self):
        self.patentsview_url = settings.PATENTSVIEW_API_URL
        self.timeout = settings.HTTP_TIMEOUT
        self.cache_enabled = settings.CACHE_ENABLED

    def _get_client(self) -> httpx.AsyncClient:
        """Erstellt einen neuen async HTTP-Client."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": f"patent-intelligence-mcp-server/{settings.VERSION}",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

    async def _post(
        self, client: httpx.AsyncClient, endpoint: str, payload: dict
    ) -> dict[str, Any]:
        """POST-Request mit optionalem Caching."""
        # Cache prüfen
        if self.cache_enabled:
            cached = _cache.get(endpoint, payload)
            if cached is not None:
                return cached

        response = await client.post(
            f"{self.patentsview_url}{endpoint}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Im Cache speichern
        if self.cache_enabled:
            _cache.set(endpoint, payload, data)

        return data

    async def search_patents(
        self,
        query: str,
        limit: int = 10,
        sort_by: str = "patent_date",
        sort_order: str = "desc",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """
        Sucht Patente über die PatentsView API.
        Nutzt Volltextsuche über Titel und Abstract.
        Optional mit Datumsfilter.
        """
        limit = min(limit, settings.MAX_LIMIT)

        # Query aufbauen
        text_query = {
            "_or": [
                {"_text_any": {"patent_title": query}},
                {"_text_any": {"patent_abstract": query}},
            ]
        }

        # Datumsfilter hinzufügen wenn angegeben
        conditions = [text_query]
        if date_from:
            conditions.append({"_gte": {"patent_date": date_from}})
        if date_to:
            conditions.append({"_lte": {"patent_date": date_to}})

        q = {"_and": conditions} if len(conditions) > 1 else text_query

        payload = {
            "q": q,
            "f": [
                "patent_number",
                "patent_title",
                "patent_abstract",
                "patent_date",
                "patent_type",
                "patent_num_claims",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
                "matched_subentities_only": True,
            },
            "s": [{sort_by: sort_order}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/patents/query", payload)

    async def get_patent_details(self, patent_number: str) -> dict[str, Any]:
        """
        Holt detaillierte Infos zu einem einzelnen Patent.
        Nutzt parallele Requests für Erfinder, Assignee, CPC.
        """
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        # Basis-Payload
        base_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_abstract",
                "patent_date",
                "patent_type",
                "patent_num_claims",
                "patent_kind",
                "patent_firstnamed_assignee_city",
                "patent_firstnamed_assignee_country",
                "patent_firstnamed_inventor_city",
                "patent_firstnamed_inventor_country",
                "app_date",
                "app_number",
            ],
            "o": {"matched_subentities_only": True},
        }

        inventor_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "inventor_first_name",
                "inventor_last_name",
                "inventor_city",
                "inventor_state",
                "inventor_country",
            ],
        }

        assignee_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "assignee_organization",
                "assignee_first_name",
                "assignee_last_name",
                "assignee_type",
                "assignee_country",
            ],
        }

        cpc_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "cpc_section_id",
                "cpc_subsection_id",
                "cpc_subsection_title",
                "cpc_group_id",
                "cpc_group_title",
            ],
        }

        async with self._get_client() as client:
            # Alle 4 Requests parallel ausfuehren
            results = await asyncio.gather(
                self._post(client, "/patents/query", base_payload),
                self._safe_post(client, "/inventors/query", inventor_payload),
                self._safe_post(client, "/assignees/query", assignee_payload),
                self._safe_post(client, "/cpc_subsections/query", cpc_payload),
            )

            patent_data = results[0]
            if results[1]:
                patent_data["inventors"] = results[1]
            if results[2]:
                patent_data["assignees"] = results[2]
            if results[3]:
                patent_data["cpc_classifications"] = results[3]

            return patent_data

    async def _safe_post(
        self, client: httpx.AsyncClient, endpoint: str, payload: dict
    ) -> dict[str, Any] | None:
        """POST-Request der bei Fehlern None zurückgibt statt Exception."""
        try:
            return await self._post(client, endpoint, payload)
        except Exception:
            return None

    async def search_by_inventor(
        self, inventor_name: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Sucht Patente eines bestimmten Erfinders.
        Unterstützt Vor- und Nachname oder nur Nachname.
        """
        limit = min(limit, settings.MAX_LIMIT)

        parts = inventor_name.strip().split()
        if len(parts) >= 2:
            query = {
                "_and": [
                    {"_text_any": {"inventor_first_name": parts[0]}},
                    {"_text_any": {"inventor_last_name": " ".join(parts[1:])}},
                ]
            }
        else:
            query = {"_text_any": {"inventor_last_name": inventor_name}}

        payload = {
            "q": query,
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "inventor_first_name",
                "inventor_last_name",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
                "matched_subentities_only": True,
            },
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/patents/query", payload)

    async def search_by_assignee(
        self, company_name: str, limit: int = 10
    ) -> dict[str, Any]:
        """Sucht Patente eines bestimmten Unternehmens/Assignees."""
        limit = min(limit, settings.MAX_LIMIT)

        payload = {
            "q": {"_text_any": {"assignee_organization": company_name}},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "assignee_organization",
                "patent_num_claims",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
                "matched_subentities_only": True,
            },
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/patents/query", payload)

    async def search_by_cpc(
        self, cpc_code: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Sucht Patente nach CPC-Klassifikationscode.
        z.B. "H01L" (Halbleiter), "G06F" (Datenverarbeitung), "A61K" (Pharma).
        """
        limit = min(limit, settings.MAX_LIMIT)

        # CPC-Code kann Section (H), Subsection (H01) oder Group (H01L) sein
        code = cpc_code.strip().upper()

        if len(code) <= 1:
            # Section-Ebene (z.B. "H")
            q = {"cpc_section_id": code}
        elif len(code) <= 3:
            # Subsection-Ebene (z.B. "H01")
            q = {"cpc_subsection_id": code}
        else:
            # Group-Ebene (z.B. "H01L" oder "H01L21")
            q = {"_text_any": {"cpc_group_id": code}}

        payload = {
            "q": q,
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "cpc_subsection_id",
                "cpc_subsection_title",
                "cpc_group_id",
                "patent_num_claims",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
                "matched_subentities_only": True,
            },
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/cpc_subsections/query", payload)

    async def get_patent_citations(
        self, patent_number: str
    ) -> dict[str, Any]:
        """
        Holt Zitationsnetzwerk eines Patents.
        Nutzt parallele Requests für zitierte und zitierende Patente.
        """
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        cited_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "cited_patent_number",
                "cited_patent_title",
                "cited_patent_date",
                "cited_patent_category",
            ],
            "o": {"per_page": 100},
        }

        citing_payload = {
            "q": {"cited_patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
            ],
            "o": {"per_page": 50},
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            # Parallel ausfuehren
            cited_result, citing_result = await asyncio.gather(
                self._safe_post(client, "/patents/query", cited_payload),
                self._safe_post(client, "/patents/query", citing_payload),
            )

            return {
                "patent_number": clean_number,
                "cited_by_this_patent": cited_result or {},
                "patents_citing_this": citing_result or {},
            }

    async def get_patent_counts_by_year(
        self, query: str, start_year: int, end_year: int
    ) -> list[dict[str, Any]]:
        """
        Holt Patent-Anmeldezahlen pro Jahr — PARALLEL statt sequentiell.
        Massiv schneller als v0.1.0.
        """

        async def _count_for_year(
            client: httpx.AsyncClient, year: int
        ) -> dict[str, Any]:
            """Einzelne Jahres-Abfrage."""
            payload = {
                "q": {
                    "_and": [
                        {
                            "_or": [
                                {"_text_any": {"patent_title": query}},
                                {"_text_any": {"patent_abstract": query}},
                            ]
                        },
                        {"_gte": {"patent_date": f"{year}-01-01"}},
                        {"_lte": {"patent_date": f"{year}-12-31"}},
                    ]
                },
                "f": ["patent_number"],
                "o": {"page": 1, "per_page": 1},
            }
            try:
                data = await self._post(client, "/patents/query", payload)
                count = data.get("total_patent_count", 0)
            except Exception:
                count = 0
            return {"year": year, "patent_count": count}

        async with self._get_client() as client:
            # Alle Jahre parallel abfragen
            tasks = [
                _count_for_year(client, year)
                for year in range(start_year, end_year + 1)
            ]
            results = await asyncio.gather(*tasks)

        return sorted(results, key=lambda x: x["year"])

    async def get_top_assignees_for_query(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        """Holt die Top-Assignees für eine bestimmte Technologie."""
        limit = min(limit, settings.MAX_LIMIT)

        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": query}},
                    {"_text_any": {"patent_abstract": query}},
                ]
            },
            "f": [
                "assignee_organization",
                "assignee_total_num_patents",
                "assignee_country",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
            },
            "s": [{"assignee_total_num_patents": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/assignees/query", payload)

    async def get_assignee_patent_count(
        self, company_name: str
    ) -> int:
        """Holt die Gesamtanzahl Patente eines Unternehmens."""
        payload = {
            "q": {"_text_any": {"assignee_organization": company_name}},
            "f": ["patent_number"],
            "o": {"page": 1, "per_page": 1},
        }

        async with self._get_client() as client:
            try:
                data = await self._post(client, "/patents/query", payload)
                return data.get("total_patent_count", 0)
            except Exception:
                return 0

    async def get_assignee_yearly_counts(
        self, company_name: str, start_year: int, end_year: int
    ) -> list[dict[str, Any]]:
        """Holt Patent-Anmeldezahlen pro Jahr fuer ein Unternehmen — parallel."""

        async def _count_year(
            client: httpx.AsyncClient, year: int
        ) -> dict[str, Any]:
            payload = {
                "q": {
                    "_and": [
                        {"_text_any": {"assignee_organization": company_name}},
                        {"_gte": {"patent_date": f"{year}-01-01"}},
                        {"_lte": {"patent_date": f"{year}-12-31"}},
                    ]
                },
                "f": ["patent_number"],
                "o": {"page": 1, "per_page": 1},
            }
            try:
                data = await self._post(client, "/patents/query", payload)
                count = data.get("total_patent_count", 0)
            except Exception:
                count = 0
            return {"year": year, "patent_count": count}

        async with self._get_client() as client:
            tasks = [
                _count_year(client, year)
                for year in range(start_year, end_year + 1)
            ]
            results = await asyncio.gather(*tasks)

        return sorted(results, key=lambda x: x["year"])

    # === Neue Methoden v0.3.0 ===

    async def search_by_classification(
        self, ipc_code: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Sucht Patente nach IPC/CPC Klassifikation auf Subgroup-Ebene.
        Erlaubt praezisere Suche als search_by_cpc (nutzt cpc_subgroup_id).
        z.B. "H04L" (Netzwerk), "A61K" (Pharma), "G06N" (ML/AI).
        """
        limit = min(limit, settings.MAX_LIMIT)
        code = ipc_code.strip().upper()

        # Je nach Code-Laenge verschiedene Felder nutzen
        if len(code) <= 1:
            q = {"cpc_section_id": code}
        elif len(code) <= 3:
            q = {"cpc_subsection_id": code}
        elif len(code) <= 4:
            # Group-Ebene, z.B. "H04L"
            q = {"_text_any": {"cpc_group_id": code}}
        else:
            # Subgroup-Ebene, z.B. "H04L9" oder "H04L9/32"
            q = {"_text_any": {"cpc_subgroup_id": code}}

        payload = {
            "q": q,
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "cpc_section_id",
                "cpc_subsection_id",
                "cpc_subsection_title",
                "cpc_group_id",
                "cpc_group_title",
                "cpc_subgroup_id",
                "cpc_subgroup_title",
                "patent_num_claims",
                "assignee_organization",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
                "matched_subentities_only": True,
            },
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/cpc_subsections/query", payload)

    async def get_patent_family(
        self, patent_number: str
    ) -> dict[str, Any]:
        """
        Findet verwandte Patente in derselben Patent-Familie.
        Nutzt Application-Number und Zitationen um Continuations,
        Divisionals und verwandte Anmeldungen zu finden.
        """
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        # Basis-Patent-Daten mit Application-Info holen
        base_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "patent_kind",
                "app_number",
                "app_date",
                "patent_firstnamed_assignee_city",
                "patent_firstnamed_assignee_country",
                "assignee_organization",
            ],
            "o": {"matched_subentities_only": True},
        }

        # Verwandte Patente ueber Zitationen (gleicher Assignee)
        cited_payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "cited_patent_number",
                "cited_patent_title",
                "cited_patent_date",
                "cited_patent_category",
            ],
            "o": {"per_page": 100},
        }

        # Patente die dieses zitieren
        citing_payload = {
            "q": {"cited_patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_type",
                "patent_kind",
                "assignee_organization",
            ],
            "o": {"per_page": 50},
            "s": [{"patent_date": "desc"}],
        }

        async with self._get_client() as client:
            base_data, cited_data, citing_data = await asyncio.gather(
                self._post(client, "/patents/query", base_payload),
                self._safe_post(client, "/patents/query", cited_payload),
                self._safe_post(client, "/patents/query", citing_payload),
            )

            return {
                "patent_number": clean_number,
                "base_patent": base_data,
                "cited_patents": cited_data or {},
                "citing_patents": citing_data or {},
            }

    async def get_top_patent_holders(
        self,
        limit: int = 20,
        sector_query: str | None = None,
    ) -> dict[str, Any]:
        """
        Holt die Top-Patentinhaber. Optional gefiltert nach Technologie-Sektor.
        """
        limit = min(limit, settings.MAX_LIMIT)

        # Wenn Sektor angegeben, filtern wir nach Suchbegriffen
        if sector_query:
            q: dict = {
                "_or": [
                    {"_text_any": {"patent_title": sector_query}},
                    {"_text_any": {"patent_abstract": sector_query}},
                ]
            }
        else:
            # Ohne Filter: alle Assignees nach Gesamtpatenten sortiert
            q = {"_gte": {"assignee_total_num_patents": 1}}

        payload = {
            "q": q,
            "f": [
                "assignee_organization",
                "assignee_total_num_patents",
                "assignee_country",
                "assignee_type",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
            },
            "s": [{"assignee_total_num_patents": "desc"}],
        }

        async with self._get_client() as client:
            return await self._post(client, "/assignees/query", payload)

    async def get_patent_claims(
        self, patent_number: str
    ) -> dict[str, Any]:
        """
        Holt die Claims (Patentansprueche) eines Patents.
        Claims sind der rechtlich bindende Teil eines Patents.
        """
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        payload = {
            "q": {"patent_number": clean_number},
            "f": [
                "patent_number",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "patent_num_claims",
                "claim_text",
                "claim_number",
                "claim_sequence",
            ],
            "o": {
                "matched_subentities_only": True,
                "per_page": 100,
            },
        }

        async with self._get_client() as client:
            return await self._post(client, "/patents/query", payload)

    async def get_landscape_cpc_distribution(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Holt die CPC-Verteilung fuer eine Technologie-Suche.
        Zeigt in welchen Klassifikationen die meisten Patente liegen.
        """
        limit = min(limit, settings.MAX_LIMIT)

        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": query}},
                    {"_text_any": {"patent_abstract": query}},
                ]
            },
            "f": [
                "cpc_subsection_id",
                "cpc_subsection_title",
                "cpc_total_num_patents",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
            },
            "s": [{"cpc_total_num_patents": "desc"}],
        }

        async with self._get_client() as client:
            return await self._safe_post(client, "/cpc_subsections/query", payload)

    async def get_landscape_country_distribution(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Holt die geografische Verteilung der Assignees fuer eine Technologie.
        """
        limit = min(limit, settings.MAX_LIMIT)

        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": query}},
                    {"_text_any": {"patent_abstract": query}},
                ]
            },
            "f": [
                "assignee_organization",
                "assignee_country",
                "assignee_total_num_patents",
            ],
            "o": {
                "page": 1,
                "per_page": limit,
            },
            "s": [{"assignee_total_num_patents": "desc"}],
        }

        async with self._get_client() as client:
            return await self._safe_post(client, "/assignees/query", payload)


# Globale Client-Instanz
patent_client = PatentClient()

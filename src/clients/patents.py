"""
Async HTTP-Client für Patent-APIs.
Nutzt USPTO PatentsView API (kostenlos, kein Key) als Hauptquelle.
"""

import httpx
from typing import Any

from src.config import settings


class PatentClient:
    """Client für USPTO PatentsView API und ergänzende Quellen."""

    def __init__(self):
        self.patentsview_url = settings.PATENTSVIEW_API_URL
        self.timeout = settings.HTTP_TIMEOUT

    def _get_client(self) -> httpx.AsyncClient:
        """Erstellt einen neuen async HTTP-Client."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": "patent-intelligence-mcp-server/0.1.0",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

    async def search_patents(
        self,
        query: str,
        limit: int = 10,
        sort_by: str = "patent_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        """
        Sucht Patente über die PatentsView API.
        Nutzt Volltextsuche über Titel und Abstract.
        """
        limit = min(limit, settings.MAX_LIMIT)

        # PatentsView API v1 Query-Format
        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": query}},
                    {"_text_any": {"patent_abstract": query}},
                ]
            },
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
            "s": [{"patent_date": sort_order}],
        }

        async with self._get_client() as client:
            response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_patent_details(self, patent_number: str) -> dict[str, Any]:
        """
        Holt detaillierte Infos zu einem einzelnen Patent.
        Inklusive Erfinder, Assignee, Claims, Klassifikation.
        """
        # Nummer bereinigen (Bindestriche/Leerzeichen entfernen)
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        payload = {
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

        async with self._get_client() as client:
            # Patent-Basis-Daten
            response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=payload,
            )
            response.raise_for_status()
            patent_data = response.json()

            # Erfinder abrufen
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
            inv_response = await client.post(
                f"{self.patentsview_url}/inventors/query",
                json=inventor_payload,
            )

            # Assignees abrufen
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
            asg_response = await client.post(
                f"{self.patentsview_url}/assignees/query",
                json=assignee_payload,
            )

            # CPC-Klassifikation abrufen
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
            cpc_response = await client.post(
                f"{self.patentsview_url}/cpc_subsections/query",
                json=cpc_payload,
            )

            result = patent_data
            if inv_response.status_code == 200:
                result["inventors"] = inv_response.json()
            if asg_response.status_code == 200:
                result["assignees"] = asg_response.json()
            if cpc_response.status_code == 200:
                result["cpc_classifications"] = cpc_response.json()

            return result

    async def search_by_inventor(
        self, inventor_name: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Sucht Patente eines bestimmten Erfinders.
        Unterstützt Vor- und Nachname oder nur Nachname.
        """
        limit = min(limit, settings.MAX_LIMIT)

        # Name aufteilen falls möglich
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
            response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def search_by_assignee(
        self, company_name: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Sucht Patente eines bestimmten Unternehmens/Assignees.
        """
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
            response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_patent_citations(
        self, patent_number: str
    ) -> dict[str, Any]:
        """
        Holt Zitationsnetzwerk eines Patents.
        Zeigt sowohl zitierte als auch zitierende Patente.
        """
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        async with self._get_client() as client:
            # Zitierte Patente (was dieses Patent zitiert)
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
            cited_response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=cited_payload,
            )

            # Zitierende Patente (wer dieses Patent zitiert)
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
            citing_response = await client.post(
                f"{self.patentsview_url}/patents/query",
                json=citing_payload,
            )

            result = {
                "patent_number": clean_number,
                "cited_by_this_patent": {},
                "patents_citing_this": {},
            }

            if cited_response.status_code == 200:
                result["cited_by_this_patent"] = cited_response.json()
            if citing_response.status_code == 200:
                result["patents_citing_this"] = citing_response.json()

            return result

    async def get_patent_counts_by_year(
        self, query: str, start_year: int, end_year: int
    ) -> list[dict[str, Any]]:
        """
        Holt Patent-Anmeldezahlen pro Jahr für eine Technologie.
        Wird für Trendanalysen genutzt.
        """
        results = []

        async with self._get_client() as client:
            for year in range(start_year, end_year + 1):
                payload = {
                    "q": {
                        "_and": [
                            {
                                "_or": [
                                    {"_text_any": {"patent_title": query}},
                                    {"_text_any": {"patent_abstract": query}},
                                ]
                            },
                            {
                                "_gte": {
                                    "patent_date": f"{year}-01-01"
                                }
                            },
                            {
                                "_lte": {
                                    "patent_date": f"{year}-12-31"
                                }
                            },
                        ]
                    },
                    "f": ["patent_number"],
                    "o": {"page": 1, "per_page": 1},
                }

                try:
                    response = await client.post(
                        f"{self.patentsview_url}/patents/query",
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    count = data.get("total_patent_count", 0)
                except Exception:
                    count = 0

                results.append({"year": year, "patent_count": count})

        return results

    async def get_top_assignees_for_query(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Holt die Top-Assignees für eine bestimmte Technologie.
        Hilfreich für Wettbewerbsanalyse.
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
            response = await client.post(
                f"{self.patentsview_url}/assignees/query",
                json=payload,
            )
            response.raise_for_status()
            return response.json()


# Globale Client-Instanz
patent_client = PatentClient()

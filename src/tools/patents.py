"""
MCP-Tools für Patent-Intelligence.
v0.3.0: 16 Tools — Suche, Details, Erfinder, Assignee, Zitationen,
Trends, CPC-Suche, Datumssuche, Portfolio-Vergleich, Technologie-Landschaft,
Klassifikationssuche (IPC/CPC), Patent-Familien, Top-Holder, Claims,
erweiterte Landschaftsanalyse, kategoriebasierte Neuheiten-Suche.
"""

import asyncio
from datetime import datetime, timedelta

from src.clients.patents import patent_client


# === Bestehende Tools (verbessert) ===


async def search_patents(
    query: str,
    country: str = "US",
    limit: int = 10,
    date_from: str = "",
    date_to: str = "",
) -> dict:
    """
    Sucht Patente nach Stichwörtern.

    Durchsucht Titel und Abstract von US-Patenten.
    Optional mit Datumsfilter für gezielte Zeitraum-Suchen.

    Args:
        query: Suchbegriff(e), z.B. "machine learning", "battery electrode"
        country: Ländercode (aktuell nur "US" unterstützt via PatentsView)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
        date_from: Startdatum im Format YYYY-MM-DD (optional)
        date_to: Enddatum im Format YYYY-MM-DD (optional)
    """
    try:
        data = await patent_client.search_patents(
            query=query,
            limit=limit,
            date_from=date_from or None,
            date_to=date_to or None,
        )

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            return {
                "query": query,
                "country": country,
                "total_results": 0,
                "patents": [],
                "hint": f"Keine Patente gefunden für '{query}'. Versuche breitere Suchbegriffe.",
            }

        results = []
        for p in patents:
            results.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
                "abstract": _truncate(p.get("patent_abstract", ""), 300),
                "type": p.get("patent_type"),
                "num_claims": p.get("patent_num_claims"),
            })

        result = {
            "query": query,
            "country": country,
            "total_results": total,
            "showing": len(results),
            "patents": results,
        }

        # Datumsfilter im Ergebnis anzeigen
        if date_from or date_to:
            result["date_filter"] = {
                "from": date_from or "unbegrenzt",
                "to": date_to or "unbegrenzt",
            }

        return result
    except Exception as e:
        return {"error": str(e), "query": query}


async def get_patent_details(patent_number: str) -> dict:
    """
    Holt vollständige Details zu einem Patent.

    Gibt Titel, Abstract, Erfinder, Assignees, CPC-Klassifikation,
    Anmeldedatum und Anzahl Claims zurück.

    Args:
        patent_number: Patent-Nummer, z.B. "11234567" oder "US-11234567"
    """
    try:
        data = await patent_client.get_patent_details(patent_number)

        patents = data.get("patents", [])
        if not patents:
            return {
                "patent_number": patent_number,
                "error": f"Patent {patent_number} nicht gefunden",
                "hint": "Prüfe die Nummer. Formate: '11234567', 'US-11234567', 'US11234567'",
            }

        patent = patents[0]

        # Erfinder extrahieren
        inventors = []
        inv_data = data.get("inventors", {})
        if inv_data and inv_data.get("inventors"):
            for inv in inv_data["inventors"]:
                name = f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                location = _build_location(
                    inv.get("inventor_city"),
                    inv.get("inventor_state"),
                    inv.get("inventor_country"),
                )
                inventors.append({"name": name, "location": location})

        # Assignees extrahieren
        assignees = []
        asg_data = data.get("assignees", {})
        if asg_data and asg_data.get("assignees"):
            for asg in asg_data["assignees"]:
                org = asg.get("assignee_organization") or (
                    f"{asg.get('assignee_first_name', '')} "
                    f"{asg.get('assignee_last_name', '')}"
                ).strip()
                assignees.append({
                    "name": org,
                    "type": _assignee_type(asg.get("assignee_type")),
                    "country": asg.get("assignee_country"),
                })

        # CPC-Klassifikation extrahieren
        classifications = []
        cpc_data = data.get("cpc_classifications", {})
        if cpc_data and cpc_data.get("cpc_subsections"):
            seen = set()
            for cpc in cpc_data["cpc_subsections"]:
                group_id = cpc.get("cpc_group_id", "")
                if group_id and group_id not in seen:
                    seen.add(group_id)
                    classifications.append({
                        "section": cpc.get("cpc_section_id"),
                        "subsection": cpc.get("cpc_subsection_id"),
                        "subsection_title": cpc.get("cpc_subsection_title"),
                        "group": group_id,
                        "group_title": cpc.get("cpc_group_title"),
                    })

        return {
            "patent_number": patent.get("patent_number"),
            "title": patent.get("patent_title"),
            "abstract": patent.get("patent_abstract"),
            "grant_date": patent.get("patent_date"),
            "application_date": patent.get("app_date"),
            "application_number": patent.get("app_number"),
            "type": patent.get("patent_type"),
            "kind": patent.get("patent_kind"),
            "num_claims": patent.get("patent_num_claims"),
            "inventors": inventors,
            "inventor_count": len(inventors),
            "assignees": assignees,
            "cpc_classifications": classifications[:10],
            "related_tools": {
                "get_patent_citations": f"Zitationsnetzwerk für {patent_number} abrufen",
                "get_patent_claims": f"Patentansprüche (Claims) für {patent_number} abrufen",
                "get_patent_family": f"Verwandte Patente (Familie) für {patent_number} finden",
            },
        }
    except Exception as e:
        return {"error": str(e), "patent_number": patent_number}


async def search_by_inventor(
    inventor_name: str, limit: int = 10
) -> dict:
    """
    Sucht Patente eines bestimmten Erfinders.

    Unterstützt Suche nach vollem Namen oder nur Nachname.

    Args:
        inventor_name: Name des Erfinders, z.B. "Elon Musk" oder "Musk"
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        data = await patent_client.search_by_inventor(
            inventor_name=inventor_name, limit=limit
        )

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            return {
                "inventor": inventor_name,
                "total_results": 0,
                "patents": [],
                "hint": f"Keine Patente für '{inventor_name}'. Versuche nur den Nachnamen.",
            }

        results = []
        for p in patents:
            inv_names = []
            for inv in p.get("inventors", []):
                name = f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                if name:
                    inv_names.append(name)

            results.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
                "abstract": _truncate(p.get("patent_abstract", ""), 200),
                "inventors": inv_names or None,
            })

        return {
            "inventor": inventor_name,
            "total_results": total,
            "showing": len(results),
            "patents": results,
        }
    except Exception as e:
        return {"error": str(e), "inventor": inventor_name}


async def search_by_assignee(
    company_name: str, limit: int = 10
) -> dict:
    """
    Sucht Patente eines Unternehmens oder einer Organisation.

    Durchsucht die Assignee-Datenbank nach Firmennamen.

    Args:
        company_name: Firmenname, z.B. "Google", "Tesla", "IBM"
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        data = await patent_client.search_by_assignee(
            company_name=company_name, limit=limit
        )

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            return {
                "company": company_name,
                "total_results": 0,
                "patents": [],
                "hint": f"Keine Patente für '{company_name}'. Versuche den vollen Firmennamen.",
            }

        results = []
        for p in patents:
            asg_names = []
            for asg in p.get("assignees", []):
                org = asg.get("assignee_organization")
                if org:
                    asg_names.append(org)

            results.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
                "abstract": _truncate(p.get("patent_abstract", ""), 200),
                "assignees": asg_names or None,
                "num_claims": p.get("patent_num_claims"),
            })

        return {
            "company": company_name,
            "total_results": total,
            "showing": len(results),
            "patents": results,
        }
    except Exception as e:
        return {"error": str(e), "company": company_name}


async def get_patent_citations(patent_number: str) -> dict:
    """
    Holt das Zitationsnetzwerk eines Patents.

    Zeigt welche Patente dieses Patent zitiert und
    welche anderen Patente dieses Patent zitieren.
    Berechnet einen Impact-Score basierend auf Zitationshäufigkeit.

    Args:
        patent_number: Patent-Nummer, z.B. "11234567"
    """
    try:
        data = await patent_client.get_patent_citations(patent_number)

        # Zitierte Patente
        cited_patents = []
        cited_data = data.get("cited_by_this_patent", {})
        if cited_data and cited_data.get("patents"):
            for p in cited_data["patents"]:
                for cited in p.get("cited_patents", []):
                    cited_patents.append({
                        "patent_number": cited.get("cited_patent_number"),
                        "title": cited.get("cited_patent_title"),
                        "date": cited.get("cited_patent_date"),
                        "category": cited.get("cited_patent_category"),
                    })

        # Zitierende Patente
        citing_patents = []
        citing_data = data.get("patents_citing_this", {})
        if citing_data and citing_data.get("patents"):
            for p in citing_data["patents"]:
                citing_patents.append({
                    "patent_number": p.get("patent_number"),
                    "title": p.get("patent_title"),
                    "date": p.get("patent_date"),
                    "abstract": _truncate(p.get("patent_abstract", ""), 150),
                })

        total_citing = citing_data.get("total_patent_count", 0) if citing_data else 0

        return {
            "patent_number": data["patent_number"],
            "citations_made": len(cited_patents),
            "cited_patents": cited_patents[:25],
            "times_cited": total_citing,
            "citing_patents": citing_patents[:25],
            "impact_score": _citation_impact_score(total_citing),
            "impact_note": _citation_impact(total_citing),
        }
    except Exception as e:
        return {"error": str(e), "patent_number": patent_number}


async def analyze_technology_trends(
    query: str, years: int = 5
) -> dict:
    """
    Analysiert Patent-Anmeldetrends für eine Technologie.

    Zeigt Anzahl der Patentanmeldungen pro Jahr,
    Wachstumsrate und Top-Anmelder im Bereich.
    Nutzt parallele API-Abfragen für schnelle Ergebnisse.

    Args:
        query: Technologie-Suchbegriff, z.B. "quantum computing", "CRISPR"
        years: Analysezeitraum in Jahren (1-20, Standard: 5)
    """
    try:
        years = max(1, min(years, 20))
        current_year = datetime.now().year
        start_year = current_year - years
        end_year = current_year - 1

        # Jahreszahlen und Top-Assignees parallel abrufen
        yearly_data, top_assignees_data = await asyncio.gather(
            patent_client.get_patent_counts_by_year(
                query=query, start_year=start_year, end_year=end_year
            ),
            patent_client.get_top_assignees_for_query(query=query, limit=10),
        )

        # Wachstumsrate berechnen
        counts = [y["patent_count"] for y in yearly_data if y["patent_count"] > 0]
        growth_rate = None
        trend = "unbekannt"

        if len(counts) >= 2:
            first_half = sum(counts[: len(counts) // 2])
            second_half = sum(counts[len(counts) // 2 :])
            if first_half > 0:
                growth_rate = round(
                    ((second_half - first_half) / first_half) * 100, 1
                )
                trend = _classify_trend(growth_rate)

        total_patents = sum(y["patent_count"] for y in yearly_data)

        # Peak-Jahr finden
        peak_year = None
        if yearly_data:
            peak = max(yearly_data, key=lambda y: y["patent_count"])
            if peak["patent_count"] > 0:
                peak_year = {"year": peak["year"], "count": peak["patent_count"]}

        # Top-Assignees formatieren
        top_companies = []
        assignees = top_assignees_data.get("assignees", [])
        if assignees:
            for asg in assignees[:10]:
                org = asg.get("assignee_organization")
                if org:
                    top_companies.append({
                        "company": org,
                        "total_patents": asg.get("assignee_total_num_patents"),
                        "country": asg.get("assignee_country"),
                    })

        return {
            "technology": query,
            "period": f"{start_year}-{end_year}",
            "total_patents_in_period": total_patents,
            "trend": trend,
            "growth_rate_percent": growth_rate,
            "peak_year": peak_year,
            "yearly_breakdown": yearly_data,
            "top_assignees": top_companies,
            "analysis_note": _trend_note(trend, query, total_patents),
        }
    except Exception as e:
        return {"error": str(e), "technology": query}


# === Neue Tools (v0.2.0) ===


async def search_by_cpc(
    cpc_code: str, limit: int = 10
) -> dict:
    """
    Sucht Patente nach CPC-Klassifikationscode.

    CPC (Cooperative Patent Classification) ist das internationale
    Klassifikationssystem für Patente. Nützlich für gezielte
    Technologie-Recherchen.

    Häufige Codes:
    - A: Lebensnotwendiges (Pharma, Medizin, Landwirtschaft)
    - B: Verfahrenstechnik, Transport
    - C: Chemie, Metallurgie
    - D: Textilien, Papier
    - E: Bauwesen
    - F: Maschinenbau, Waffen
    - G: Physik (G06F=Computing, G06N=ML/AI)
    - H: Elektrotechnik (H01L=Halbleiter, H04=Telekommunikation)

    Args:
        cpc_code: CPC-Code, z.B. "G06N" (ML/AI), "H01L" (Halbleiter), "A61K" (Pharma)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        data = await patent_client.search_by_cpc(cpc_code=cpc_code, limit=limit)

        # CPC-Subsections enthalten die Patentdaten verschachtelt
        subsections = data.get("cpc_subsections", [])
        total = data.get("total_cpc_subsection_count", 0)

        if not subsections:
            return {
                "cpc_code": cpc_code.upper(),
                "total_results": 0,
                "patents": [],
                "hint": f"Keine Patente für CPC '{cpc_code}'. Gültige Codes: A-H (Section), H01 (Subsection), H01L (Group).",
            }

        results = []
        seen_patents = set()
        for sub in subsections:
            for p in sub.get("patents", []):
                pn = p.get("patent_number")
                if pn and pn not in seen_patents:
                    seen_patents.add(pn)
                    results.append({
                        "patent_number": pn,
                        "title": p.get("patent_title"),
                        "date": p.get("patent_date"),
                        "abstract": _truncate(p.get("patent_abstract", ""), 200),
                        "cpc_subsection": sub.get("cpc_subsection_id"),
                        "cpc_title": sub.get("cpc_subsection_title"),
                        "num_claims": p.get("patent_num_claims"),
                    })

        return {
            "cpc_code": cpc_code.upper(),
            "cpc_description": _cpc_section_name(cpc_code[0].upper()) if cpc_code else "",
            "total_results": total,
            "showing": len(results),
            "patents": results[:limit],
        }
    except Exception as e:
        return {"error": str(e), "cpc_code": cpc_code}


async def search_recent_patents(
    query: str,
    days: int = 90,
    limit: int = 10,
    category: str = "",
) -> dict:
    """
    Sucht die neuesten Patente in einem Technologiebereich.

    Fokussiert auf kürzlich erteilte Patente. Nützlich um aktuelle
    Innovationen und neue Entwicklungen zu finden.
    Optional mit Kategorie-Filter (CPC-Section) für präzisere Ergebnisse.

    Args:
        query: Technologie-Suchbegriff, z.B. "autonomous driving", "mRNA vaccine"
        days: Zeitraum in Tagen zurück (Standard: 90, Max: 730)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
        category: CPC-Kategorie zum Filtern, z.B. "pharma", "tech", "energy", "automotive", "telecom" (optional)
    """
    try:
        days = max(1, min(days, 730))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        date_from = start_date.strftime("%Y-%m-%d")
        date_to = end_date.strftime("%Y-%m-%d")

        # Kategorie-Mapping auf CPC-Codes und erweiterte Suchbegriffe
        category_map = {
            "pharma": ("A61K", "pharmaceutical drug compound"),
            "tech": ("G06", "computing software algorithm"),
            "energy": ("H02", "energy battery solar power"),
            "automotive": ("B60", "vehicle automotive driving"),
            "telecom": ("H04", "wireless network communication"),
            "biotech": ("C12", "biotechnology gene protein enzyme"),
            "semiconductor": ("H01L", "semiconductor chip transistor"),
            "ai": ("G06N", "artificial intelligence machine learning neural network"),
            "medical": ("A61B", "medical device surgical diagnostic"),
            "aerospace": ("B64", "aircraft drone aerospace"),
        }

        # Wenn Kategorie angegeben, den Query erweitern
        effective_query = query
        cpc_filter = None
        if category and category.lower() in category_map:
            cpc_filter, extra_terms = category_map[category.lower()]
            if not query:
                effective_query = extra_terms

        data = await patent_client.search_patents(
            query=effective_query,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            sort_by="patent_date",
            sort_order="desc",
        )

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            hint = f"Keine neuen Patente für '{effective_query}' in den letzten {days} Tagen."
            if days < 365:
                hint += " USPTO-Daten haben oft Verzögerung — versuche einen längeren Zeitraum."
            return {
                "query": effective_query,
                "category": category or None,
                "period": f"Letzte {days} Tage ({date_from} bis {date_to})",
                "total_results": 0,
                "patents": [],
                "hint": hint,
            }

        results = []
        for p in patents:
            results.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
                "abstract": _truncate(p.get("patent_abstract", ""), 250),
                "type": p.get("patent_type"),
                "num_claims": p.get("patent_num_claims"),
            })

        return {
            "query": effective_query,
            "category": category or None,
            "cpc_filter": cpc_filter,
            "period": f"Letzte {days} Tage ({date_from} bis {date_to})",
            "total_results": total,
            "showing": len(results),
            "patents": results,
            "available_categories": list(category_map.keys()) if not category else None,
        }
    except Exception as e:
        return {"error": str(e), "query": query}


async def compare_portfolios(
    company_a: str,
    company_b: str,
    years: int = 5,
) -> dict:
    """
    Vergleicht die Patent-Portfolios zweier Unternehmen.

    Zeigt Gesamtzahl, Wachstumstrend und neueste Patente
    beider Firmen im direkten Vergleich.

    Args:
        company_a: Erste Firma, z.B. "Apple"
        company_b: Zweite Firma, z.B. "Samsung"
        years: Vergleichszeitraum in Jahren (1-10, Standard: 5)
    """
    try:
        years = max(1, min(years, 10))
        current_year = datetime.now().year
        start_year = current_year - years
        end_year = current_year - 1

        # Alle 4 Abfragen parallel
        count_a, count_b, yearly_a, yearly_b = await asyncio.gather(
            patent_client.get_assignee_patent_count(company_a),
            patent_client.get_assignee_patent_count(company_b),
            patent_client.get_assignee_yearly_counts(company_a, start_year, end_year),
            patent_client.get_assignee_yearly_counts(company_b, start_year, end_year),
        )

        # Wachstumsraten berechnen
        def _calc_growth(yearly: list) -> float | None:
            counts = [y["patent_count"] for y in yearly if y["patent_count"] > 0]
            if len(counts) < 2:
                return None
            first = sum(counts[: len(counts) // 2])
            second = sum(counts[len(counts) // 2 :])
            if first == 0:
                return None
            return round(((second - first) / first) * 100, 1)

        growth_a = _calc_growth(yearly_a)
        growth_b = _calc_growth(yearly_b)

        total_a = sum(y["patent_count"] for y in yearly_a)
        total_b = sum(y["patent_count"] for y in yearly_b)

        # Wer fuehrt?
        if total_a > total_b * 1.1:
            leader = company_a
        elif total_b > total_a * 1.1:
            leader = company_b
        else:
            leader = "Gleichauf"

        return {
            "comparison": f"{company_a} vs {company_b}",
            "period": f"{start_year}-{end_year}",
            "leader_in_period": leader,
            company_a: {
                "total_patents_all_time": count_a,
                "patents_in_period": total_a,
                "growth_rate_percent": growth_a,
                "trend": _classify_trend(growth_a) if growth_a is not None else "unbekannt",
                "yearly": yearly_a,
            },
            company_b: {
                "total_patents_all_time": count_b,
                "patents_in_period": total_b,
                "growth_rate_percent": growth_b,
                "trend": _classify_trend(growth_b) if growth_b is not None else "unbekannt",
                "yearly": yearly_b,
            },
        }
    except Exception as e:
        return {"error": str(e), "companies": [company_a, company_b]}


async def get_patent_landscape(
    query: str,
    years: int = 5,
    top_n: int = 10,
) -> dict:
    """
    Erstellt eine umfassende Technologie-Landschaft für einen Bereich.

    Kombiniert Trend-Analyse, Top-Player, CPC-Klassifikationsverteilung,
    geografische Verteilung, Aktivitäts-Heatmap und Wettbewerbsintensität.
    Ideal für strategische Patent-Recherche, Due Diligence und Marktanalysen.

    Args:
        query: Technologie-Suchbegriff, z.B. "solid state battery", "gene therapy"
        years: Analysezeitraum in Jahren (1-20, Standard: 5)
        top_n: Anzahl Top-Unternehmen (1-20, Standard: 10)
    """
    try:
        years = max(1, min(years, 20))
        top_n = max(1, min(top_n, 20))

        current_year = datetime.now().year
        start_year = current_year - years
        end_year = current_year - 1

        # Fuenf Abfragen parallel fuer maximale Geschwindigkeit
        (
            yearly_data,
            top_assignees_data,
            recent_data,
            cpc_data,
            geo_data,
        ) = await asyncio.gather(
            patent_client.get_patent_counts_by_year(
                query=query, start_year=start_year, end_year=end_year
            ),
            patent_client.get_top_assignees_for_query(query=query, limit=top_n),
            patent_client.search_patents(
                query=query, limit=5, sort_by="patent_date", sort_order="desc"
            ),
            patent_client.get_landscape_cpc_distribution(query=query, limit=10),
            patent_client.get_landscape_country_distribution(query=query, limit=20),
        )

        total_patents = sum(y["patent_count"] for y in yearly_data)

        # Trend
        counts = [y["patent_count"] for y in yearly_data if y["patent_count"] > 0]
        growth_rate = None
        trend = "unbekannt"
        if len(counts) >= 2:
            first_half = sum(counts[: len(counts) // 2])
            second_half = sum(counts[len(counts) // 2 :])
            if first_half > 0:
                growth_rate = round(
                    ((second_half - first_half) / first_half) * 100, 1
                )
                trend = _classify_trend(growth_rate)

        # Peak-Jahr
        peak_year = None
        if yearly_data:
            peak = max(yearly_data, key=lambda y: y["patent_count"])
            if peak["patent_count"] > 0:
                peak_year = {"year": peak["year"], "count": peak["patent_count"]}

        # Top-Player
        top_players = []
        assignees = top_assignees_data.get("assignees", [])
        if assignees:
            for asg in assignees[:top_n]:
                org = asg.get("assignee_organization")
                if org:
                    top_players.append({
                        "company": org,
                        "total_patents": asg.get("assignee_total_num_patents"),
                        "country": asg.get("assignee_country"),
                    })

        # CPC-Verteilung extrahieren
        top_classifications = []
        if cpc_data and cpc_data.get("cpc_subsections"):
            for cpc in cpc_data["cpc_subsections"][:10]:
                cpc_id = cpc.get("cpc_subsection_id")
                if cpc_id:
                    top_classifications.append({
                        "cpc_code": cpc_id,
                        "title": cpc.get("cpc_subsection_title"),
                        "total_patents": cpc.get("cpc_total_num_patents"),
                    })

        # Geografische Verteilung extrahieren
        country_distribution = {}
        if geo_data and geo_data.get("assignees"):
            for asg in geo_data["assignees"]:
                country = asg.get("assignee_country", "Unbekannt")
                if country:
                    country_distribution[country] = country_distribution.get(country, 0) + 1

        # Wettbewerbsintensitaet berechnen
        if len(top_players) >= 2:
            top1 = top_players[0].get("total_patents", 0) or 0
            top2 = top_players[1].get("total_patents", 0) or 0
            if top1 > 0 and top2 > 0:
                ratio = top2 / top1
                if ratio > 0.8:
                    competition = "Sehr hoch — Top-Player nahezu gleichauf"
                elif ratio > 0.5:
                    competition = "Hoch — starker Wettbewerb"
                elif ratio > 0.3:
                    competition = "Mittel — klarer Marktführer, aber Verfolger aktiv"
                else:
                    competition = "Niedrig — dominanter Marktführer"
            else:
                competition = "Nicht bestimmbar"
        else:
            competition = "Wenige Player — Nischenbereich"

        # Neueste Patente
        recent_patents = []
        for p in recent_data.get("patents", [])[:5]:
            recent_patents.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
            })

        # Aktivitaets-Bewertung
        if total_patents == 0:
            activity = "Inaktiv"
        elif total_patents < 100:
            activity = "Geringe Aktivität — Nische oder frühe Technologie"
        elif total_patents < 1000:
            activity = "Moderate Aktivität — wachsender Bereich"
        elif total_patents < 10000:
            activity = "Hohe Aktivität — etabliertes Technologiefeld"
        else:
            activity = "Sehr hohe Aktivität — Mainstream-Technologie"

        return {
            "technology": query,
            "period": f"{start_year}-{end_year}",
            "summary": {
                "total_patents": total_patents,
                "trend": trend,
                "growth_rate_percent": growth_rate,
                "peak_year": peak_year,
                "activity_level": activity,
                "competition_intensity": competition,
            },
            "yearly_breakdown": yearly_data,
            "top_players": top_players,
            "top_ipc_classifications": top_classifications,
            "geographic_distribution": country_distribution or None,
            "recent_patents": recent_patents,
            "analysis_note": _trend_note(trend, query, total_patents),
        }
    except Exception as e:
        return {"error": str(e), "technology": query}


# === Neue Tools v0.3.0 ===


async def search_by_classification(
    ipc_code: str,
    limit: int = 10,
) -> dict:
    """
    Sucht Patente nach IPC/CPC-Klassifikationscode.

    Präzisere Suche als search_by_cpc — nutzt Subgroup-Ebene für
    detaillierte Technologie-Recherchen. Unterstützt alle Ebenen:
    Section (H), Subsection (H04), Group (H04L), Subgroup (H04L9/32).

    Beliebte Codes:
    - H04L: Netzwerktechnik, Datenübertragung
    - A61K: Pharmazeutische Präparate
    - G06N: Computing (ML, AI, Neural Networks)
    - H01L: Halbleiter, integrierte Schaltungen
    - B60W: Fahrzeugsteuerung, autonomes Fahren
    - C12N: Biotechnologie, Mikroorganismen
    - H02J: Energieverteilung, Stromnetze

    Args:
        ipc_code: IPC/CPC-Code, z.B. "H04L" (Netzwerk), "A61K" (Pharma), "G06N20" (ML)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        code = ipc_code.strip().upper()
        if not code:
            return {
                "error": "Kein Klassifikationscode angegeben",
                "hint": "Gib einen IPC/CPC-Code an, z.B. 'H04L' für Netzwerktechnik.",
            }

        data = await patent_client.search_by_classification(
            ipc_code=code, limit=limit
        )

        subsections = data.get("cpc_subsections", [])
        total = data.get("total_cpc_subsection_count", 0)

        if not subsections:
            return {
                "ipc_code": code,
                "total_results": 0,
                "patents": [],
                "hint": (
                    f"Keine Patente für '{code}'. Versuche einen breiteren Code "
                    f"(z.B. '{code[:3]}' statt '{code}') oder prüfe die Schreibweise."
                ),
                "code_examples": {
                    "H04L": "Netzwerktechnik",
                    "A61K": "Pharma",
                    "G06N": "AI/ML",
                    "H01L": "Halbleiter",
                },
            }

        results = []
        seen_patents = set()
        for sub in subsections:
            for p in sub.get("patents", []):
                pn = p.get("patent_number")
                if pn and pn not in seen_patents:
                    seen_patents.add(pn)
                    results.append({
                        "patent_number": pn,
                        "title": p.get("patent_title"),
                        "date": p.get("patent_date"),
                        "abstract": _truncate(p.get("patent_abstract", ""), 200),
                        "assignee": p.get("assignee_organization"),
                        "cpc_group": sub.get("cpc_group_id"),
                        "cpc_subgroup": sub.get("cpc_subgroup_id"),
                        "cpc_title": sub.get("cpc_subsection_title"),
                        "num_claims": p.get("patent_num_claims"),
                    })

        return {
            "ipc_code": code,
            "section": _cpc_section_name(code[0]) if code else "",
            "total_results": total,
            "showing": len(results),
            "patents": results[:limit],
        }
    except Exception as e:
        return {"error": str(e), "ipc_code": ipc_code}


async def get_patent_family(
    patent_number: str,
) -> dict:
    """
    Findet verwandte Patente in derselben Patent-Familie.

    Zeigt Continuations, Divisionals und verwandte Anmeldungen.
    Identifiziert Patente desselben Assignees die dieses Patent
    zitieren oder von ihm zitiert werden — typisch für Patent-Familien.

    Args:
        patent_number: Patent-Nummer, z.B. "11234567" oder "US-11234567"
    """
    try:
        data = await patent_client.get_patent_family(patent_number)
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        # Basis-Patent extrahieren
        base = data.get("base_patent", {})
        patents = base.get("patents", [])
        if not patents:
            return {
                "patent_number": clean_number,
                "error": f"Patent {clean_number} nicht gefunden",
                "hint": "Prüfe die Nummer. Formate: '11234567', 'US-11234567'",
            }

        base_patent = patents[0]
        base_assignee = None
        for asg in base_patent.get("assignees", []):
            org = asg.get("assignee_organization")
            if org:
                base_assignee = org
                break

        # Zitierte Patente sammeln (potenzielle Parent-Patente)
        cited_patents = []
        cited_data = data.get("cited_patents", {})
        if cited_data and cited_data.get("patents"):
            for p in cited_data["patents"]:
                for cited in p.get("cited_patents", []):
                    cat = cited.get("cited_patent_category", "")
                    cited_patents.append({
                        "patent_number": cited.get("cited_patent_number"),
                        "title": cited.get("cited_patent_title"),
                        "date": cited.get("cited_patent_date"),
                        "category": cat,
                        "relationship": _classify_citation_relationship(cat),
                    })

        # Zitierende Patente (potenzielle Continuations/Divisionals)
        family_members = []
        non_family = []
        citing_data = data.get("citing_patents", {})
        if citing_data and citing_data.get("patents"):
            for p in citing_data["patents"]:
                entry = {
                    "patent_number": p.get("patent_number"),
                    "title": p.get("patent_title"),
                    "date": p.get("patent_date"),
                    "type": p.get("patent_type"),
                    "kind": p.get("patent_kind"),
                }

                # Wenn gleicher Assignee: wahrscheinlich Familie
                citing_assignees = [
                    a.get("assignee_organization")
                    for a in p.get("assignees", [])
                    if a.get("assignee_organization")
                ]

                if base_assignee and base_assignee in citing_assignees:
                    entry["assignee"] = base_assignee
                    entry["likely_relationship"] = "Potenzielle Continuation/Divisional (gleicher Assignee)"
                    family_members.append(entry)
                else:
                    entry["assignee"] = citing_assignees[0] if citing_assignees else None
                    non_family.append(entry)

        return {
            "patent_number": clean_number,
            "base_patent": {
                "title": base_patent.get("patent_title"),
                "date": base_patent.get("patent_date"),
                "type": base_patent.get("patent_type"),
                "kind": base_patent.get("patent_kind"),
                "application_number": base_patent.get("app_number"),
                "application_date": base_patent.get("app_date"),
                "assignee": base_assignee,
            },
            "likely_family_members": family_members[:20],
            "family_member_count": len(family_members),
            "parent_patents_cited": cited_patents[:15],
            "other_citing_patents": non_family[:10],
            "analysis": _family_analysis(
                len(family_members), len(cited_patents), len(non_family)
            ),
        }
    except Exception as e:
        return {"error": str(e), "patent_number": patent_number}


async def get_top_patent_holders(
    limit: int = 20,
    sector: str = "",
) -> dict:
    """
    Ranking der Unternehmen nach Patentanzahl.

    Zeigt die größten Patentinhaber, optional gefiltert nach
    Technologie-Sektor. Nützlich für Wettbewerbsanalysen und
    um die dominanten Player in einem Bereich zu identifizieren.

    Verfügbare Sektoren:
    - pharma: Medikamente, Wirkstoffe
    - tech: Software, Computing, Hardware
    - semiconductor: Halbleiter, Chips
    - telecom: Telekommunikation, Netzwerk
    - automotive: Fahrzeuge, Antriebe
    - energy: Energie, Batterien, Solar
    - biotech: Biotechnologie, Gentechnik
    - ai: Künstliche Intelligenz, Machine Learning
    - medical: Medizintechnik, Diagnostik
    - aerospace: Luft- und Raumfahrt

    Args:
        limit: Anzahl Ergebnisse (1-50, Standard: 20)
        sector: Technologie-Sektor zum Filtern (optional)
    """
    try:
        # Sektor auf Suchbegriffe mappen
        sector_queries = {
            "pharma": "pharmaceutical drug compound therapeutic",
            "tech": "computing software algorithm processor",
            "semiconductor": "semiconductor integrated circuit transistor wafer",
            "telecom": "wireless communication network antenna",
            "automotive": "vehicle engine automotive transmission",
            "energy": "battery solar energy power generation",
            "biotech": "biotechnology gene protein enzyme dna",
            "ai": "artificial intelligence machine learning neural network",
            "medical": "medical device surgical diagnostic imaging",
            "aerospace": "aircraft aerospace propulsion satellite",
        }

        sector_query = None
        if sector and sector.lower() in sector_queries:
            sector_query = sector_queries[sector.lower()]
        elif sector:
            # Unbekannter Sektor — als freien Suchbegriff nutzen
            sector_query = sector

        data = await patent_client.get_top_patent_holders(
            limit=limit, sector_query=sector_query
        )

        assignees = data.get("assignees", [])
        total = data.get("total_assignee_count", 0)

        if not assignees:
            return {
                "sector": sector or "Alle",
                "total_results": 0,
                "holders": [],
                "hint": f"Keine Patentinhaber gefunden für Sektor '{sector}'.",
                "available_sectors": list(sector_queries.keys()),
            }

        holders = []
        for i, asg in enumerate(assignees, 1):
            org = asg.get("assignee_organization")
            if org:
                holders.append({
                    "rank": i,
                    "company": org,
                    "total_patents": asg.get("assignee_total_num_patents"),
                    "country": asg.get("assignee_country"),
                    "type": _assignee_type(asg.get("assignee_type")),
                })

        return {
            "sector": sector or "Alle Sektoren",
            "total_assignees_found": total,
            "showing": len(holders),
            "top_holders": holders,
            "available_sectors": list(sector_queries.keys()) if not sector else None,
        }
    except Exception as e:
        return {"error": str(e), "sector": sector}


async def analyze_patent_landscape(
    query: str,
    years: int = 5,
) -> dict:
    """
    Umfassende Landschaftsanalyse für einen Technologiebereich.

    Analysiert parallel: Top-Assignees, Anmeldetrends pro Jahr,
    Top-IPC/CPC-Codes, geografische Verteilung und Wettbewerbsintensität.
    Gibt eine strukturierte Analyse zurück — ideal für Reports und
    strategische Entscheidungen.

    Unterschied zu get_patent_landscape: Fokussiert auf strukturierte
    Analyse-Insights statt Rohdaten. Gibt Handlungsempfehlungen.

    Args:
        query: Technologie-Suchbegriff, z.B. "quantum computing", "CRISPR gene editing"
        years: Analysezeitraum in Jahren (1-20, Standard: 5)
    """
    try:
        years = max(1, min(years, 20))
        current_year = datetime.now().year
        start_year = current_year - years
        end_year = current_year - 1

        # Fuenf parallele Abfragen fuer maximale Geschwindigkeit
        (
            yearly_data,
            top_assignees_data,
            recent_data,
            cpc_data,
            geo_data,
        ) = await asyncio.gather(
            patent_client.get_patent_counts_by_year(
                query=query, start_year=start_year, end_year=end_year
            ),
            patent_client.get_top_assignees_for_query(query=query, limit=15),
            patent_client.search_patents(
                query=query, limit=10, sort_by="patent_date", sort_order="desc"
            ),
            patent_client.get_landscape_cpc_distribution(query=query, limit=10),
            patent_client.get_landscape_country_distribution(query=query, limit=20),
        )

        total_patents = sum(y["patent_count"] for y in yearly_data)

        # Trend-Berechnung
        counts = [y["patent_count"] for y in yearly_data if y["patent_count"] > 0]
        growth_rate = None
        trend = "unbekannt"
        if len(counts) >= 2:
            first_half = sum(counts[: len(counts) // 2])
            second_half = sum(counts[len(counts) // 2 :])
            if first_half > 0:
                growth_rate = round(
                    ((second_half - first_half) / first_half) * 100, 1
                )
                trend = _classify_trend(growth_rate)

        # Peak-Jahr
        peak_year = None
        if yearly_data:
            peak = max(yearly_data, key=lambda y: y["patent_count"])
            if peak["patent_count"] > 0:
                peak_year = {"year": peak["year"], "count": peak["patent_count"]}

        # Top-Assignees
        top_assignees = []
        assignees = top_assignees_data.get("assignees", [])
        total_top_patents = 0
        if assignees:
            for asg in assignees[:15]:
                org = asg.get("assignee_organization")
                pat_count = asg.get("assignee_total_num_patents", 0) or 0
                if org:
                    top_assignees.append({
                        "company": org,
                        "total_patents": pat_count,
                        "country": asg.get("assignee_country"),
                    })
                    total_top_patents += pat_count

        # CPC-Verteilung
        ipc_distribution = []
        if cpc_data and cpc_data.get("cpc_subsections"):
            for cpc in cpc_data["cpc_subsections"][:10]:
                cpc_id = cpc.get("cpc_subsection_id")
                if cpc_id:
                    ipc_distribution.append({
                        "code": cpc_id,
                        "title": cpc.get("cpc_subsection_title"),
                        "total_patents": cpc.get("cpc_total_num_patents"),
                    })

        # Geografische Verteilung
        geo_distribution = {}
        if geo_data and geo_data.get("assignees"):
            for asg in geo_data["assignees"]:
                country = asg.get("assignee_country", "Unbekannt")
                if country:
                    geo_distribution[country] = geo_distribution.get(country, 0) + 1

        # Top-3-Laender
        top_countries = sorted(
            geo_distribution.items(), key=lambda x: x[1], reverse=True
        )[:5]

        # Wettbewerbsanalyse
        concentration = "Nicht bestimmbar"
        if len(top_assignees) >= 2:
            top1 = top_assignees[0].get("total_patents", 0) or 0
            top2 = top_assignees[1].get("total_patents", 0) or 0
            if top1 > 0:
                ratio = top2 / top1
                if ratio > 0.8:
                    concentration = "Fragmentiert — kein klarer Marktführer"
                elif ratio > 0.5:
                    concentration = "Wettbewerbsintensiv — mehrere starke Player"
                elif ratio > 0.3:
                    concentration = "Moderate Konzentration — Marktführer erkennbar"
                else:
                    concentration = "Hoch konzentriert — dominanter Player"

        # Neueste Patente
        latest = []
        for p in recent_data.get("patents", [])[:5]:
            latest.append({
                "patent_number": p.get("patent_number"),
                "title": p.get("patent_title"),
                "date": p.get("patent_date"),
            })

        # Handlungsempfehlungen generieren
        insights = _generate_landscape_insights(
            trend, growth_rate, total_patents, len(top_assignees), concentration
        )

        return {
            "technology": query,
            "period": f"{start_year}-{end_year}",
            "filing_trends": {
                "total_patents": total_patents,
                "trend": trend,
                "growth_rate_percent": growth_rate,
                "peak_year": peak_year,
                "yearly_breakdown": yearly_data,
            },
            "top_assignees": top_assignees,
            "market_concentration": concentration,
            "top_ipc_codes": ipc_distribution,
            "geographic_distribution": {
                "top_countries": [{"country": c, "assignees": n} for c, n in top_countries],
                "all_countries": geo_distribution or None,
            },
            "latest_patents": latest,
            "strategic_insights": insights,
        }
    except Exception as e:
        return {"error": str(e), "technology": query}


async def get_patent_claims(
    patent_number: str,
) -> dict:
    """
    Extrahiert die Patentansprüche (Claims) eines Patents.

    Claims sind der rechtlich bindende Teil eines Patents und definieren
    den Schutzumfang. Claim 1 ist typischerweise der breiteste Anspruch
    (Independent Claim), die folgenden sind abhängige Ansprüche.

    Args:
        patent_number: Patent-Nummer, z.B. "11234567" oder "US-11234567"
    """
    try:
        data = await patent_client.get_patent_claims(patent_number)
        clean_number = patent_number.strip().replace("-", "").replace(" ", "")

        patents = data.get("patents", [])
        if not patents:
            return {
                "patent_number": clean_number,
                "error": f"Patent {clean_number} nicht gefunden oder keine Claims verfügbar",
                "hint": "PatentsView stellt nicht für alle Patente Claims bereit. Ältere Patente haben oft keine digitalen Claims.",
            }

        patent = patents[0]
        claims_raw = patent.get("claims", [])

        # Claims sortieren und formatieren
        claims = []
        independent_claims = []
        dependent_claims = []

        for claim in claims_raw:
            text = claim.get("claim_text", "").strip()
            num = claim.get("claim_number")
            seq = claim.get("claim_sequence")

            if not text:
                continue

            # Unabhaengige Claims erkennen (beginnen nicht mit "The X of claim Y")
            is_independent = not any(
                phrase in text.lower()[:100]
                for phrase in ["of claim", "according to claim", "as claimed in"]
            )

            entry = {
                "claim_number": num or seq,
                "text": text,
                "type": "independent" if is_independent else "dependent",
            }

            claims.append(entry)
            if is_independent:
                independent_claims.append(entry)
            else:
                dependent_claims.append(entry)

        if not claims:
            return {
                "patent_number": clean_number,
                "title": patent.get("patent_title"),
                "total_claims": patent.get("patent_num_claims"),
                "claims": [],
                "hint": "Keine Claim-Texte verfügbar. Claims sind in PatentsView nicht für alle Patente digitalisiert.",
            }

        return {
            "patent_number": clean_number,
            "title": patent.get("patent_title"),
            "grant_date": patent.get("patent_date"),
            "total_claims_reported": patent.get("patent_num_claims"),
            "claims_retrieved": len(claims),
            "independent_claim_count": len(independent_claims),
            "dependent_claim_count": len(dependent_claims),
            "claims": claims,
            "broadest_claim": independent_claims[0] if independent_claims else None,
            "analysis_hint": (
                f"Patent hat {len(independent_claims)} unabhängige und "
                f"{len(dependent_claims)} abhängige Ansprüche. "
                "Der erste unabhängige Claim definiert den breitesten Schutzumfang."
            ),
        }
    except Exception as e:
        return {"error": str(e), "patent_number": patent_number}


# === Hilfsfunktionen ===


def _truncate(text: str, max_len: int) -> str:
    """Kürzt Text auf maximale Länge."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def _build_location(*parts: str | None) -> str:
    """Baut Ortsangabe aus Teilen zusammen."""
    return ", ".join(p for p in parts if p)


def _assignee_type(type_code: str | None) -> str:
    """Übersetzt Assignee-Type-Code in lesbaren Text."""
    types = {
        "1": "Unternehmen (US)",
        "2": "Unternehmen (International)",
        "3": "Person (US)",
        "4": "Person (International)",
        "5": "US-Regierung",
        "6": "Internationale Regierung",
        "7": "Behörde/Land",
        "8": "Behörde/Stadt",
        "9": "Behörde/Kreis",
    }
    return types.get(str(type_code), f"Typ {type_code}")


def _citation_impact(times_cited: int) -> str:
    """Bewertet den Impact anhand der Zitationshäufigkeit."""
    if times_cited == 0:
        return "Noch keine Zitationen — möglicherweise neues Patent"
    elif times_cited < 5:
        return "Wenige Zitationen — normaler Impact"
    elif times_cited < 20:
        return "Moderate Zitationszahl — relevantes Patent"
    elif times_cited < 50:
        return "Viele Zitationen — einflussreiches Patent"
    else:
        return f"Sehr einflussreich — {times_cited} Zitationen, Schlüsselpatent im Bereich"


def _citation_impact_score(times_cited: int) -> str:
    """Gibt einen numerischen Impact-Score (1-5)."""
    if times_cited == 0:
        return "1/5"
    elif times_cited < 5:
        return "2/5"
    elif times_cited < 20:
        return "3/5"
    elif times_cited < 50:
        return "4/5"
    else:
        return "5/5"


def _classify_trend(growth_rate: float) -> str:
    """Klassifiziert einen Trend anhand der Wachstumsrate."""
    if growth_rate > 20:
        return "stark wachsend"
    elif growth_rate > 5:
        return "wachsend"
    elif growth_rate > -5:
        return "stabil"
    elif growth_rate > -20:
        return "rückläufig"
    else:
        return "stark rückläufig"


def _trend_note(trend: str, query: str, total: int) -> str:
    """Erstellt eine kurze Zusammenfassung des Trends."""
    if total == 0:
        return f"Keine Patentdaten für '{query}'. USPTO-Daten haben 1-2 Jahre Verzögerung."
    return (
        f"Technologiebereich '{query}' zeigt {trend}en Trend "
        f"mit insgesamt {total:,} Patenten im Analysezeitraum."
    )


def _cpc_section_name(section: str) -> str:
    """Gibt den CPC-Sektionsnamen zurück."""
    sections = {
        "A": "Lebensnotwendiges (Pharma, Medizin, Landwirtschaft)",
        "B": "Verfahrenstechnik, Transport",
        "C": "Chemie, Metallurgie",
        "D": "Textilien, Papier",
        "E": "Bauwesen",
        "F": "Maschinenbau, Beleuchtung, Heizung, Waffen",
        "G": "Physik (Computing, Optik, Messtechnik)",
        "H": "Elektrotechnik (Halbleiter, Telekommunikation)",
        "Y": "Neue technologische Entwicklungen (Querschnitt)",
    }
    return sections.get(section, f"Sektion {section}")


def _classify_citation_relationship(category: str) -> str:
    """Klassifiziert die Beziehung basierend auf der Zitationskategorie."""
    if not category:
        return "Unbekannt"
    cat = category.lower()
    if "cited by examiner" in cat:
        return "Vom Prüfer zitiert"
    elif "cited by applicant" in cat:
        return "Vom Anmelder zitiert (mögliche Familie)"
    elif "cited" in cat:
        return "Zitiert"
    return category


def _family_analysis(
    family_count: int, cited_count: int, other_count: int
) -> str:
    """Erstellt eine Analyse der Patent-Familie."""
    if family_count == 0 and cited_count == 0:
        return "Keine verwandten Patente identifiziert. Das Patent steht möglicherweise allein."
    parts = []
    if family_count > 0:
        parts.append(
            f"{family_count} potenzielle Familienmitglieder (gleicher Assignee) gefunden"
        )
    if cited_count > 0:
        parts.append(f"{cited_count} zitierte Parent-Patente")
    if other_count > 0:
        parts.append(f"{other_count} weitere zitierende Patente anderer Inhaber")
    return ". ".join(parts) + "."


def _generate_landscape_insights(
    trend: str,
    growth_rate: float | None,
    total_patents: int,
    num_players: int,
    concentration: str,
) -> list[str]:
    """Generiert strategische Insights basierend auf der Landschaftsanalyse."""
    insights = []

    # Trend-basierte Insights
    if trend == "stark wachsend":
        insights.append(
            "Stark wachsender Bereich — früher Einstieg kann First-Mover-Advantage sichern."
        )
    elif trend == "wachsend":
        insights.append(
            "Wachsender Bereich — gute Möglichkeiten für Patentanmeldungen vorhanden."
        )
    elif trend == "stabil":
        insights.append(
            "Stabiler, reifer Bereich — Fokus auf Differenzierung und Nischen empfohlen."
        )
    elif trend in ("rückläufig", "stark rückläufig"):
        insights.append(
            "Rückläufiger Bereich — Vorsicht bei Investitionen, Technologie könnte abgelöst werden."
        )

    # Volumen-basierte Insights
    if total_patents > 10000:
        insights.append(
            "Hochaktives Feld mit starkem Wettbewerb — präzise Nischen-Strategie wichtig."
        )
    elif total_patents < 100:
        insights.append(
            "Nischenbereich mit wenig Patentaktivität — kann Chance oder fehlendes Marktinteresse bedeuten."
        )

    # Wettbewerbs-Insights
    if "Hoch konzentriert" in concentration:
        insights.append(
            "Ein dominanter Player — schwierig als Newcomer, Lizenzierung prüfen."
        )
    elif "Fragmentiert" in concentration:
        insights.append(
            "Fragmentierter Markt — gute Chancen durch Konsolidierung oder Spezialisierung."
        )

    if not insights:
        insights.append("Standardmäßige Patentaktivität — detaillierte Analyse empfohlen.")

    return insights

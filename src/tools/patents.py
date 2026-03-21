"""
MCP-Tools für Patent-Intelligence.
6 Tools: Suche, Details, Erfinder, Assignee, Zitationen, Trends.
"""

from datetime import datetime

from src.clients.patents import patent_client


async def search_patents(
    query: str, country: str = "US", limit: int = 10
) -> dict:
    """
    Sucht Patente nach Stichwörtern.

    Durchsucht Titel und Abstract von US-Patenten.
    Gibt Patent-Nummer, Titel, Datum und Abstract zurück.

    Args:
        query: Suchbegriff(e), z.B. "machine learning", "battery electrode"
        country: Ländercode (aktuell nur "US" unterstützt via PatentsView)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        data = await patent_client.search_patents(query=query, limit=limit)

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            return {
                "query": query,
                "country": country,
                "total_results": 0,
                "patents": [],
                "message": f"Keine Patente gefunden für '{query}'",
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

        return {
            "query": query,
            "country": country,
            "total_results": total,
            "showing": len(results),
            "patents": results,
        }
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
            "assignees": assignees,
            "cpc_classifications": classifications[:10],
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
                "message": f"Keine Patente gefunden für Erfinder '{inventor_name}'",
            }

        results = []
        for p in patents:
            # Erfindernamen aus dem Patent extrahieren
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
                "message": f"Keine Patente gefunden für '{company_name}'",
            }

        results = []
        for p in patents:
            # Assignee-Namen extrahieren
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

    Args:
        patent_number: Patent-Nummer, z.B. "11234567"
    """
    try:
        data = await patent_client.get_patent_citations(patent_number)

        # Zitierte Patente verarbeiten
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

        # Zitierende Patente verarbeiten
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

    Args:
        query: Technologie-Suchbegriff, z.B. "quantum computing", "CRISPR"
        years: Analysezeitraum in Jahren (1-20, Standard: 5)
    """
    try:
        current_year = datetime.now().year
        start_year = current_year - years
        # PatentsView hat Daten bis ca. 1-2 Jahre vor heute
        end_year = current_year - 1

        # Jahreszahlen abrufen
        yearly_data = await patent_client.get_patent_counts_by_year(
            query=query, start_year=start_year, end_year=end_year
        )

        # Top-Assignees für diese Technologie
        top_assignees_data = await patent_client.get_top_assignees_for_query(
            query=query, limit=10
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
                if growth_rate > 20:
                    trend = "stark wachsend"
                elif growth_rate > 5:
                    trend = "wachsend"
                elif growth_rate > -5:
                    trend = "stabil"
                elif growth_rate > -20:
                    trend = "rückläufig"
                else:
                    trend = "stark rückläufig"

        total_patents = sum(y["patent_count"] for y in yearly_data)

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
            "yearly_breakdown": yearly_data,
            "top_assignees": top_companies,
            "analysis_note": _trend_note(trend, query, total_patents),
        }
    except Exception as e:
        return {"error": str(e), "technology": query}


# --- Hilfsfunktionen ---


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


def _trend_note(trend: str, query: str, total: int) -> str:
    """Erstellt eine kurze Zusammenfassung des Trends."""
    if total == 0:
        return f"Keine Patentdaten gefunden für '{query}'. Prüfe den Suchbegriff."
    return (
        f"Technologiebereich '{query}' zeigt {trend}en Trend "
        f"mit insgesamt {total:,} Patenten im Analysezeitraum."
    )

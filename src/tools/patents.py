"""
MCP-Tools für Patent-Intelligence.
v0.2.0: 10 Tools — Suche, Details, Erfinder, Assignee, Zitationen,
Trends, CPC-Suche, Datumssuche, Portfolio-Vergleich, Technologie-Landschaft.
"""

from datetime import datetime

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
        import asyncio
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
) -> dict:
    """
    Sucht die neuesten Patente in einem Technologiebereich.

    Fokussiert auf kürzlich erteilte Patente. Nützlich um aktuelle
    Innovationen und neue Entwicklungen zu finden.

    Args:
        query: Technologie-Suchbegriff, z.B. "autonomous driving", "mRNA vaccine"
        days: Zeitraum in Tagen zurück (Standard: 90, Max: 730)
        limit: Maximale Anzahl Ergebnisse (1-50, Standard: 10)
    """
    try:
        days = max(1, min(days, 730))
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        date_from = start_date.strftime("%Y-%m-%d")
        date_to = end_date.strftime("%Y-%m-%d")

        data = await patent_client.search_patents(
            query=query,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            sort_by="patent_date",
            sort_order="desc",
        )

        patents = data.get("patents", [])
        total = data.get("total_patent_count", 0)

        if not patents:
            return {
                "query": query,
                "period": f"Letzte {days} Tage ({date_from} bis {date_to})",
                "total_results": 0,
                "patents": [],
                "hint": f"Keine neuen Patente für '{query}' in den letzten {days} Tagen. USPTO-Daten haben oft 1-2 Jahre Verzögerung.",
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
            "query": query,
            "period": f"Letzte {days} Tage ({date_from} bis {date_to})",
            "total_results": total,
            "showing": len(results),
            "patents": results,
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
        import asyncio
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
    Erstellt eine Technologie-Landschaft für einen Bereich.

    Kombiniert Trend-Analyse, Top-Player, Aktivitäts-Heatmap
    und Wettbewerbsintensität zu einem Gesamtbild.
    Ideal für strategische Patent-Recherche und Marktanalysen.

    Args:
        query: Technologie-Suchbegriff, z.B. "solid state battery", "gene therapy"
        years: Analysezeitraum in Jahren (1-20, Standard: 5)
        top_n: Anzahl Top-Unternehmen (1-20, Standard: 10)
    """
    try:
        years = max(1, min(years, 20))
        top_n = max(1, min(top_n, 20))
        import asyncio

        current_year = datetime.now().year
        start_year = current_year - years
        end_year = current_year - 1

        # Drei Abfragen parallel
        yearly_data, top_assignees_data, recent_data = await asyncio.gather(
            patent_client.get_patent_counts_by_year(
                query=query, start_year=start_year, end_year=end_year
            ),
            patent_client.get_top_assignees_for_query(query=query, limit=top_n),
            patent_client.search_patents(
                query=query, limit=5, sort_by="patent_date", sort_order="desc"
            ),
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
            "recent_patents": recent_patents,
            "analysis_note": _trend_note(trend, query, total_patents),
        }
    except Exception as e:
        return {"error": str(e), "technology": query}


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

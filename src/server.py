"""
Patent Intelligence MCP Server v0.3.0.
Gibt AI-Agents Zugriff auf US-Patentdaten über die USPTO PatentsView API.
16 Tools: Suche, Details, Erfinder, Assignee, Zitationen, Trends,
CPC-Suche, Neueste Patente, Portfolio-Vergleich, Technologie-Landschaft,
IPC/CPC-Klassifikation, Patent-Familien, Top-Holder, Claims,
Landschaftsanalyse mit Insights, kategoriebasierte Monitoring.
"""

from mcp.server.fastmcp import FastMCP

from src.tools.patents import (
    search_patents,
    get_patent_details,
    search_by_inventor,
    search_by_assignee,
    get_patent_citations,
    analyze_technology_trends,
    search_by_cpc,
    search_recent_patents,
    compare_portfolios,
    get_patent_landscape,
    # Neue Tools v0.3.0
    search_by_classification,
    get_patent_family,
    get_top_patent_holders,
    analyze_patent_landscape,
    get_patent_claims,
)

# Server erstellen
mcp = FastMCP(
    "Patent Intelligence",
    instructions=(
        "Gibt AI-Agents Zugriff auf US-Patentdaten: "
        "Patent-Suche, Erfinder-Lookup, Firmen-Portfolios, "
        "Zitationsnetzwerke, Technologie-Trendanalysen, IPC/CPC-Klassifikationssuche, "
        "Patent-Familien, Patentansprüche (Claims), Top-Patentinhaber-Rankings, "
        "Portfolio-Vergleiche, Technologie-Landschaften und strategische Landschaftsanalysen. "
        "16 Tools für umfassende Patent-Intelligence. "
        "Nutzt die kostenlose USPTO PatentsView API."
    ),
)

# --- Tools registrieren ---

# Kern-Suche
mcp.tool()(search_patents)
mcp.tool()(get_patent_details)
mcp.tool()(search_by_inventor)
mcp.tool()(search_by_assignee)
mcp.tool()(get_patent_citations)
mcp.tool()(analyze_technology_trends)

# Tools v0.2.0
mcp.tool()(search_by_cpc)
mcp.tool()(search_recent_patents)
mcp.tool()(compare_portfolios)
mcp.tool()(get_patent_landscape)

# Neue Tools v0.3.0
mcp.tool()(search_by_classification)
mcp.tool()(get_patent_family)
mcp.tool()(get_top_patent_holders)
mcp.tool()(analyze_patent_landscape)
mcp.tool()(get_patent_claims)


def main():
    """Startet den MCP-Server über stdio-Transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

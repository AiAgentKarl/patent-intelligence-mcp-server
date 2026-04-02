"""
Patent Intelligence MCP Server v0.2.0.
Gibt AI-Agents Zugriff auf US-Patentdaten über die USPTO PatentsView API.
10 Tools: Suche, Details, Erfinder, Assignee, Zitationen, Trends,
CPC-Suche, Neueste Patente, Portfolio-Vergleich, Technologie-Landschaft.
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
)

# Server erstellen
mcp = FastMCP(
    "Patent Intelligence",
    instructions=(
        "Gibt AI-Agents Zugriff auf US-Patentdaten: "
        "Patent-Suche (mit Datumsfilter), Erfinder-Lookup, Firmen-Portfolios, "
        "Zitationsnetzwerke, Technologie-Trendanalysen, CPC-Klassifikations-Suche, "
        "Portfolio-Vergleiche und Technologie-Landschaften. "
        "10 Tools für umfassende Patent-Intelligence. "
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

# Neue Tools v0.2.0
mcp.tool()(search_by_cpc)
mcp.tool()(search_recent_patents)
mcp.tool()(compare_portfolios)
mcp.tool()(get_patent_landscape)


def main():
    """Startet den MCP-Server über stdio-Transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

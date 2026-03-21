"""
Patent Intelligence MCP Server.
Gibt AI-Agents Zugriff auf US-Patentdaten über die USPTO PatentsView API.
"""

from mcp.server.fastmcp import FastMCP

from src.tools.patents import (
    search_patents,
    get_patent_details,
    search_by_inventor,
    search_by_assignee,
    get_patent_citations,
    analyze_technology_trends,
)

# Server erstellen
mcp = FastMCP(
    "Patent Intelligence",
    instructions=(
        "Gibt AI-Agents Zugriff auf US-Patentdaten: "
        "Patent-Suche, Erfinder-Lookup, Firmen-Portfolios, "
        "Zitationsnetzwerke und Technologie-Trendanalysen. "
        "Nutzt die kostenlose USPTO PatentsView API."
    ),
)

# --- Tools registrieren ---

mcp.tool()(search_patents)
mcp.tool()(get_patent_details)
mcp.tool()(search_by_inventor)
mcp.tool()(search_by_assignee)
mcp.tool()(get_patent_citations)
mcp.tool()(analyze_technology_trends)


def main():
    """Startet den MCP-Server über stdio-Transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

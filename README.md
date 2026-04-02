# Patent Intelligence MCP Server

<!-- mcp-name: patent-intelligence-mcp-server -->

[![PyPI version](https://badge.fury.io/py/patent-intelligence-mcp-server.svg)](https://pypi.org/project/patent-intelligence-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

MCP server that gives AI agents access to US patent data. **10 tools** for patent search, citation networks, technology trend analysis, CPC classification lookup, company portfolio comparison, and technology landscape mapping — all through the free USPTO PatentsView API.

## Features

| Tool | Description |
|------|-------------|
| `search_patents` | Search patents by keyword with optional date range filter |
| `get_patent_details` | Full patent details: inventors, assignees, CPC classifications |
| `search_by_inventor` | Find all patents by a specific inventor |
| `search_by_assignee` | Find all patents owned by a company or organization |
| `get_patent_citations` | Citation networks with impact scoring |
| `analyze_technology_trends` | Patent filing trends over time with growth rates |
| `search_by_cpc` | Search by CPC classification code (e.g. G06N for AI/ML) |
| `search_recent_patents` | Find the newest patents in a technology area |
| `compare_portfolios` | Head-to-head comparison of two companies' patent portfolios |
| `get_patent_landscape` | Full technology landscape: trends, top players, competition intensity |

### What's New in v0.2.0

- **4 new tools**: CPC search, recent patents, portfolio comparison, technology landscape
- **Parallel API requests**: Trend analysis and patent details are now 3-5x faster
- **In-memory caching**: Repeated queries return instantly (10-minute TTL)
- **Date range filters**: Search patents within specific time periods
- **Impact scoring**: Citation analysis now includes numerical impact scores
- **Better error messages**: Helpful hints when no results are found

## Installation

```bash
pip install patent-intelligence-mcp-server
```

## Quick Start

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "patents": {
      "command": "patent-server"
    }
  }
}
```

### Claude Code CLI

```bash
claude mcp add patents -- patent-server
```

### Direct Usage

```bash
patent-server
```

## Example Queries

Once connected, your AI agent can answer questions like:

**Basic Search:**
- "Search for recent patents about quantum computing"
- "Show me details for patent US-11234567"
- "What patents has Elon Musk filed?"
- "Find all Tesla patents"

**Advanced Analysis:**
- "Compare Apple's and Samsung's patent portfolios over 5 years"
- "Show me the technology landscape for solid state batteries"
- "Find patents in CPC class G06N (machine learning)"
- "Show the newest patents about mRNA vaccines from the last 6 months"
- "Analyze patent trends in CRISPR technology over 10 years"
- "How does Google's patent portfolio compare to Microsoft's?"

## CPC Classification Codes

Common codes for the `search_by_cpc` tool:

| Code | Area |
|------|------|
| `G06N` | Machine Learning / AI |
| `G06F` | Digital Data Processing |
| `H01L` | Semiconductor Devices |
| `H04` | Telecommunications |
| `A61K` | Pharmaceuticals |
| `C12N` | Biotechnology |
| `B60` | Vehicles |
| `F03D` | Wind Turbines |

## API Source

**USPTO PatentsView API** — Free, no API key required. Covers all US patents with full metadata, inventors, assignees, citations, and CPC classifications.

## Configuration

Optional environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PATENT_HTTP_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `PATENT_DEFAULT_LIMIT` | `10` | Default number of results |
| `PATENT_MAX_LIMIT` | `50` | Maximum results per query |
| `PATENT_CACHE_ENABLED` | `true` | Enable/disable response caching |
| `PATENT_CACHE_TTL` | `600` | Cache time-to-live in seconds |

## Performance

v0.2.0 includes significant performance improvements:

- **Parallel requests**: Patent details fetch 4 data sources simultaneously instead of sequentially
- **Trend analysis**: Year-by-year queries run in parallel (5-year analysis: ~1 request time instead of ~5)
- **In-memory caching**: Repeated queries return from cache (256 entries, 10-minute TTL)

## Related MCP Servers

- [cybersecurity-mcp-server](https://pypi.org/project/cybersecurity-mcp-server/) — CVE and vulnerability data
- [eu-company-mcp-server](https://pypi.org/project/eu-company-mcp-server/) — EU company data
- [legal-court-mcp-server](https://pypi.org/project/legal-court-mcp-server/) — US court data

## Development

```bash
git clone https://github.com/AiAgentKarl/patent-intelligence-mcp-server.git
cd patent-intelligence-mcp-server
pip install -e .
patent-server
```

## License

MIT

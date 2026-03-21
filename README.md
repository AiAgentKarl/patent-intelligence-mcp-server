# Patent Intelligence MCP Server

<!-- mcp-name: patent-intelligence-mcp-server -->

[![PyPI version](https://badge.fury.io/py/patent-intelligence-mcp-server.svg)](https://pypi.org/project/patent-intelligence-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

MCP server that gives AI agents access to US patent data. Search patents, explore citation networks, analyze technology trends, and research company portfolios — all through the free USPTO PatentsView API.

## Features

| Tool | Description |
|------|-------------|
| `search_patents` | Search patents by keyword across titles and abstracts |
| `get_patent_details` | Get full patent details including inventors, assignees, and CPC classification |
| `search_by_inventor` | Find all patents by a specific inventor |
| `search_by_assignee` | Find all patents owned by a company or organization |
| `get_patent_citations` | Explore citation networks — who cites whom |
| `analyze_technology_trends` | Patent filing trends over time with top assignees |

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

## API Sources

- **USPTO PatentsView API** — Free, no API key required. Covers all US patents with full metadata, inventors, assignees, citations, and CPC classifications.

## Example Queries

Once connected, your AI agent can answer questions like:

- "Search for recent patents about quantum computing"
- "Show me details for patent US-11234567"
- "What patents has Elon Musk filed?"
- "Find all Tesla patents from the last year"
- "Show the citation network for patent 10987654"
- "Analyze patent trends in CRISPR technology over 10 years"

## Configuration

Optional environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PATENT_HTTP_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `PATENT_DEFAULT_LIMIT` | `10` | Default number of results |
| `PATENT_MAX_LIMIT` | `50` | Maximum results per query |

## Rate Limits

The USPTO PatentsView API is free with no API key required. Be respectful with request frequency.

## Development

```bash
git clone https://github.com/AiAgentKarl/patent-intelligence-mcp-server.git
cd patent-intelligence-mcp-server
pip install -e .
patent-server
```

## License

MIT

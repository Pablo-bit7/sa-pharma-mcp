# ZA Pharma Intelligence — MCP Server

A high-performance Model Context Protocol (MCP) server that aggregates, normalizes, and exposes South African pharmaceutical regulatory and procurement data through structured AI-callable tools.

---

## Overview

South Africa's pharmaceutical landscape spans two distinct markets: a public sector driven by state tenders and a private sector governed by Single Exit Pricing (SEP) regulation. The data underpinning both is publicly available but scattered across siloed government portals in inconsistent formats.

**ZA Pharma Intelligence** serves as a unified intelligence layer. It connects to live endpoints from SAHPRA (South African Health Products Regulatory Authority) and the National Department of Health (NDoH), normalizes data at runtime, and exposes it through a clean set of AI-callable tools. This enables LLM-powered agents to conduct complex, domain-specific analysis — such as cross-referencing tender awards against manufacturing licenses — using real-time, authoritative data.

---

## Key Features

### Tools

| Tool | Description |
|---|---|
| `get_licensed_companies` | Retrieves official SAHPRA establishment lists across 10 license categories (Manufacturers, API Producers, etc.) |
| `search_sahpra_products` | Searches the SAHPRA registered medicine database by company name, returning product portfolio and registration metadata |
| `analyse_ndoh_market` | Analyzes the NDoH Master Health Product List (MHPL) for contract values, supplier share, and tender pipeline |
| `analyse_private_market` | Analyzes the Database of Medicine Prices (MPR/SEP) for private sector pricing competitiveness and applicant market presence |

### Prompts (Agentic Workflows)

Pre-built templates that chain tools into structured multi-step analyses:

- **`supplier_integrity_audit`** — Cross-references a supplier's tender footprint against their SAHPRA license status.
- **`therapeutic_category_assessment`** — Identifies market concentration and supply chain risk within specific ATC drug classes.
- **`market_entry_scouting`** — Evaluates the public sector opportunity for new generic product launches.
- **`private_market_disruption_scouting`** — Locates pricing gaps in the private SEP landscape for competitive entry.
- **`cross_market_viability_check`** — Compares state tender pricing against private SEP to assess dual-market margin viability.

---

## Tech Stack

- **Python 3.11+** — Core runtime
- **FastMCP** — MCP server framework (`mcp.server.fastmcp`)
- **uv** — High-performance dependency manager and runtime
- **httpx** — Asynchronous HTTP client for upstream data retrieval
- **pandas** — Data normalization, filtering, and aggregation
- **openpyxl / xlrd** — High-speed Excel parsing for NDoH and MPR source files

---

## Usage

### 1. Installation & Setup

We use **uv** for lightning-fast dependency management and environment isolation.

```bash
# Clone the repository
git clone https://github.com/your-username/za-pharma-mcp
cd za-pharma-mcp

# Sync environment and dependencies
uv sync
```

### 2. Development & Testing

To launch the **FastMCP Inspector** and test tools and prompts visually in your browser:

```bash
uv run fastmcp dev server.py
```

### 3. Integration with Claude Desktop

Add the following to your `claude_desktop_config.json` to enable the pharma intelligence tools:

```json
{
  "mcpServers": {
    "za-pharma": {
      "command": "uv",
      "args": [
        "run",
        "--path",
        "/absolute/path/to/project",
        "fastmcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

### 4. Deployment (SSE Transport)

To run the server as a stateless HTTP service (e.g., for **n8n** integration or a custom UI):

```bash
PORT=8080 uv run fastmcp run server.py --transport sse
```

---

## Future Roadmap

- **Vector Migration** — Transition to a RAG-based vector store for longitudinal trend analysis.
- **Proactive Refresh** — Scheduled background refresh of caches to eliminate cold-start latency.

---

## Author

**Paballo Mogane**  
Junior Python Developer | Automation Engineer

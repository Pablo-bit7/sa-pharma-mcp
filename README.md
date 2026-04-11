# ZA Pharma Intelligence — MCP Server

A stateless Model Context Protocol (MCP) server that aggregates, normalises, and exposes South African pharmaceutical regulatory and procurement data through structured AI-callable tools.

---

## Overview

South Africa's pharmaceutical landscape spans two distinct markets — a public sector driven by state tenders, and a private sector governed by Single Exit Pricing (SEP) regulation. The data underpinning both markets is publicly available but scattered across multiple government portals in inconsistent formats.

**ZA Pharma Intelligence** solves this by acting as a unified intelligence layer. It connects to live public endpoints from SAHPRA (South African Health Products Regulatory Authority) and the National Department of Health (NDoH), normalises the data at runtime, and exposes it through a clean set of AI-callable tools via the MCP protocol. This enables LLM-powered agents to answer complex, domain-specific questions about market structure, supplier presence, and pricing dynamics — using real, authoritative data.

---

## Key Features

### Tools

| Tool | Description |
|---|---|
| `get_licensed_companies` | Retrieves official SAHPRA establishment lists across 10 licence categories (Manufacturers, API Producers, Bond Stores, etc.) |
| `search_sahpra_products` | Searches the SAHPRA registered medicine database by company name, returning product portfolio and registration metadata |
| `analyse_ndoh_market` | Analyses the NDoH Master Health Product List (MHPL) for public sector contract values, pricing, supplier share, and tender pipeline |
| `analyse_private_market` | Analyses the Database of Medicine Prices (MPR/SEP) for private sector pricing competitiveness and applicant market presence |

### Prompts (Agentic Workflows)

Pre-built prompt templates that chain tools into structured multi-step analyses:

- **`supplier_integrity_audit`** — Cross-references a supplier's tender footprint against their SAHPRA licence status and product registrations, with visual discrepancy flagging
- **`therapeutic_category_assessment`** — Identifies market concentration and supply chain risk within a specific ATC drug class
- **`market_entry_scouting`** — Evaluates the public sector opportunity for a new generic product launch
- **`private_market_disruption_scouting`** — Locates pricing gaps in the private SEP landscape where a lower-cost entrant could compete
- **`cross_market_viability_check`** — Compares state tender pricing against private sector SEP to assess dual-market margin viability

### Data Pipeline

- **SAHPRA nonce caching** — Fetches and caches the Ninja Tables public nonce used by SAHPRA's licence endpoints for 12 hours, reducing redundant page fetches
- **MHPL caching** — Discovers the latest NDoH MHPL Excel link at runtime, downloads and parses it, and persists a normalised CSV locally; falls back to stale cache on failure
- **MPR/SEP caching** — Two-layer cache (RAM + disk) for the Medicine Prices database, with in-memory hit detection to avoid repeated disk reads between requests

---

## Tech Stack

- **Python 3** — Core runtime
- **FastMCP** — MCP server framework (`mcp.server.fastmcp`)
- **httpx** — Async HTTP client for all upstream requests
- **pandas** — Data normalisation, filtering, aggregation, and Markdown table rendering
- **openpyxl / xlrd** — Excel parsing for NDoH and MPR source files
- **Stateless HTTP transport** — Deployed as a horizontally scalable, sessionless service

---

## Data Sources

| Source | Dataset | Update Frequency |
|---|---|---|
| SAHPRA (`sahpra.org.za`) | Approved Establishment Licences | As published |
| SAHPRA (`medapps.sahpra.org.za`) | Registered Medicine Database | As published |
| NDoH (`health.gov.za/tenders`) | Master Health Product List (MHPL) | Per tender cycle |
| NDoH (`health.gov.za/nhi-pee`) | Database of Medicine Prices (MPR/SEP) | Per SEP update |

---

## Usage

### Prerequisites

```bash
pip install fastmcp httpx pandas openpyxl tabulate
```

### Run Locally (stdio transport)

```bash
python server.py
```

### Run as HTTP Service

```bash
PORT=8080 python server.py
```

The server binds to `0.0.0.0:{PORT}` using the `streamable-http` transport, suitable for deployment behind a reverse proxy.

### Example Tool Call (via MCP client)

```json
{
  "tool": "analyse_ndoh_market",
  "arguments": {
    "query": "Tenofovir",
    "filter_type": "inn",
    "aggregate_by": "Supplier",
    "top_n": 10
  }
}
```

---

## Future Improvements

- Add a `search_ndoh_market` tool with fuzzy matching for medicine name resolution
- Scheduled background refresh of MHPL and MPR caches to eliminate cold-start latency
- Webhook support to notify downstream systems when new tender data is detected
- Structured JSON output mode alongside Markdown for programmatic consumers

---

## Author

**Paballo Mogane**  
Junior Python Developer | Automation Engineer

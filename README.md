# QuantGist MCP Server

<!-- mcp-name: io.github.QuantGist-Technologies/quantgist-mcp -->

[![smithery badge](https://smithery.ai/badge/quantgist/quantgist-mcp)](https://smithery.ai/servers/quantgist/quantgist-mcp)

Exposes [QuantGist](https://quantgist.com) macro-economic event data as **Model Context Protocol (MCP)** tools so Claude and other AI agents can query calendars, check event proximity, and assess trade safety — all within a conversation.

## What it does

The server registers fifteen tools that any MCP-compatible client (Claude Desktop, Claude Code, custom agents) can call:

**Macro economic events**

| Tool | Description |
|------|-------------|
| `get_upcoming_events` | Events scheduled in the next N hours, filtered by impact |
| `get_events_range` | Events in a date range with optional country/symbol/impact filters |
| `get_economic_calendar` | Full day calendar grouped by time, formatted as a schedule |
| `get_event_detail` | Full details for one event by ID (actual, forecast, previous, symbols) |

**Earnings**

| Tool | Description |
|------|-------------|
| `get_earnings_upcoming` | Next upcoming earnings reports across all tickers, with EPS/revenue estimates |
| `get_earnings_for_ticker` | Earnings history for one ticker (estimate vs actual, beat/miss, EDGAR links) |
| `get_earnings_summary` | Beat / miss / in-line counts and overall beat rate for a ticker |
| `get_earnings_surprises` | Largest EPS surprises across the market in the latest reports |
| `get_earnings_season_summary` | Index-level summary of the current earnings season |

**Markets**

| Tool | Description |
|------|-------------|
| `get_markets_overview` | End-of-day quotes for major indices and instruments (S&P 500, Nasdaq, gold, oil…) |

**Discovery & help** (read-only, no API key required)

| Tool | Description |
|------|-------------|
| `get_pricing` | Plans, prices, and feature gates (free → enterprise) + the Bot Usage Add-On |
| `get_limits` | Per-plan caps: request quotas, history window, data delay, WS, watchlists, rate limiting |
| `recommend_endpoint` | Map a natural-language use case to the best REST endpoint + MCP tool |
| `get_status` | Check API reachability and link the public status page |
| `estimate_usage_cost` | Estimate which plan fits a request volume + overage / Bot Usage Add-On notes |

## Requirements

- Python 3.10+ (for the local/stdio install — not needed for the hosted server)
- A QuantGist API key — get one at [quantgist.com](https://quantgist.com) (free tier: 100 calls/day)

## Connect to the hosted server (no install)

The MCP server is hosted over HTTP at **`https://api.quantgist.com/mcp`** — no install, no
Python. Any client that supports the streamable-HTTP transport can connect by sending your
QuantGist key in an `X-API-Key` header (multi-tenant: billed to your own quota).

Claude Code, in one command:

```bash
claude mcp add --transport http quantgist https://api.quantgist.com/mcp \
  --header "X-API-Key: qg_live_YOUR_KEY"
```

Any streamable-HTTP MCP client:

```json
{
  "mcpServers": {
    "quantgist": {
      "type": "streamable-http",
      "url": "https://api.quantgist.com/mcp",
      "headers": { "X-API-Key": "qg_live_YOUR_KEY" }
    }
  }
}
```

**Connectors that only accept a URL (e.g. ChatGPT):** if you can't set a custom header, put the
key in the URL instead — `https://api.quantgist.com/mcp?apiKey=qg_live_YOUR_KEY` (also accepts
`Authorization: Bearer <key>`). The header is preferred where possible, since a key in the URL can
be recorded in proxy/server logs.

Prefer to run it yourself? Install locally (below) or self-host the HTTP server — see [DEPLOY.md](DEPLOY.md).

## Installation

### Option A — install from the package (recommended)

```bash
pip install quantgist-mcp
# or with uv:
uv pip install quantgist-mcp
```

### Option B — install from source (development)

```bash
git clone https://github.com/QuantGist-Technologies/QuantGist_MCP
cd QuantGist_MCP
uv sync          # installs all dependencies into a venv
uv run quantgist-mcp   # start the server
```

## Claude Desktop configuration

Locate your Claude Desktop config file:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Add the `quantgist` server block (see `claude_desktop_config_example.json`):

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "quantgist-mcp",
      "env": {
        "QUANTGIST_API_KEY": "qg_live_YOUR_KEY_HERE"
      }
    }
  }
}
```

Restart Claude Desktop after saving. The tools will appear in the tool list.

### Using `uv run` instead of a global install

If you prefer not to install globally, point Claude Desktop at `uv run`:

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Quangist_MCP", "quantgist-mcp"],
      "env": {
        "QUANTGIST_API_KEY": "qg_live_YOUR_KEY_HERE"
      }
    }
  }
}
```

## Claude Code configuration

Add to `.claude/mcp_settings.json` in your project (or the global `~/.claude/mcp_settings.json`):

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "quantgist-mcp",
      "env": {
        "QUANTGIST_API_KEY": "qg_live_YOUR_KEY_HERE"
      }
    }
  }
}
```

## Self-hosting (HTTP transport)

Besides the stdio transport above, the server can run as a hosted HTTP service via the
`quantgist-mcp-http` entry point (`GET /health`, MCP at `/mcp`). It accepts a per-request
`X-API-Key` header (multi-tenant) or a server-side `QUANTGIST_API_KEY` env var.

```bash
docker build -t quantgist-mcp .
docker run -p 8000:8000 -e QUANTGIST_API_KEY=qg_live_YOUR_KEY quantgist-mcp
curl http://localhost:8000/health
```

See [DEPLOY.md](DEPLOY.md) for Docker, Docker Compose, and Coolify deployment.

## Tool reference

### `get_upcoming_events`

Returns events in the next N hours.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | integer (1–168) | 24 | Look-ahead window in hours |
| `impact` | high \| medium \| low \| all | high | Impact filter |

### `get_events_range`

Returns events in a date range.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | ISO string | Yes | Start date/datetime |
| `to_date` | ISO string | Yes | End date/datetime |
| `country` | string | No | 2-letter country code (e.g. "US") |
| `impact` | enum | No | high \| medium \| low \| all |
| `symbol` | string | No | Trading symbol (e.g. "XAUUSD") |

### `get_economic_calendar`

Returns the day's calendar grouped by release time.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | ISO date | today (UTC) | Date to fetch |
| `impact` | enum | high | Impact filter |

### `get_event_detail`

Returns full detail for one event.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_id` | string | Yes | Event ID from any other tool |

### `get_earnings_upcoming`

Returns the next upcoming earnings reports across all tickers, ordered by report date.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer (1–100) | 20 | Number of upcoming reports to return |

### `get_earnings_for_ticker`

Returns earnings history for a single ticker (EPS estimate vs actual, revenue, beat/miss, EDGAR links).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ticker` | string | required | Stock ticker, e.g. "AAPL" |
| `limit` | integer (1–50) | 10 | Number of historical reports to return |

### `get_earnings_summary`

Returns beat / miss / in-line counts and overall beat rate for a ticker.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | string | Yes | Stock ticker, e.g. "AAPL" |

### `get_earnings_surprises`

Returns the largest EPS surprises across the market in the most recent reports.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer (1–50) | 20 | Number of top surprises to return |

### `get_earnings_season_summary`

Returns the index-level summary of the current earnings season (total reports, overall beat rate, average EPS surprise, season label). No parameters.

### `get_markets_overview`

Returns end-of-day quotes for major market indices and instruments (S&P 500, Nasdaq, Dow Jones, gold, oil, etc.). No parameters.

## Example prompts

These prompts work out of the box once the server is connected:

- "What high-impact events are in the next 4 hours?"
- "Show me today's full economic calendar"
- "Show me this week's high-impact USD events"
- "What macro events affect EURUSD this Friday?"
- "Get me details on event ID abc123"
- "Which companies report earnings soon?"
- "Show me AAPL's earnings beat rate"
- "What were the biggest EPS surprises this season?"
- "Give me a quick market overview"

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QUANTGIST_API_KEY` | Yes | Your QuantGist API key (`qg_live_...` or `qg_test_...`) |

## Development

```bash
uv sync
uv run quantgist-mcp          # run the MCP server
uv run pytest                 # run tests (if present)
uv run ruff check src/        # lint
uv run ruff format src/       # format
```

## API rate limits

The free tier allows 100 API calls/day with up to 365 days of event history. Each tool invocation makes 1–2 API calls. Upgrade at [quantgist.com/pricing](https://quantgist.com/pricing) for higher limits.

## License

MIT

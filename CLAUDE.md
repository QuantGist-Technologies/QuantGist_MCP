# CLAUDE.md — QuantGist MCP Server

**Layer:** L2 · **Tentpole:** T2 (AI/developer adoption)
**Stack:** Python 3.10+ using the official `mcp` SDK (low-level `Server` API, stdio transport)
**Protocol:** Model Context Protocol (MCP)
**Distribution:** PyPI package `quantgist-mcp` (entry point `quantgist-mcp`), runnable via `pip`/`uv`/`uvx`.

---

## Purpose

Exposes QuantGist data as MCP tools so Claude and other AI agents can query macro
events, earnings, and market snapshots — all within an AI conversation.

Use cases:
- Claude Code agents checking event risk before generating trading code
- Claude.ai / Claude Desktop users asking "what macro events affect EURUSD this week?"
- AI trading assistants checking "is it safe to trade gold right now?"

The server is a thin client over the public QuantGist REST API
(`https://api.quantgist.com/v1`). It holds no data of its own — every tool maps to
one or two REST calls. The earnings and markets tools require the corresponding
backend feature flags (`EARNINGS_API_ENABLED`, `MARKETS_API_ENABLED`) to be on in
production; both are enabled today.

---

## MCP tools (10)

Macro events:

| Tool | Maps to |
|------|---------|
| `get_upcoming_events` | `GET /events` (now → now+N hours) |
| `get_events_range` | `GET /events` (explicit range + country/impact/symbol filters) |
| `get_economic_calendar` | `GET /events` (single day, grouped by release time) |
| `get_event_detail` | `GET /events/{id}` |

Earnings:

| Tool | Maps to |
|------|---------|
| `get_earnings_upcoming` | `GET /earnings/upcoming` |
| `get_earnings_for_ticker` | `GET /earnings/{ticker}` |
| `get_earnings_summary` | `GET /earnings/{ticker}/summary` |
| `get_earnings_surprises` | `GET /earnings/surprises` |
| `get_earnings_season_summary` | `GET /earnings/season/summary` |

Markets:

| Tool | Maps to |
|------|---------|
| `get_markets_overview` | `GET /markets/overview` |

---

## Package structure

```
Quangist_MCP/
├── src/
│   └── quantgist_mcp/
│       ├── __init__.py       # __version__
│       ├── server.py         # MCP Server, tool schemas, dispatch, stdio entry main()
│       ├── http.py           # streamable-HTTP transport (quantgist-mcp-http), Starlette app
│       ├── api.py            # QuantGistAPI — async httpx wrapper; per-request key contextvar
│       └── formatters.py     # raw event/earnings/markets dicts → readable text/markdown
├── pyproject.toml            # hatchling build; scripts quantgist-mcp + quantgist-mcp-http
├── server.json               # official MCP Registry manifest
├── Dockerfile                # python:3.12-slim + uv, runs quantgist-mcp-http
├── docker-compose.yml        # Coolify deploy (pre-built GHCR image, never build:)
├── DEPLOY.md                 # Docker / Compose / Coolify hosting guide
├── README.md
├── CHANGELOG.md
├── claude_desktop_config_example.json
└── .github/workflows/
    ├── ci.yml                # import check + build; PyPI + MCP-registry publish on v* tags
    └── docker-build.yml      # build arm64 → GHCR → Coolify deploy on push to main
```

Two transports, one `Server`: stdio (`quantgist-mcp`, in `server.py`) and streamable-HTTP
(`quantgist-mcp-http`, in `http.py`). HTTP reads a per-request `X-API-Key` header (via the
`set_request_api_key` contextvar in `api.py`), falling back to the `QUANTGIST_API_KEY` env var.

There is **no** `tools/` subpackage — all tool schemas and handlers live in `server.py`,
dispatched through the `handlers` dict in `_dispatch()`.

---

## Commands

```bash
uv sync
uv run quantgist-mcp          # start the MCP server (requires QUANTGIST_API_KEY)
uv run ruff check src/        # lint
uv run ruff format src/       # format
uv build                      # build sdist + wheel into dist/
```

To publish a new release: bump `version` in `pyproject.toml` and `__version__` in
`__init__.py`, update `CHANGELOG.md`, then `uv build && uv publish`.

---

## Claude Desktop / Claude Code integration

After `pip install quantgist-mcp`:

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "quantgist-mcp",
      "env": { "QUANTGIST_API_KEY": "qg_live_..." }
    }
  }
}
```

Or without installing, via `uv run --directory`:

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Quangist_MCP", "quantgist-mcp"],
      "env": { "QUANTGIST_API_KEY": "qg_live_..." }
    }
  }
}
```

---

## Rules

- Tools return human-readable text built by `formatters.py`, except the structured
  tools (`get_earnings_summary`, `get_earnings_season_summary`) which return indented
  JSON. Keep new event-list tools going through `format_event_list`.
- Always surface `release_time_utc` (or `release_time`) in event output — callers need raw timestamps.
- Errors are caught in `call_tool` and returned as JSON envelopes:
  `{ "error": "api_error" | "invalid_input" | "internal_error", "detail": "..." }`.
  Raise `QuantGistAPIError` from `api.py` for non-2xx upstream responses.
- Never hardcode the API key — always read `QUANTGIST_API_KEY` from the env. `main()`
  fails fast at startup if it's missing.
- Keep tool descriptions concise and precise — they land directly in the model's tool list.
- When adding a tool: add the schema to `TOOLS`, add a `_tool_*` handler, register it in
  the `_dispatch` `handlers` dict, and document it in `README.md`.

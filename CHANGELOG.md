# Changelog

## 0.3.0 - 2026-06-27

- Added a **streamable-HTTP transport** (`quantgist-mcp-http`) so the server can be
  hosted as a network service (Docker / Coolify). `GET /health` for probes, `/mcp` for
  the MCP endpoint. Per-request `X-API-Key` header is honoured (multi-tenant), falling
  back to the `QUANTGIST_API_KEY` env var (single-tenant).
- Fixed earnings tool formatting — `get_earnings_upcoming`, `get_earnings_for_ticker`,
  and `get_earnings_surprises` now show ticker, company, EPS estimate/actual, beat/miss
  %, and fiscal period (previously rendered as empty macro-event rows).
- Fixed `get_markets_overview` — now renders the grouped snapshot (indexes, equities,
  commodities…) with prices and daily % change (previously returned "No events found").
- Added optional `QUANTGIST_API_URL` env override for the API base URL.

## 0.2.0 - 2026-06-27

- **Removed** the `check_safe_to_trade` tool. It evaluated proximity to *all* global
  high-impact events rather than only those affecting the queried symbol, producing
  misleading "unsafe" verdicts. Use `get_upcoming_events` / `get_events_range` with a
  `symbol` filter instead. (Breaking change — server now exposes 10 tools.)
- Documented all tools in the README (earnings + markets were previously undocumented).
- Added project URLs and keywords to package metadata.

## 0.1.0 - 2026-05-25

- Prepared the MCP server for public launch with repository metadata and CI.
- Exposes QuantGist macro event tools for agent workflows.

# Changelog

## 0.4.0 - 2026-06-29

- Added 5 read-only **discovery / help tools** (no API key required) so agents can evaluate
  QuantGist before signing up: `get_pricing`, `get_limits`, `recommend_endpoint`,
  `get_status`, `estimate_usage_cost`. Server now exposes **15 tools**.

## 0.3.5 - 2026-06-28

- HTTP transport now also accepts the API key via `?apiKey=` (or `?api_key=`/`?key=`)
  query parameter and `Authorization: Bearer`, in addition to the `X-API-Key` header.
  Lets connector UIs that only accept a URL (e.g. ChatGPT) authenticate without headers.

## 0.3.4 - 2026-06-28

- Tools now return machine-readable `structuredContent` and declare `outputSchema`. List
  tools return `{ "<events|earnings>": [...], "count": N }`; detail/summary/markets tools
  return the underlying object. Errors return `isError` results (no schema constraint).

## 0.3.3 - 2026-06-28

- Added human-readable `title` and behavioural `annotations` (readOnlyHint, destructiveHint,
  idempotentHint, openWorldHint) to all 10 tools — every tool is read-only and queries live
  external data. Improves client/registry capability scans and MCP best-practice scores.

## 0.3.2 - 2026-06-28

- Register empty `resources/list` and `prompts/list` handlers so capability scans
  (e.g. Smithery) no longer log "method not found" warnings for this tools-only server.

## 0.3.1 - 2026-06-28

- Fixed the HTTP transport returning a `307` trailing-slash redirect on `/mcp`. The MCP
  app is now served at the mount root, so `POST /mcp` (initialize) returns `200` directly.
  Strict gateways (e.g. Smithery) that don't follow `307` on POST failed to initialize
  before this. `/health` and `/mcp/health` both serve liveness.

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

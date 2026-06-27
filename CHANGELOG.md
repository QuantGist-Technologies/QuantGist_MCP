# Changelog

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

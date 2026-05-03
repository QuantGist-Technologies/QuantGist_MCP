# CLAUDE.md — QuantGist MCP Server

**Layer:** L2 · **Tentpole:** T2 (AI/developer adoption)  
**Stack:** Python 3.10+ using `fastmcp` or `mcp` SDK  
**Protocol:** Model Context Protocol (MCP)

---

## Purpose

Exposes QuantGist data as MCP tools so Claude and other AI agents can query macro events, check event proximity for symbols, and filter calendars — all within an AI conversation.

Use cases:
- Claude Code agents checking event risk before generating trading code
- Claude.ai users asking "what macro events affect EURUSD this week?"
- AI trading assistants checking "is it safe to trade gold right now?"

---

## MCP Tools to implement

| Tool name | Description |
|-----------|-------------|
| `get_events_today` | Returns today's economic events (optionally filtered by impact, country, currency) |
| `get_events_for_symbol` | Given a symbol (e.g. XAUUSD), returns events affecting it in the next N hours |
| `get_upcoming_high_impact` | Returns the next N high-impact events globally |
| `check_trade_window` | Given symbol + optional timeframe, returns risk level + nearest event countdown |
| `get_central_bank_rates` | Returns current rates + next decision dates for major central banks |
| `get_surprise_score` | Returns surprise score for a recent event release |

---

## Package structure

```
Quangist_MCP/
├── src/
│   └── quantgist_mcp/
│       ├── server.py        # MCP server entry point
│       ├── tools/
│       │   ├── events.py
│       │   ├── symbols.py
│       │   └── central_banks.py
│       └── api.py           # quantgist Python SDK wrapper
├── pyproject.toml
├── README.md
└── mcp_config_example.json  # example Claude Desktop / Claude Code config
```

---

## Commands

```bash
uv sync
uv run quantgist-mcp          # start the MCP server
uv run pytest
```

## Claude Code integration

Add to `.claude/mcp_settings.json`:
```json
{
  "mcpServers": {
    "quantgist": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/Quangist_MCP", "quantgist-mcp"],
      "env": {
        "QUANTGIST_API_KEY": "qg_live_..."
      }
    }
  }
}
```

---

## Rules

- Tools must return structured data (dicts/lists), not prose — the AI formats output
- Always include `release_time_utc` in event responses — callers need raw timestamps
- Error responses: `{ "error": "rate_limit" | "not_found" | "api_error", "detail": "..." }`
- Never hardcode API key — always from env var `QUANTGIST_API_KEY`
- Keep tool descriptions concise and precise — they appear in the AI's tool list

# QuantGist MCP Server

Exposes [QuantGist](https://quantgist.com) macro-economic event data as **Model Context Protocol (MCP)** tools so Claude and other AI agents can query calendars, check event proximity, and assess trade safety — all within a conversation.

## What it does

The server registers five tools that any MCP-compatible client (Claude Desktop, Claude Code, custom agents) can call:

| Tool | Description |
|------|-------------|
| `get_upcoming_events` | Events scheduled in the next N hours, filtered by impact |
| `get_events_range` | Events in a date range with optional country/symbol/impact filters |
| `check_safe_to_trade` | Is it safe to trade a symbol right now? (high-impact event proximity check) |
| `get_economic_calendar` | Full day calendar grouped by time, formatted as a schedule |
| `get_event_detail` | Full details for one event by ID (actual, forecast, previous, symbols) |

## Requirements

- Python 3.10+
- A QuantGist API key — get one at [quantgist.com](https://quantgist.com) (free tier: 50 calls/day)

## Installation

### Option A — install from the package (recommended)

```bash
pip install quantgist-mcp
# or with uv:
uv pip install quantgist-mcp
```

### Option B — install from source (development)

```bash
git clone https://github.com/quantgist/quantgist-mcp
cd quantgist-mcp
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

### `check_safe_to_trade`

Checks if a symbol is safe to trade based on nearby high-impact events.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | required | Symbol to check (e.g. "XAUUSD") |
| `minutes_before` | integer (0–120) | 10 | Flag unsafe N minutes before an event |
| `minutes_after` | integer (0–120) | 5 | Flag unsafe N minutes after an event |

Returns a JSON object:
```json
{
  "symbol": "XAUUSD",
  "safe": false,
  "reason": "High-impact event within window: US CPI (YoY). Avoid trading XAUUSD until the window passes.",
  "dangerous_events_count": 1,
  "next_event": {
    "id": "abc123",
    "title": "US CPI (YoY)",
    "currency": "USD",
    "impact": "high",
    "release_time_utc": "2025-01-15T13:30:00Z",
    "minutes_from_now": 7.3
  },
  "window": { "minutes_before": 10, "minutes_after": 5 },
  "checked_at_utc": "2025-01-15 13:22 UTC"
}
```

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

## Example prompts

These prompts work out of the box once the server is connected:

- "What high-impact events are in the next 4 hours?"
- "Is it safe to trade XAUUSD right now?"
- "Show me today's full economic calendar"
- "Show me this week's high-impact USD events"
- "What macro events affect EURUSD this Friday?"
- "Get me details on event ID abc123"
- "Check if GBPUSD is safe to trade with a 15-minute buffer before events"

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

The free tier allows 50 API calls/day. Each tool invocation makes 1–2 API calls. Upgrade at [quantgist.com/pricing](https://quantgist.com/pricing) for higher limits.

## License

MIT

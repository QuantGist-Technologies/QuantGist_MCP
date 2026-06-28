"""QuantGist MCP server — exposes macro event tools to Claude and AI agents."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from quantgist_mcp.api import QuantGistAPI, QuantGistAPIError
from quantgist_mcp.formatters import (
    format_calendar,
    format_earnings_list,
    format_event_detail,
    format_event_list,
    format_markets_overview,
)

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("quantgist")

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

_IMPACT_ENUM = {
    "type": "string",
    "enum": ["high", "medium", "low", "all"],
    "description": "Filter by impact level. Use 'all' for no filter.",
}

TOOLS: list[types.Tool] = [
    types.Tool(
        name="get_upcoming_events",
        description=(
            "Get macro-economic events scheduled in the next N hours. "
            "Use this to find out what news/data releases are coming up that could move markets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 168,
                    "default": 24,
                    "description": "How many hours ahead to look (1–168). Default: 24.",
                },
                "impact": {
                    **_IMPACT_ENUM,
                    "default": "high",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_events_range",
        description=(
            "Get economic events within a specific date range, optionally filtered by "
            "country, impact level, or trading symbol."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date or datetime in ISO 8601 format (e.g. '2025-01-15' or '2025-01-15T00:00:00Z').",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date or datetime in ISO 8601 format.",
                },
                "country": {
                    "type": "string",
                    "description": "Optional 2-letter country code (e.g. 'US', 'GB', 'EU').",
                },
                "impact": {
                    **_IMPACT_ENUM,
                    "default": "all",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional trading symbol to filter events (e.g. 'XAUUSD', 'EURUSD', 'US30').",
                },
            },
            "required": ["from_date", "to_date"],
        },
    ),
    types.Tool(
        name="get_economic_calendar",
        description=(
            "Get the full economic calendar for a specific date, grouped by time. "
            "Useful for planning trading sessions or showing the day's schedule."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "ISO date to fetch (e.g. '2025-01-15'). Defaults to today (UTC).",
                },
                "impact": {
                    **_IMPACT_ENUM,
                    "default": "high",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_event_detail",
        description=(
            "Get full details for a specific economic event by its ID, "
            "including actual/forecast/previous values and affected symbols."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The unique event ID returned by other tools.",
                },
            },
            "required": ["event_id"],
        },
    ),
    types.Tool(
        name="get_earnings_upcoming",
        description=(
            "Get the next upcoming earnings reports across all tickers, ordered by report date. "
            "Use this to see which companies are reporting soon and their EPS/revenue estimates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Number of upcoming reports to return (default 20).",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_earnings_for_ticker",
        description=(
            "Get earnings history for a specific stock ticker, including EPS estimates vs actuals, "
            "revenue, beat/miss classification, and SEC EDGAR filing links."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. 'AAPL', 'MSFT', 'NVDA'.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Number of historical reports to return (default 10).",
                },
            },
            "required": ["ticker"],
        },
    ),
    types.Tool(
        name="get_earnings_summary",
        description=(
            "Get a beat/miss/in-line summary for a ticker — how many quarters did it beat, miss, "
            "or come in-line with EPS estimates? Includes overall beat rate."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. 'AAPL'.",
                },
            },
            "required": ["ticker"],
        },
    ),
    types.Tool(
        name="get_earnings_surprises",
        description=(
            "Get the largest EPS surprises across the market — stocks that significantly beat or "
            "missed analyst estimates in their most recent earnings report."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "description": "Number of top surprises to return (default 20).",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_earnings_season_summary",
        description=(
            "Get the index-level summary of the current earnings season — total reports, "
            "overall beat rate, average EPS surprise, and season label (e.g. 'Q1 2025')."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    types.Tool(
        name="get_markets_overview",
        description=(
            "Get end-of-day quotes for major market indices and instruments "
            "(S&P 500, Nasdaq, Dow Jones, gold, oil, etc.). "
            "Useful for a quick snapshot of overall market conditions."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]

# Human-readable titles + behavioural annotations. Every tool is read-only (it only
# fetches data), non-destructive, idempotent (no side effects), and open-world (it
# queries live external data). Surfacing these hints is MCP best practice and lets
# clients/registries reason about safety.
_TOOL_TITLES: dict[str, str] = {
    "get_upcoming_events": "Upcoming Economic Events",
    "get_events_range": "Economic Events by Date Range",
    "get_economic_calendar": "Economic Calendar (by day)",
    "get_event_detail": "Economic Event Detail",
    "get_earnings_upcoming": "Upcoming Earnings Reports",
    "get_earnings_for_ticker": "Earnings History by Ticker",
    "get_earnings_summary": "Earnings Beat/Miss Summary",
    "get_earnings_surprises": "Top EPS Surprises",
    "get_earnings_season_summary": "Earnings Season Summary",
    "get_markets_overview": "Markets Overview",
}

# Output schemas. Each tool also returns machine-readable `structuredContent` matching
# these. Item shapes are left as open objects (records carry many optional, often-null
# fields) — the wrapper (array + count) is what callers iterate on.
_ITEM = {"type": "object", "additionalProperties": True}


def _list_out(key: str) -> dict:
    return {
        "type": "object",
        "properties": {key: {"type": "array", "items": _ITEM}, "count": {"type": "integer"}},
        "required": [key, "count"],
    }


_OPEN_OBJECT = {"type": "object", "additionalProperties": True}

_OUTPUT_SCHEMAS: dict[str, dict] = {
    "get_upcoming_events": _list_out("events"),
    "get_events_range": _list_out("events"),
    "get_economic_calendar": {
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "events": {"type": "array", "items": _ITEM},
            "count": {"type": "integer"},
        },
        "required": ["date", "events", "count"],
    },
    "get_event_detail": _OPEN_OBJECT,
    "get_earnings_upcoming": _list_out("earnings"),
    "get_earnings_for_ticker": _list_out("earnings"),
    "get_earnings_summary": _OPEN_OBJECT,
    "get_earnings_surprises": _list_out("earnings"),
    "get_earnings_season_summary": _OPEN_OBJECT,
    "get_markets_overview": {
        "type": "object",
        "properties": {
            "as_of": {"type": "string"},
            "recency": {"type": "string"},
            "delay_minutes": {"type": "integer"},
            "groups": {"type": "array", "items": _ITEM},
        },
        "additionalProperties": True,
    },
}

for _tool in TOOLS:
    _tool.title = _TOOL_TITLES.get(_tool.name)
    _tool.outputSchema = _OUTPUT_SCHEMAS.get(_tool.name)
    _tool.annotations = types.ToolAnnotations(
        title=_TOOL_TITLES.get(_tool.name),
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )

# ---------------------------------------------------------------------------
# Tool list handler
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


# This server exposes tools only. Registering empty resource/prompt list handlers
# makes resources/list and prompts/list return [] instead of "method not found",
# which keeps client/registry capability scans (e.g. Smithery) warning-free.
@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return []


@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return []


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


def _error_result(error: str, detail: str, **extra: Any) -> types.CallToolResult:
    """Build an isError result. Returned as CallToolResult so it bypasses the
    outputSchema validation that applies to successful structured results."""
    payload = {"error": error, "detail": detail, **extra}
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        isError=True,
    )


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> tuple[list[types.TextContent], dict[str, Any]] | types.CallToolResult:
    """Dispatch MCP tool calls. Returns (text content, structured content) on success."""
    try:
        text, structured = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=text)], structured
    except QuantGistAPIError as exc:
        return _error_result("api_error", exc.detail, status_code=exc.status_code)
    except ValueError as exc:
        return _error_result("invalid_input", str(exc))
    except Exception as exc:  # noqa: BLE001
        return _error_result("internal_error", str(exc))


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------
# Each handler returns a (text, structured) tuple: human-readable text plus a
# JSON-serializable dict matching the tool's outputSchema.


async def _dispatch(name: str, args: dict) -> tuple[str, dict[str, Any]]:
    handlers = {
        "get_upcoming_events": _tool_get_upcoming_events,
        "get_events_range": _tool_get_events_range,
        "get_economic_calendar": _tool_get_economic_calendar,
        "get_event_detail": _tool_get_event_detail,
        # Earnings
        "get_earnings_upcoming": _tool_get_earnings_upcoming,
        "get_earnings_for_ticker": _tool_get_earnings_for_ticker,
        "get_earnings_summary": _tool_get_earnings_summary,
        "get_earnings_surprises": _tool_get_earnings_surprises,
        "get_earnings_season_summary": _tool_get_earnings_season_summary,
        # Markets
        "get_markets_overview": _tool_get_markets_overview,
    }
    handler = handlers.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name!r}")
    return await handler(args)


async def _tool_get_upcoming_events(args: dict) -> tuple[str, dict[str, Any]]:
    hours = int(args.get("hours", 24))
    impact = str(args.get("impact", "high"))

    if not 1 <= hours <= 168:
        raise ValueError("hours must be between 1 and 168")

    async with QuantGistAPI() as api:
        events = await api.get_upcoming_events(hours=hours, impact=impact)

    impact_label = f" ({impact} impact)" if impact != "all" else ""
    title = f"Upcoming Events — next {hours}h{impact_label}"
    return format_event_list(events, title), {"events": events, "count": len(events)}


async def _tool_get_events_range(args: dict) -> tuple[str, dict[str, Any]]:
    from_date = args.get("from_date")
    to_date = args.get("to_date")
    if not from_date or not to_date:
        raise ValueError("from_date and to_date are required")

    country = args.get("country")
    impact = args.get("impact", "all")
    symbol = args.get("symbol")

    async with QuantGistAPI() as api:
        events = await api.get_events(
            from_time=from_date,
            to_time=to_date,
            impact=impact,
            country=country,
            symbol=symbol,
        )

    parts = [f"{from_date} to {to_date}"]
    if country:
        parts.append(f"country={country}")
    if impact and impact != "all":
        parts.append(f"impact={impact}")
    if symbol:
        parts.append(f"symbol={symbol}")
    title = "Events — " + ", ".join(parts)
    return format_event_list(events, title), {"events": events, "count": len(events)}


async def _tool_get_economic_calendar(args: dict) -> tuple[str, dict[str, Any]]:
    date_str = str(args.get("date", "")).strip()
    if not date_str:
        date_str = date.today().isoformat()

    impact = str(args.get("impact", "high"))

    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"date must be in YYYY-MM-DD format, got: {date_str!r}")

    from_time = f"{date_str}T00:00:00Z"
    to_time = f"{date_str}T23:59:59Z"

    async with QuantGistAPI() as api:
        events = await api.get_events(
            from_time=from_time,
            to_time=to_time,
            impact=impact,
        )

    return (
        format_calendar(events, date_str),
        {"date": date_str, "events": events, "count": len(events)},
    )


async def _tool_get_event_detail(args: dict) -> tuple[str, dict[str, Any]]:
    event_id = str(args.get("event_id", "")).strip()
    if not event_id:
        raise ValueError("event_id is required")

    async with QuantGistAPI() as api:
        event = await api.get_event(event_id)

    return format_event_detail(event), event


# ---------------------------------------------------------------------------
# Earnings tool implementations
# ---------------------------------------------------------------------------


async def _tool_get_earnings_upcoming(args: dict) -> tuple[str, dict[str, Any]]:
    limit = int(args.get("limit", 20))
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    async with QuantGistAPI() as api:
        events = await api.get_earnings_upcoming(limit=limit)

    text = format_earnings_list(events, f"Upcoming Earnings — next {limit} reports")
    return text, {"earnings": events, "count": len(events)}


async def _tool_get_earnings_for_ticker(args: dict) -> tuple[str, dict[str, Any]]:
    ticker = str(args.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    limit = int(args.get("limit", 10))

    async with QuantGistAPI() as api:
        events = await api.get_earnings_for_ticker(ticker, limit=limit)

    text = format_earnings_list(events, f"Earnings History — {ticker}")
    return text, {"earnings": events, "count": len(events)}


async def _tool_get_earnings_summary(args: dict) -> tuple[str, dict[str, Any]]:
    ticker = str(args.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker is required")

    async with QuantGistAPI() as api:
        summary = await api.get_earnings_summary(ticker)

    return json.dumps(summary, indent=2, default=str), summary


async def _tool_get_earnings_surprises(args: dict) -> tuple[str, dict[str, Any]]:
    limit = int(args.get("limit", 20))

    async with QuantGistAPI() as api:
        surprises = await api.get_earnings_surprises(limit=limit)

    text = format_earnings_list(surprises, f"Top {limit} EPS Surprises")
    return text, {"earnings": surprises, "count": len(surprises)}


async def _tool_get_earnings_season_summary(args: dict) -> tuple[str, dict[str, Any]]:
    async with QuantGistAPI() as api:
        summary = await api.get_earnings_season_summary()

    return json.dumps(summary, indent=2, default=str), summary


# ---------------------------------------------------------------------------
# Markets tool implementations
# ---------------------------------------------------------------------------


async def _tool_get_markets_overview(args: dict) -> tuple[str, dict[str, Any]]:
    async with QuantGistAPI() as api:
        overview = await api.get_markets_overview()

    structured = overview if isinstance(overview, dict) else {"groups": overview}
    return format_markets_overview(overview), structured


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point registered in pyproject.toml."""
    # Validate API key is present at startup so the error is obvious
    if not os.environ.get("QUANTGIST_API_KEY"):
        raise SystemExit(
            "ERROR: QUANTGIST_API_KEY environment variable is not set.\n"
            "Export your API key before starting the server:\n"
            "  export QUANTGIST_API_KEY=qg_live_...\n"
            "Or add it to the 'env' section of your Claude Desktop config."
        )
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()

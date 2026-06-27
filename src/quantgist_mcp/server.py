"""QuantGist MCP server — exposes macro event tools to Claude and AI agents."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from quantgist_mcp.api import QuantGistAPI, QuantGistAPIError
from quantgist_mcp.formatters import (
    format_calendar,
    format_event_detail,
    format_event_list,
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

# ---------------------------------------------------------------------------
# Tool list handler
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Dispatch MCP tool calls to the appropriate handler."""
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=result)]
    except QuantGistAPIError as exc:
        error_payload = json.dumps(
            {"error": "api_error", "detail": exc.detail, "status_code": exc.status_code},
            indent=2,
        )
        return [types.TextContent(type="text", text=error_payload)]
    except ValueError as exc:
        error_payload = json.dumps({"error": "invalid_input", "detail": str(exc)}, indent=2)
        return [types.TextContent(type="text", text=error_payload)]
    except Exception as exc:  # noqa: BLE001
        error_payload = json.dumps({"error": "internal_error", "detail": str(exc)}, indent=2)
        return [types.TextContent(type="text", text=error_payload)]


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------


async def _dispatch(name: str, args: dict) -> str:
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


async def _tool_get_upcoming_events(args: dict) -> str:
    hours = int(args.get("hours", 24))
    impact = str(args.get("impact", "high"))

    if not 1 <= hours <= 168:
        raise ValueError("hours must be between 1 and 168")

    async with QuantGistAPI() as api:
        events = await api.get_upcoming_events(hours=hours, impact=impact)

    impact_label = f" ({impact} impact)" if impact != "all" else ""
    title = f"Upcoming Events — next {hours}h{impact_label}"
    return format_event_list(events, title)


async def _tool_get_events_range(args: dict) -> str:
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
    return format_event_list(events, title)


async def _tool_get_economic_calendar(args: dict) -> str:
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

    return format_calendar(events, date_str)


async def _tool_get_event_detail(args: dict) -> str:
    event_id = str(args.get("event_id", "")).strip()
    if not event_id:
        raise ValueError("event_id is required")

    async with QuantGistAPI() as api:
        event = await api.get_event(event_id)

    return format_event_detail(event)


# ---------------------------------------------------------------------------
# Earnings tool implementations
# ---------------------------------------------------------------------------


async def _tool_get_earnings_upcoming(args: dict) -> str:
    limit = int(args.get("limit", 20))
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    async with QuantGistAPI() as api:
        events = await api.get_earnings_upcoming(limit=limit)

    return format_event_list(events, f"Upcoming Earnings — next {limit} reports")


async def _tool_get_earnings_for_ticker(args: dict) -> str:
    ticker = str(args.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    limit = int(args.get("limit", 10))

    async with QuantGistAPI() as api:
        events = await api.get_earnings_for_ticker(ticker, limit=limit)

    return format_event_list(events, f"Earnings History — {ticker}")


async def _tool_get_earnings_summary(args: dict) -> str:
    ticker = str(args.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker is required")

    async with QuantGistAPI() as api:
        summary = await api.get_earnings_summary(ticker)

    return json.dumps(summary, indent=2, default=str)


async def _tool_get_earnings_surprises(args: dict) -> str:
    limit = int(args.get("limit", 20))

    async with QuantGistAPI() as api:
        surprises = await api.get_earnings_surprises(limit=limit)

    return format_event_list(surprises, f"Top {limit} EPS Surprises")


async def _tool_get_earnings_season_summary(args: dict) -> str:
    async with QuantGistAPI() as api:
        summary = await api.get_earnings_season_summary()

    return json.dumps(summary, indent=2, default=str)


# ---------------------------------------------------------------------------
# Markets tool implementations
# ---------------------------------------------------------------------------


async def _tool_get_markets_overview(args: dict) -> str:
    async with QuantGistAPI() as api:
        quotes = await api.get_markets_overview()

    return format_event_list(quotes, "Markets Overview")


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

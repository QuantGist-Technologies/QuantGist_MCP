"""QuantGist MCP server — exposes macro event tools to Claude and AI agents."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

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
        name="check_safe_to_trade",
        description=(
            "Check whether it is currently safe to trade a given symbol. "
            "Returns safe/unsafe status based on proximity of high-impact macro events. "
            "Use before placing trades or generating trading signals."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol to check (e.g. 'XAUUSD', 'EURUSD', 'GBPUSD', 'US30').",
                },
                "minutes_before": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 120,
                    "default": 10,
                    "description": "Minutes before an event to flag as unsafe. Default: 10.",
                },
                "minutes_after": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 120,
                    "default": 5,
                    "description": "Minutes after an event to flag as unsafe. Default: 5.",
                },
            },
            "required": ["symbol"],
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
        "check_safe_to_trade": _tool_check_safe_to_trade,
        "get_economic_calendar": _tool_get_economic_calendar,
        "get_event_detail": _tool_get_event_detail,
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


async def _tool_check_safe_to_trade(args: dict) -> str:
    symbol = str(args.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    minutes_before = int(args.get("minutes_before", 10))
    minutes_after = int(args.get("minutes_after", 5))

    now_utc = datetime.now(timezone.utc)

    # Fetch upcoming events for the next 2 hours affecting the symbol
    async with QuantGistAPI() as api:
        events = await api.get_upcoming_events(hours=2, impact=None)

    # Also fetch events affecting this specific symbol from range query
    # (symbol filter may narrow results further)
    async with QuantGistAPI() as api:
        symbol_events = await api.get_events(
            from_time=now_utc.isoformat(),
            to_time=(now_utc + timedelta(hours=2)).isoformat(),
            symbol=symbol,
        )

    # Merge and deduplicate by id
    seen_ids: set[str] = set()
    all_events: list[dict] = []
    for evt in events + symbol_events:
        eid = str(evt.get("id", ""))
        if eid and eid in seen_ids:
            continue
        seen_ids.add(eid)
        all_events.append(evt)

    # Parse release times and find dangerous events
    dangerous: list[dict] = []
    next_event: dict | None = None
    next_event_minutes: float | None = None

    for evt in all_events:
        raw = evt.get("release_time") or evt.get("release_time_utc") or ""
        if not raw:
            continue
        try:
            raw = raw.replace("Z", "+00:00")
            release_dt = datetime.fromisoformat(raw).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue

        delta_minutes = (release_dt - now_utc).total_seconds() / 60

        # Track the nearest upcoming event overall
        if delta_minutes >= 0:
            if next_event_minutes is None or delta_minutes < next_event_minutes:
                next_event_minutes = delta_minutes
                next_event = evt

        # Flag as dangerous if within the before/after window
        impact = str(evt.get("impact", "")).lower()
        if impact == "high":
            if -minutes_after <= delta_minutes <= minutes_before:
                dangerous.append(evt)

    is_safe = len(dangerous) == 0

    # Build next_event summary for the response
    next_event_summary: dict[str, Any] | None = None
    if next_event is not None:
        raw_time = next_event.get("release_time") or next_event.get("release_time_utc") or ""
        next_event_summary = {
            "id": next_event.get("id"),
            "title": next_event.get("title"),
            "currency": next_event.get("currency"),
            "impact": next_event.get("impact"),
            "release_time_utc": raw_time,
            "minutes_from_now": round(next_event_minutes, 1) if next_event_minutes is not None else None,
        }

    if is_safe:
        if next_event_summary:
            mins = next_event_summary["minutes_from_now"]
            reason = (
                f"No high-impact events within the ±{minutes_before}/{minutes_after}-minute window. "
                f"Next event in ~{mins:.0f} min: {next_event_summary['title']} ({next_event_summary['currency']})."
            )
        else:
            reason = "No upcoming events found in the next 2 hours. Clear window."
    else:
        titles = ", ".join(e.get("title", "?") for e in dangerous)
        reason = (
            f"High-impact event(s) within the trading window: {titles}. "
            f"Avoid trading {symbol} until the window passes."
        )

    result = {
        "symbol": symbol,
        "safe": is_safe,
        "reason": reason,
        "dangerous_events_count": len(dangerous),
        "next_event": next_event_summary,
        "window": {
            "minutes_before": minutes_before,
            "minutes_after": minutes_after,
        },
        "checked_at_utc": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
    }

    return json.dumps(result, indent=2)


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

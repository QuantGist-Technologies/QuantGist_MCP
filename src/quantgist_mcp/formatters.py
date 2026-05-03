"""Formatting helpers — turn raw QuantGist event dicts into readable text."""
from __future__ import annotations

from datetime import datetime, timezone


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

_IMPACT_EMOJI: dict[str, str] = {
    "high": "[HIGH]",
    "medium": "[MED]",
    "low": "[LOW]",
}

_UNKNOWN = "n/a"


def _impact_tag(event: dict) -> str:
    impact = str(event.get("impact", "")).lower()
    return _IMPACT_EMOJI.get(impact, f"[{impact.upper()}]")


def _ts(event: dict) -> str:
    """Return a short human-readable UTC timestamp from the event dict."""
    raw = event.get("release_time") or event.get("release_time_utc") or ""
    if not raw:
        return _UNKNOWN
    try:
        # Handle both 'Z' suffix and '+00:00'
        raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return str(raw)


def _val(event: dict, key: str) -> str:
    v = event.get(key)
    if v is None or v == "":
        return _UNKNOWN
    return str(v)


# ------------------------------------------------------------------ #
# Public formatters                                                    #
# ------------------------------------------------------------------ #


def format_event(event: dict) -> str:
    """Return a compact one-liner for an event.

    Example::

        [HIGH] 2025-01-15 13:30 UTC | USD | US CPI (YoY) | Forecast: 3.2% | Actual: 3.1%
    """
    tag = _impact_tag(event)
    time_str = _ts(event)
    currency = _val(event, "currency")
    title = _val(event, "title")
    forecast = _val(event, "forecast")
    actual = _val(event, "actual")

    parts = [f"{tag} {time_str}", currency, title]
    if forecast != _UNKNOWN:
        parts.append(f"Forecast: {forecast}")
    if actual != _UNKNOWN:
        parts.append(f"Actual: {actual}")

    return " | ".join(parts)


def format_event_list(events: list[dict], title: str = "Events") -> str:
    """Return a numbered markdown list with a header.

    Args:
        events: List of raw event dicts from the QuantGist API.
        title: Section heading to display above the list.

    Returns:
        Multi-line formatted string.
    """
    if not events:
        return f"**{title}**\n\nNo events found."

    lines = [f"**{title}** ({len(events)} event{'s' if len(events) != 1 else ''})\n"]
    for i, evt in enumerate(events, 1):
        lines.append(f"{i}. {format_event(evt)}")

    return "\n".join(lines)


def format_event_detail(event: dict) -> str:
    """Return a rich multi-line detail block for a single event.

    Example output::

        ## US CPI (YoY)
        ID:          abc123
        Time:        2025-01-15 13:30 UTC
        Currency:    USD
        Country:     US
        Impact:      HIGH
        Forecast:    3.2%
        Actual:      3.1%
        Previous:    3.4%
        Symbols:     XAUUSD, EURUSD, DXY
        Source:      ForexFactory
    """
    title = _val(event, "title")
    lines = [
        f"## {title}",
        "",
        f"{'ID:':<14} {_val(event, 'id')}",
        f"{'Time:':<14} {_ts(event)}",
        f"{'Currency:':<14} {_val(event, 'currency')}",
        f"{'Country:':<14} {_val(event, 'country')}",
        f"{'Impact:':<14} {str(event.get('impact', _UNKNOWN)).upper()}",
        f"{'Forecast:':<14} {_val(event, 'forecast')}",
        f"{'Actual:':<14} {_val(event, 'actual')}",
        f"{'Previous:':<14} {_val(event, 'previous')}",
    ]

    # Symbols may be a list or a comma-separated string
    symbols = event.get("symbols") or event.get("affected_symbols")
    if symbols:
        if isinstance(symbols, list):
            symbols_str = ", ".join(symbols)
        else:
            symbols_str = str(symbols)
        lines.append(f"{'Symbols:':<14} {symbols_str}")

    source = event.get("source")
    if source:
        lines.append(f"{'Source:':<14} {source}")

    description = event.get("description")
    if description:
        lines.extend(["", f"**Description:** {description}"])

    return "\n".join(lines)


def format_calendar(events: list[dict], date_str: str) -> str:
    """Return events grouped by hour, formatted as a daily schedule.

    Args:
        events: List of raw event dicts.
        date_str: The date being displayed (e.g. "2025-01-15").

    Returns:
        Multi-line formatted string with time-grouped sections.
    """
    if not events:
        return f"**Economic Calendar — {date_str}**\n\nNo events scheduled."

    # Group by hour bucket
    buckets: dict[str, list[dict]] = {}
    for evt in events:
        raw = evt.get("release_time") or evt.get("release_time_utc") or ""
        try:
            raw = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw).astimezone(timezone.utc)
            hour_key = dt.strftime("%H:%M UTC")
        except (ValueError, TypeError):
            hour_key = "Unknown time"
        buckets.setdefault(hour_key, []).append(evt)

    lines = [f"**Economic Calendar — {date_str}** ({len(events)} events)\n"]
    for hour_key in sorted(buckets):
        lines.append(f"### {hour_key}")
        for evt in buckets[hour_key]:
            tag = _impact_tag(evt)
            currency = _val(evt, "currency")
            title = _val(evt, "title")
            forecast = _val(evt, "forecast")
            actual = _val(evt, "actual")

            detail = f"{tag} {currency} — {title}"
            if actual != _UNKNOWN:
                detail += f"  *(actual: {actual}"
                if forecast != _UNKNOWN:
                    detail += f", forecast: {forecast}"
                detail += ")*"
            elif forecast != _UNKNOWN:
                detail += f"  *(forecast: {forecast})*"
            lines.append(f"  - {detail}")
        lines.append("")

    return "\n".join(lines).rstrip()

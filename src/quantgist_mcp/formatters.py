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


def _num(v: object, suffix: str = "") -> str | None:
    """Format a numeric value compactly, or None when absent."""
    if v is None or v == "":
        return None
    try:
        return f"{float(v):g}{suffix}"
    except (ValueError, TypeError):
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


def format_earnings(rec: dict) -> str:
    """Return a compact one-liner for an earnings record.

    Example::

        AAPL (Apple Inc.) | 2024-08-01 | EPS est 1.34 act 1.4 beat +4.5% | FY2024 Q2
    """
    ticker = rec.get("ticker") or _UNKNOWN
    company = rec.get("company_name")
    head = ticker if not company else f"{ticker} ({company})"

    when = rec.get("date") or _ts(rec)
    parts = [head, str(when)]

    eps_bits: list[str] = []
    est = _num(rec.get("eps_estimate"))
    act = _num(rec.get("eps_actual"))
    if est is not None:
        eps_bits.append(f"est {est}")
    if act is not None:
        eps_bits.append(f"act {act}")
    surprise = rec.get("eps_surprise_percent")
    if surprise is not None:
        try:
            sp = float(surprise)
            label = "beat" if sp > 0 else "miss" if sp < 0 else "in-line"
            eps_bits.append(f"{label} {sp:+.1f}%")
        except (ValueError, TypeError):
            pass
    if eps_bits:
        parts.append("EPS " + " ".join(eps_bits))

    fy = rec.get("fiscal_year")
    fp = rec.get("fiscal_period")
    period = f"{'FY' + str(fy) if fy else ''}{' ' + fp if fp else ''}".strip()
    if period:
        parts.append(period)

    if rec.get("sec_filing_url"):
        parts.append(str(rec["sec_filing_url"]))

    return " | ".join(parts)


def format_earnings_list(records: list[dict], title: str = "Earnings") -> str:
    """Return a numbered list of earnings records with a header."""
    if not records:
        return f"**{title}**\n\nNo earnings reports found."

    plural = "s" if len(records) != 1 else ""
    lines = [f"**{title}** ({len(records)} report{plural})\n"]
    for i, rec in enumerate(records, 1):
        lines.append(f"{i}. {format_earnings(rec)}")
    return "\n".join(lines)


def format_markets_overview(data: dict) -> str:
    """Return market groups (indexes, equities, …) as a readable snapshot.

    The /markets/overview payload is ``{as_of, recency, delay_minutes, groups:[...]}``
    where each group is ``{name, items:[{symbol, name, price, change_percent, ...}]}``.
    """
    if not isinstance(data, dict):
        return "**Markets Overview**\n\nNo market data available."

    groups = data.get("groups") or []
    if not groups:
        return "**Markets Overview**\n\nNo market data available."

    meta = []
    as_of = data.get("as_of")
    if as_of:
        meta.append(f"as of {_ts({'release_time': as_of})}")
    if data.get("recency"):
        meta.append(str(data["recency"]))
    header = "**Markets Overview**" + (f" — {', '.join(meta)}" if meta else "")

    lines = [header, ""]
    for group in groups:
        items = group.get("items") or []
        if not items:
            continue
        lines.append(f"### {group.get('name', 'Group')}")
        for it in items:
            symbol = it.get("symbol", "?")
            name = it.get("name", "")
            price = _num(it.get("price")) or _UNKNOWN
            chg = it.get("change_percent")
            chg_str = ""
            if chg is not None:
                try:
                    chg_str = f" ({float(chg):+.2f}%)"
                except (ValueError, TypeError):
                    pass
            label = symbol if not name else f"{symbol} {name}"
            lines.append(f"  - {label}: {price}{chg_str}")
        lines.append("")

    return "\n".join(lines).rstrip()


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

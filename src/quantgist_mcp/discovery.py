"""Read-only discovery / help data + logic for the agent-facing helper tools.

These power get_pricing / get_limits / recommend_endpoint / estimate_usage_cost.
They need NO API key — they let an agent evaluate QuantGist before signing up. Keep
this in sync with `backend/.../config.py PLAN_LIMITS` and the published pricing.
"""
from __future__ import annotations

from typing import Any

# Mirrors backend PLAN_LIMITS + published pricing. Prices are USD/month.
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "price_usd_month": 0, "requests": "100/day", "history": "365 days",
        "delay": "15 minutes", "sentiment": False, "webhooks": False,
        "ws_connections": 0, "watchlists": 1,
    },
    "starter": {
        "price_usd_month": 19, "requests": "5,000/day", "history": "3 years",
        "delay": "~1 minute", "sentiment": True, "webhooks": False,
        "ws_connections": 1, "watchlists": 3,
    },
    "pro": {
        "price_usd_month": 79, "requests": "50,000/day", "history": "10 years",
        "delay": "real-time", "sentiment": True, "webhooks": True,
        "ws_connections": 2, "watchlists": 10,
    },
    "team": {
        "price_usd_month": 299, "requests": "250,000/month", "history": "10 years",
        "delay": "real-time", "sentiment": True, "webhooks": True,
        "ws_connections": 10, "watchlists": "unlimited",
    },
    "enterprise": {
        "price_usd_month": "custom", "requests": "custom/unlimited",
        "history": "full archive", "delay": "real-time", "sentiment": True,
        "webhooks": True, "ws_connections": "custom", "watchlists": "unlimited",
    },
}

# Numeric caps for cost estimation.
_DAILY_CAP = {"free": 100, "starter": 5_000, "pro": 50_000}
_MONTHLY_CAP = {"team": 250_000}

BOT_ADD_ON: dict[str, Any] = {
    "status": "planned",
    "summary": "Opt-in metered usage add-on for paid plans, for high-volume bots/agents.",
    "billing_rail": "Stripe metered billing (first); x402 per-request pay is a future pilot.",
    "requires_hard_budget_cap": True,
    "explicit_approval_required": True,
}

RATE_LIMIT = {
    "scheme": "per-plan daily/monthly request quotas, enforced via Redis.",
    "headers": "Responses carry X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset.",
    "pagination": "List endpoints cap per_page at 100.",
    "on_exceed": "HTTP 429 with a RateLimitError detail once the quota is exhausted.",
}

SIGNUP_URL = "https://quantgist.com"
PRICING_URL = "https://quantgist.com/pricing"
STATUS_URL = "https://quantgist.com/status"
DOCS_URL = "https://quantgist.com/docs"

# use_case -> best REST endpoint + MCP tool. keywords drive matching.
ENDPOINT_CATALOG: list[dict[str, Any]] = [
    {
        "use_case": "Scheduled macro risk / no-trade windows (next releases)",
        "keywords": ["no-trade", "no trade", "blackout", "upcoming", "next", "soon",
                     "window", "risk window", "before trading", "schedule"],
        "rest": "GET /v1/calendar/upcoming",
        "mcp_tool": "get_upcoming_events",
        "min_plan": "free",
    },
    {
        "use_case": "Economic calendar for a specific day",
        "keywords": ["calendar", "today", "day", "schedule", "agenda"],
        "rest": "GET /v1/calendar",
        "mcp_tool": "get_economic_calendar",
        "min_plan": "free",
    },
    {
        "use_case": "Broad macro/market event feed over a date range",
        "keywords": ["events", "range", "history", "feed", "macro", "filter",
                     "country", "impact", "symbol"],
        "rest": "GET /v1/events",
        "mcp_tool": "get_events_range",
        "min_plan": "free",
    },
    {
        "use_case": "Full detail for one event",
        "keywords": ["detail", "single event", "event id", "specific event", "lookup"],
        "rest": "GET /v1/events/{id}",
        "mcp_tool": "get_event_detail",
        "min_plan": "free",
    },
    {
        "use_case": "Backtest-safe / point-in-time macro series",
        "keywords": ["backtest", "point-in-time", "vintage", "first print", "as_of",
                     "research", "historical series"],
        "rest": "GET /v2/backtest (or GET /v1/events?backtest_safe=true)",
        "mcp_tool": None,
        "min_plan": "pro",
    },
    {
        "use_case": "Unscheduled news / geopolitical / shock risk monitoring",
        "keywords": ["news", "radar", "unscheduled", "geopolitical", "shock", "oil",
                     "sanctions", "war", "cyber", "headline"],
        "rest": "GET /v1/news/radar",
        "mcp_tool": None,
        "min_plan": "free",
    },
    {
        "use_case": "Earnings (upcoming, history, beat/miss, surprises, season)",
        "keywords": ["earnings", "eps", "report", "ticker", "beat", "miss",
                     "surprise", "season", "quarter"],
        "rest": "GET /v1/earnings/*",
        "mcp_tool": "get_earnings_upcoming / get_earnings_for_ticker / get_earnings_summary "
                    "/ get_earnings_surprises / get_earnings_season_summary",
        "min_plan": "free",
    },
    {
        "use_case": "Market snapshot for major indices/instruments",
        "keywords": ["markets", "overview", "quote", "index", "indices", "price",
                     "snapshot", "stocks", "commodities"],
        "rest": "GET /v1/markets/overview",
        "mcp_tool": "get_markets_overview",
        "min_plan": "free",
    },
    {
        "use_case": "Push alerts for live automation",
        "keywords": ["webhook", "push", "alert", "notify", "real-time", "subscribe",
                     "callback"],
        "rest": "POST /v1/webhooks",
        "mcp_tool": None,
        "min_plan": "pro",
    },
]


# ---------------------------------------------------------------------------
# Builders — each returns (human_text, structured_dict)
# ---------------------------------------------------------------------------


def get_pricing() -> tuple[str, dict[str, Any]]:
    lines = ["**QuantGist pricing** (USD/month)\n"]
    for name, p in PLANS.items():
        price = p["price_usd_month"]
        price_s = "custom" if price == "custom" else f"${price}"
        lines.append(
            f"- **{name.capitalize()}** — {price_s} · {p['requests']} · {p['history']} "
            f"history · {p['delay']} delay · "
            f"sentiment {'yes' if p['sentiment'] else 'no'} · "
            f"webhooks {'yes' if p['webhooks'] else 'no'}"
        )
    lines.append(f"\nBot Usage Add-On: {BOT_ADD_ON['summary']} (status: {BOT_ADD_ON['status']}).")
    lines.append(f"Sign up free: {SIGNUP_URL} · Full pricing: {PRICING_URL}")
    structured = {
        "plans": PLANS,
        "bot_usage_add_on": BOT_ADD_ON,
        "signup_url": SIGNUP_URL,
        "pricing_url": PRICING_URL,
    }
    return "\n".join(lines), structured


def get_limits() -> tuple[str, dict[str, Any]]:
    lines = ["**QuantGist plan limits**\n"]
    for name, p in PLANS.items():
        lines.append(
            f"- **{name.capitalize()}**: {p['requests']} · {p['history']} history · "
            f"{p['delay']} delay · {p['ws_connections']} WS · "
            f"{p['watchlists']} watchlists"
        )
    lines.append(
        f"\nRate limiting: {RATE_LIMIT['scheme']} {RATE_LIMIT['headers']} "
        f"{RATE_LIMIT['pagination']} {RATE_LIMIT['on_exceed']}"
    )
    structured = {
        "plans": {k: {kk: v[kk] for kk in (
            "requests", "history", "delay", "ws_connections", "watchlists",
            "sentiment", "webhooks")} for k, v in PLANS.items()},
        "rate_limit": RATE_LIMIT,
    }
    return "\n".join(lines), structured


def recommend_endpoint(use_case: str) -> tuple[str, dict[str, Any]]:
    q = (use_case or "").lower()
    scored = []
    for entry in ENDPOINT_CATALOG:
        score = sum(1 for kw in entry["keywords"] if kw in q)
        # light boost if the use_case text appears in the description
        if any(w in entry["use_case"].lower() for w in q.split() if len(w) > 3):
            score += 1
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        text = (
            f"No specific match for {use_case!r}. Browse all endpoints at {DOCS_URL}, "
            "or try terms like 'no-trade window', 'earnings', 'news risk', 'markets', "
            "'backtest', or 'webhook alerts'."
        )
        return text, {"query": use_case, "matches": [], "docs_url": DOCS_URL}

    top = scored[0][1]
    alts = [e for _, e in scored[1:4]]

    def _fmt(e: dict[str, Any]) -> str:
        mcp = f" · MCP `{e['mcp_tool']}`" if e["mcp_tool"] else " · (no MCP tool — use REST)"
        return f"`{e['rest']}`{mcp} — {e['use_case']} (min plan: {e['min_plan']})"

    lines = [f"**Best fit for {use_case!r}:**", _fmt(top)]
    if alts:
        lines.append("\nAlternatives:")
        lines.extend(f"- {_fmt(e)}" for e in alts)
    structured = {
        "query": use_case,
        "best": top,
        "alternatives": alts,
        "docs_url": DOCS_URL,
    }
    return "\n".join(lines), structured


def estimate_usage_cost(
    requests_per_day: int, plan: str | None = None
) -> tuple[str, dict[str, Any]]:
    if requests_per_day < 0:
        raise ValueError("requests_per_day must be >= 0")
    monthly = requests_per_day * 30  # ~30-day month

    # Smallest plan that fits the daily volume (free/starter/pro), else team/enterprise.
    fits_daily = next(
        (p for p in ("free", "starter", "pro") if requests_per_day <= _DAILY_CAP[p]),
        None,
    )
    if fits_daily:
        recommended = fits_daily
    elif monthly <= _MONTHLY_CAP["team"]:
        recommended = "team"
    else:
        recommended = "enterprise"

    rec_price = PLANS[recommended]["price_usd_month"]
    notes = []
    if requests_per_day > _DAILY_CAP["pro"] and recommended in ("team", "enterprise"):
        notes.append(
            "Volume exceeds Pro's 50k/day; Team (250k/month) or Enterprise fits, or use "
            "the (planned) Bot Usage Add-On for metered overage on a paid plan."
        )
    if plan and plan.lower() in PLANS:
        chosen = plan.lower()
        cap = _DAILY_CAP.get(chosen)
        if cap is not None and requests_per_day > cap:
            notes.append(
                f"Your stated plan '{chosen}' caps at {cap:,}/day — {requests_per_day:,}/day "
                "would exceed it (429s or metered overage)."
            )

    price_s = "custom" if rec_price == "custom" else f"${rec_price}/mo"
    text = (
        f"**Usage estimate** — ~{requests_per_day:,} requests/day (~{monthly:,}/month)\n"
        f"Recommended plan: **{recommended.capitalize()}** ({price_s}, "
        f"{PLANS[recommended]['requests']})."
    )
    if notes:
        text += "\n" + "\n".join(f"- {n}" for n in notes)
    text += f"\nPricing: {PRICING_URL}"

    structured = {
        "requests_per_day": requests_per_day,
        "estimated_requests_per_month": monthly,
        "recommended_plan": recommended,
        "recommended_plan_price_usd_month": rec_price,
        "stated_plan": plan,
        "notes": notes,
        "bot_usage_add_on": BOT_ADD_ON,
        "pricing_url": PRICING_URL,
    }
    return text, structured

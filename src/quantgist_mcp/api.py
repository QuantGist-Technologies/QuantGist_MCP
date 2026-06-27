"""Thin async httpx wrapper around the QuantGist REST API."""
from __future__ import annotations

import contextvars
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

BASE_URL = os.environ.get("QUANTGIST_API_URL", "https://api.quantgist.com/v1")
_DEFAULT_TIMEOUT = 20.0

# Per-request API key, set by the HTTP transport from an incoming X-API-Key
# header. The stdio transport never sets this, so it falls back to the env var.
_request_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "quantgist_request_api_key", default=None
)


def set_request_api_key(key: str | None) -> contextvars.Token:
    """Bind an API key for the current request context. Returns a reset token."""
    return _request_api_key.set(key)


def reset_request_api_key(token: contextvars.Token) -> None:
    _request_api_key.reset(token)


class QuantGistAPIError(Exception):
    """Raised when the QuantGist API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"QuantGist API error {status_code}: {detail}")


class QuantGistAPI:
    """Async client for the QuantGist macro event API.

    Usage::

        async with QuantGistAPI() as api:
            events = await api.get_upcoming_events(hours=4, impact="high")
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or _request_api_key.get() or os.environ.get("QUANTGIST_API_KEY", "")
        if not key:
            raise ValueError(
                "No QuantGist API key available. Set QUANTGIST_API_KEY, or (when using "
                "the HTTP transport) send your key in the X-API-Key request header."
            )
        self._headers = {"X-API-Key": key, "Accept": "application/json"}
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------ #
    # Context-manager helpers                                              #
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> "QuantGistAPI":
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self._headers,
            timeout=_DEFAULT_TIMEOUT,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "QuantGistAPI must be used as an async context manager."
            )
        return self._client

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        client = self._ensure_client()
        # Remove None values so they don't appear as the string "None"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await client.get(path, params=clean_params)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = body.get("detail") or body.get("error") or resp.text
            except Exception:
                detail = resp.text
            raise QuantGistAPIError(resp.status_code, detail)
        return resp.json()

    # ------------------------------------------------------------------ #
    # Public API methods                                                   #
    # ------------------------------------------------------------------ #

    async def get_upcoming_events(
        self,
        hours: int = 24,
        impact: str | None = None,
    ) -> list[dict]:
        """Return events scheduled in the next *hours* hours.

        The backend does not expose a separate /events/upcoming route; this
        maps the upcoming window to GET /events with canonical filters.
        """
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "from_date": now.isoformat(),
            "to_date": (now + timedelta(hours=hours)).isoformat(),
            "per_page": 100,
        }
        if impact and impact != "all":
            params["impact"] = impact
        data = await self._get("/events", params)
        if isinstance(data, list):
            return data
        return data.get("data", data.get("events", []))

    async def get_events(
        self,
        from_time: str | None = None,
        to_time: str | None = None,
        impact: str | None = None,
        country: str | None = None,
        symbol: str | None = None,
    ) -> list[dict]:
        """Return events within a date/time range with optional filters.

        Args:
            from_time: ISO 8601 start (date or datetime).
            to_time: ISO 8601 end (date or datetime).
            impact: high | medium | low.
            country: 2-letter country code, e.g. "US".
            symbol: Forex/commodity symbol, e.g. "XAUUSD".

        Returns:
            List of event dicts.
        """
        params: dict[str, Any] = {
            "from_date": from_time,
            "to_date": to_time,
            "impact": impact if impact and impact != "all" else None,
            "country": country,
            "symbol": symbol,
        }
        data = await self._get("/events", params)
        if isinstance(data, list):
            return data
        return data.get("data", data.get("events", []))

    async def get_event(self, event_id: str) -> dict:
        """Return full detail for a single event by its ID.

        Args:
            event_id: Unique event identifier.

        Returns:
            Event dict.
        """
        data = await self._get(f"/events/{event_id}")
        # API may wrap the event in {"data": {...}}
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            return data["data"]
        return data

    # ------------------------------------------------------------------ #
    # Earnings API                                                         #
    # ------------------------------------------------------------------ #

    async def get_earnings_upcoming(self, limit: int = 20) -> list[dict]:
        """Return the next N upcoming earnings reports.

        Args:
            limit: Number of reports to return (default 20).

        Returns:
            List of earnings event dicts.
        """
        data = await self._get("/earnings/upcoming", {"limit": limit})
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def get_earnings_for_ticker(self, ticker: str, limit: int = 20) -> list[dict]:
        """Return earnings history for a single ticker.

        Args:
            ticker: Ticker symbol (e.g. "AAPL").
            limit: Results per page (default 20).

        Returns:
            List of earnings event dicts.
        """
        data = await self._get(f"/earnings/{ticker.upper()}", {"limit": limit})
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def get_earnings_summary(self, ticker: str) -> dict:
        """Return beat/miss/in-line summary for a ticker.

        Args:
            ticker: Ticker symbol.

        Returns:
            Summary dict with beat, miss, in_line, total, beat_rate.
        """
        data = await self._get(f"/earnings/{ticker.upper()}/summary")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    async def get_earnings_surprises(self, limit: int = 20) -> list[dict]:
        """Return largest cross-market EPS surprises.

        Args:
            limit: Maximum results (default 20).

        Returns:
            List of surprise dicts.
        """
        data = await self._get("/earnings/surprises", {"limit": limit})
        if isinstance(data, list):
            return data
        return data.get("data", [])

    async def get_earnings_season_summary(self) -> dict:
        """Return index-level aggregate for the current earnings season.

        Returns:
            Season summary dict.
        """
        data = await self._get("/earnings/season/summary")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    # ------------------------------------------------------------------ #
    # Markets API                                                          #
    # ------------------------------------------------------------------ #

    async def get_markets_overview(self) -> dict:
        """Return the market overview snapshot.

        The payload is a dict of the form
        ``{as_of, recency, delay_minutes, groups: [{name, items: [...]}, ...]}``.

        Returns:
            The overview dict (unwrapped from a ``{"data": ...}`` envelope if present).
        """
        data = await self._get("/markets/overview")
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            return data["data"]
        return data

    # ------------------------------------------------------------------ #
    # Changelog                                                            #
    # ------------------------------------------------------------------ #

    async def get_changelog(self) -> list[dict]:
        """Return the public API changelog entries.

        Returns:
            List of changelog entry dicts.
        """
        data = await self._get("/changelog")
        if isinstance(data, list):
            return data
        return data.get("data", [])

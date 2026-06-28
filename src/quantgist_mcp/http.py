"""Streamable-HTTP transport for the QuantGist MCP server.

Runs the same `Server` (and its 10 tools) as the stdio transport, but over HTTP so
it can be hosted as a long-running network service (Docker, Coolify, etc.).

Endpoints:
  GET  /health   — liveness probe (no auth)
  *    /mcp       — MCP streamable-HTTP endpoint

Authentication (per request, in priority order):
  1. `X-API-Key` request header — the caller's own QuantGist key (multi-tenant).
  2. `QUANTGIST_API_KEY` env var — a server-side fallback key (single-tenant).

Run with: `quantgist-mcp-http` (honours PORT / HOST env vars; defaults 0.0.0.0:8000).
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator
from urllib.parse import parse_qs

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from quantgist_mcp import __version__
from quantgist_mcp.api import reset_request_api_key, set_request_api_key
from quantgist_mcp.server import server

# Stateless = a fresh session per request; simplest model for a horizontally
# scalable hosted endpoint behind a load balancer.
_session_manager = StreamableHTTPSessionManager(
    app=server,
    json_response=False,
    stateless=True,
)


def _extract_api_key(scope: Scope) -> str | None:
    """Resolve the caller's QuantGist key, in priority order:

    1. ``X-API-Key`` header (preferred).
    2. ``Authorization: Bearer <key>`` header.
    3. ``?apiKey=`` / ``?api_key=`` / ``?key=`` query parameter — for connector UIs
       (e.g. ChatGPT) that only accept a URL and can't set custom headers.
    """
    headers = dict(scope.get("headers") or [])

    raw = headers.get(b"x-api-key")
    if raw:
        return raw.decode()

    auth = headers.get(b"authorization")
    if auth:
        value = auth.decode()
        if value.lower().startswith("bearer "):
            return value[7:].strip()

    qs = scope.get("query_string") or b""
    if qs:
        params = parse_qs(qs.decode())
        for name in ("apiKey", "api_key", "key", "x-api-key"):
            if params.get(name):
                return params[name][0]

    return None


async def _handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
    """ASGI handler that binds the caller's API key (if any) for the request."""
    token = set_request_api_key(_extract_api_key(scope))
    try:
        await _session_manager.handle_request(scope, receive, send)
    finally:
        reset_request_api_key(token)


async def _health(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        {"status": "ok", "service": "quantgist-mcp", "version": __version__}
    )
    await response(scope, receive, send)


async def _root(scope: Scope, receive: Receive, send: Send) -> None:
    """Dispatch /health to liveness; everything else to the MCP endpoint.

    The MCP app is served at the mount ROOT (not a "/mcp" sub-mount) so the exact path
    returns the MCP response directly with NO trailing-slash 307 redirect. Strict clients
    (e.g. the Smithery gateway) do not follow 307 on POST, so a redirect breaks
    initialization. The proxy routes only /mcp* to this container, and the in-container
    healthcheck uses /health.
    """
    if scope["type"] == "http" and scope.get("path") in ("/health", "/mcp/health"):
        await _health(scope, receive, send)
        return
    await _handle_mcp(scope, receive, send)


@contextlib.asynccontextmanager
async def _lifespan(_: Starlette) -> AsyncIterator[None]:
    async with _session_manager.run():
        yield


app = Starlette(
    debug=False,
    routes=[Mount("/", app=_root)],
    lifespan=_lifespan,
)


def main() -> None:
    """Entry point for the `quantgist-mcp-http` console script."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    if not os.environ.get("QUANTGIST_API_KEY"):
        print(
            "WARNING: QUANTGIST_API_KEY is not set — callers must supply their own key "
            "via the X-API-Key header or every tool call will fail.",
            flush=True,
        )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

# CLAUDE.md — QuantGist MCP Server

**Layer:** L2 · **Tentpole:** T2 (AI/developer adoption)
**Stack:** Python 3.10+ using the official `mcp` SDK (low-level `Server` API, stdio transport)
**Protocol:** Model Context Protocol (MCP)
**Distribution:** PyPI package `quantgist-mcp` (entry point `quantgist-mcp`), runnable via `pip`/`uv`/`uvx`.

---

## Purpose

Exposes QuantGist data as MCP tools so Claude and other AI agents can query macro
events, earnings, and market snapshots — all within an AI conversation.

Use cases:
- Claude Code agents checking event risk before generating trading code
- Claude.ai / Claude Desktop users asking "what macro events affect EURUSD this week?"
- AI trading assistants checking "is it safe to trade gold right now?"

The server is a thin client over the public QuantGist REST API
(`https://api.quantgist.com/v1`). It holds no data of its own — every tool maps to
one or two REST calls. The earnings and markets tools require the corresponding
backend feature flags (`EARNINGS_API_ENABLED`, `MARKETS_API_ENABLED`) to be on in
production; both are enabled today.

---

## MCP tools (15)

Macro events:

| Tool | Maps to |
|------|---------|
| `get_upcoming_events` | `GET /events` (now → now+N hours) |
| `get_events_range` | `GET /events` (explicit range + country/impact/symbol filters) |
| `get_economic_calendar` | `GET /events` (single day, grouped by release time) |
| `get_event_detail` | `GET /events/{id}` |

Earnings:

| Tool | Maps to |
|------|---------|
| `get_earnings_upcoming` | `GET /earnings/upcoming` |
| `get_earnings_for_ticker` | `GET /earnings/{ticker}` |
| `get_earnings_summary` | `GET /earnings/{ticker}/summary` |
| `get_earnings_surprises` | `GET /earnings/surprises` |
| `get_earnings_season_summary` | `GET /earnings/season/summary` |

Markets:

| Tool | Maps to |
|------|---------|
| `get_markets_overview` | `GET /markets/overview` |

Discovery / help (read-only, **no API key** — static/computed data in `discovery.py`):

| Tool | Source |
|------|--------|
| `get_pricing` | `discovery.PLANS` + `BOT_ADD_ON` (keep in sync with backend `PLAN_LIMITS`) |
| `get_limits` | `discovery.PLANS` + `RATE_LIMIT` |
| `recommend_endpoint` | keyword match over `discovery.ENDPOINT_CATALOG` |
| `get_status` | keyless `GET /changelog` reachability + status page URL |
| `estimate_usage_cost` | computed from `discovery._DAILY_CAP` / `_MONTHLY_CAP` |

---

## Package structure

```
Quangist_MCP/
├── src/
│   └── quantgist_mcp/
│       ├── __init__.py       # __version__
│       ├── server.py         # MCP Server, tool schemas, dispatch, stdio entry main()
│       ├── http.py           # streamable-HTTP transport (quantgist-mcp-http), Starlette app
│       ├── api.py            # QuantGistAPI — async httpx wrapper; per-request key contextvar
│       └── formatters.py     # raw event/earnings/markets dicts → readable text/markdown
├── pyproject.toml            # hatchling build; scripts quantgist-mcp + quantgist-mcp-http
├── server.json               # official MCP Registry manifest
├── Dockerfile                # python:3.12-slim + uv, runs quantgist-mcp-http
├── docker-compose.yml        # Coolify deploy (pre-built GHCR image, never build:)
├── DEPLOY.md                 # Docker / Compose / Coolify hosting guide
├── README.md
├── CHANGELOG.md
├── claude_desktop_config_example.json
└── .github/workflows/
    ├── ci.yml                # import check + build; PyPI + MCP-registry publish on v* tags
    └── docker-build.yml      # build arm64 → GHCR → Coolify deploy on push to main
```

Two transports, one `Server`: stdio (`quantgist-mcp`, in `server.py`) and streamable-HTTP
(`quantgist-mcp-http`, in `http.py`). HTTP reads a per-request `X-API-Key` header (via the
`set_request_api_key` contextvar in `api.py`), falling back to the `QUANTGIST_API_KEY` env var.

There is **no** `tools/` subpackage — all tool schemas and handlers live in `server.py`,
dispatched through the `handlers` dict in `_dispatch()`.

---

## Commands

```bash
uv sync
uv run quantgist-mcp          # start the MCP server (requires QUANTGIST_API_KEY)
uv run ruff check src/        # lint
uv run ruff format src/       # format
uv build                      # build sdist + wheel into dist/
```

Releases publish automatically — see **Release & deploy** below. Do **not** run `uv publish`
manually (PyPI uses trusted publishing via CI on `v*` tags).

---

## Claude Desktop / Claude Code integration

After `pip install quantgist-mcp`:

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "quantgist-mcp",
      "env": { "QUANTGIST_API_KEY": "qg_live_..." }
    }
  }
}
```

Or without installing, via `uv run --directory`:

```json
{
  "mcpServers": {
    "quantgist": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Quangist_MCP", "quantgist-mcp"],
      "env": { "QUANTGIST_API_KEY": "qg_live_..." }
    }
  }
}
```

---

## Rules

- **Every tool handler returns a `(text, structured)` tuple.** `text` is the human-readable
  rendering (via `formatters.py`); `structured` is a JSON-serializable **dict** matching the tool's
  `outputSchema`. List tools wrap as `{"events"|"earnings": [...], "count": N}`; detail/summary/markets
  tools return the underlying object. `call_tool` returns `([TextContent], structured)`.
- Always surface `release_time` / `release_time_utc` in event output — callers need raw timestamps.
- **Errors return `types.CallToolResult(isError=True)`** (via `_error_result`) — NOT a tuple. This
  bypasses `outputSchema` validation. Raise `QuantGistAPIError` from `api.py` for non-2xx upstream.
- Never hardcode the API key. stdio reads `QUANTGIST_API_KEY` (fails fast in `main()`); HTTP reads the
  per-request `X-API-Key` header via the `api.py` contextvar, env as fallback.
- Keep tool + parameter descriptions concise and precise — they land in the model's context and are
  scored by registries.
- **Adding a tool — do ALL of these** or scans/score regress:
  1. Append the `types.Tool` to `TOOLS` (with `description` + per-param `description`).
  2. Add an entry to `_TOOL_TITLES` and `_OUTPUT_SCHEMAS` (the post-`TOOLS` loop attaches
     `title` + `annotations` + `outputSchema`).
  3. Write a `_tool_*` handler returning `(text, structured_dict)`.
  4. Register it in the `_dispatch` `handlers` dict.
  5. Document it in `README.md` **and** `web/.../docs/mcp/page.tsx` (keep tool counts in sync).

---

## Release & deploy

One tag ships everything. To cut a release:

1. Bump version in **all three**: `pyproject.toml`, `src/quantgist_mcp/__init__.py`, and
   `server.json` (×2 — top-level + package). Update `CHANGELOG.md`.
2. `git commit && git push origin main` — push to `main` triggers **`docker-build.yml`**: build
   `linux/arm64` → push `ghcr.io/quantgist-technologies/quantgist-mcp` → call the Coolify deploy
   webhook → live host pulls + redeploys (`pull_policy: always`) → health-gate on `/mcp/health`.
3. `git tag -a vX.Y.Z -m … && git push origin vX.Y.Z` — the tag triggers **`ci.yml`**: PyPI
   (trusted publishing, OIDC) + official MCP Registry (`mcp-publisher`, OIDC).
4. After it lands, the user re-publishes on **Smithery** (dashboard) to re-scan.

CI secrets/vars already set: secret `COOLIFY_API_TOKEN`; vars `COOLIFY_MCP_DEPLOY_UUID`
(`ob3ch1y0yudvpsm9m6w2u4ri`), `MCP_HEALTH_URL` (`/mcp/health`). Full ops runbook: `DEPLOY.md`.
Distribution/registry guide: `../../internals/mcp-distribution.md`. Cross-MCP playbook:
`../../0planning/MCP-checklist.md`.

---

## Critical invariants (do not regress)

- **HTTP: serve the MCP app at the mount ROOT** (`Mount("/", _root)` in `http.py`), never
  `Mount("/mcp", …)`. The sub-mount adds a **307** trailing-slash redirect that strict gateways
  (Smithery) won't follow on POST → init 502. `POST /mcp` must return **200**, not 307.
- Keep the **empty `list_resources` / `list_prompts` handlers** (avoids "method not found" in scans).
- Keep **annotations + `outputSchema` on every tool** (capability-quality score; machine readability).
- `server.json` `description` ≤ **100 chars**; `version` == PyPI version; README keeps the
  `mcp-name: io.github.QuantGist-Technologies/quantgist-mcp` marker (registry ownership check).
- `docker-compose.yml`: keep `pull_policy: always`, no Coolify domain (routing is the Traefik
  file-router `deploy/traefik-mcp.yml`, priority 2000 — it must outrank `api-no-redirect.yml`).
- Coolify auto-deploy stays **off**; only CI triggers deploys.

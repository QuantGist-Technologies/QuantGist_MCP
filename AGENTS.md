# AGENTS.md — quantgist-mcp

QuantGist MCP server: 10 read-only tools (macro events, earnings, markets) over **two transports**
from one codebase — stdio (`quantgist-mcp`) and streamable-HTTP (`quantgist-mcp-http`). Thin client
over `https://api.quantgist.com/v1`. Python 3.10+, low-level `mcp` SDK.

**`CLAUDE.md` is the full source of truth** (architecture, tool list, release & deploy, rules). Read it
before non-trivial work. This file is the short version for any agent.

## Commands
```bash
uv sync
uv run quantgist-mcp                 # stdio server (needs QUANTGIST_API_KEY)
uv run quantgist-mcp-http            # HTTP server (PORT/HOST env; /health + /mcp)
uvx ruff check src/                  # lint
uv build                             # sdist + wheel
```
Test against prod with a real key before shipping: build + clean-install, then a full MCP handshake
(initialize → list_tools → call_tool) over **both** transports.

## Layout
`src/quantgist_mcp/`: `server.py` (tools, dispatch, stdio `main`), `http.py` (HTTP transport),
`api.py` (async httpx client + per-request key contextvar), `formatters.py` (dicts → text). All tool
schemas/handlers live in `server.py` (no `tools/` subpackage).

## Invariants — do NOT regress
- **HTTP serves the MCP app at the mount ROOT** (`Mount("/", _root)`), never `Mount("/mcp")` — the
  sub-mount adds a 307 redirect that breaks strict gateways (Smithery → 502). `POST /mcp` must be 200.
- Every tool handler returns a **`(text, structured_dict)` tuple**; the dict matches the tool's
  `outputSchema`. Errors return `CallToolResult(isError=True)` (not a tuple).
- Keep on every tool: `description` + per-param descriptions, `title`, `annotations`, `outputSchema`.
- Keep the empty `list_resources`/`list_prompts` handlers (avoids "method not found" in scans).
- Never hardcode the API key (env for stdio; `X-API-Key` header for HTTP).

## Adding a tool (all five, or scans/score regress)
1. Add `types.Tool` to `TOOLS`. 2. Add to `_TOOL_TITLES` + `_OUTPUT_SCHEMAS`. 3. Write `_tool_*`
returning `(text, structured)`. 4. Register in `_dispatch`. 5. Document in `README.md` **and**
`web/.../docs/mcp/page.tsx` (keep tool counts in sync).

## Release (one tag ships everything)
1. Bump version in `pyproject.toml`, `src/quantgist_mcp/__init__.py`, and `server.json` (×2); update
   `CHANGELOG.md`. 2. Push to `main` → `docker-build.yml` builds arm64 → GHCR → Coolify webhook →
   live redeploy. 3. `git tag -a vX.Y.Z && git push origin vX.Y.Z` → `ci.yml` publishes PyPI + MCP
   Registry (both OIDC; do **not** `uv publish` manually). Then re-publish on Smithery to re-scan.

Constraints: `server.json` `description` ≤ 100 chars and `version` == PyPI version; README keeps the
`mcp-name: io.github.QuantGist-Technologies/quantgist-mcp` marker. Runbook: `DEPLOY.md`. Distribution:
`../../internals/mcp-distribution.md`. Cross-MCP playbook: `../../0planning/MCP-checklist.md`.

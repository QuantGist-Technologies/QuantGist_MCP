# Deploying QuantGist MCP

The server ships **two transports** from one codebase:

| Transport | Entry point | Use for |
|-----------|-------------|---------|
| **stdio** | `quantgist-mcp` | Local clients that launch the server as a subprocess (Claude Desktop, Claude Code). |
| **streamable-HTTP** | `quantgist-mcp-http` | Hosting as a long-running network service (Docker, Coolify, any PaaS). |

This guide covers the HTTP transport — running it under Docker and on Coolify.

---

## 1. Prerequisites — install Docker

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in afterwards
docker version
```

**macOS / Windows:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/), then confirm:
```bash
docker version
```

You also need a **QuantGist API key** (`qg_live_...` or `qg_test_...`) — free at <https://quantgist.com>.

---

## 2. Run with `docker run` (quickest)

Build the image from source and run it:

```bash
git clone https://github.com/QuantGist-Technologies/QuantGist_MCP
cd QuantGist_MCP

docker build -t quantgist-mcp .

docker run -d --name quantgist-mcp \
  -p 8000:8000 \
  -e QUANTGIST_API_KEY=qg_live_YOUR_KEY \
  quantgist-mcp
```

Verify it's up:
```bash
curl http://localhost:8000/health
# {"status":"ok","service":"quantgist-mcp","version":"0.3.0"}
```

The MCP endpoint is `http://localhost:8000/mcp`.

### Authentication model

- **Single-tenant:** set `QUANTGIST_API_KEY` on the container (above). Every request uses that key.
- **Multi-tenant:** omit the env key and have each caller send **their own** key in an `X-API-Key`
  header. If both are present, the header wins. This lets you host one endpoint that bills each
  user against their own QuantGist quota.

> ⚠️ If you expose a single-tenant instance publicly, anyone who finds the URL can spend your
> QuantGist quota. Put it behind auth (reverse-proxy basic-auth, Cloudflare Access, a VPN/Tailscale),
> or use the multi-tenant header model.

---

## 3. Run with Docker Compose

`docker-compose.yml` in this repo references the **pre-built GHCR image** (for Coolify). To
self-host from source instead, use this override:

```yaml
# docker-compose.local.yml
services:
  quantgist-mcp:
    build: .
    image: quantgist-mcp:local
    restart: unless-stopped
    environment:
      - QUANTGIST_API_KEY=${QUANTGIST_API_KEY}
      - PORT=8000
    ports:
      - "8000:8000"
```

```bash
export QUANTGIST_API_KEY=qg_live_YOUR_KEY
docker compose -f docker-compose.local.yml up -d --build
```

---

## 4. Connect a client to the hosted server

**Claude Code** (or any client supporting HTTP/streamable transports):
```bash
claude mcp add --transport http quantgist https://your-host.example.com/mcp \
  --header "X-API-Key: qg_live_YOUR_KEY"
```

**Generic MCP client config:**
```json
{
  "mcpServers": {
    "quantgist": {
      "type": "streamable-http",
      "url": "https://your-host.example.com/mcp",
      "headers": { "X-API-Key": "qg_live_YOUR_KEY" }
    }
  }
}
```

---

## 5. Deploy on Coolify (GitHub Actions → GHCR → Coolify)

The pipeline mirrors the quantgist-web app: GitHub Actions builds a `linux/arm64` image (the
Coolify host is ARM64), pushes it to GHCR, and triggers a Coolify redeploy that **pulls** the
image (Coolify never builds — keeps deploys fast and avoids the slow ARM build box).

Files involved:
- `Dockerfile` — the image.
- `docker-compose.yml` — Coolify deploys this (uses `image:`, never `build:`).
- `.github/workflows/docker-build.yml` — build → push → deploy.

### One-time setup

1. **Create the Coolify application**
   - Coolify → *New Resource* → *Docker Compose* → connect this GitHub repo.
   - Paste / point at `docker-compose.yml`.
   - **Disable auto-deploy** (only GitHub Actions should trigger deploys, so Coolify doesn't tear
     down the container before the image pull completes).
   - Set the public domain (e.g. `mcp.quantgist.com`) and enable TLS. Coolify's proxy routes it to
     the container's port `8000`.

2. **Set the env var in Coolify** (Laravel-encrypted via the UI, or `php artisan tinker` — see the
   repo `CLAUDE.md`): `QUANTGIST_API_KEY=qg_live_...` with `is_shown_once=false`.

3. **GHCR access** — the image is `ghcr.io/quantgist-technologies/quantgist-mcp`. If the package is
   private, give the Coolify host a GHCR pull credential (the same helper-image PAT pattern used by
   quantgist-web). Making the GHCR package **public** avoids this entirely.

4. **Wire the deploy trigger** — in the GitHub repo:
   - Secret `COOLIFY_API_TOKEN` (Coolify → Keys & Tokens → API tokens).
   - Variable `COOLIFY_MCP_DEPLOY_UUID` = the application's deploy UUID
     (Coolify app → Webhooks / *Deploy* endpoint).
   - Variable `MCP_HEALTH_URL` = `https://mcp.quantgist.com/health` (optional; gates the post-deploy
     health wait).

   Until `COOLIFY_MCP_DEPLOY_UUID` is set, the workflow still builds & pushes the image but **skips**
   the deploy step cleanly.

### Deploying

Push to `main` touching `src/**`, `Dockerfile`, or `pyproject.toml` (or run the workflow manually):
```bash
gh workflow run docker-build.yml
```

Confirm:
```bash
curl https://mcp.quantgist.com/health
```

# QuantGist MCP server — streamable-HTTP transport, for self-hosting / Coolify.
# Build:  docker build -t quantgist-mcp .
# Run:    docker run -p 8000:8000 -e QUANTGIST_API_KEY=qg_live_... quantgist-mcp
FROM python:3.12-slim

# Faster, reproducible installs via uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install dependencies first (cached layer) using only the manifest.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# Drop privileges.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Container-level healthcheck hits the liveness probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health').read()" || exit 1

CMD ["quantgist-mcp-http"]

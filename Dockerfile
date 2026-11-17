# byg-mcp som container til Cloudflare Containers (bygges af Cloudflare Workers Builds ved push til main).
# Ingen nøgler i billedet: de kommer som miljøvariabler fra Workerens secrets ved opstart.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Afhængigheder først, så de caches mellem builds
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# Cachen er midlertidig i containeren
ENV BYG_MCP_HOST=0.0.0.0 \
    BYG_MCP_PORT=8080 \
    BYG_MCP_STATELESS=1 \
    BYG_MCP_SKJUL_VAERKTOEJER=energimaerke \
    BYG_MCP_CACHE=/tmp/byg-mcp-cache.sqlite

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8080
CMD ["/app/.venv/bin/byg-mcp", "--http"]

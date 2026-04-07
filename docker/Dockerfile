# syntax=docker/dockerfile:1

# Builder stage — install dependencies with uv
FROM ghcr.io/astral-sh/uv:0.11.3-python3.14-trixie-slim AS builder

WORKDIR /build

ARG APP_VERSION=0.1.0

COPY pyproject.toml ./

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN uv sync --frozen --no-dev --no-install-project --no-cache 2>/dev/null || \
    uv sync --no-dev --no-install-project --no-cache

# Copy source code
COPY cwo/ ./cwo/

# Runtime stage
FROM ghcr.io/astral-sh/uv:0.11.3-python3.14-trixie-slim

ARG APP_VERSION=0.1.0

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/cwo /app/cwo

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

LABEL org.opencontainers.image.source="https://github.com/cdelgehier/crossplane-watcher-operator"
LABEL org.opencontainers.image.description="Crossplane Watcher Operator — watches Crossplane claims and posts status updates on GitHub PRs"
LABEL org.opencontainers.image.version="$APP_VERSION"

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app
USER app

ENTRYPOINT ["python", "-m", "cwo.main"]

# Alpine-вариант:
#   docker build --build-arg BASE=ghcr.io/astral-sh/uv:python3.12-alpine \
#     --build-arg RUNTIME=python:3.12-alpine -t yozhka-mcp:alpine .
ARG BASE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG RUNTIME=python:3.12-slim-bookworm

FROM ${BASE} AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_HTTP_TIMEOUT=180
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM ${RUNTIME}
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
USER 65534
EXPOSE 8000
ENTRYPOINT ["python", "-m", "yozhka_mcp.server"]

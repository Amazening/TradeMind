# syntax=docker/dockerfile:1
# One image: the API, with the built frontend inside it.

# 1. Build the frontend.
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Install the Python app and its locked dependencies into a virtual environment.
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# 3. The image that runs. No build tools, and not as root.
FROM python:3.13-slim
RUN useradd --system --no-create-home --uid 10001 app \
    && mkdir /data && chown app /data
COPY --from=builder /app/.venv /app/.venv
COPY --from=frontend /frontend/dist /app/frontend-dist
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIR=/app/frontend-dist \
    PRICE_CACHE_DIR=/data/prices
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
# --behind-proxy is safe here because the compose file only exposes this port to the proxy.
CMD ["trademind", "serve", "--host", "0.0.0.0", "--port", "8000", "--behind-proxy"]

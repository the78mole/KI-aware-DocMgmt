# syntax=docker/dockerfile:1

# --- SPA bauen ---
FROM node:24-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Backend-Abhängigkeiten ---
FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev

# --- Laufzeit ---
FROM python:3.13-slim
RUN useradd --system --uid 10001 docmgmt
WORKDIR /app
COPY --from=backend /app /app
COPY --from=frontend /app/dist /app/static
ENV PATH="/app/.venv/bin:$PATH" STATIC_DIR=/app/static
USER docmgmt
EXPOSE 8000
CMD ["fastapi", "run", "src/docmgmt/main.py", "--host", "0.0.0.0", "--port", "8000"]

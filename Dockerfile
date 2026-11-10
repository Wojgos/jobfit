# Single image for Cloud Run: FastAPI serves the API and the built Angular app.

FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx ng build --configuration production

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=frontend /frontend/dist/frontend/browser ./static

ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static
RUN useradd --create-home appuser
USER appuser

# Cloud Run sets PORT (8080). Migrations run before the server starts.
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]

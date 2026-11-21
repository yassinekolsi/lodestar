# One image for a hosted deployment (Render, see render.yaml and docs/DEPLOY.md): the backend
# serves the API under /api and the built frontend everywhere else, so the browser, its
# WebSockets and the API share one origin. Postgres (Neon) and Qdrant (Qdrant Cloud) are outside.
#
# Local development keeps its own images: backend/Dockerfile and frontend/Dockerfile, via compose.

# 1. The frontend, built once ------------------------------------------------------------------
FROM node:24.22.0-slim AS web
ENV ONNXRUNTIME_NODE_INSTALL_CUDA=skip
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. The backend, with the frontend's files ------------------------------------------------------
FROM python:3.14.5-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HF_HOME=/opt/hf \
    LODESTAR_WEB_DIR=/app/web \
    LODESTAR_MEMORY_DIR=/app/memory

# LightGBM (growth forecast, docs/plan/10) needs the OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project --extra whisper
# The embedding models and the private-voice speech model ship in the image: no download on the
# first request, and nothing fetched while a student waits.
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5'); SparseTextEmbedding('Qdrant/bm25')" \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')" \
    && chmod -R a+rX /opt/fastembed /opt/hf

RUN useradd --create-home --uid 1000 lodestar && mkdir -p /app/memory && chown lodestar /app/memory
COPY alembic.ini ./
COPY backend ./backend
COPY registry ./registry
COPY models ./models
COPY --from=web /web/dist ./web

USER lodestar
EXPOSE 8000
# Render sets PORT. Migrations run first, so a fresh Neon database is ready on the first boot.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.api.web:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

FROM python:3.11-slim AS base

ARG BUILD_REV=2026-04-17-enum-fix-v4
ENV BUILD_REV=${BUILD_REV}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install .

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
RUN chmod +x /app/scripts/start.sh

RUN useradd --system --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

CMD ["/app/scripts/start.sh"]

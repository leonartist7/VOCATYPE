# ── Stage 1: Build ──────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM python:3.12-slim

# Security: run as non-root
RUN groupadd -r vocatype && useradd -r -g vocatype vocatype

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/

# Switch to non-root user
USER vocatype

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run with uvicorn
CMD uvicorn app.main:app --host ${HOST} --port ${PORT} --workers 1 --timeout-keep-alive 30

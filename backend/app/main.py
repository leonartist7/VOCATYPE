"""
Vocatype Backend — FastAPI Application Entry Point.

Initializes the transcription stack on startup (faster-whisper locally, plus
the DeepSeek cleaning client in online mode), configures CORS and security
middleware, mounts the audio processing route, and exposes observability
endpoints (health, metrics).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.middleware import SecurityMiddleware
from app.routes.audio import router as audio_router
from app.services.metrics import content_type, metrics_enabled, render_metrics

# ── Logging ─────────────────────────────────────────────────────────────────────

settings = get_settings()


class _JsonFormatter(logging.Formatter):
    """Emit structured JSON lines for Cloud Run / log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def _configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    if settings.log_format == "json":
        handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]


logger = logging.getLogger("vocatype")


# ── Lifespan ────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    mode = settings.transcription_mode
    logger.info("🚀 Vocatype backend starting up (mode=%s)…", mode)

    # Whisper STT is the engine in both modes — pre-warm it.
    from app.services.whisper import _load_model

    try:
        _load_model()
        logger.info("✅ Whisper model ready (model=%s)", settings.whisper_model)
    except Exception as exc:
        logger.warning("⚠ Whisper model not available at startup: %s", exc)

    if settings.is_online:
        if not settings.deepseek_api_key:
            logger.error("DEEPSEEK_API_KEY is empty — online mode cannot clean text.")
            raise RuntimeError("DEEPSEEK_API_KEY is required when TRANSCRIPTION_MODE=online.")
        from app.services.deepseek import initialize_deepseek

        initialize_deepseek()
        logger.info("✅ DeepSeek client initialized (model=%s)", settings.deepseek_model)

    yield  # App is running

    logger.info("🛑 Vocatype backend shutting down...")


# ── App ─────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Vocatype API",
    description=(
        "AI-powered dictation backend. Transcribes audio locally with "
        "faster-whisper (offline), then — in online mode — cleans the text "
        "with DeepSeek V4 Flash: punctuation, filler-word removal, tone."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security & observability middleware ─────────────────────────────────────────
# Added last so it wraps everything above it in the stack.

app.add_middleware(SecurityMiddleware)

# ── Logging init ────────────────────────────────────────────────────────────────

_configure_logging()

# ── Routes ──────────────────────────────────────────────────────────────────────

app.include_router(audio_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/preview", response_class=HTMLResponse, include_in_schema=False)
async def preview_page():
    """Serve the interactive Web Preview & Studio UI."""
    static_dir = Path(__file__).parent / "static"
    preview_file = static_dir / "preview.html"
    if preview_file.exists():
        return HTMLResponse(content=preview_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Vocatype API Server</h1><p>Preview UI not found.</p>")


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint for Cloud Run / load balancers."""
    mode = settings.transcription_mode
    response: dict[str, str] = {
        "status": "healthy",
        "service": "vocatype-backend",
        "mode": mode,
        "whisper_model": settings.whisper_model,
    }
    if settings.is_online:
        response["cleaner"] = settings.deepseek_model
    return response


@app.get("/metrics", tags=["system"], include_in_schema=False)
async def metrics_endpoint():
    """Prometheus metrics for production monitoring."""
    if not metrics_enabled():
        return Response(content=b"# vocatype_metrics_disabled 1\n", media_type="text/plain")
    return Response(content=render_metrics(), media_type=content_type())


# ── Uvicorn entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )

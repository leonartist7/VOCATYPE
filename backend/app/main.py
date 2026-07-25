"""
Vocatype Backend — FastAPI Application Entry Point.

Initializes the Gemini client on startup, configures CORS,
and mounts the audio processing route.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.routes.audio import router as audio_router
from app.services.gemini import initialize_gemini

# ── Logging ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vocatype")


# ── Lifespan ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Vocatype backend starting up...")
    settings = get_settings()
    logger.info("Model: %s", settings.gemini_model)

    # Initialize Gemini SDK
    initialize_gemini()
    logger.info("✅ Gemini client initialized")

    yield  # App is running

    logger.info("🛑 Vocatype backend shutting down...")


# ── App ─────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Vocatype API",
    description=(
        "AI-powered dictation backend. Accepts audio recordings, "
        "transcribes via Gemini 1.5 Flash, strips filler words, "
        "adapts tone, and returns clean formatted text."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────────

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {
        "status": "healthy",
        "service": "vocatype-backend",
        "model": settings.gemini_model,
    }


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

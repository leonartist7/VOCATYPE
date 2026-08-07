"""
Application configuration loaded from environment variables / .env file.
Uses Pydantic BaseSettings for type-safe, validated config.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings, auto-loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Gemini ──────────────────────────────────────────────
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"

    # ── Server ──────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── CORS ────────────────────────────────────────────────
    allowed_origins: str = "*"

    # ── Authentication ──────────────────────────────────────
    # Shared API token. When set, /process-audio requires X-API-Token header.
    api_token: str = ""

    # ── Logging ─────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"

    # ── Audio limits ────────────────────────────────────────
    max_audio_mb: float = 20.0

    # ── Rate limiting ───────────────────────────────────────
    rate_limit_per_minute: int = 30

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so .env is only read once."""
    return Settings()  # type: ignore[call-arg]

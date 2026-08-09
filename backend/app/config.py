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

    # ── Transcription mode ──────────────────────────────────
    # "offline": local faster-whisper only (no internet needed).
    # "online":  whisper STT + DeepSeek text cleaning (punctuation, tone).
    transcription_mode: str = "online"

    # ── Whisper (local offline STT) ─────────────────────────
    # "tiny.en" (39 MB, fastest), "base.en" (74 MB), "small.en" (483 MB)
    whisper_model: str = "tiny.en"
    whisper_device: str = "auto"  # "auto", "cpu", or "cuda"
    whisper_compute_type: str = "auto"  # "auto", "int8", "float16", etc.

    # ── DeepSeek (online text cleaning) ─────────────────────
    # Required when transcription_mode is "online".
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"

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

    @property
    def is_online(self) -> bool:
        """Whether DeepSeek text cleaning is enabled."""
        return self.transcription_mode.lower() == "online"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so .env is only read once."""
    return Settings()  # type: ignore[call-arg]

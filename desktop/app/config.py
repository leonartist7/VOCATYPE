"""
Desktop client configuration loaded from .env file.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the desktop directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


@dataclass
class Config:
    """Desktop client settings."""

    backend_url: str = field(
        default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8000")
    )
    hotkey_combo: str = field(default_factory=lambda: os.getenv("HOTKEY_COMBO", "ctrl+space"))

    # Audio settings
    sample_rate: int = field(default_factory=lambda: int(os.getenv("SAMPLE_RATE", "16000")))
    channels: int = field(default_factory=lambda: int(os.getenv("CHANNELS", "1")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1024")))

    # Derived
    sample_width: int = 2  # 16-bit audio

    @property
    def platform(self) -> str:
        """Detect current platform."""
        if sys.platform == "darwin":
            return "macos"
        elif sys.platform == "win32":
            return "windows"
        else:
            return "linux"

    @property
    def paste_hotkey(self) -> list[str]:
        """Platform-appropriate paste keystroke."""
        if self.platform == "macos":
            return ["command", "v"]
        return ["ctrl", "v"]


config = Config()

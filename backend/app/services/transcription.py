"""
Audio format detection and preparation for Gemini multimodal input.
Handles WAV, M4A, WebM, OGG, and other common audio formats.
"""

from __future__ import annotations

import logging
import mimetypes

logger = logging.getLogger(__name__)

# Mapping of file extensions to MIME types Gemini accepts
SUPPORTED_MIME_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".3gp": "audio/3gpp",
    ".3gpp": "audio/3gpp",
}


def detect_mime_type(filename: str, content_type: str | None = None) -> str:
    """
    Detect the MIME type of an audio file.

    Priority:
    1. Extension-based lookup from our known map
    2. Provided content_type header
    3. Python mimetypes module
    4. Fallback to audio/wav

    Args:
        filename: Original filename with extension.
        content_type: Optional MIME type from the upload header.

    Returns:
        A MIME type string suitable for the Gemini API.
    """
    # 1. Check extension against our map
    if filename:
        ext = _get_extension(filename)
        if ext in SUPPORTED_MIME_TYPES:
            detected = SUPPORTED_MIME_TYPES[ext]
            logger.debug("MIME detected from extension '%s': %s", ext, detected)
            return detected

    # 2. Use provided content type if valid
    if content_type and content_type.startswith("audio/"):
        logger.debug("Using provided content_type: %s", content_type)
        return content_type

    # 3. Try Python's mimetypes
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed and guessed.startswith("audio/"):
            logger.debug("MIME guessed by mimetypes module: %s", guessed)
            return guessed

    # 4. Fallback
    logger.warning(
        "Could not detect MIME type for '%s' (content_type=%s). Falling back to audio/wav.",
        filename,
        content_type,
    )
    return "audio/wav"


def validate_audio_size(
    audio_bytes: bytes,
    max_size_mb: float = 20.0,
) -> None:
    """
    Validate that the audio file is within acceptable size limits.

    Args:
        audio_bytes: The raw audio data.
        max_size_mb: Maximum allowed size in megabytes.

    Raises:
        ValueError: If the file exceeds the size limit.
    """
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"Audio file too large: {size_mb:.1f}MB exceeds maximum of {max_size_mb:.0f}MB."
        )
    logger.debug("Audio size: %.2f MB (limit: %.0f MB)", size_mb, max_size_mb)


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension including the dot."""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx:].lower()

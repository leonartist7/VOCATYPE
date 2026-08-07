"""
Lightweight Prometheus metrics for the Vocatype backend.

Exports counters and histograms for audio processing so deployments can be
observed in production (mirrors LiveKit's telemetry approach).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Use prometheus_client when available; degrade gracefully otherwise.
try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    REQUESTS_TOTAL = Counter(
        "vocatype_requests_total",
        "Total HTTP requests by method and path",
        ["method", "path"],
    )
    PROCESS_AUDIO_TOTAL = Counter(
        "vocatype_process_audio_total",
        "Audio processing requests by outcome",
        ["outcome"],  # success | error
    )
    PROCESS_AUDIO_DURATION = Histogram(
        "vocatype_process_audio_duration_seconds",
        "Duration of audio processing in seconds",
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
    )
    AUDIO_BYTES = Histogram(
        "vocatype_audio_bytes",
        "Size of uploaded audio in bytes",
        buckets=(32_768, 131_072, 524_288, 2_097_152, 8_388_608, 20_971_520),
    )
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("prometheus_client not installed — metrics disabled.")


def metrics_enabled() -> bool:
    return METRICS_ENABLED


def render_metrics() -> bytes:
    """Render the Prometheus exposition format."""
    if not METRICS_ENABLED:
        return b"# vocatype_metrics_disabled 1\n"
    return generate_latest()


def content_type() -> str:
    return CONTENT_TYPE_LATEST if METRICS_ENABLED else "text/plain"

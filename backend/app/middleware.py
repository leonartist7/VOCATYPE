"""
HTTP middleware for the Vocatype backend.

- API token authentication (when configured)
- In-process rate limiting for the audio endpoint
- Request logging with latency, status, and client info
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

logger = logging.getLogger(__name__)

# Header used for API token authentication.
API_TOKEN_HEADER = "x-api-token"

# Rate limiter state: client key -> deque of recent request timestamps.
_rate_buckets: dict[str, deque[float]] = {}
_rate_lock = threading.Lock()


def _client_key(request: Request) -> str:
    """Return a stable key identifying the calling client."""
    return request.client.host if request.client else "unknown"


def _is_rate_limited(request: Request) -> bool:
    """Enforce per-client request limits (token-bucket window)."""
    settings = get_settings()
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return False

    key = _client_key(request)
    now = time.monotonic()
    window_start = now - 60.0

    with _rate_lock:
        bucket = _rate_buckets.setdefault(key, deque())
        # Drop timestamps outside the rolling window.
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= limit:
            return True

        bucket.append(now)
        return False


def _is_authorized(request: Request) -> bool:
    """Validate the shared API token, if authentication is configured."""
    token = get_settings().api_token
    if not token:
        return True  # auth disabled

    provided = request.headers.get(API_TOKEN_HEADER, "")
    return provided == token


class SecurityMiddleware(BaseHTTPMiddleware):
    """Authenticates requests and enforces rate limits."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()

        # Protect only the API endpoint; keep /health, /preview, /docs public.
        if request.url.path == "/process-audio":
            if not _is_authorized(request):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "detail": "Missing or invalid X-API-Token header.",
                    },
                )
            if _is_rate_limited(request):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too many requests",
                        "detail": "Rate limit exceeded. Try again shortly.",
                    },
                )

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        if request.url.path not in ("/health", "/favicon.ico"):
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response

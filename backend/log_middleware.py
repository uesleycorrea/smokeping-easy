"""Request logging middleware with sensitive-field redaction.

This is registered as the FIRST middleware so it wraps every request. It logs
only request *metadata* (method, redacted path, status, duration, client IP) —
never request/response bodies. Query-string values for sensitive keys are
redacted so tokens passed as query params (e.g. ``?api_key=...``) never reach
the logs.

``redact()`` is also importable by other modules that need to log a dict
safely (e.g. when logging a settings update).
"""
from __future__ import annotations

import logging
import time
from urllib.parse import parse_qsl, urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

log = logging.getLogger("smokeping_easy.access")

# Field names whose values must never be logged.
SENSITIVE_FIELDS = frozenset(
    {
        "api_key",
        "password",
        "new_password",
        "current_password",
        "old_password",
        "bot_token",
        "token",
        "secret",
        "chat_id",
        "authorization",
        "cookie",
    }
)

REDACTED = "***"


def _is_sensitive(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in SENSITIVE_FIELDS)


def redact(obj):
    """Recursively redact sensitive keys in dicts/lists. Safe for logging."""
    if isinstance(obj, dict):
        return {
            k: (REDACTED if _is_sensitive(str(k)) else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj


def redact_query_string(query: str) -> str:
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    cleaned = [(k, REDACTED if _is_sensitive(k) else v) for k, v in pairs]
    return urlencode(cleaned)


def _redacted_path(request: Request) -> str:
    path = request.url.path
    query = redact_query_string(request.url.query)
    return f"{path}?{query}" if query else path


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        client_ip = request.headers.get("x-forwarded-for", "")
        client_ip = client_ip.split(",")[0].strip() if client_ip else (
            request.client.host if request.client else "-"
        )
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            log.info(
                "%s %s %s %d %.1fms",
                client_ip,
                request.method,
                _redacted_path(request),
                status,
                duration_ms,
            )

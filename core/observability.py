from __future__ import annotations

import json
import logging
import time
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional
from urllib import request as urlrequest

from django.conf import settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_ctx: ContextVar[str | None] = ContextVar("request_user", default=None)


def set_request_context(request_id: str | None, user_id: str | None = None) -> None:
    request_id_ctx.set(request_id)
    user_ctx.set(user_id)


def clear_request_context() -> None:
    request_id_ctx.set(None)
    user_ctx.set(None)


def get_request_id() -> str | None:
    return request_id_ctx.get()


def get_request_user() -> str | None:
    return user_ctx.get()


class RequestIDLogFilter(logging.Filter):
    """Injects request_id/user_id into log records for structured logging."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.request_id = get_request_id() or "-"
        record.user_id = get_request_user() or getattr(record, "user", None) or "-"
        return True


def capture_exception(exc: BaseException, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Lightweight error-reporting hook. Logs locally and, if SENTRY_DSN is set,
    POSTs a minimal payload. Failures are swallowed to avoid cascading errors.
    """
    logger = logging.getLogger("parkshare.errors")
    payload = {
        "error": exc.__class__.__name__,
        "message": str(exc),
        "trace": traceback.format_exc(),
        "request_id": get_request_id(),
        "context": context or {},
    }
    logger.error("Exception captured", extra={"payload": payload})

    dsn = getattr(settings, "SENTRY_DSN", "") or ""
    if not dsn:
        return

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            dsn,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlrequest.urlopen(req, timeout=2)
    except Exception:
        logger.warning("Failed to forward exception to Sentry-compatible DSN")


class Span:
    """Minimal tracing span for timing critical operations."""

    def __init__(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.attributes = attributes or {}
        self.start = time.perf_counter()
        self._logger = logging.getLogger("parkshare.tracing")

    def __enter__(self):
        self._logger.debug(
            "span_start",
            extra={
                "span": self.name,
                "attrs": self.attributes,
                "request_id": get_request_id(),
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start
        extra = {
            "span": self.name,
            "duration_ms": int(duration * 1000),
            "attrs": self.attributes,
            "request_id": get_request_id(),
        }
        if exc_val:
            extra["error"] = str(exc_val)
        self._logger.info("span_end", extra=extra)


@contextmanager
def start_span(name: str, **attrs: Any):
    if not getattr(settings, "ENABLE_TRACING", True):
        yield None
        return
    with Span(name, attrs):
        yield None

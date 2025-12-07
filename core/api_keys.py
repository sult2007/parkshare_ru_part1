from __future__ import annotations

import hashlib
import secrets
from functools import wraps
from typing import Callable, TypeVar

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils import timezone

from .models import ApiKey

F = TypeVar("F", bound=Callable[..., HttpResponse])


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key(name: str) -> tuple[str, ApiKey]:
    """Generate and persist a new API key. Returns raw key and model instance."""
    raw = secrets.token_urlsafe(28)
    prefix = raw[:8]
    instance = ApiKey.objects.create(name=name, prefix=prefix, key_hash=_hash(raw))
    return raw, instance


def require_api_key(view_func: F) -> F:
    """Decorator to protect partner endpoints with X-API-Key header."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        header_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
        if not header_key:
            return HttpResponseForbidden("API key required")
        prefix = header_key[:8]
        try:
            record = ApiKey.objects.get(prefix=prefix, revoked_at__isnull=True)
        except ApiKey.DoesNotExist:
            return HttpResponseForbidden("Invalid API key")
        if record.key_hash != _hash(header_key):
            return HttpResponseForbidden("Invalid API key")
        record.last_used_at = timezone.now()
        record.save(update_fields=["last_used_at"])
        return view_func(request, *args, **kwargs)

    return wrapper  # type: ignore[return-value]

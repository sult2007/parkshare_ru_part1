from __future__ import annotations

import time
from typing import Callable

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse, JsonResponse


# core/middleware.py

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Добавляет базовые защитные заголовки.
    COOP/COEP/CORP берём из settings.* и в DEBUG по умолчанию отключаем,
    чтобы не ломать dev-фичи вроде Leaflet / внешних API.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # CSP
        csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        if csp:
            response.setdefault("Content-Security-Policy", csp)

        # X-Frame-Options
        frame_option = getattr(settings, "X_FRAME_OPTIONS", "DENY")
        if frame_option:
            response.setdefault("X-Frame-Options", frame_option)

        # X-Content-Type-Options
        response.setdefault("X-Content-Type-Options", "nosniff")

        # Referrer-Policy
        referrer = getattr(settings, "REFERRER_POLICY", None)
        if referrer:
            response.setdefault("Referrer-Policy", referrer)

        # Permissions-Policy
        perm = getattr(settings, "PERMISSIONS_POLICY", None)
        if perm:
            response.setdefault("Permissions-Policy", perm)

        # --- COOP / COEP / CORP ---

        if settings.DEBUG:
            # В dev вообще не ставим их, и заодно сносим, если кто-то выше их повесил
            for header in (
                "Cross-Origin-Opener-Policy",
                "Cross-Origin-Embedder-Policy",
                "Cross-Origin-Resource-Policy",
            ):
                if header in response:
                    del response[header]
        else:
            coop = getattr(settings, "CROSS_ORIGIN_OPENER_POLICY", None)
            coep = getattr(settings, "CROSS_ORIGIN_EMBEDDER_POLICY", None)
            corp = getattr(settings, "CROSS_ORIGIN_RESOURCE_POLICY", None)

            if coop:
                response.setdefault("Cross-Origin-Opener-Policy", coop)
            if coep:
                response.setdefault("Cross-Origin-Embedder-Policy", coep)
            if corp:
                response.setdefault("Cross-Origin-Resource-Policy", corp)

        return response


class RateLimitMiddleware:
    """Простейший rate limiting на уровне приложения.

    Используем cache (Redis в продакшене) для подсчёта количества запросов
    в фиксированное окно. Если лимит превышен — отдаём 429 и заголовок
    ``Retry-After``.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.cache = caches[getattr(settings, "RATE_LIMIT_CACHE", "default")]
        self.window = int(getattr(settings, "RATE_LIMIT_WINDOW", 60))
        self.limit = int(getattr(settings, "RATE_LIMIT_REQUESTS", 120))
        self.whitelist = set(getattr(settings, "RATE_LIMIT_WHITELIST", []))

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method.upper() == "OPTIONS":
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        if client_ip and client_ip not in self.whitelist:
            if self._is_rate_limited(client_ip):
                retry_after = self.window
                return JsonResponse(
                    {"detail": "Too many requests, please retry later."},
                    status=429,
                    headers={"Retry-After": str(retry_after)},
                )

        return self.get_response(request)

    def _get_client_ip(self, request: HttpRequest) -> str:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _is_rate_limited(self, client_ip: str) -> bool:
        window_start = int(time.time() // self.window) * self.window
        cache_key = f"ratelimit:{client_ip}:{window_start}"

        added = self.cache.add(cache_key, 1, timeout=self.window)
        if added:
            return False

        try:
            current = self.cache.incr(cache_key)
        except Exception:
            # Fallback: если бекенд не поддерживает incr, пробуем читать/писать вручную.
            current = int(self.cache.get(cache_key) or 0) + 1
            self.cache.set(cache_key, current, timeout=self.window)

        return current > self.limit
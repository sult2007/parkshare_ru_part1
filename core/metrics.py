from __future__ import annotations

import time
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Request-level metrics
request_counter = Counter(
    "parkshare_http_requests_total",
    "HTTP requests by method/path/status",
    ["method", "path", "status"],
)
request_latency = Histogram(
    "parkshare_http_request_duration_seconds",
    "Request latency by method/path",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Domain counters
booking_events = Counter(
    "parkshare_booking_events_total",
    "Booking events",
    ["event"],
)
payment_events = Counter(
    "parkshare_payment_events_total",
    "Payment attempts and statuses",
    ["provider", "status"],
)
assistant_invocations = Counter(
    "parkshare_assistant_invocations_total",
    "AI assistant tool invocations",
    ["tool"],
)


def metrics_view(request: HttpRequest) -> HttpResponse:
    """Expose Prometheus metrics when ENABLE_METRICS=true."""
    if not getattr(settings, "ENABLE_METRICS", False):
        return HttpResponseForbidden("Metrics disabled")
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


def record_booking_event(event: str) -> None:
    if not getattr(settings, "ENABLE_METRICS", False):
        return
    booking_events.labels(event=event or "unknown").inc()


def record_payment_event(provider: Optional[str], status: str) -> None:
    if not getattr(settings, "ENABLE_METRICS", False):
        return
    payment_events.labels(provider=provider or "unknown", status=status or "unknown").inc()


def record_assistant_tool(tool: str) -> None:
    if not getattr(settings, "ENABLE_METRICS", False):
        return
    assistant_invocations.labels(tool=tool or "unknown").inc()


class RequestMetricsMiddleware:
    """Collect request count/latency when metrics enabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if not getattr(settings, "ENABLE_METRICS", False):
            return self.get_response(request)

        start = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - start

        path_label = getattr(request, "resolver_match", None)
        if path_label and path_label.view_name:
            path_value = path_label.view_name
        else:
            path_value = (request.path or "").split("?")[0]

        status_code = getattr(response, "status_code", 0)
        request_counter.labels(method=request.method, path=path_value, status=str(status_code)).inc()
        request_latency.labels(method=request.method, path=path_value).observe(duration)
        return response

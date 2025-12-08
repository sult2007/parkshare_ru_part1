# services/llm.py
"""Async client helpers for communicating with the LLM microservice."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
CONNECT_TIMEOUT = 3.0

# По умолчанию ожидаем локальный сервис на 8002 (см. docker-compose).
# 1) внутри docker-сети: llm_service:8002
# 2) с хоста: localhost:8002
DEFAULT_LLM_URLS: List[str] = [
    "http://llm_service:8002",
    "http://127.0.0.1:8002",
    "http://localhost:8002",
]

LEGACY_ENDPOINTS: List[str] = [
    "/parse",
    "/api/v1/llm/parse-search-query",
]

DEFAULT_RETRIES = 2


class LLMClientError(Exception):
    """Raised when the LLM service cannot process the request."""


def _candidate_endpoints() -> Iterable[str]:
    """Return candidate base URLs to try for the LLM service.

    Priority: explicit env var, then defaults (llm_service, localhost).
    """
    env_url = os.getenv("LLM_SERVICE_URL")
    if env_url:
        yield env_url.rstrip("/")

    for url in DEFAULT_LLM_URLS:
        if not env_url or url.rstrip("/") != env_url.rstrip("/"):
            yield url.rstrip("/")


async def parse_search_query(query: str) -> Dict[str, Any]:
    """Parse a user parking search query via the LLM microservice.

    Args:
        query: Raw text query from the user.

    Returns:
        Structured dict with parking search attributes.

    Raises:
        LLMClientError: If the request fails or returns non-200 status.
        ValueError: If query is empty.
    """
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    if httpx is None:
        raise LLMClientError("LLM client is disabled: httpx is not installed")

    retries = int(os.getenv("LLM_CLIENT_RETRIES", DEFAULT_RETRIES))
    timeout_value = float(os.getenv("LLM_CLIENT_TIMEOUT", DEFAULT_TIMEOUT))
    timeout = httpx.Timeout(timeout_value, connect=CONNECT_TIMEOUT)

    last_error: Exception | None = None
    last_error_message: str | None = None

    for base_url in _candidate_endpoints():
        for path in LEGACY_ENDPOINTS:
            endpoint = f"{base_url}{path}"
            logger.info(
                "Calling LLM service",
                extra={
                    "endpoint": endpoint,
                    "timeout": timeout_value,
                    "retries": retries,
                    "query_preview": query[:120],
                },
            )
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    for attempt in range(1, retries + 1):
                        try:
                            logger.debug(
                                "LLM HTTP request",
                                extra={
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "timeout": timeout_value,
                                },
                            )
                            response = await client.post(endpoint, json={"query": query})
                            response.raise_for_status()
                            data = response.json()
                            logger.debug(
                                "LLM service response",
                                extra={
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "response": data,
                                },
                            )
                            return data
                        except httpx.TimeoutException as exc:
                            logger.warning(
                                "LLM request timeout",
                                extra={"endpoint": endpoint, "attempt": attempt, "event": "llm_service_unavailable"},
                            )
                            last_error = exc
                            last_error_message = "timeout"
                        except httpx.HTTPStatusError as exc:
                            status_code = exc.response.status_code
                            log_level = logging.ERROR if status_code >= 500 else logging.WARNING
                            logger.log(
                                log_level,
                                "LLM service returned HTTP error",
                                extra={
                                    "status": status_code,
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "body": exc.response.text[:500],
                                    "event": "llm_service_http_error",
                                },
                            )
                            last_error = exc
                            last_error_message = f"HTTP {status_code}"
                            break
                        except httpx.RequestError as exc:
                            logger.error(
                                "LLM request error",
                                extra={
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "event": "llm_service_unavailable",
                                },
                                exc_info=exc,
                            )
                            last_error = exc
                            last_error_message = "network_error"
                        except ValueError as exc:
                            logger.warning(
                                "LLM service returned invalid JSON",
                                extra={"endpoint": endpoint, "attempt": attempt},
                                exc_info=exc,
                            )
                            last_error = exc
                            last_error_message = "invalid_json"
                            break
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Unexpected LLM client error", extra={"endpoint": endpoint}
                )

    if last_error:
        message = last_error_message or str(last_error)
        raise LLMClientError(f"LLM service unreachable: {message}") from last_error

    raise LLMClientError("LLM service unreachable: no endpoints configured")


async def check_llm_health() -> Dict[str, Any]:
    """Check health endpoints of the LLM service for diagnostics."""
    if httpx is None:
        return {"ok": False, "detail": "httpx not installed"}

    timeout_value = float(os.getenv("LLM_CLIENT_TIMEOUT", DEFAULT_TIMEOUT))
    timeout = httpx.Timeout(timeout_value, connect=CONNECT_TIMEOUT)

    results: Dict[str, Any] = {"endpoints": []}

    for base_url in _candidate_endpoints():
        for path in ["/health", "/healthz"]:
            health_url = f"{base_url}{path}"
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(health_url)
                results["endpoints"].append(
                    {
                        "url": health_url,
                        "status": resp.status_code,
                        "body": resp.json()
                        if resp.headers.get("content-type", "").startswith(
                            "application/json"
                        )
                        else resp.text,
                    }
                )
                if resp.status_code == 200:
                    results["ok"] = True
                    results["active_url"] = health_url
                    return results
            except Exception as exc:
                logger.warning(
                    "LLM health check failed", extra={"url": health_url}, exc_info=exc
                )
                results["endpoints"].append({"url": health_url, "error": str(exc)})

    results["ok"] = False
    return results

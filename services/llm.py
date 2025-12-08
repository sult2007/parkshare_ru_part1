# services/llm.py
"""Async client helpers for communicating with the LLM microservice."""
from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, Iterable, List

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
CONNECT_TIMEOUT = 3.0
OPENAI_DEFAULT_MODEL = "gpt-3.5-turbo"

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

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


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


def _strip_code_fences(content: str) -> str:
    """Remove Markdown code fences if the model returns them."""

    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1])
        text = text.strip()
    return text.strip("` \n")


async def _call_llm_service(query: str, retries: int, timeout_value: float) -> Dict[str, Any]:
    """Call the LLM microservice with retries."""

    if httpx is None:
        raise LLMClientError("LLM client is disabled: httpx is not installed", retryable=False)

    timeout = httpx.Timeout(timeout_value, connect=CONNECT_TIMEOUT)

    last_error: Exception | None = None
    last_error_message: str | None = None
    retryable = False

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
                                "llm_service_unavailable",
                                extra={"endpoint": endpoint, "attempt": attempt, "event": "llm_service_unavailable"},
                            )
                            last_error = exc
                            last_error_message = "timeout"
                            retryable = True
                        except httpx.HTTPStatusError as exc:
                            status_code = exc.response.status_code
                            event = "llm_service_5xx" if status_code >= 500 else "llm_service_http_error"
                            logger.log(
                                logging.ERROR if status_code >= 500 else logging.WARNING,
                                event,
                                extra={
                                    "status": status_code,
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "body": exc.response.text[:500],
                                    "event": event,
                                },
                            )
                            last_error = exc
                            last_error_message = f"HTTP {status_code}"
                            retryable = status_code >= 500 or status_code in {401, 403}
                            break
                        except httpx.RequestError as exc:
                            logger.error(
                                "llm_service_unavailable",
                                extra={
                                    "endpoint": endpoint,
                                    "attempt": attempt,
                                    "event": "llm_service_unavailable",
                                },
                                exc_info=exc,
                            )
                            last_error = exc
                            last_error_message = "network_error"
                            retryable = True
                        except ValueError as exc:
                            logger.warning(
                                "LLM service returned invalid JSON",
                                extra={"endpoint": endpoint, "attempt": attempt},
                                exc_info=exc,
                            )
                            last_error = exc
                            last_error_message = "invalid_json"
                            retryable = True
                            break
            except Exception as exc:
                last_error = exc
                retryable = True
                logger.exception(
                    "Unexpected LLM client error", extra={"endpoint": endpoint}
                )

    if last_error:
        raise LLMClientError(f"LLM service unreachable: {last_error_message or last_error}", retryable=retryable) from last_error

    raise LLMClientError("LLM service unreachable: no endpoints configured", retryable=True)


async def _call_openai_direct(query: str, timeout_value: float) -> Dict[str, Any]:
    """Call OpenAI GPT-3.5 directly as a fallback."""

    if httpx is None:
        raise LLMClientError("OpenAI client requires httpx", retryable=False)

    api_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("LLM_OPENAI_API_KEY", "").strip()
    )
    if not api_key:
        logger.warning("llm_openai_unavailable", extra={"event": "llm_openai_unavailable"})
        raise LLMClientError("OpenAI is not configured", retryable=False)

    base_url = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("LLM_OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        os.getenv("OPENAI_CHAT_MODEL")
        or os.getenv("LLM_DEFAULT_MODEL")
        or OPENAI_DEFAULT_MODEL
    ).strip() or OPENAI_DEFAULT_MODEL
    timeout = httpx.Timeout(timeout_value, connect=CONNECT_TIMEOUT)

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract parking search parameters from user text and return ONLY compact JSON. "
                    "Schema: {\"city\": string|null, \"near_metro\": string|null, \"has_ev_charging\": bool, "
                    "\"covered\": bool, \"max_price_per_hour\": number|null, \"start_at\": string|null, "
                    "\"end_at\": string|null}. "
                    "city may be Russian. If unknown, use null/false. No explanations."
                ),
            },
            {"role": "user", "content": query},
        ],
    }

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        logger.warning("llm_openai_unavailable", extra={"event": "llm_openai_unavailable"})
        raise LLMClientError("OpenAI timeout", retryable=False) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "llm_openai_unavailable",
            extra={"event": "llm_openai_unavailable", "detail": str(exc)},
        )
        raise LLMClientError("OpenAI network error", retryable=False) from exc

    if response.status_code >= 500:
        logger.warning(
            "llm_openai_5xx",
            extra={
                "event": "llm_openai_5xx",
                "status": response.status_code,
                "body": response.text[:500],
            },
        )
        raise LLMClientError(f"OpenAI 5xx: {response.status_code}", retryable=False)
    if response.status_code >= 400:
        logger.warning(
            "llm_openai_4xx",
            extra={
                "event": "llm_openai_4xx",
                "status": response.status_code,
                "body": response.text[:500],
            },
        )
        raise LLMClientError(f"OpenAI error: HTTP {response.status_code}", retryable=False)

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("llm_openai_4xx", extra={"event": "llm_openai_4xx", "detail": "invalid_json"})
        raise LLMClientError("OpenAI returned invalid JSON", retryable=False) from exc

    try:
        content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
        parsed_text = _strip_code_fences(content)
        parsed = json.loads(parsed_text)
        if not isinstance(parsed, dict):
            raise ValueError("response is not an object")
        return parsed
    except Exception as exc:
        logger.warning(
            "llm_openai_parse_error",
            extra={"event": "llm_openai_parse_error", "body": str(data)[:500]},
        )
        raise LLMClientError("OpenAI response parse error", retryable=False) from exc


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
    retries = int(os.getenv("LLM_CLIENT_RETRIES", DEFAULT_RETRIES))
    timeout_value = float(os.getenv("LLM_CLIENT_TIMEOUT", DEFAULT_TIMEOUT))

    last_error: LLMClientError | None = None

    try:
        return await _call_llm_service(query, retries=retries, timeout_value=timeout_value)
    except LLMClientError as exc:
        last_error = exc
        if not exc.retryable:
            raise
        logger.warning(
            "llm_service_fallback_openai",
            extra={"event": "llm_service_fallback_openai", "reason": str(exc)},
        )

    # Fallback to direct OpenAI
    try:
        return await _call_openai_direct(query, timeout_value=timeout_value)
    except LLMClientError as exc:
        if last_error:
            raise LLMClientError(
                f"OpenAI fallback failed after LLM service error: {exc}"
            ) from exc
        raise


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

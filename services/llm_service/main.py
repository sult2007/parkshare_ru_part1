"""Modern FastAPI-based LLM gateway for ParkShare.

Highlights
- OpenAI-compatible /v1/chat/completions endpoint with fallbacks (OpenAI/Anthropic/Groq/local via LiteLLM).
- In-memory caching and rate limiting to reduce latency and protect upstream APIs.
- Health probes and lightweight parking-aware helper endpoint for UI chat integrations.
- Context memory per conversation with TTL to keep replies coherent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from functools import lru_cache
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

try:  # lightweight optional cache backend
    from cachetools import TTLCache
except Exception:  # pragma: no cover - fallback when dependency is absent
    TTLCache = None  # type: ignore

try:
    from aiolimiter import AsyncLimiter
except Exception:  # pragma: no cover
    AsyncLimiter = None  # type: ignore

try:
    import litellm
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "LiteLLM must be installed (requirements.txt) to start the LLM service"
    ) from exc

logger = logging.getLogger("parkshare.llm_service")
logging.basicConfig(level=logging.INFO)


class Settings(BaseSettings):
    """Service configuration loaded from environment/.env."""

    # Networking
    host: str = "0.0.0.0"
    port: int = 8002
    cors_allow_origins: list[str] = []

    # Provider configuration
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    default_model: str = "gpt-4o-mini"
    fallback_models: list[str] = ["gpt-4o-mini"]

    # Service features
    cache_ttl_seconds: int = 30
    cache_size: int = 128
    max_history_messages: int = 16
    history_ttl_seconds: int = 3600
    requests_per_minute: int = 60
    request_timeout: float = 20.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LLM_",
        case_sensitive=False,
        extra="ignore",
    )


class ChatMessage(BaseModel):
    role: str = Field(..., description="system|user|assistant")
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: float | None = 0.3
    max_tokens: Optional[int] = None
    user: Optional[str] = None
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation key to keep lightweight context in memory",
    )


class CompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class CompletionUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[CompletionChoice]
    usage: CompletionUsage | None = None


class ParkingChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


class ParkingChatResponse(BaseModel):
    reply: str
    conversation_id: str
    provider: str


class RateLimiter:
    """Simple in-memory sliding window limiter."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self.events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            window_start = now - 60
            while self.events and self.events[0] < window_start:
                self.events.popleft()
            if len(self.events) >= self.max_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="LLM rate limit exceeded",
                )
            self.events.append(now)


class MemoryCache:
    """TTL cache wrapper with graceful fallback."""

    def __init__(self, size: int, ttl: int) -> None:
        if TTLCache:
            self._cache = TTLCache(maxsize=size, ttl=ttl)
        else:  # pragma: no cover - simplified fallback
            self._cache: Dict[str, tuple[float, Any]] = {}
            self.ttl = ttl

    def get(self, key: str) -> Any:
        if TTLCache:
            return self._cache.get(key)
        value = self._cache.get(key)
        if not value:
            return None
        expire_at, payload = value
        if expire_at < time.time():
            self._cache.pop(key, None)
            return None
        return payload

    def set(self, key: str, value: Any) -> None:
        if TTLCache:
            self._cache[key] = value
        else:
            self._cache[key] = (time.time() + self.ttl, value)


class ConversationMemory:
    """Keeps short-lived message history to provide context continuity."""

    def __init__(self, limit: int, ttl: int) -> None:
        self.limit = limit
        self.ttl = ttl
        self.storage: Dict[str, tuple[float, List[ChatMessage]]] = {}

    def get_history(self, conv_id: str) -> List[ChatMessage]:
        payload = self.storage.get(conv_id)
        if not payload:
            return []
        expires_at, messages = payload
        if expires_at < time.time():
            self.storage.pop(conv_id, None)
            return []
        return messages

    def append(self, conv_id: str, messages: List[ChatMessage]) -> None:
        history = self.get_history(conv_id)
        combined = (history + messages)[-self.limit :]
        self.storage[conv_id] = (time.time() + self.ttl, combined)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_rate_limiter(settings: Settings = Depends(get_settings)) -> RateLimiter:
    return RateLimiter(settings.requests_per_minute)


@lru_cache(maxsize=1)
def get_cache(settings: Settings = Depends(get_settings)) -> MemoryCache:
    return MemoryCache(settings.cache_size, settings.cache_ttl_seconds)


@lru_cache(maxsize=1)
def get_history(settings: Settings = Depends(get_settings)) -> ConversationMemory:
    return ConversationMemory(settings.max_history_messages, settings.history_ttl_seconds)


app = FastAPI(title="ParkShare LLM Gateway", version="1.0.0")
_settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if AsyncLimiter:
    limiter = AsyncLimiter(_settings.requests_per_minute, time_period=60)
else:
    limiter = None


async def _call_litellm(model: str, request: ChatCompletionRequest, settings: Settings) -> Dict[str, Any]:
    """Invoke LiteLLM with provider-specific credentials."""

    common_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [m.model_dump() for m in request.messages],
        "timeout": settings.request_timeout,
    }
    if request.temperature is not None:
        common_kwargs["temperature"] = request.temperature
    if request.max_tokens:
        common_kwargs["max_tokens"] = request.max_tokens
    if request.user:
        common_kwargs["user"] = request.user

    if model.startswith("claude") and settings.anthropic_api_key:
        common_kwargs["api_key"] = settings.anthropic_api_key
        common_kwargs["base_url"] = "https://api.anthropic.com"
    elif model.startswith("gpt") and settings.openai_api_key:
        common_kwargs["api_key"] = settings.openai_api_key
        common_kwargs["base_url"] = settings.openai_base_url.rstrip("/")
    elif settings.groq_api_key and model.startswith("groq"):
        common_kwargs["api_key"] = settings.groq_api_key
        common_kwargs["base_url"] = "https://api.groq.com/openai/v1"

    try:
        response = await litellm.acompletion(**common_kwargs)
    except litellm.RateLimitError as exc:  # pragma: no cover - network-specific
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except litellm.BadRequestError as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.exception("LLM provider error")
        raise HTTPException(status_code=502, detail="LLM upstream error") from exc

    return response  # type: ignore[no-any-return]


async def _make_response(
    provider_payload: Dict[str, Any],
    model: str,
    conversation_id: Optional[str],
    history: ConversationMemory,
) -> ChatCompletionResponse:
    first_choice = provider_payload["choices"][0]
    message_payload = first_choice["message"]
    message = ChatMessage(role=message_payload.get("role", "assistant"), content=message_payload.get("content", ""))

    if conversation_id:
        history.append(conversation_id, [message])

    usage = provider_payload.get("usage") or {}
    return ChatCompletionResponse(
        id=provider_payload.get("id") or f"chatcmpl-{uuid.uuid4().hex}",
        created=int(provider_payload.get("created") or time.time()),
        model=model,
        choices=[
            CompletionChoice(index=0, message=message, finish_reason=first_choice.get("finish_reason")),
        ],
        usage=CompletionUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        ),
    )


def _cache_key(request: ChatCompletionRequest) -> str:
    payload = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _with_history(request: ChatCompletionRequest, history: ConversationMemory) -> ChatCompletionRequest:
    if not request.conversation_id:
        return request
    previous = history.get_history(request.conversation_id)
    if not previous:
        return request
    merged = previous + request.messages
    return ChatCompletionRequest(**{**request.model_dump(), "messages": merged})


@app.middleware("http")
async def guard_rate_limit(request: Request, call_next):
    if limiter:
        async with limiter:
            return await call_next(request)
    return await call_next(request)


@app.get("/health", tags=["health"])
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "provider": "litellm",
        "default_model": _settings.default_model,
        "fallbacks": _settings.fallback_models,
    }


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, Any]:
    return await health()


@app.get("/v1/models")
async def list_models(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    models = list({settings.default_model, *settings.fallback_models})
    return {"data": [{"id": m, "object": "model"} for m in models], "object": "list"}


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    payload: ChatCompletionRequest,
    settings: Settings = Depends(get_settings),
    cache: MemoryCache = Depends(get_cache),
    history: ConversationMemory = Depends(get_history),
    limiter_dep: RateLimiter = Depends(get_rate_limiter),
) -> ChatCompletionResponse:
    await limiter_dep.acquire()
    payload = await _with_history(payload, history)
    cache_key = _cache_key(payload)
    cached = cache.get(cache_key)
    if cached:
        return cached

    models_chain = [payload.model or settings.default_model, *settings.fallback_models]
    last_error: Optional[Exception] = None
    for model in models_chain:
        try:
            provider_payload = await _call_litellm(model, payload, settings)
            response = await _make_response(provider_payload, model, payload.conversation_id, history)
            cache.set(cache_key, response)
            return response
        except HTTPException as exc:
            last_error = exc
            if exc.status_code < 500:
                break
            continue
        except Exception as exc:  # pragma: no cover - unexpected fallback
            last_error = exc
            logger.exception("Unexpected LLM error for model %s", model)
            continue

    if last_error:
        raise last_error  # type: ignore[misc]
    raise HTTPException(status_code=502, detail="LLM provider unavailable")


@app.post("/v1/parkshare/chat", response_model=ParkingChatResponse)
async def parking_chat(
    payload: ParkingChatRequest,
    settings: Settings = Depends(get_settings),
    history: ConversationMemory = Depends(get_history),
) -> ParkingChatResponse:
    """Parking-aware helper endpoint to drive the web chat UI."""

    system_prompt = (
        "You are ParkShare's multilingual assistant. "
        "You help users book and discover parking spots with contextual hints from their history. "
        "Answer succinctly in the language of the user."
    )
    conversation_id = payload.conversation_id or uuid.uuid4().hex
    messages: List[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
    history_messages = history.get_history(conversation_id)
    messages.extend(history_messages[-6:])
    messages.append(ChatMessage(role="user", content=payload.query))

    request_payload = ChatCompletionRequest(
        model=settings.default_model,
        messages=messages,
        conversation_id=conversation_id,
        temperature=0.4,
    )
    response = await chat_completions(request_payload, settings, get_cache(settings), history, get_rate_limiter(settings))
    reply = response.choices[0].message.content
    return ParkingChatResponse(reply=reply, conversation_id=conversation_id, provider=response.model)


@app.exception_handler(ValidationError)
async def validation_exception_handler(_: Request, exc: ValidationError):  # pragma: no cover - FastAPI hook
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=_settings.host, port=_settings.port)

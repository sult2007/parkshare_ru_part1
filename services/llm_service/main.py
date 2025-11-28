# services/llm_service/main.py
"""
FastAPI приложение для LLM‑разбора пользовательских запросов на поиск парковки.
Включает абстрактный клиент LLMClient и реализацию для OpenAI.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Protocol, runtime_checkable

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация сервиса, читаемая из переменных окружения."""

    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_base_url: str = Field(
        "https://api.openai.com/v1",
        env="OPENAI_BASE_URL",
    )
    openai_model: str = Field("gpt-3.5-turbo", env="OPENAI_MODEL")
    request_timeout: float = Field(30.0, env="LLM_REQUEST_TIMEOUT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@runtime_checkable
class LLMClient(Protocol):
    """Простейший протокол для LLM-клиентов."""

    async def parse_search_query(self, system_prompt: str, user_query: str) -> Dict[str, Any]:
        """Получить структурированные данные по текстовому запросу пользователя."""


class OpenAILLMClient:
    """LLM-клиент для работы с OpenAI Chat Completions API."""

    def __init__(self, settings: Settings):
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout = settings.request_timeout

    async def parse_search_query(self, system_prompt: str, user_query: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"LLM HTTP error: {exc.response.status_code}",
                ) from exc
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="LLM request error",
                ) from exc

        try:
            raw = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM returned invalid JSON",
            ) from exc

        try:
            content = (
                raw["choices"][0]["message"]["content"]
                if raw.get("choices")
                else None
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected response format from LLM",
            ) from exc

        if not content:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Empty response from LLM",
            )

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM response is not valid JSON",
            ) from exc


PARSER_SYSTEM_PROMPT = """
You are an assistant that extracts structured parking search intent for ParkShare.
Return a strict JSON object with the following fields:
- city: string with the city name in nominative case, or null if unknown.
- start_at: ISO 8601 datetime with timezone (offset or Z) when parking should start, or null.
- end_at: ISO 8601 datetime with timezone (offset or Z) when parking should end, or null.
- max_price_per_hour: number (float) with the hourly price ceiling, or null.
- near_metro: boolean, true if the user wants parking near metro/public transit, else false or null.
- has_ev_charging: boolean, true if the user requires EV charging, else false or null.
- covered: boolean, true if the user prefers indoor/covered parking, else false or null.
Rules:
- If the user did not provide a value, set it to null.
- Never invent unavailable dates or cities; prefer null.
- Output only the JSON object without explanations, markdown, or comments.
- Respect the language of the request, but city names should be in nominative form.
Example output:
{"city": "Moscow", "start_at": "2024-02-10T08:00:00+03:00", "end_at": null, "max_price_per_hour": 250.0, "near_metro": true, "has_ev_charging": false, "covered": true}
"""


class SearchQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Текстовый запрос пользователя",
    )


class SearchQueryResponse(BaseModel):
    city: str | None = Field(None, description="Город, указанный пользователем")
    start_at: datetime | None = Field(
        None, description="ISO 8601 время начала парковки (или null)"
    )
    end_at: datetime | None = Field(
        None, description="ISO 8601 время завершения парковки (или null)"
    )
    max_price_per_hour: float | None = Field(
        None, description="Максимальная цена в час, если указана"
    )
    near_metro: bool | None = Field(
        None, description="True, если нужно рядом с метро/транспортом"
    )
    has_ev_charging: bool | None = Field(
        None, description="True, если требуется зарядка для электромобиля"
    )
    covered: bool | None = Field(
        None, description="True, если требуется крытая/подземная парковка"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    return OpenAILLMClient(settings)


app = FastAPI(title="ParkShare LLM Service", version="0.1.0")


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/llm/parse-search-query",
    response_model=SearchQueryResponse,
    tags=["llm"],
    summary="Распарсить поисковый запрос пользователя через LLM",
)
async def parse_search_query_endpoint(
    payload: SearchQueryRequest,
    client: LLMClient = Depends(get_llm_client),
) -> SearchQueryResponse:
    try:
        data = await client.parse_search_query(PARSER_SYSTEM_PROMPT, payload.query)
        return SearchQueryResponse.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned invalid payload: {exc}",
        ) from exc

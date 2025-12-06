"""
Умный помощник подбирает парковки по текстовому запросу, используя
простые правила и существующие данные модели парковок. При желании сюда
можно подключить обученные NLP-модели.
"""
from __future__ import annotations

import logging
import random
import re
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:  # pragma: no cover - безопасный фолбэк без зависимостей
    TfidfVectorizer = None
    cosine_similarity = None

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db.models import Q

from parking.models import ParkingSpot
from services.llm import LLMClientError, parse_search_query

User = get_user_model()
logger = logging.getLogger(__name__)


def _extract_budget(text: str) -> Optional[int]:
    match = re.search(r"(\d{2,5})\s*(?:₽|р|руб)", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _extract_time_hint(text: str) -> str:
    if "завтра" in text:
        return "на завтра"
    if "ноч" in text:
        return "на ночь"
    if re.search(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b", text):
        return "в указанное окно времени"
    if "сейчас" in text or "прямо сейчас" in text:
        return "на ближайший час"
    return "скоро"


def _extract_time_window(text: str) -> tuple[Optional[int], Optional[int], str]:
    """Парсинг диапазона времени (часы) или быстрых подсказок."""

    match = re.search(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b", text)
    if match:
        start_h, end_h = match.groups()
        try:
            return int(start_h), int(end_h), f"с {start_h}:00 до {end_h}:00"
        except ValueError:
            return None, None, ""

    lowered = text.lower()
    if "сейчас" in lowered or "прямо сейчас" in lowered:
        return None, None, "на ближайший час"
    if "завтра" in lowered:
        return None, None, "на завтра"
    if "ноч" in lowered:
        return None, None, "на ночь"
    return None, None, ""


INTENT_CORPUS: list[tuple[str, str]] = [
    ("ev", "зарядка для электромобиля ev электромобиль tesla leaf"),
    ("budget", "самая дешёвая дёшево бюджет эконом"),
    ("night", "ночь ночевка оставить на ночь круглосуточно"),
    ("covered", "крытая парковка подземная защита от дождя"),
    ("fast", "сейчас ближайшая возле меня рядом срочно прямо сейчас"),
]


@lru_cache(maxsize=1)
def _intent_vectorizer():
    if not TfidfVectorizer:
        return None, None
    labels, texts = zip(*INTENT_CORPUS)
    vect = TfidfVectorizer(stop_words=None)
    matrix = vect.fit_transform(texts)
    return vect, (labels, matrix)


def _detect_intents(text: str) -> list[str]:
    vect, payload = _intent_vectorizer()
    if not vect or not payload:
        return []
    labels, matrix = payload
    query_vec = vect.transform([text])
    sims = cosine_similarity(query_vec, matrix).flatten()
    ranked: list[Tuple[float, str]] = sorted(zip(sims, labels), reverse=True)
    return [lbl for score, lbl in ranked if score > 0.18][:3]


def _build_base_queryset() -> Iterable[ParkingSpot]:
    return (
        ParkingSpot.objects.filter(
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        )
        .select_related("lot")
    )


def _parse_with_llm(text: str) -> dict[str, Any] | None:
    """Try to parse a query using the external LLM service.

    Returns None if the service is unavailable or any error occurs so that we can
    gracefully fallback to the rule-based parsing.
    """

    try:
        logger.info(
            "Invoking LLM parser for chat message",
            extra={"query": text[:200]},
        )
        parsed = async_to_sync(parse_search_query)(text)
        logger.info(
            "LLM parsed query",
            extra={"query": text, "parsed": parsed},
        )
        return parsed
    except (LLMClientError, ValueError) as exc:
        logger.warning(
            "LLM parsing failed, using rule-based fallback",
            extra={"query": text},
            exc_info=exc,
        )
    except Exception as exc:  # pragma: no cover - непредвиденная ошибка
        logger.exception(
            "Unexpected LLM parse error, using fallback", extra={"query": text}
        )
    return None


def _apply_llm_filters(queryset, payload: dict[str, Any]):
    q_filter = Q()
    city = payload.get("city")
    if city:
        q_filter &= Q(lot__city__iexact=city) | Q(lot__address__icontains=city)

    if payload.get("has_ev_charging") is True:
        q_filter &= Q(has_ev_charging=True)
    if payload.get("covered") is True:
        q_filter &= Q(is_covered=True)

    max_price = payload.get("max_price_per_hour")
    if max_price is not None:
        try:
            q_filter &= Q(hourly_price__lte=float(max_price))
        except (TypeError, ValueError):
            logger.debug("Skip invalid max_price_per_hour", extra={"value": max_price})

    near_metro = payload.get("near_metro")
    if near_metro:
        q_filter &= Q(lot__address__icontains="метро") | Q(lot__name__icontains="метро")

    if q_filter:
        queryset = queryset.filter(q_filter)
    return queryset


def _apply_intents(queryset, text: str):
    lowered = text.lower()
    q_filter = Q()
    intents = set(_detect_intents(lowered))
    if "ev" in lowered or "заряд" in lowered or "электро" in lowered or "ev" in intents:
        q_filter &= Q(has_ev_charging=True)
    if "крыт" in lowered or "covered" in intents:
        q_filter &= Q(is_covered=True)
    if "24/7" in lowered or "круглосуточ" in lowered or "night" in intents:
        q_filter &= Q(is_24_7=True)
    if "budget" in intents:
        q_filter &= Q(hourly_price__lte=300)
    metro_match = re.search(r"метро\s+([\wёЁ\-\s]+)", lowered)
    if metro_match:
        station = metro_match.group(1).strip()
        q_filter &= Q(lot__address__icontains=station) | Q(lot__name__icontains=station)
    address_match = re.search(r"(ул\.|улица|проспект|шоссе|пл\.|площадь)\s+([\wёЁ\s\-]+)", lowered)
    if address_match:
        fragment = address_match.group(0)
        q_filter &= Q(lot__address__icontains=fragment)
    budget = _extract_budget(lowered)
    if budget:
        q_filter &= Q(hourly_price__lte=budget)
    if q_filter:
        queryset = queryset.filter(q_filter)
    return queryset, intents


def _spot_payload(spot: ParkingSpot) -> dict[str, Any]:
    tags = []
    if spot.has_ev_charging:
        tags.append("EV")
    if spot.is_covered:
        tags.append("крытая")
    if spot.is_24_7:
        tags.append("24/7")
    if getattr(spot, "allow_dynamic_pricing", False):
        tags.append("AI")
    return {
        "spot_id": str(spot.id),
        "title": f"{spot.lot.name} — {spot.name}",
        "price": float(spot.hourly_price or 0),
        "distance_m": getattr(spot, "distance_km", None) * 1000 if getattr(spot, "distance_km", None) else None,
        "tags": tags,
        "occupancy_now": float(getattr(spot, "occupancy_7d", 0.0) or 0.0),
    }


def _compose_reply(context: dict[str, Any], count: int) -> str:
    templates = [
        "Нашёл для вас {count} вариантов около {area}. Цены от {min_price} до {max_price} ₽/час. Сейчас свободно примерно {availability}%.",
        "Подобрал {count} парковок {time_hint}. Минимальный тариф {min_price} ₽/час, максимальный {max_price} ₽/час.",
        "Есть {count} подходящих мест {area}. Чтобы расширить выбор, можно скорректировать бюджет {budget_hint}.",
    ]
    area = context.get("area") or "рядом"
    min_price = context.get("min_price", 0)
    max_price = context.get("max_price", max(min_price, min_price + 50))
    availability = context.get("availability", 60)
    budget_hint = f"до {context['budget']} ₽" if context.get("budget") else "или радиус"
    time_hint = context.get("time_hint", "")
    template = random.choice(templates)
    return template.format(
        count=count or 0,
        area=area,
        min_price=min_price,
        max_price=max_price,
        availability=availability,
        budget_hint=budget_hint,
        time_hint=time_hint,
    )


def _llm_time_hint(payload: dict[str, Any]) -> str:
    start_at = payload.get("start_at")
    end_at = payload.get("end_at")
    if start_at and end_at:
        return "на выбранный интервал"
    if start_at:
        return "к указанному времени"
    return "скоро"


def _prepare_context(
    spots: list[ParkingSpot], area: Optional[str], budget: Optional[int], time_hint: str
) -> dict[str, Any]:
    prices = [float(s.hourly_price or 0) for s in spots] or [0]
    return {
        "area": area or "рядом",
        "min_price": int(min(prices)),
        "max_price": int(max(prices)),
        "availability": int(
            100
            - (sum([float(getattr(s, "occupancy_7d", 0.0) or 0) for s in spots]) / len(prices))
            * 100
        )
        if spots
        else 0,
        "budget": budget,
        "time_hint": time_hint,
    }


def _reply_payload(spots: list[ParkingSpot], context: dict[str, Any], reasoning: str) -> dict[str, Any]:
    suggestions = [_spot_payload(spot) for spot in spots][:6]
    if not suggestions:
        reply = "Сейчас нет парковок под эти условия. Попробуйте увеличить бюджет или выбрать другой район."
        reasoning = reasoning or "Запрос слишком узкий или в базе пока нет подходящих мест."
    else:
        reply = _compose_reply(context, len(suggestions))
    return {
        "reply": reply,
        "suggestions": suggestions,
        "reason": reasoning,
        "intents": context.get("intents", []),
    }


def _handle_llm_flow(text: str):
    parsed = _parse_with_llm(text)
    if not parsed:
        logger.debug(
            "LLM returned no result; will use rule-based fallback",
            extra={"query": text[:120]},
        )
        return None

    qs = _apply_llm_filters(_build_base_queryset(), parsed)
    qs = qs.order_by("lot__stress_index", "hourly_price")[:12]
    spots = list(qs)

    area_hint = None
    if parsed.get("near_metro"):
        area_hint = "рядом с метро"
    if parsed.get("city"):
        area_hint = parsed["city"]

    budget = parsed.get("max_price_per_hour")
    time_hint = _llm_time_hint(parsed)
    context = _prepare_context(spots, area_hint, budget, time_hint)
    reasoning_parts = ["LLM разобрал намерение пользователя"]
    if parsed.get("has_ev_charging"):
        reasoning_parts.append("учтена EV-зарядка")
    if parsed.get("covered"):
        reasoning_parts.append("оставлены крытые места")
    if budget:
        reasoning_parts.append("отфильтровано по бюджету")
    context["intents"] = []

    return _reply_payload(spots, context, ", ".join(reasoning_parts))


def _handle_rule_based_flow(lowered: str):
    qs, intents = _apply_intents(_build_base_queryset(), lowered)
    budget = _extract_budget(lowered)
    if budget:
        qs = qs.filter(hourly_price__lte=budget)

    qs = qs.order_by("lot__stress_index", "hourly_price")[:12]
    spots = list(qs)

    area_hint = None
    metro_match = re.search(r"метро\s+([\wёЁ\-\s]+)", lowered)
    if metro_match:
        area_hint = f"у метро {metro_match.group(1).strip().title()}"
    start_h, end_h, time_hint_parsed = _extract_time_window(lowered)
    time_hint = time_hint_parsed or _extract_time_hint(lowered)
    context = _prepare_context(spots, area_hint, budget, time_hint)
    context["intents"] = list(intents)
    if start_h is not None and end_h is not None:
        context["time_hint"] = f"с {start_h}:00 до {end_h}:00"

    why = []
    if "ev" in intents:
        why.append("учёл наличие EV-зарядки")
    if "budget" in intents or budget:
        why.append("отсортировал по цене")
    if "night" in intents:
        why.append("оставил только круглосуточные")
    if time_hint_parsed:
        why.append(f"учёл интервал {time_hint_parsed}")
    reasoning = ", ".join(why) if why else "использовал ближайшие и менее загруженные места"
    return _reply_payload(spots, context, reasoning)


def generate_chat_reply(message: str, history: Optional[List[dict]], user: Optional[User]) -> dict[str, Any]:
    text = (message or "").strip()
    logger.info(
        "Incoming parking chat message",
        extra={
            "message": text[:200],
            "history_len": len(history or []),
            "user": getattr(user, "id", None),
        },
    )
    if not text:
        logger.info("Empty chat message, returning friendly prompt")
        return {
            "reply": "Опишите улицу, метро, бюджет и время: например, \"Тверская, с 9 до 11, до 350 ₽/ч, крытая\".",
            "suggestions": [],
            "reason": "empty_message",
        }

    lowered = text.lower()

    try:
        llm_response = _handle_llm_flow(text)
        if llm_response:
            return llm_response
    except Exception as exc:  # pragma: no cover - непредвиденная ошибка
        logger.exception("LLM flow errored, forcing rule-based fallback", exc_info=exc)
        fallback = _handle_rule_based_flow(lowered)
        fallback["reason"] = (fallback.get("reason") or "") + " · AI сервис недоступен, используем эвристику"
        fallback["reply"] = fallback.get("reply") or "Работаю в упрощённом режиме без внешнего AI, но покажу подходящие места."
        return fallback

    logger.info("Falling back to rule-based parser")
    response = _handle_rule_based_flow(lowered)
    if not response.get("suggestions"):
        response["reply"] = (
            "Не очень понял запрос. Попробуйте формат: ‘Курская, парковка с 9 до 11, до 300 ₽/час, с зарядкой EV’."
        )
    return response

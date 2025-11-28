from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="ParkShare AI Pricing Service",
    version="0.1.0",
    description=(
        "Отдельный микросервис ParkMate AI для динамического ценообразования "
        "парковочных мест. Пока использует простые эвристики, но интерфейс "
        "готов для подключения CatBoost/Transformer‑моделей."
    ),
)


def round_price(value: float, step: float = 10.0) -> float:
    """
    Локальная реализация round_price, не зависящая от Django.
    Округляет цену к ближайшему step (по умолчанию 10 ₽).
    """
    if step <= 0:
        return float(Decimal(str(value)).quantize(Decimal("0.01")))

    v = Decimal(str(value))
    step_dec = Decimal(str(step))
    scaled = (v / step_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    result = scaled * step_dec
    return float(result)


# ai_services/ai_pricing_service/main.py

class PricingRequest(BaseModel):
    base_price: float = Field(
        ...,
        gt=0,
        description="Базовая цена за час, ₽",
    )
    occupancy_7d: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Загруженность места за последние 7 дней (0..1)",
    )
    stress_index: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Индекс загруженности парковки (0..1)",
    )
    hour: Optional[int] = Field(
        None,
        ge=0,
        le=23,
        description="Час суток (0–23, локальное время парковки)",
    )
    dow: Optional[int] = Field(
        None,
        ge=0,
        le=6,
        description="День недели (0=понедельник, 6=воскресенье)",
    )
    use_ml: bool = Field(
        False,
        description=(
            "Флаг для использования ML‑модели (зарезервировано; "
            "пока используется только эвристика)."
        ),
    )



class PricingResponse(BaseModel):
    base_price: float
    recommended_price: float
    min_price: float
    max_price: float
    discount_percent: float
    is_discount: bool
    reason: str


@app.get("/health", tags=["health"])
def health() -> dict:
    """
    Простой healthcheck.
    """
    return {"status": "ok"}


@app.post(
    "/api/v1/pricing/recommend",
    response_model=PricingResponse,
    tags=["pricing"],
    summary="Получить рекомендованную цену за час",
)
def recommend_price(payload: PricingRequest) -> PricingResponse:
    """
    Эвристическое ценообразование на основе:
    - базовой цены;
    - загруженности места/парковки;
    - времени суток (час пик / не час пик).

    В дальнейшем сюда можно подставить CatBoost/Transformer‑модель.
    """
    base_price = payload.base_price
    occ = float(payload.occupancy_7d or 0.0)
    stress = float(payload.stress_index or 0.0)

    factor = 1.0
    reasons: list[str] = []

    # Загруженность места
    if occ > 0.8:
        factor += 0.15
        reasons.append("место часто занято (высокая загруженность за 7 дней)")
    elif occ < 0.3:
        factor -= 0.10
        reasons.append("место простаивает (низкая загруженность за 7 дней)")

    # Стресс по парковке
    if stress > 0.7:
        factor += 0.10
        reasons.append("высокий парковочный стресс по объекту")
    elif stress < 0.3:
        factor -= 0.05
        reasons.append("низкий парковочный стресс по объекту")

    # Время суток
    if payload.hour is not None:
        hour = payload.hour
        if 8 <= hour <= 11 or 17 <= hour <= 21:
            factor += 0.10
            reasons.append("час пик")
        else:
            factor -= 0.05
            reasons.append("не час пик")

    # Ограничиваем фактор
    if factor < 0.5:
        factor = 0.5
    if factor > 1.5:
        factor = 1.5

    recommended = round_price(base_price * factor, step=5.0)
    min_price = round_price(recommended * 0.9, step=5.0)
    max_price = round_price(recommended * 1.1, step=5.0)

    # Скидка относительно базовой цены
    discount_percent = 0.0
    is_discount = False
    if recommended < base_price:
        diff = (base_price - recommended) / base_price
        discount_percent = float(
            (Decimal(str(diff)) * Decimal("100")).quantize(Decimal("0.1"))
        )
        is_discount = True

    if not reasons:
        reasons.append("используется только базовая ставка")

    reason = "; ".join(reasons)

    return PricingResponse(
        base_price=base_price,
        recommended_price=recommended,
        min_price=min_price,
        max_price=max_price,
        discount_percent=discount_percent,
        is_discount=is_discount,
        reason=reason,
    )

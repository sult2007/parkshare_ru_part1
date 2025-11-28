from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from django.utils import timezone

from ai.pricing import recommend_price_for_spot


class PricingDecision:
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload

    @property
    def price(self) -> Decimal:
        return Decimal(str(self.payload.get("recommended_price", 0)))

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


class AvailabilityDecision:
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


def apply_ai_pricing(booking) -> PricingDecision | None:
    """Подключает ML/GBM модель динамического ценообразования.

    Для MVP используем существующую recommend_price_for_spot, но сохраняем
    полную структуру для будущих CatBoost/GBM моделей (ParkMate).
    """

    suggestion = recommend_price_for_spot(booking.spot)
    if not suggestion:
        return None

    hours = max(Decimal("1"), Decimal((booking.end_at - booking.start_at).total_seconds()) / Decimal(3600))
    base_total = Decimal(str(booking.total_price))
    ai_hour_price = Decimal(str(suggestion["recommended_price"]))
    ai_total = (ai_hour_price * hours).quantize(Decimal("0.01"))

    booking.total_price = ai_total
    booking.dynamic_pricing_applied = True
    booking.ai_snapshot = {
        "pricing": suggestion,
        "calculated_at": timezone.now().isoformat(),
    }
    return PricingDecision({
        **suggestion,
        "applied_total": str(ai_total),
        "hours": str(hours),
    })


def attach_availability_forecast(booking, forecast: Dict[str, Any] | None = None) -> None:
    if forecast:
        booking.ai_snapshot = {
            **(booking.ai_snapshot or {}),
            "availability": forecast,
        }

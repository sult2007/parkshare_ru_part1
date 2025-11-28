from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    # Официальный синхронный SDK YooKassa
    from yookassa import Configuration, Payment as YooPayment  # type: ignore[import]
except ImportError:  # pragma: no cover - мягкий фолбэк
    Configuration = None
    YooPayment = None


class YooKassaError(Exception):
    """Базовая ошибка при работе с YooKassa."""


def _configure_yookassa() -> None:
    """
    Настраивает SDK YooKassa из Django settings.

    Требуются:
    - YOOKASSA_SHOP_ID
    - YOOKASSA_SECRET_KEY
    """
    if Configuration is None or YooPayment is None:
        raise ImproperlyConfigured(
            "Пакет 'yookassa' не установлен. Добавьте его в requirements.txt."
        )

    shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
    secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", "")
    if not shop_id or not secret_key:
        raise ImproperlyConfigured(
            "Не заданы YOOKASSA_SHOP_ID и/или YOOKASSA_SECRET_KEY в настройках."
        )

    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def create_yookassa_payment(booking) -> Tuple[str, str, dict[str, Any]]:
    """
    Создаёт платёж в YooKassa для указанной брони.

    Возвращает:
        (payment_url, provider_payment_id, raw_response_dict)

    Все сетевые вызовы инкапсулированы здесь.
    """
    _configure_yookassa()

    from parking.models import Booking  # локальный импорт, чтобы избежать циклов

    if not isinstance(booking, Booking):
        raise YooKassaError("create_yookassa_payment ожидает экземпляр Booking.")

    amount = booking.total_price
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    amount_str = str(amount.quantize(Decimal("0.01")))
    currency = booking.currency or "RUB"
    return_url = getattr(settings, "YOOKASSA_RETURN_URL", "")

    description = f"Оплата брони #{booking.id} — {booking.spot}"

    payload: dict[str, Any] = {
        "amount": {
            "value": amount_str,
            "currency": currency,
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "capture": True,
        "description": description,
        "metadata": {
            "booking_id": str(booking.id),
            "user_id": str(booking.user_id),
        },
    }

    try:
        payment = YooPayment.create(payload, uuid.uuid4())
    except Exception as exc:  # noqa: BLE001
        raise YooKassaError(str(exc)) from exc

    confirmation = getattr(payment, "confirmation", None)
    payment_url = getattr(confirmation, "confirmation_url", None) if confirmation else None
    provider_payment_id = getattr(payment, "id", None)

    if not payment_url or not provider_payment_id:
        raise YooKassaError(
            "Некорректный ответ от YooKassa: не получены id или URL оплаты."
        )

    raw_response = {
        "id": provider_payment_id,
        "status": getattr(payment, "status", None),
    }

    return payment_url, provider_payment_id, raw_response

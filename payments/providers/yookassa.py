from __future__ import annotations

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import PaymentProvider

try:  # pragma: no cover - soft dependency
    from yookassa import Configuration, Payment as YooPayment  # type: ignore[import]
except ImportError:  # pragma: no cover - fallback
    Configuration = None
    YooPayment = None


class YooKassaError(Exception):
    """Базовая ошибка при работе с YooKassa."""


class YooKassaProvider(PaymentProvider):
    key = "yookassa"

    def _configure(self) -> None:
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

    def create_payment(
        self, payment, return_url: str, webhook_url: str
    ) -> Dict[str, Any]:
        self._configure()
        from parking.models import Booking  # локальный импорт

        booking: Booking = payment.booking
        amount = booking.total_price
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        amount_str = str(amount.quantize(Decimal("0.01")))
        currency = booking.currency or "RUB"
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
                "webhook": webhook_url,
            },
        }

        try:
            provider_payment = YooPayment.create(payload, uuid.uuid4())
        except Exception as exc:  # noqa: BLE001
            raise YooKassaError(str(exc)) from exc

        confirmation = getattr(provider_payment, "confirmation", None)
        payment_url = (
            getattr(confirmation, "confirmation_url", None) if confirmation else None
        )
        provider_payment_id = getattr(provider_payment, "id", None)

        if not payment_url or not provider_payment_id:
            raise YooKassaError(
                "Некорректный ответ от YooKassa: не получены id или URL оплаты."
            )

        raw_response = {
            "id": provider_payment_id,
            "status": getattr(provider_payment, "status", None),
        }

        return {
            "payment_url": payment_url,
            "provider_payment_id": provider_payment_id,
            "raw": raw_response,
        }

    def handle_webhook(self, request) -> Optional[Payment]:
        from payments.models import Payment

        data = request.data or {}
        event = data.get("event")
        obj = data.get("object") or {}
        provider_payment_id = obj.get("id")

        if not provider_payment_id:
            return None

        try:
            payment = Payment.objects.select_related("booking").get(
                provider_payment_id=provider_payment_id
            )
        except Payment.DoesNotExist:
            return None

        status_from_provider = obj.get("status")
        payment.raw_webhook = data

        if status_from_provider == "succeeded" or event == "payment.succeeded":
            payment.mark_succeeded(webhook_data=data)
        elif status_from_provider in ("canceled", "cancelled") or event == "payment.canceled":
            payment.mark_cancelled(webhook_data=data)
        else:
            payment.status = Payment.Status.PENDING
            payment.success = False
            payment.failure = False
            payment.save(
                update_fields=["status", "success", "failure", "raw_webhook", "updated_at"]
            )

        return payment

    def refund(self, payment, amount: Optional[float] = None) -> None:
        # Неполная реализация для MVP
        raise NotImplementedError("YooKassa refunds are not implemented in this stub.")

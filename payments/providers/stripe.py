from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from django.conf import settings

from .base import PaymentProvider


class StripeProvider(PaymentProvider):
    key = "stripe"

    def create_payment(
        self, payment, return_url: str, webhook_url: str
    ) -> Dict[str, Any]:
        """Stub: эмуляция Stripe Checkout Session.

        В бою надо подключить stripe SDK и создать Checkout Session с
        success/cancel URL. Здесь формируется предсказуемая ссылка.
        """

        session_id = str(uuid.uuid4())
        confirmation_url = f"https://checkout.stripe.com/pay/{session_id}"
        return {
            "payment_url": confirmation_url,
            "provider_payment_id": session_id,
            "raw": {
                "mode": "payment",
                "return_url": return_url,
                "webhook": webhook_url,
            },
        }

    def handle_webhook(self, request) -> Optional["Payment"]:
        from payments.models import Payment

        payload = request.data or {}
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})
        provider_payment_id = data_object.get("id")
        if not provider_payment_id:
            return None

        try:
            payment = Payment.objects.select_related("booking").get(
                provider_payment_id=provider_payment_id
            )
        except Payment.DoesNotExist:
            return None

        if event_type == "checkout.session.completed":
            payment.mark_succeeded(webhook_data=payload)
        elif event_type == "payment_intent.payment_failed":
            payment.mark_failed(webhook_data=payload)
        return payment

    def refund(self, payment, amount: Optional[float] = None) -> None:
        # Заглушка — Stripe refund через SDK
        return None

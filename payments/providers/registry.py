from __future__ import annotations

from typing import Dict, Type

from django.core.exceptions import ImproperlyConfigured

from .base import PaymentProvider
from .stripe import StripeProvider
from .yookassa import YooKassaProvider

REGISTRY: Dict[str, Type[PaymentProvider]] = {
    "yookassa": YooKassaProvider,
    "stripe": StripeProvider,
}


def get_payment_provider(provider_key: str) -> PaymentProvider:
    provider_cls = REGISTRY.get(provider_key)
    if not provider_cls:
        raise ImproperlyConfigured(f"Unknown payment provider: {provider_key}")
    return provider_cls()

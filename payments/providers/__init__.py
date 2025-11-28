# payments/providers/__init__.py

from __future__ import annotations

from typing import Dict, Type

from django.conf import settings

from .base import BasePaymentProvider
from .yookassa import YooKassaProvider
from .stripe import StripeProvider


# Реестр провайдеров по коду
_PROVIDER_REGISTRY: Dict[str, Type[BasePaymentProvider]] = {
    "yookassa": YooKassaProvider,
    "yoomoney": YooKassaProvider,  # на будущее – алиас
    "stripe": StripeProvider,
    # сюда же можно добавить Sber, Tinkoff, Mir Pay, QIWI и т.д.
}


def get_payment_provider(name: str | None = None) -> BasePaymentProvider:
    """
    Возвращает инстанс провайдера платежей по имени.

    name:
      - None     -> берём DEFAULT_PAYMENT_PROVIDER / PAYMENT_PROVIDER из настроек
      - "yookassa", "stripe" и т.п.

    Для RU-профиля по умолчанию используется YooKassa, для GLOBAL – Stripe,
    но это задаётся в .env / настройках.
    """
    # Совместимость с разными именами переменных
    configured = getattr(settings, "DEFAULT_PAYMENT_PROVIDER", None) or getattr(
        settings, "PAYMENT_PROVIDER", "yookassa"
    )

    provider_name = (name or configured or "yookassa").lower()
    provider_cls = _PROVIDER_REGISTRY.get(provider_name)

    if provider_cls is None:
        raise ValueError(
            f"Unknown payment provider '{provider_name}'. "
            f"Доступные: {', '.join(sorted(_PROVIDER_REGISTRY.keys()))}"
        )

    return provider_cls()

# payments/providers/base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..models import Payment  # относительный импорт, чтобы избежать циклов


class BasePaymentProvider(ABC):
    """
    Базовый интерфейс платёжного провайдера.

    Этот класс — единая точка расширения для YooKassa, Stripe, Сбера и т.д.
    """

    @abstractmethod
    def create_payment(
        self,
        payment: Payment,
        return_url: str,
        webhook_url: str,
    ) -> Dict[str, Any]:
        """
        Создать платёж у провайдера и вернуть его данные (включая URL для подтверждения/оплаты).
        Должен вернуть словарь с полями вроде:
            {
                "payment_url": "...",
                "provider_payment_id": "...",
                ...
            }
        """
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, request) -> Optional[Payment]:
        """
        Обработать webhook от провайдера и обновить Payment/Booking.

        Должен:
        - найти Payment по данным из webhook;
        - обновить статус/флаги;
        - вернуть обновлённый Payment (или None, если не найден/игнорируем).
        """
        raise NotImplementedError

    @abstractmethod
    def refund(self, payment: Payment, amount: Optional[float] = None) -> None:
        """
        Инициировать возврат по платежу (полный или частичный).
        """
        raise NotImplementedError


# ---------------------------------------------------------
# Обратная совместимость:
# старый код может импортировать PaymentProvider или BasePaymentProvider.
# ---------------------------------------------------------
PaymentProvider = BasePaymentProvider

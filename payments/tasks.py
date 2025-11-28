from __future__ import annotations

from celery import shared_task

from .models import Payment


@shared_task
def check_stale_payments() -> str:
    """
    Заготовка фоновой задачи для проверки "зависших" платежей.

    В будущей версии здесь можно реализовать:
    - поиск платежей в статусе PENDING слишком долго;
    - запрос их фактического состояния у YooKassa;
    - перевод в FAILED/CANCELLED при необходимости.
    """
    pending_count = Payment.objects.filter(status=Payment.Status.PENDING).count()
    return f"Pending payments count: {pending_count}"

# backend/parking/tasks.py

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Booking


@shared_task
def expire_unpaid_bookings() -> str:
    """
    Фоновая задача: помечает как EXPIRED неоплаченные бронирования,
    у которых время начала уже давно прошло.

    Подключена в CELERY_BEAT_SCHEDULE как parking.tasks.expire_unpaid_bookings.
    """

    now = timezone.now()
    grace = timedelta(minutes=15)  # "льготный" период
    qs = Booking.objects.filter(
        status=Booking.Status.PENDING,
        is_paid=False,
        start_at__lt=now - grace,
    )
    count = qs.count()
    for booking in qs:
        booking.status = Booking.Status.EXPIRED
        booking.save(update_fields=["status"])
    return f"Expired {count} unpaid bookings"

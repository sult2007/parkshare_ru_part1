from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from parking.models import Booking, ParkingLot, ParkingSpot
from .features import bookings_dataframe
from .pricing import train_pricing_model


@shared_task
def update_models() -> None:
    """
    Периодически обучает модель цен и обновляет метрики загруженности.

    Делает три вещи:
    1) обучает/переобучает ML‑модель ценообразования;
    2) считает occupancy_7d для активных мест;
    3) считает stress_index для парковок (средняя загрузка мест).
    """
    df = bookings_dataframe()
    train_pricing_model(df)

    now = timezone.now()
    window_start = now - timedelta(days=7)

    # 1–2. Обновляем occupancy_7d для мест
    active_spots = ParkingSpot.objects.filter(
        status=ParkingSpot.SpotStatus.ACTIVE,
        lot__is_active=True,
        lot__is_approved=True,
    ).select_related("lot")

    total_period_hours = 24 * 7

    for spot in active_spots:
        qs = Booking.objects.filter(
            spot=spot,
            start_at__lt=now,
            end_at__gt=window_start,
            status__in=[
                Booking.Status.CONFIRMED,
                Booking.Status.ACTIVE,
                Booking.Status.COMPLETED,
            ],
        )

        booked_hours = 0.0
        for b in qs:
            start = max(b.start_at, window_start)
            end = min(b.end_at, now)
            delta_h = max((end - start).total_seconds() / 3600.0, 0.0)
            booked_hours += delta_h

        occupancy = booked_hours / float(total_period_hours)
        spot.occupancy_7d = max(0.0, min(occupancy, 1.0))
        spot.save(update_fields=["occupancy_7d"])

    # 3. Индекс загруженности по объектам парковки
    lots = ParkingLot.objects.filter(is_active=True, is_approved=True)
    for lot in lots:
        spots = lot.spots.all()
        if not spots:
            lot.stress_index = 0.0
            lot.save(update_fields=["stress_index"])
            continue
        values = [max(0.0, min(s.occupancy_7d, 1.0)) for s in spots]
        lot.stress_index = sum(values) / len(values)
        lot.save(update_fields=["stress_index"])

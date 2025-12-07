from datetime import timedelta
import logging
from django.utils import timezone
from django.conf import settings

from .models import Booking, PushSubscription
from .models_notification import NotificationSettings

logger = logging.getLogger(__name__)


def bookings_expiring_within(minutes: int = 30):
    """Возвращает брони, заканчивающиеся в ближайшие X минут и требующие напоминания."""
    now = timezone.now()
    soon = now + timedelta(minutes=minutes)
    qs = Booking.objects.filter(
        end_at__gte=now,
        end_at__lte=soon,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.ACTIVE],
    ).select_related("user")
    eligible = []
    for booking in qs:
        settings = getattr(booking.user, "notification_settings", None)
        if settings and not settings.notify_booking_expiry:
            continue
        eligible.append(booking)
    return eligible


def target_subscriptions_for_user(user):
    """Возвращает push-подписки пользователя для отправки уведомлений."""
    return PushSubscription.objects.filter(user=user)


def send_push(subscription: PushSubscription, title: str, body: str, data: dict | None = None):
    """
    Отправка WebPush (stub-friendly). Реальная интеграция может использовать pywebpush или внешний сервис.
    """
    payload = {"title": title, "body": body, "data": data or {}}
    # Здесь мог бы быть вызов внешней службы. Логируем для проверки.
    logger.info("Sending push", extra={"endpoint": subscription.endpoint, "payload": payload})
    return True


def send_booking_expiry_notifications(minutes: int = 30):
    """Обходит активные брони и отправляет напоминания за minutes до окончания."""
    count = 0
    for booking in bookings_expiring_within(minutes):
        subs = target_subscriptions_for_user(booking.user)
        for sub in subs:
            send_push(
                sub,
                title="Бронь скоро заканчивается",
                body=f"Парковка {booking.spot.lot.name} завершится в {booking.end_at.strftime('%H:%M')}",
                data={"booking_id": str(booking.id)},
            )
            count += 1
    return count


def night_restriction_stub():
    """Заглушка под ночные ограничения, сохраняет архитектурную точку входа."""
    if getattr(settings, "ENABLE_NIGHT_RESTRICTION_NOTICES", False):
        logger.info("Night restriction notifications not implemented; stub path invoked.")

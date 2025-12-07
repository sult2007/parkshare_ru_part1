from datetime import timedelta
from django.utils import timezone

from .models import Booking, PushSubscription
from .models_notification import NotificationSettings


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

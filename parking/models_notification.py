from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationSettings(models.Model):
    """Настройки уведомлений для пользователя."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )
    notify_booking_expiry = models.BooleanField(
        _("Напоминать о завершении брони"), default=True
    )
    notify_night_restrictions = models.BooleanField(
        _("Напоминать о ночных ограничениях"), default=False
    )

    class Meta:
        verbose_name = _("Настройки уведомлений")
        verbose_name_plural = _("Настройки уведомлений")

    def __str__(self) -> str:
        return f"Notifications({self.user})"

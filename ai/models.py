# ai/models.py

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel, TimeStampedUUIDModel


class DeviceProfile(TimeStampedUUIDModel):
    """
    Профиль устройства/клиента для адаптивного UI.

    Связан либо с пользователем, либо с анонимным device_id (из cookies/LS).
    """

    class LayoutProfile(models.TextChoices):
        COMPACT = "compact", _("Компактный")
        COMFORTABLE = "comfortable", _("Комфортный")

    class Theme(models.TextChoices):
        LIGHT = "light", _("Светлая")
        DARK = "dark", _("Тёмная")
        SYSTEM = "system", _("Системная")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_profiles",
    )
    device_id = models.CharField(
        _("ID устройства"),
        max_length=64,
        db_index=True,
    )

    viewport_width = models.IntegerField(_("Ширина viewport"), null=True, blank=True)
    viewport_height = models.IntegerField(_("Высота viewport"), null=True, blank=True)
    pixel_ratio = models.FloatField(_("Pixel ratio"), null=True, blank=True)
    user_agent = models.TextField(_("User‑Agent"), blank=True)

    layout_profile = models.CharField(
        _("Профиль компоновки"),
        max_length=32,
        choices=LayoutProfile.choices,
        default=LayoutProfile.COMPACT,
    )
    theme = models.CharField(
        _("Тема"),
        max_length=16,
        choices=Theme.choices,
        default=Theme.SYSTEM,
    )

    class Meta:
        verbose_name = _("Профиль устройства")
        verbose_name_plural = _("Профили устройств")
        unique_together = ("device_id", "user")

    def __str__(self) -> str:
        return f"DeviceProfile({self.device_id}, {self.layout_profile})"


class UiEvent(TimeStampedUUIDModel):
    """
    Сырые события UI/адаптивности (scroll, resize, layout_probe и т.п.).
    """

    device_profile = models.ForeignKey(
        DeviceProfile,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(_("Тип события"), max_length=64)
    payload = models.JSONField(_("Payload"), null=True, blank=True)

    class Meta:
        verbose_name = _("UI‑событие")
        verbose_name_plural = _("UI‑события")

    def __str__(self) -> str:
        return f"UiEvent({self.event_type})"


class ChatSession(TimeStampedUUIDModel):
    """Сессия чата (cookie ps_chat_sid)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )
    client_info = models.JSONField("Данные клиента", null=True, blank=True)
    last_activity_at = models.DateTimeField("Последняя активность", auto_now=True)

    class Meta:
        verbose_name = "Сессия чата"
        verbose_name_plural = "Сессии чата"

    def __str__(self) -> str:
        return f"ChatSession({self.id})"


class ChatMessage(TimeStampedModel):
    """Сообщения в рамках сессии."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField("Роль", max_length=16, choices=Role.choices)
    text = models.TextField("Текст")
    meta = models.JSONField("Метаданные", null=True, blank=True)

    class Meta:
        verbose_name = "Сообщение чата"
        verbose_name_plural = "Сообщения чата"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"[{self.role}] {self.text[:30]}"


class ChatFeedback(TimeStampedModel):
    """Оценки ответов ассистента."""

    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    rating = models.IntegerField("Оценка", default=0)

    class Meta:
        verbose_name = "Фидбек чата"
        verbose_name_plural = "Фидбек чата"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Feedback({self.rating})"

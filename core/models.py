# backend/core/models.py
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """
    Абстрактная модель с полями created_at/updated_at.

    Используется для единообразного аудита времени создания и обновления
    записей в базовых моделях (парковки, бронирования, платежи и т.п.).
    """

    created_at = models.DateTimeField(_("Дата создания"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Дата обновления"), auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Абстрактная модель с UUID в качестве первичного ключа."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedUUIDModel(TimeStampedModel, UUIDModel):
    """Комбо UUID + таймстемпы."""

    class Meta:
        abstract = True


class FeatureFlag(TimeStampedUUIDModel):
    """Управление фичами и процентными раскатками."""

    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    rollout_percentage = models.PositiveSmallIntegerField(
        default=100,
        help_text="0-100, deterministic по пользователю",
    )
    conditions = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Фича-флаг"
        verbose_name_plural = "Фича-флаги"

    def __str__(self) -> str:  # pragma: no cover - удобочитаемость в админке
        return self.name


class ApiKey(TimeStampedUUIDModel):
    """Простой API-ключ для партнёрских S2S-интеграций."""

    name = models.CharField(max_length=128)
    prefix = models.CharField(max_length=8, db_index=True)
    key_hash = models.CharField(max_length=128, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API-ключ"
        verbose_name_plural = "API-ключи"

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix})"


class AuditLog(TimeStampedUUIDModel):
    """Мини-аудит для операций с пользователем/настройками."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Аудит"
        verbose_name_plural = "Аудит-лог"
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} -> {self.target_type}:{self.target_id}"

# backend/core/models.py
import uuid

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

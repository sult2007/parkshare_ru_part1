import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Vehicle(TimeStampedModel):
    """
    Машина пользователя.

    Важно:
    - реальный госномер нигде не хранится;
    - в БД есть только хэш цифр номера и произвольная метка (label).
    """

    class VehicleType(models.TextChoices):
        CAR = "car", _("Легковой автомобиль")
        MOTO = "moto", _("Мотоцикл")
        COMMERCIAL = "commercial", _("Коммерческий транспорт")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
        verbose_name=_("Владелец"),
    )
    label = models.CharField(
        _("Название/описание"),
        max_length=64,
        blank=True,
        help_text=_("Например: «Серая Toyota у дома»."),
    )
    vehicle_type = models.CharField(
        _("Тип транспорта"),
        max_length=16,
        choices=VehicleType.choices,
        default=VehicleType.CAR,
    )
    plate_hash = models.CharField(
        _("Хэш номера"),
        max_length=64,
        db_index=True,
        help_text=_("SHA‑256‑хэш цифр госномера с солью."),
    )

    class Meta:
        verbose_name = _("Машина")
        verbose_name_plural = _("Машины")
        unique_together = (("owner", "plate_hash"),)
        ordering = ("-created_at",)

    def __str__(self) -> str:
        if self.label:
            return f"{self.label} ({self.owner.username})"
        return f"Машина {self.pk}"

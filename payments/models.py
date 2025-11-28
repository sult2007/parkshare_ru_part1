from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """
    Платёж за бронирование через внешнего провайдера (по умолчанию — YooKassa).

    Для простоты в текущей реализации у каждой брони может быть не более
    одного связанного платежа (OneToOne), который используется повторно
    при повторных попытках оплаты, пока не станет успешным или не будет
    отменён/завершён с ошибкой.
    """

    class Provider(models.TextChoices):
        YOOKASSA = "yookassa", "YooKassa"
        STRIPE = "stripe", "Stripe"

    class Status(models.TextChoices):
        CREATED = "created", _("Создан")
        PENDING = "pending", _("Ожидает оплаты")
        SUCCEEDED = "succeeded", _("Успешен")
        CANCELLED = "cancelled", _("Отменён")
        FAILED = "failed", _("Ошибка")

    booking = models.OneToOneField(
        "parking.Booking",
        on_delete=models.CASCADE,
        related_name="payment",
        verbose_name=_("Бронь"),
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("Плательщик"),
    )

    provider = models.CharField(
        _("Провайдер"),
        max_length=32,
        choices=Provider.choices,
        default=Provider.YOOKASSA,
    )
    provider_payment_id = models.CharField(
        _("ID платежа у провайдера"),
        max_length=128,
        blank=True,
        db_index=True,
    )

    amount = models.DecimalField(
        _("Сумма"),
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(
        _("Валюта"),
        max_length=8,
        default="RUB",
    )

    status = models.CharField(
        _("Статус"),
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    success = models.BooleanField(_("Успешен"), default=False)
    failure = models.BooleanField(_("Ошибка"), default=False)

    raw_response = models.JSONField(
        _("Ответ провайдера"),
        null=True,
        blank=True,
        help_text=_("Сырые данные, вернувшиеся при создании платежа."),
    )
    raw_webhook = models.JSONField(
        _("Последний webhook"),
        null=True,
        blank=True,
        help_text=_("Последнее уведомление провайдера по этому платежу."),
    )

    class Meta:
        verbose_name = _("Платёж")
        verbose_name_plural = _("Платежи")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Payment #{self.pk} for booking #{self.booking_id}"

    @property
    def is_active(self) -> bool:
        """
        "Активный" платёж — тот, который ещё может сменить состояние на успешное.
        """
        return self.status in {self.Status.CREATED, self.Status.PENDING}

    def _update_status(
        self,
        status: str,
        success: bool,
        failure: bool,
        webhook_data: Optional[dict[str, Any]] = None,
    ) -> None:
        self.status = status
        self.success = success
        self.failure = failure
        if webhook_data is not None:
            self.raw_webhook = webhook_data
        self.save(
            update_fields=[
                "status",
                "success",
                "failure",
                "raw_webhook",
                "updated_at",
            ]
        )

    def mark_succeeded(self, webhook_data: Optional[dict[str, Any]] = None) -> None:
        """
        Помечает платёж как успешный и вызывает booking.mark_paid(...).

        Вызывается из обработчика вебхуков YooKassa после подтверждения
        успешного платежа.
        """
        self._update_status(
            status=self.Status.SUCCEEDED,
            success=True,
            failure=False,
            webhook_data=webhook_data,
        )

        # Обновляем связанную бронь.
        booking = self.booking
        if booking:
            booking.mark_paid(payment_id=self.provider_payment_id or "")

    def mark_failed(self, webhook_data: Optional[dict[str, Any]] = None) -> None:
        """
        Помечает платёж как неуспешный (ошибка).
        """
        self._update_status(
            status=self.Status.FAILED,
            success=False,
            failure=True,
            webhook_data=webhook_data,
        )

    def mark_cancelled(self, webhook_data: Optional[dict[str, Any]] = None) -> None:
        """
        Помечает платёж как отменённый пользователем или провайдером.
        """
        self._update_status(
            status=self.Status.CANCELLED,
            success=False,
            failure=True,
            webhook_data=webhook_data,
        )


class PaymentMethod(TimeStampedModel):
    """
    Привязанный способ оплаты (карта/кошелёк), без хранения PAN.

    Данные карты хранятся в токенизированном виде у провайдера эквайринга,
    здесь остаётся только маска и метаданные для UI. Настоящий токен
    хранится в encrypted поле token_masked, чтобы можно было инициировать
    повторные списания в будущем.
    """

    class Brand(models.TextChoices):
        VISA = "visa", "VISA"
        MASTERCARD = "mc", "Mastercard"
        MIR = "mir", "Мир"
        UNIONPAY = "up", "UnionPay"
        OTHER = "other", "Другая"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_methods",
        verbose_name=_("Пользователь"),
    )
    label = models.CharField(
        _("Название"),
        max_length=64,
        blank=True,
        help_text=_("Например: 'Личная', 'Для работы', 'Юрлицо'."),
    )
    brand = models.CharField(
        _("Бренд"),
        max_length=16,
        choices=Brand.choices,
        default=Brand.OTHER,
    )
    last4 = models.CharField(_("Последние 4 цифры"), max_length=4)
    exp_month = models.PositiveSmallIntegerField(_("Месяц окончания"))
    exp_year = models.PositiveSmallIntegerField(_("Год окончания"))
    is_default = models.BooleanField(_("По умолчанию"), default=False)
    token_masked = models.CharField(
        _("Токен/маска"),
        max_length=255,
        help_text=_("Служебный идентификатор платёжного провайдера."),
    )

    class Meta:
        verbose_name = _("Способ оплаты")
        verbose_name_plural = _("Способы оплаты")
        ordering = ("-is_default", "-created_at")
        unique_together = ("user", "token_masked")

    def __str__(self) -> str:
        return f"{self.get_brand_display()} ****{self.last4}"

    def save(self, *args, **kwargs):
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        return super().save(*args, **kwargs)

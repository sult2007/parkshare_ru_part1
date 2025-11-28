# payments/serializers.py

from __future__ import annotations

from typing import Any, Dict

from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from parking.models import Booking
from .models import Payment, PaymentMethod
from .providers import get_payment_provider


class PaymentSerializer(serializers.ModelSerializer):
    """
    Создание платежа для бронирования.

    Поток:
      - клиент вызывает POST /api/payments/ с booking_id;
      - сериализатор поднимает Booking, вызывает AI-ценообразование (если нужно – уже
        сделано при создании брони), берёт итоговую сумму;
      - выбирает провайдера по REGION/PLATFORM (YooKassa для RU, Stripe для GLOBAL);
      - создаёт payment в БД и у провайдера;
      - возвращает клиенту payment_url, по которому можно уйти на оплату.

    Важно: бизнес-логика расчёта цены (включая AI) находится в booking/ai,
    здесь только оркестрация и адаптеры к платёжным провайдерам.
    """

    booking_id = serializers.UUIDField(write_only=True)
    payment_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "booking_id",
            "amount",
            "currency",
            "status",
            "provider",
            "provider_payment_id",
            "created_at",
            "updated_at",
            "payment_url",
        )
        read_only_fields = (
            "id",
            "amount",
            "currency",
            "status",
            "provider",
            "provider_payment_id",
            "created_at",
            "updated_at",
            "payment_url",
        )

    def validate_booking_id(self, value):
        try:
            booking = Booking.objects.select_related("spot", "spot__lot").get(pk=value)
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Бронирование не найдено.")
        if booking.status not in (
            Booking.Status.PENDING,
            Booking.Status.CONFIRMED,
        ):
            raise serializers.ValidationError(
                "Платёж можно создать только для ожидающего/подтверждённого бронирования."
            )
        return value

    def _get_booking(self, booking_id) -> Booking:
        return Booking.objects.select_related("spot", "spot__lot").get(pk=booking_id)

    def create(self, validated_data: Dict[str, Any]) -> Payment:
        request = self.context.get("request")
        booking_id = validated_data["booking_id"]
        booking = self._get_booking(booking_id)

        # Сумма для оплаты – итоговая цена брони (уже с AI-ценообразованием, если применено)
        amount = booking.total_price
        currency = getattr(settings, "DEFAULT_CURRENCY", "RUB")

        # Выбор провайдера:
        #   - для RU профиль по умолчанию будет YooKassa (см. .env/.env.prod);
        #   - для GLOBAL можно выставить stripe в PAYMENT_PROVIDER/DEFAULT_PAYMENT_PROVIDER.
        provider = get_payment_provider()

        payment = Payment.objects.create(
            booking=booking,
            amount=amount,
            currency=currency,
            provider=provider.code,
            status=Payment.Status.CREATED,
        )

        # URL возврата пользователя после оплаты
        if request is not None:
            return_url = request.build_absolute_uri(
                reverse("payments:return")  # см. urls в payments/views
            )
            webhook_url = request.build_absolute_uri(
                reverse("payments:webhook", kwargs={"provider": provider.code})
            )
        else:
            # fallback для внутренних вызовов/тестов
            return_url = getattr(settings, "YOOKASSA_RETURN_URL", "/")
            webhook_url = ""

        # Вызов провайдера (адаптер)
        provider_response = provider.create_payment(
            payment=payment,
            return_url=return_url,
            webhook_url=webhook_url,
        )

        # Ожидаем, что адаптер вернёт структуру с provider_payment_id и
        # опциональным полем payment_url/confirmation_url.
        payment.provider_payment_id = provider_response.get("id") or provider_response.get(
            "provider_payment_id", ""
        )
        payment.raw_response = provider_response
        payment.save(update_fields=["provider_payment_id", "raw_response"])

        return payment

    def get_payment_url(self, obj: Payment) -> str | None:
        """
        Вытаскиваем URL для редиректа пользователя из raw_response.
        Для YooKassa это обычно confirmation.redirect_url,
        для Stripe – session.url и т.п.
        """
        data = obj.raw_response or {}
        # Общий подход: пытаемся найти наиболее очевидные поля
        return (
            data.get("payment_url")
            or data.get("confirmation_url")
            or (data.get("confirmation") or {}).get("confirmation_url")
            or (data.get("session") or {}).get("url")
        )


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Сериализатор для сохранённых карт/кошельков."""

    mask = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PaymentMethod
        fields = (
            "id",
            "label",
            "brand",
            "last4",
            "exp_month",
            "exp_year",
            "is_default",
            "token_masked",
            "mask",
            "created_at",
        )
        read_only_fields = ("id", "mask", "created_at")

    def get_mask(self, obj: PaymentMethod) -> str:
        return f"**** **** **** {obj.last4}"

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["user"] = request.user
        return super().create(validated_data)

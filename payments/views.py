from __future__ import annotations

from django.conf import settings
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, PaymentMethod
from .serializers import PaymentMethodSerializer, PaymentSerializer
from .providers.registry import get_payment_provider


class PaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    API платежей:

    - GET  /api/payments/       — список платежей текущего пользователя;
    - POST /api/payments/       — начать оплату для брони;
    - GET  /api/payments/{id}/  — детали платежа.

    Только владелец платежа видит свои платежи; админ — все.
    """

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related(
            "booking",
            "booking__spot",
            "booking__spot__lot",
            "payer",
        )
        if not user.is_authenticated:
            return Payment.objects.none()
        if user.is_superuser:
            return qs
        return qs.filter(payer=user)

    def perform_create(self, serializer: PaymentSerializer) -> None:
        serializer.save()


class PaymentMethodViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Мини-API для управления сохранёнными картами в ЛК.

    POST /api/payment-methods/ — добавить карту (пока без реального токенизации);
    GET  /api/payment-methods/ — список карт пользователя;
    DELETE /api/payment-methods/{id}/ — удалить карту.
    """

    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return PaymentMethod.objects.none()
        if user.is_superuser:
            return PaymentMethod.objects.select_related("user").order_by("-is_default", "-created_at")
        return PaymentMethod.objects.filter(user=user).order_by("-is_default", "-created_at")

    def perform_create(self, serializer: PaymentMethodSerializer) -> None:
        serializer.save(user=self.request.user)

    def perform_update(self, serializer: PaymentMethodSerializer) -> None:
        serializer.save(user=self.request.user)


class YooKassaWebhookView(APIView):
    """
    Обработчик webhook‑уведомлений YooKassa.

    URL: /payments/webhook/yookassa/  (см. backend.config.urls)

    Ожидается JSON вида:

    {
        "event": "payment.succeeded",
        "object": {
            "id": "...",
            "status": "succeeded",
            ...
        }
    }

    Подпись/секрет проверяется по заголовку X-Yookassa-Signature
    (или X-Yookassa-Webhook-Secret), который совпадает с
    settings.YOOKASSA_WEBHOOK_SECRET. Если секрет не задан, проверка
    подписи пропускается.
    """

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        secret_expected = getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "")
        if secret_expected:
            signature = (
                request.headers.get("X-Yookassa-Signature")
                or request.headers.get("X-Yookassa-Webhook-Secret")
            )
            if not signature or signature != secret_expected:
                return Response(
                    {"detail": "Invalid webhook signature"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        data = request.data or {}
        event = data.get("event")
        obj = data.get("object") or {}
        provider_payment_id = obj.get("id")

        if not provider_payment_id:
            return Response(
                {"detail": "Missing payment id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_related("booking").get(
                provider_payment_id=provider_payment_id
            )
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_from_provider = obj.get("status")
        payment.raw_webhook = data

        if status_from_provider == "succeeded" or event == "payment.succeeded":
            payment.mark_succeeded(webhook_data=data)
        elif status_from_provider in ("canceled", "cancelled") or event == "payment.canceled":
            payment.mark_cancelled(webhook_data=data)
        else:
            # Любые промежуточные статусы считаем ожидающими
            payment.status = Payment.Status.PENDING
            payment.success = False
            payment.failure = False
            payment.save(
                update_fields=["status", "success", "failure", "raw_webhook", "updated_at"]
            )

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)


class StripeWebhookView(APIView):
    """Простой webhook Stripe (stub)."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        provider = get_payment_provider("stripe")
        payment = provider.handle_webhook(request)
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

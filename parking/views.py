from __future__ import annotations

from typing import Any, Iterable, List
import uuid
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Q
import math
import requests
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from core.metrics import record_booking_event
from core.permissions import IsAdminOrReadOnly
from core.utils import haversine_distance_km, parse_float
from vehicles.models import Vehicle
from payments.models import PaymentMethod
from ai import tools as ai_tools
from ai.models import DeviceProfile, UiEvent
from parking.models_notification import NotificationSettings
from parking.analytics import compute_funnel

logger = logging.getLogger(__name__)
from accounts.models import UserLevel, UserBadge, PromoReward

from .models import (
    Booking,
    Complaint,
    FavoriteParkingSpot,
    ParkingLot,
    ParkingSpot,
    PushSubscription,
    SavedPlace,
    WaitlistEntry,
)
from .serializers import (
    BookingSerializer,
    ComplaintSerializer,
    FavoriteParkingSpotSerializer,
    ParkingLotSerializer,
    ParkingSpotSerializer,
    PushSubscriptionSerializer,
    SavedPlaceSerializer,
    WaitlistEntrySerializer,
)


def api_error(code: str, message: str, status_code=status.HTTP_400_BAD_REQUEST, details=None):
    return Response({"code": code, "message": message, "details": details or {}}, status=status_code)


def wants_json(request):
    accept = request.headers.get("Accept", "")
    return "application/json" in accept or request.content_type == "application/json"


# =======================
#   DRF ViewSets (API)
# =======================


class ParkingLotViewSet(viewsets.ModelViewSet):
    """
    CRUD по объектам парковки.

    - GET /api/parking/lots/ — список (фильтрация по городу/типу)
    - POST /api/parking/lots/ — создать (только владельцы/админы)
    """

    serializer_class = ParkingLotSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = ParkingLot.objects.select_related("owner")
        user = self.request.user
        if not user.is_authenticated or (
            not user.is_staff and not getattr(user, "is_owner", False)
        ):
            qs = qs.filter(is_active=True, is_approved=True)

        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city)

        parking_type = self.request.query_params.get("parking_type")
        if parking_type:
            qs = qs.filter(parking_type=parking_type)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated or not getattr(user, "is_owner", False):
            raise permissions.PermissionDenied(
                "Создавать объекты парковки могут только пользователи с ролью 'owner' или администраторы."
            )
        serializer.save(owner=user)


class ParkingSpotViewSet(viewsets.ModelViewSet):
    """
    CRUD по парковочным местам.

    - GET /api/parking/spots/?lat=.&lng=.&radius_km=2 — места рядом
    - Фильтры: ?city=, ?vehicle_type=, ?max_price=, ?has_ev=1, ?covered=1, ?is_24_7=1
    """

    serializer_class = ParkingSpotSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = ParkingSpot.objects.select_related("lot", "lot__owner").all()
        user = self.request.user

        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            qs = qs.filter(
                status=ParkingSpot.SpotStatus.ACTIVE,
                lot__is_active=True,
                lot__is_approved=True,
            )
        else:
            # Управлять местами может только владелец/админ
            if not user.is_authenticated or (
                not getattr(user, "is_owner", False) and not user.is_superuser
            ):
                return ParkingSpot.objects.none()
            qs = qs.filter(lot__owner=user)

        # Фильтрация
        params = self.request.query_params
        city = params.get("city")
        if city:
            qs = qs.filter(lot__city__iexact=city)

        vehicle_type = params.get("vehicle_type")
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)

        max_price = parse_float(params.get("max_price"))
        if max_price is not None:
            qs = qs.filter(hourly_price__lte=max_price)

        has_ev = params.get("has_ev")
        if has_ev == "1":
            qs = qs.filter(has_ev_charging=True)

        covered = params.get("covered")
        if covered == "1":
            qs = qs.filter(is_covered=True)

        is_24_7 = params.get("is_24_7")
        if is_24_7 == "1":
            qs = qs.filter(is_24_7=True)

        return qs

    def list(self, request, *args, **kwargs):
        """
        Список мест c опциональной фильтрацией по радиусу от точки (lat/lng).
        """
        queryset = self.filter_queryset(self.get_queryset())

        try:
            page_size = int(request.query_params.get("page_size") or 50)
        except (TypeError, ValueError):
            page_size = 50
        page_size = min(max(page_size, 1), 100)
        if hasattr(self, "paginator"):
            self.paginator.page_size = page_size

        lat = parse_float(request.query_params.get("lat"))
        lng = parse_float(request.query_params.get("lng"))
        radius_km = parse_float(request.query_params.get("radius_km")) or 5
        radius_km = min(radius_km, 25)

        if lat is not None and lng is not None and radius_km is not None:
            lat_delta = radius_km / 111  # приблизительно ~111 км на градус
            lng_delta = radius_km / max(1, 111 * math.cos(math.radians(lat)))
            queryset = queryset.filter(
                lot__latitude__gte=lat - lat_delta,
                lot__latitude__lte=lat + lat_delta,
                lot__longitude__gte=lng - lng_delta,
                lot__longitude__lte=lng + lng_delta,
            )
            # Python‑фильтрация по расстоянию (работает и без PostGIS)
            filtered: List[ParkingSpot] = []
            for spot in queryset:
                lot = spot.lot
                if lot.latitude is None or lot.longitude is None:
                    continue
                distance = haversine_distance_km(
                    lat, lng, lot.latitude, lot.longitude
                )
                if distance <= radius_km:
                    spot.distance_km = distance  # для сериализатора
                    filtered.append(spot)
            queryset = filtered

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            self._maybe_cache_response(request, response.data)
            return response

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        self._maybe_cache_response(request, data)
        return Response(data)

    def _maybe_cache_response(self, request, data):
        user = request.user
        if user.is_authenticated:
            return
        lat = parse_float(request.query_params.get("lat"))
        lng = parse_float(request.query_params.get("lng"))
        if lat is None or lng is None:
            return
        cache_key = "spots:{lat:.4f}:{lng:.4f}:{radius}:{page}:{size}".format(
            lat=lat,
            lng=lng,
            radius=request.query_params.get("radius_km") or "default",
            page=request.query_params.get("page") or "1",
            size=request.query_params.get("page_size") or "",
        )
        cache.set(cache_key, data, 60)


class BookingViewSet(viewsets.ModelViewSet):
    """
    Бронирования.

    - Пользователь видит свои бронирования.
    - Владелец видит свои бронирования и брони по своим местам.
    """

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Booking.objects.select_related(
            "spot", "spot__lot", "user", "vehicle"
        ).all()
        if not user.is_authenticated:
            return Booking.objects.none()

        if user.is_superuser:
            return qs

        if getattr(user, "is_owner", False):
            return qs.filter(Q(user=user) | Q(spot__lot__owner=user))
        return qs.filter(user=user)

    def perform_create(self, serializer):
        booking = serializer.save()
        try:
            record_booking_event("created")
        except Exception:
            pass
        return booking

    def destroy(self, request, *args, **kwargs):
        """
        Отмена бронирования: помечаем как CANCELLED, если оно ещё не началось.
        """
        instance: Booking = self.get_object()
        if instance.has_started:
            return Response(
                {"detail": "Нельзя отменить уже начавшееся бронирование."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.status = Booking.Status.CANCELLED
        instance.save(update_fields=["status"])
        try:
            record_booking_event("cancelled")
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class WaitlistViewSet(viewsets.ModelViewSet):
    """
    Лист ожидания. Пользователь управляет только своими записями.
    Админ может видеть всё.
    """

    serializer_class = WaitlistEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = WaitlistEntry.objects.select_related("spot", "spot__lot", "user")
        if user.is_superuser:
            return qs
        return qs.filter(user=user)


class ComplaintViewSet(viewsets.ModelViewSet):
    """
    Жалобы. Создатель видит свои, админ — все.
    """

    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Complaint.objects.select_related("author", "spot", "booking")
        if user.is_superuser:
            return qs
        return qs.filter(author=user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class FavoriteParkingSpotViewSet(viewsets.ModelViewSet):
    """API избранных парковочных мест."""

    serializer_class = FavoriteParkingSpotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = FavoriteParkingSpot.objects.select_related("spot", "spot__lot")
        if user.is_superuser:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedPlaceViewSet(viewsets.ModelViewSet):
    """Сохранённые точки (дом/офис)."""

    serializer_class = SavedPlaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = SavedPlace.objects.all()
        if user.is_superuser:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PushSubscriptionViewSet(viewsets.ModelViewSet):
    """Регистрация WebPush подписок."""

    serializer_class = PushSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return PushSubscription.objects.none()
        return PushSubscription.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user if self.request.user.is_authenticated else None)


# =======================
#   HTML-вьюхи
# =======================


class LandingPageView(TemplateView):
    """
    Лендинг с картой и списком парковок/мест.
    Поддерживает фильтры:
    - city
    - lat, lng, radius_km (поиск по радиусу)
    """

    template_name = "parking/landing.html"

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        city = (self.request.GET.get("city") or "").strip()
        ctx["lots"] = []  # данные отдаём через API, чтобы не дублировать шаблонную логику
        ctx["spots"] = []
        ctx["has_query"] = bool(city)
        ctx["spots_total"] = ParkingSpot.objects.filter(
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        ).count()
        return ctx


class MapPageView(LandingPageView):
    """Полноэкранная карта с теми же данными, что и лендинг."""

    template_name = "parking/map_fullscreen.html"


class PWAInstallGuideView(TemplateView):
    """Простая страница с инструкциями по установке PWA."""

    template_name = "parking/pwa_install.html"


class UserDashboardView(LoginRequiredMixin, TemplateView):
    """
    Личный кабинет водителя: его машины и бронирования.
    """

    template_name = "parking/user_dashboard.html"

    def _level_progress(self, user, completed_count: int):
        levels = list(UserLevel.objects.all().order_by("threshold"))
        current = None
        next_level = None
        for lvl in levels:
            if completed_count >= lvl.threshold:
                current = lvl
            elif completed_count < lvl.threshold and not next_level:
                next_level = lvl
        remaining = max(0, (next_level.threshold - completed_count)) if next_level else 0
        progress = 100
        if next_level and next_level.threshold:
            prev_threshold = current.threshold if current else 0
            span = next_level.threshold - prev_threshold
            progress = int(min(100, max(0, ((completed_count - prev_threshold) / span) * 100)))
        return current, next_level, remaining, progress

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        vehicles = Vehicle.objects.filter(owner=user).order_by("-created_at")
        bookings = (
            Booking.objects.filter(user=user)
            .select_related("spot", "spot__lot")
            .order_by("-start_at")
        )
        completed_count = bookings.filter(status__in=[Booking.Status.COMPLETED, Booking.Status.CONFIRMED, Booking.Status.ACTIVE]).count()
        current_level, next_level, remaining, progress = self._level_progress(user, completed_count)
        ctx["vehicles"] = vehicles
        ctx["bookings"] = bookings
        ctx["badges"] = UserBadge.objects.filter(user=user)
        ctx["level"] = current_level
        ctx["next_level"] = next_level
        ctx["level_remaining"] = remaining
        ctx["level_progress"] = progress
        return ctx


class OwnerDashboardView(LoginRequiredMixin, TemplateView):
    """
    Кабинет владельца: его паркинги, места и бронирования по ним.
    """

    template_name = "parking/owner_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not (getattr(user, "is_owner", False) or user.is_superuser):
            # Если не владелец — отправляем в обычный кабинет
            return redirect("user_dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        lots = (
            ParkingLot.objects.filter(owner=user)
            .prefetch_related("spots")
            .order_by("city", "name")
        )
        spots = (
            ParkingSpot.objects.filter(lot__owner=user)
            .select_related("lot")
            .order_by("lot__city", "lot__name", "name")
        )
        bookings = (
            Booking.objects.filter(spot__lot__owner=user)
            .select_related("spot", "spot__lot", "user")
            .order_by("-start_at")
        )
        ctx["lots"] = lots
        ctx["spots"] = spots
        ctx["bookings"] = bookings
        return ctx


class BookingConfirmView(LoginRequiredMixin, TemplateView):
    """
    Экран подтверждения бронирования с выбором интервала, оплаты и бизнес-флага.
    """

    template_name = "parking/booking_confirm.html"

    def _normalize_hours(self, hours: float, billing_mode: str) -> float:
        if billing_mode == Booking.BillingMode.PREPAID_BLOCK:
            blocks = max(1, math.ceil(hours / 2))
            return blocks * 2
        return hours

    def _estimate_price(self, spot: ParkingSpot, hours: float, billing_mode: str, booking_type=None):
        hours = self._normalize_hours(hours, billing_mode)
        start_at = timezone.now()
        end_at = start_at + timezone.timedelta(hours=hours)
        booking = Booking(
            user=self.request.user,
            spot=spot,
            start_at=start_at,
            end_at=end_at,
            booking_type=booking_type or Booking.BookingType.HOURLY,
            billing_mode=billing_mode or Booking.BillingMode.PAYG,
            total_price=0,
        )
        return float(booking.calculate_price())

    def get_spot(self):
        spot_id = self.request.GET.get("spot_id") or self.request.POST.get("spot_id")
        return get_object_or_404(
            ParkingSpot,
            pk=spot_id,
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        )

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        spot = self.get_spot()
        user = self.request.user
        vehicles = Vehicle.objects.filter(owner=user).order_by("-created_at")
        payment_methods = PaymentMethod.objects.filter(user=user).order_by("-is_default", "-created_at")
        billing_mode = self.request.POST.get("billing_mode") or self.request.GET.get("billing_mode") or Booking.BillingMode.PAYG
        ctx.update(
            {
                "spot": spot,
                "spot_estimates": {
                    "h1": self._estimate_price(spot, 1, billing_mode, Booking.BookingType.HOURLY),
                    "h3": self._estimate_price(spot, 3, billing_mode, Booking.BookingType.HOURLY),
                    "h24": self._estimate_price(spot, 24, billing_mode, Booking.BookingType.DAILY),
                },
                "vehicles": vehicles,
                "payment_methods": payment_methods,
                "default_vehicle": vehicles.first(),
                "default_payment": payment_methods.first(),
                "errors": kwargs.get("errors") or [],
                "success": kwargs.get("success"),
                "selected_hours": kwargs.get("selected_hours", 1),
                "billing_mode": billing_mode,
            }
        )
        return ctx

    def post(self, request, *args, **kwargs):
        spot = self.get_spot()
        user = request.user
        if getattr(settings, "MAINTENANCE_MODE", False):
            return api_error("maintenance", "Сервис временно недоступен для бронирования.", status.HTTP_503_SERVICE_UNAVAILABLE)
        hours = float(request.POST.get("hours") or 1)
        vehicle_id = request.POST.get("vehicle_id")
        payment_method_id = request.POST.get("payment_method_id")
        billing_mode = request.POST.get("billing_mode") or Booking.BillingMode.PAYG
        is_business = request.POST.get("is_business") == "on"

        hours_norm = self._normalize_hours(hours, billing_mode)
        start_at = timezone.now()
        end_at = start_at + timezone.timedelta(hours=hours_norm)
        booking_type = Booking.BookingType.DAILY if hours >= 24 else Booking.BookingType.HOURLY

        errors = []
        if not Booking.is_spot_available(spot, start_at, end_at):
            errors.append("Место занято в выбранный период. Выберите другой интервал.")

        if errors:
            return self.render_to_response(
                self.get_context_data(
                    errors=errors,
                    selected_hours=hours,
                )
            )

        booking = Booking.objects.create(
            user=user,
            spot=spot,
            vehicle_id=vehicle_id or None,
            booking_type=booking_type,
            billing_mode=billing_mode,
            start_at=start_at,
            end_at=end_at,
            status=Booking.Status.PENDING,
            total_price=0,
            ai_snapshot={"billing_mode": billing_mode, "business_trip": is_business},
        )
        booking.calculate_price()
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["total_price", "status", "ai_snapshot"])

        # Статус оплаты — заглушка: интеграция с провайдером может обновить позже
        success_msg = f"Бронь #{booking.id} создана. Сумма: {booking.total_price} ₽."
        logger.info("Booking created", extra={"booking_id": booking.id, "user": user.id, "billing_mode": billing_mode})
        return self.render_to_response(
            self.get_context_data(
                success=success_msg,
                selected_hours=hours,
            )
        )


def _get_device_profile(request):
    device_id = request.COOKIES.get("ps_device_id") or f"ps_{uuid.uuid4().hex}"
    profile, _ = DeviceProfile.objects.get_or_create(
        device_id=device_id,
        user=request.user if request.user.is_authenticated else None,
        defaults={"layout_profile": DeviceProfile.LayoutProfile.COMPACT},
    )
    return profile


class ProfileSettingsView(LoginRequiredMixin, TemplateView):
    """Настройки профиля: предпочтения парковки и уведомления."""

    template_name = "parking/profile_settings.html"

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        profile = _get_device_profile(self.request)
        prefs = ai_tools.load_preferences(profile)
        notif, _ = NotificationSettings.objects.get_or_create(user=self.request.user)
        ctx.update(
            {
                "preferences": prefs,
                "success": kwargs.get("success"),
                "notifications": notif,
            }
        )
        return ctx

    def post(self, request, *args, **kwargs):
        profile = _get_device_profile(request)
        if "reset_prefs" in request.POST:
            UiEvent.objects.filter(device_profile=profile, event_type="preferences").delete()
            if wants_json(request):
                return Response({"message": "Предпочтения сброшены"}, status=status.HTTP_200_OK)
            return self.render_to_response(self.get_context_data(success="Предпочтения сброшены"))
        notif, _ = NotificationSettings.objects.get_or_create(user=request.user)
        notif.notify_booking_expiry = request.POST.get("notify_booking_expiry") == "on"
        notif.notify_night_restrictions = request.POST.get("notify_night_restrictions") == "on"
        notif.save(update_fields=["notify_booking_expiry", "notify_night_restrictions"])
        if wants_json(request):
            return Response({"message": "Настройки уведомлений обновлены"}, status=status.HTTP_200_OK)
        return self.render_to_response(self.get_context_data(success="Настройки уведомлений обновлены"))


class PaymentMethodsPageView(LoginRequiredMixin, TemplateView):
    """Страница управления способами оплаты (минимальная заглушка)."""

    template_name = "parking/payment_methods.html"

    def _detect_brand(self, card_number: str) -> str:
        if card_number.startswith("4"):
            return PaymentMethod.Brand.VISA
        if card_number.startswith("5"):
            return PaymentMethod.Brand.MASTERCARD
        if card_number.startswith("220"):
            return PaymentMethod.Brand.MIR
        if card_number.startswith("62"):
            return PaymentMethod.Brand.UNIONPAY
        return PaymentMethod.Brand.OTHER

    def post(self, request, *args, **kwargs):
        user = request.user
        if getattr(settings, "MAINTENANCE_MODE", False):
            if wants_json(request):
                return api_error("maintenance", "Сервис недоступен для изменения оплаты.", status.HTTP_503_SERVICE_UNAVAILABLE)
            return self.render_to_response(self.get_context_data(success="Сервис недоступен для изменения оплаты."))
        if "delete_id" in request.POST:
            PaymentMethod.objects.filter(user=user, id=request.POST.get("delete_id")).delete()
            if wants_json(request):
                return Response({"message": "Метод оплаты удалён"}, status=status.HTTP_200_OK)
            logger.info("Payment method deleted", extra={"user": user.id})
            return self.render_to_response(self.get_context_data(success="Метод оплаты удалён"))

        card = (request.POST.get("card_number") or "").replace(" ", "")
        if len(card) < 12:
            if wants_json(request):
                return api_error("invalid_card", "Некорректный номер карты")
            return self.render_to_response(self.get_context_data(success="Некорректный номер карты"))
        last4 = card[-4:] if len(card) >= 4 else "0000"
        exp = (request.POST.get("exp") or "").split("/")
        try:
            exp_month = int(exp[0]) if exp else 1
            exp_year = int(exp[1]) if len(exp) > 1 else 30
        except ValueError:
            exp_month, exp_year = 1, 30
        label = request.POST.get("label") or "Моя карта"
        brand = self._detect_brand(card)
        is_default = request.POST.get("is_default") == "on"
        PaymentMethod.objects.create(
            user=user,
            label=label,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
            token_masked=f"stub_{last4}_{timezone.now().timestamp()}",
        )
        logger.info("Payment method added", extra={"user": user.id, "brand": brand, "last4": last4})
        if wants_json(request):
            return Response({"message": "Метод оплаты добавлен"}, status=status.HTTP_200_OK)
        return self.render_to_response(self.get_context_data(success="Метод оплаты добавлен"))

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        methods = PaymentMethod.objects.filter(user=self.request.user).order_by("-is_default", "-created_at")
        ctx["methods"] = methods
        ctx["success"] = kwargs.get("success")
        return ctx


class PromoActivateView(LoginRequiredMixin, TemplateView):
    """Простая активация промокода."""

    template_name = "parking/promo_activate.html"

    def post(self, request, *args, **kwargs):
        code = (request.POST.get("code") or "").strip()
        if len(code) > 64:
            if wants_json(request):
                return api_error("invalid_promo", "Промокод слишком длинный.", status.HTTP_400_BAD_REQUEST)
            code = code[:64]
        message = "Промокод недействителен или исчерпан."
        try:
            reward = PromoReward.objects.get(code__iexact=code, active=True)
            message = f"Промокод применён: {reward.description or 'бонус'}"
        except PromoReward.DoesNotExist:
            if wants_json(request):
                return api_error("invalid_promo", "Промокод недействителен или исчерпан.", status.HTTP_400_BAD_REQUEST)
            message = "Промокод недействителен или исчерпан."
            logger.warning("Promo activation failed", extra={"user": request.user.id, "code": code})
        if wants_json(request):
            return Response({"message": message}, status=status.HTTP_200_OK)
        return self.render_to_response({"message": message})

    def get(self, request, *args, **kwargs):
        return self.render_to_response({"message": None})


class BusinessReportsView(LoginRequiredMixin, TemplateView):
    """Отчёты по служебным поездкам с экспортом CSV."""

    template_name = "parking/business_reports.html"

    def get_queryset(self, start=None, end=None, city=None):
        user = self.request.user
        qs = (
            Booking.objects.filter(user=user)
            .select_related("spot", "spot__lot")
            .order_by("-start_at")
        )
        qs = [b for b in qs if (b.ai_snapshot or {}).get("business_trip")]
        if start:
            qs = [b for b in qs if b.start_at.date() >= start]
        if end:
            qs = [b for b in qs if b.start_at.date() <= end]
        if city:
            qs = [b for b in qs if b.spot.lot.city.lower() == city.lower()]
        return qs

    def get(self, request, *args, **kwargs):
        start_param = request.GET.get("start")
        end_param = request.GET.get("end")
        city = request.GET.get("city") or None
        start = end = None
        if start_param:
            try:
                start = timezone.datetime.fromisoformat(start_param).date()
            except ValueError:
                start = None
        if end_param:
            try:
                end = timezone.datetime.fromisoformat(end_param).date()
            except ValueError:
                end = None
        qs = self.get_queryset(start, end, city)
        if request.GET.get("export") == "csv":
            rows = [
                ["Дата", "Локация", "Адрес", "Длительность (ч)", "Стоимость", "Режим биллинга", "Бизнес"]
            ]
            for b in qs:
                duration_h = round((b.end_at - b.start_at).total_seconds() / 3600, 2)
                rows.append(
                    [
                        b.start_at.strftime("%Y-%m-%d %H:%M"),
                        b.spot.lot.name,
                        b.spot.lot.address,
                        duration_h,
                        float(b.total_price),
                        b.billing_mode,
                        (b.ai_snapshot or {}).get("business_trip", False),
                    ]
                )
            content = "\n".join([",".join(map(lambda x: str(x), row)) for row in rows])
            resp = HttpResponse(content, content_type="text/csv")
            resp["Content-Disposition"] = 'attachment; filename="business_bookings.csv"'
            return resp
        total_duration = sum((b.end_at - b.start_at).total_seconds() / 3600 for b in qs)
        total_cost = sum(float(b.total_price) for b in qs)
        return self.render_to_response(
            {
                "bookings": qs,
                "total_count": len(qs),
                "total_duration": round(total_duration, 2),
                "total_cost": round(total_cost, 2),
                "filters": {"start": start_param, "end": end_param, "city": city},
            }
        )


class MetricsDashboardView(LoginRequiredMixin, TemplateView):
    """Внутренний дашборд для метрик/воронок (staff only)."""

    template_name = "admin/metrics.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect("admin:login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        ctx["total_bookings"] = Booking.objects.count()
        ctx["business_bookings"] = Booking.objects.filter(ai_snapshot__business_trip=True).count()
        ctx["ai_sessions"] = UiEvent.objects.filter(event_type="preferences").count()
        ctx["last7"] = compute_funnel(7)
        ctx["last30"] = compute_funnel(30)
        return ctx

# parking/views.py (добавить после существующих APIView/ ViewSet)

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ai.orchestrator import AvailabilityDecision
from .models import ParkingSpot


class ParkingMapAPIView(APIView):
    """
    Лёгкий эндпоинт для карты:
    - фильтры по цене/фичам;
    - возвращает GeoJSON‑подобную структуру (features).
    """

    permission_classes = [AllowAny]
    throttle_classes = [UserRateThrottle, AnonRateThrottle]

    def get(self, request, *args, **kwargs):
        params = request.query_params
        only_free = params.get("only_free") == "true"
        has_ev = params.get("ev") == "true"
        covered = params.get("covered") == "true"
        is_24_7 = params.get("is_24_7") == "true"
        ai_only = params.get("ai_recommended") == "true"

        try:
            min_price = float(params.get("min_price") or 0)
        except ValueError:
            min_price = 0.0
        try:
            max_price = float(params.get("max_price") or 0)
        except ValueError:
            max_price = 0.0

        qs = ParkingSpot.objects.filter(
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        ).select_related("lot")

        if has_ev:
            qs = qs.filter(has_ev_charging=True)
        if covered:
            qs = qs.filter(is_covered=True)
        if is_24_7:
            qs = qs.filter(is_24_7=True)
        if min_price:
            qs = qs.filter(hourly_price__gte=min_price)
        if max_price:
            qs = qs.filter(hourly_price__lte=max_price)
        if ai_only:
            qs = qs.filter(allow_dynamic_pricing=True)

        features = []
        for spot in qs[:500]:  # safety limit
            lat = getattr(spot.lot, "latitude", None)
            lng = getattr(spot.lot, "longitude", None)
            if lat is None or lng is None:
                continue

            availability_score = 1.0 - float(spot.occupancy_7d or 0.0)
            is_free_like = availability_score > 0.3

            if only_free and not is_free_like:
                continue

            features.append(
                {
                    "id": str(spot.id),
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat],
                    },
                    "properties": {
                        "spot_id": str(spot.id),
                        "lot_id": str(spot.lot_id),
                        "lot_name": spot.lot.name,
                        "city": spot.lot.city,
                        "address": spot.lot.address,
                        "name": spot.name,
                        "vehicle_type": spot.vehicle_type,
                        "has_ev_charging": spot.has_ev_charging,
                        "is_covered": spot.is_covered,
                        "is_24_7": spot.is_24_7,
                        "hourly_price": float(spot.hourly_price),
                        "nightly_price": float(spot.nightly_price or 0),
                        "daily_price": float(spot.daily_price or 0),
                        "monthly_price": float(spot.monthly_price or 0),
                        "status": spot.status,
                        "allow_dynamic_pricing": spot.allow_dynamic_pricing,
                        "occupancy_7d": float(spot.occupancy_7d or 0.0),
                        "stress_index": float(spot.lot.stress_index or 0.0),
                    },
                }
            )

        return Response(
            {
                "type": "FeatureCollection",
                "features": features,
            }
        )


class GeocodeAPIView(APIView):
    """Простой прокси к Nominatim с кешированием."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"detail": "q is required"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"geocode:{query}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        url = "https://nominatim.openstreetmap.org/search"
        try:
            resp = requests.get(
                url,
                params={"q": query, "format": "json", "limit": 5, "addressdetails": 1},
                headers={"User-Agent": "ParkShare-RU/1.0"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return api_error("geocode_unavailable", "Геокодер временно недоступен", status.HTTP_503_SERVICE_UNAVAILABLE)
        results = [
            {
                "title": item.get("display_name"),
                "lat": float(item.get("lat")),
                "lng": float(item.get("lon")),
            }
            for item in data
        ]
        payload = {"results": results}
        cache.set(cache_key, payload, 60 * 10)
        return Response(payload)


from __future__ import annotations

from typing import Any, Iterable, List

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import Q
import math
import requests
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from core.utils import haversine_distance_km, parse_float
from vehicles.models import Vehicle

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

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        vehicles = Vehicle.objects.filter(owner=user).order_by("-created_at")
        bookings = (
            Booking.objects.filter(user=user)
            .select_related("spot", "spot__lot")
            .order_by("-start_at")
        )
        ctx["vehicles"] = vehicles
        ctx["bookings"] = bookings
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
        resp = requests.get(
            url,
            params={"q": query, "format": "json", "limit": 5, "addressdetails": 1},
            headers={"User-Agent": "ParkShare-RU/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
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


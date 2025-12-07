# backend/ai/views.py

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from parking.models import ParkingLot, ParkingSpot
from ai.pricing import recommend_price_for_spot
from ai.models import DeviceProfile, UiEvent
from services.llm import check_llm_health
from ai.chat.parking_assistant import generate_chat_reply

logger = logging.getLogger(__name__)



class RecommendationsAPIView(APIView):
    """
    Реальные AI-рекомендации по парковкам.

    Пример:
    GET /api/ai/recommendations/?city=Москва&limit=10
    """

    def get(self, request, *args: Any, **kwargs: Any) -> Response:
        city = request.query_params.get("city")
        limit = int(request.query_params.get("limit", 10))

        qs = ParkingSpot.objects.filter(
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        ).select_related("lot")

        if city:
            qs = qs.filter(lot__city__iexact=city)

        # Сначала берём самые "менее загруженные" и дешёвые места
        qs = qs.order_by("lot__stress_index", "hourly_price")[: limit * 2]

        recommendations: list[dict[str, Any]] = []
        now = timezone.now()

        for spot in qs[:limit]:
            try:
                pricing = recommend_price_for_spot(spot)
            except Exception:
                pricing = None

            rec: dict[str, Any] = {
                "spot_id": str(spot.id),
                "lot_id": str(spot.lot_id),
                "lot_name": spot.lot.name,
                "city": spot.lot.city,
                "address": spot.lot.address,
                "vehicle_type": spot.get_vehicle_type_display(),
                "hourly_price": float(spot.hourly_price or 0),
                "occupancy_7d": float(spot.occupancy_7d or 0.0),
                "stress_index": float(spot.lot.stress_index or 0.0),
                "is_covered": spot.is_covered,
                "has_ev_charging": spot.has_ev_charging,
                "is_24_7": spot.is_24_7,
                "now": now,
            }

            if pricing:
                rec.update(
                    {
                        "ai_recommended_hourly_price": float(
                            pricing.get("recommended_price", 0.0)
                        ),
                        "ai_base_price": float(pricing.get("base_price", 0.0)),
                        "ai_min_price": float(pricing.get("min_price", 0.0)),
                        "ai_max_price": float(pricing.get("max_price", 0.0)),
                        "ai_reason": pricing.get("reason", ""),
                        "ai_discount_percent": float(
                            pricing.get("discount_percent") or 0.0
                        ),
                        "ai_is_discount": bool(pricing.get("is_discount") or False),
                    }
                )

            recommendations.append(rec)

        return Response(
            {
                "count": len(recommendations),
                "results": recommendations,
            },
            status=status.HTTP_200_OK,
        )


class StressIndexAPIView(APIView):
    """
    Реальный индекс загруженности по городам / парковкам.

    Пример:
    GET /api/ai/stress-index/          # общий срез
    GET /api/ai/stress-index/?city=СПб
    """

    def get(self, request, *args: Any, **kwargs: Any) -> Response:
        city = request.query_params.get("city")

        lots_qs = ParkingLot.objects.filter(is_active=True, is_approved=True)
        if city:
            lots_qs = lots_qs.filter(city__iexact=city)

        lots = list(
            lots_qs.values(
                "id",
                "name",
                "city",
                "address",
                "stress_index",
            )
        )

        if not lots:
            return Response(
                {
                    "stress_index": 0.0,
                    "lots": [],
                    "details": "Нет активных парковок для выбранного фильтра",
                },
                status=status.HTTP_200_OK,
            )

        values = [float(l["stress_index"] or 0.0) for l in lots]
        avg = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)

        return Response(
            {
                "stress_index": round(avg, 3),
                "min": round(min_val, 3),
                "max": round(max_val, 3),
                "lots": lots,
            },
            status=status.HTTP_200_OK,
        )


class DepartureAssistantAPIView(APIView):
    """
    Простейший помощник по времени выезда (пока без внешних API).

    Принимает:
    POST /api/ai/departure-assistant/
    {
      "desired_arrival_iso": "2025-11-22T19:00:00+03:00",
      "parking_buffer_minutes": 10,
      "traffic_buffer_minutes": 20
    }
    """

    def post(self, request, *args: Any, **kwargs: Any) -> Response:
        from datetime import timedelta
        from django.utils.dateparse import parse_datetime

        desired_arrival_iso = request.data.get("desired_arrival_iso")
        parking_buffer = int(request.data.get("parking_buffer_minutes", 10))
        traffic_buffer = int(request.data.get("traffic_buffer_minutes", 20))

        if not desired_arrival_iso:
            return Response(
                {
                    "detail": "Нужен параметр desired_arrival_iso в ISO-формате",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        desired_arrival = parse_datetime(desired_arrival_iso)
        if desired_arrival is None:
            return Response(
                {
                    "detail": "Не удалось распарсить desired_arrival_iso",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_buffer = timedelta(
            minutes=parking_buffer + traffic_buffer,
        )
        suggested_departure = desired_arrival - total_buffer

        return Response(
            {
                "suggested_departure_time": suggested_departure,
                "desired_arrival_time": desired_arrival,
                "parking_buffer_minutes": parking_buffer,
                "traffic_buffer_minutes": traffic_buffer,
                "message": "Пока без пробок/погоды, но уже считает буферы времени.",
            },
            status=status.HTTP_200_OK,
        )


class LLMServiceHealthAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            health = async_to_sync(check_llm_health)()
        except Exception as exc:  # pragma: no cover - сеть/IO
            logger.warning("LLM health check failed", exc_info=exc)
            return Response(
                {"ok": False, "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(health, status=status.HTTP_200_OK if health.get("ok") else status.HTTP_503_SERVICE_UNAVAILABLE)


class ChatStreamAPIView(APIView):
    """
    Минимальный чат‑эндпоинт для AI concierge на Django-страницах.
    Принимает список сообщений в формате [{role, content}] и возвращает потоковый текстовый ответ.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data or {}
        messages = data.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return Response({"detail": "messages is required"}, status=status.HTTP_400_BAD_REQUEST)

        last = messages[-1] if isinstance(messages[-1], dict) else {}
        user_text = (last.get("content") or "").strip()
        history = [m for m in messages[:-1] if isinstance(m, dict)]
        reply_text = "Сервис временно недоступен. Попробуйте позже."
        try:
            reply_payload = generate_chat_reply(
                user_text,
                history,
                request.user if request.user.is_authenticated else None,
            )
            reply_text = (reply_payload.get("reply") or reply_text).strip()
        except Exception as exc:  # pragma: no cover - внешние сервисы
            logger.warning("Chat reply failed", exc_info=exc)

        def stream():
            for token in reply_text.split():
                yield (token + " ").encode("utf-8")

        return StreamingHttpResponse(stream(), content_type="text/plain; charset=utf-8")


# ===== ParkMate AI — конфиг и предсказания (price/availability) =====


class ParkMateConfigAPIView(APIView):
    """
    AI‑помощник адаптивности:
    - принимает телеметрию клиента (viewport, pixelRatio, platform);
    - создаёт/обновляет DeviceProfile;
    - записывает UiEvent;
    - возвращает layout_profile / design_mode / theme.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args: Any, **kwargs: Any) -> Response:
        data = request.data or {}
        client = data.get("client") or {}
        action = data.get("action") or "adaptive-profile"

        width = int(client.get("width") or 0)
        height = int(client.get("height") or 0)
        pixel_ratio = float(client.get("pixelRatio") or client.get("pixel_ratio") or 1.0)
        platform = (client.get("platform") or "RU")[:8]
        device_id = (request.COOKIES.get("ps_device_id") or client.get("deviceId") or "anonymous")[:64]
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:1024]

        # Эвристика layout‑профиля
        if width < 640:
            layout = DeviceProfile.LayoutProfile.COMPACT
        elif width < 1024:
            layout = DeviceProfile.LayoutProfile.COMFORTABLE
        else:
            layout = DeviceProfile.LayoutProfile.COMFORTABLE

        design_mode = "pwa" if width < 1024 else "desktop"

        user = request.user if request.user.is_authenticated else None
        profile, _ = DeviceProfile.objects.get_or_create(
            device_id=device_id,
            user=user,
            defaults={
                "viewport_width": width,
                "viewport_height": height,
                "pixel_ratio": pixel_ratio,
                "user_agent": user_agent,
                "layout_profile": layout,
            },
        )

        # Обновляем основные параметры
        profile.viewport_width = width
        profile.viewport_height = height
        profile.pixel_ratio = pixel_ratio
        profile.layout_profile = layout
        profile.save(update_fields=["viewport_width", "viewport_height", "pixel_ratio", "layout_profile", "updated_at"])

        UiEvent.objects.create(
            device_profile=profile,
            event_type=action,
            payload={
                "width": width,
                "height": height,
                "pixel_ratio": pixel_ratio,
                "platform": platform,
            },
        )

        return Response(
            {
                "layout_profile": layout,
                "design_mode": design_mode,
                "theme": profile.theme,
            }
        )

    def get(self, request, *args: Any, **kwargs: Any) -> Response:
        """
        Возвращает фронту конфиг ParkMateAI (контракты/URL‑ы сервисов).
        Формат согласован с static/js/parkmate-ai.ts (ParkMateAI).
        """
        data = {
            "voiceCommands": {
                "booking": "Забронировать парковку рядом",
                "navigation": "Построить маршрут до парковки",
                "payment": "Оплатить текущую парковку",
                "support": "Связаться с поддержкой ParkShare",
            },
            "computerVision": {
                "licensePlateRecognition": "/api/ai/cv/license-plate/",
                "parkingSpotDetection": "/api/ai/cv/parking-occupancy/",
                "damageDetection": "/api/ai/cv/vehicle-damage/",  # зарезервировано
                "occupancyAnalytics": "/api/ai/stress-index/",
            },
            "predictions": {
                "arrivalTime": "/api/ai/departure-assistant/",
                "priceForecast": "/api/ai/parkmate/price-forecast/",
                "availability": "/api/ai/parkmate/availability/",
            },
        }
        return Response(data, status=status.HTTP_200_OK)


# Остальные классы (RecommendationsAPIView, StressIndexAPIView, DepartureAssistantAPIView,
# ParkMatePriceForecastAPIView, ParkMateAvailabilityForecastAPIView) остаются без изменений


class ParkMatePriceForecastAPIView(APIView):
    """
    Эндпоинт ParkMate для прогноза цены по конкретному месту.

    POST /api/ai/parkmate/price-forecast/
    {
      "spot_id": "uuid"
    }
    """

    permission_classes = [AllowAny]

    def post(self, request, *args: Any, **kwargs: Any) -> Response:
        from django.shortcuts import get_object_or_404

        spot_id = request.data.get("spot_id")
        if not spot_id:
            return Response(
                {"detail": "spot_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        spot = get_object_or_404(
            ParkingSpot,
            pk=spot_id,
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        )

        pricing = recommend_price_for_spot(spot)
        if not pricing:
            return Response(
                {"detail": "AI pricing is not available for this spot."},
                status=status.HTTP_404_NOT_FOUND,
            )

        base_price = float(pricing.get("base_price", 0.0))
        recommended_price = float(pricing.get("recommended_price", base_price))
        min_price = float(pricing.get("min_price", recommended_price))
        max_price = float(pricing.get("max_price", recommended_price))
        discount_percent = float(pricing.get("discount_percent") or 0.0)
        is_discount = bool(pricing.get("is_discount") or False)

        data = {
            "spot_id": str(spot.id),
            "lot_id": str(spot.lot_id),
            "currency": "RUB",
            "base_price": base_price,
            "recommended_price": recommended_price,
            "min_price": min_price,
            "max_price": max_price,
            "discount_percent": discount_percent,
            "is_discount": is_discount,
            "reason": pricing.get("reason", ""),
        }
        return Response(data, status=status.HTTP_200_OK)


class ParkMateAvailabilityForecastAPIView(APIView):
    """
    Эндпоинт ParkMate для прогноза доступности места.

    POST /api/ai/parkmate/availability/
    {
      "spot_id": "uuid"        # либо
      "occupancy_7d": 0.4,
      "stress_index": 0.5
    }
    """

    permission_classes = [AllowAny]

    def post(self, request, *args: Any, **kwargs: Any) -> Response:
        from django.shortcuts import get_object_or_404

        spot_id = request.data.get("spot_id")
        occupancy_7d = request.data.get("occupancy_7d")
        stress_index = request.data.get("stress_index")

        spot = None
        if spot_id:
            spot = get_object_or_404(
                ParkingSpot,
                pk=spot_id,
                status=ParkingSpot.SpotStatus.ACTIVE,
                lot__is_active=True,
                lot__is_approved=True,
            )
            occupancy_7d = float(spot.occupancy_7d or 0.0)
            stress_index = float(spot.lot.stress_index or 0.0)
        else:
            try:
                occupancy_7d = float(occupancy_7d or 0.0)
                stress_index = float(stress_index or 0.0)
            except (TypeError, ValueError):
                return Response(
                    {
                        "detail": (
                            "occupancy_7d и stress_index должны быть числами, "
                            "если не передан spot_id."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Нормализация
        occupancy_7d = max(0.0, min(float(occupancy_7d), 1.0))
        stress_index = max(0.0, min(float(stress_index), 1.0))

        # Простая эвристика: чем выше загрузка/стресс, тем ниже вероятность доступности
        base_avail = 1.0 - 0.7 * occupancy_7d - 0.3 * stress_index
        base_avail = max(0.0, min(base_avail, 1.0))

        next_1h = round(base_avail, 3)
        next_3h = round(max(0.0, base_avail - 0.1), 3)
        next_24h = round(max(0.0, base_avail - 0.2), 3)

        now = timezone.now()

        data = {
            "spot_id": str(spot.id) if spot else None,
            "occupancy_7d": occupancy_7d,
            "stress_index": stress_index,
            "as_of": now,
            "availability": {
                "next_1h": next_1h,
                "next_3h": next_3h,
                "next_24h": next_24h,
            },
        }
        return Response(data, status=status.HTTP_200_OK)


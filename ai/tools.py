"""Tool layer for the assistant to operate on parking/search/booking primitives."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.utils import haversine_distance_km
from parking.models import Booking, FavoriteParkingSpot, ParkingSpot

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class ToolError(Exception):
    code: str
    message: str
    details: Optional[dict] = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details or {}}


def _serialize_spot(spot: ParkingSpot, distance_km: float | None = None) -> dict[str, Any]:
    return {
        "id": str(spot.id),
        "name": spot.name,
        "lot": {
            "id": str(spot.lot_id),
            "name": spot.lot.name,
            "city": spot.lot.city,
            "address": spot.lot.address,
            "stress_index": float(spot.lot.stress_index or 0.0),
        },
        "coords": {
            "lat": spot.lot.latitude,
            "lng": spot.lot.longitude,
        },
        "status": spot.status,
        "price": {
            "hourly": float(spot.hourly_price or 0),
            "nightly": float(spot.nightly_price or 0),
            "daily": float(spot.daily_price or 0),
        },
        "features": {
            "ev": spot.has_ev_charging,
            "covered": spot.is_covered,
            "is_24_7": spot.is_24_7,
            "allow_dynamic_pricing": spot.allow_dynamic_pricing,
        },
        "distance_km": distance_km,
        "occupancy_7d": float(spot.occupancy_7d or 0.0),
    }


def search_parking(params: dict[str, Any], user: Optional[User] = None) -> list[dict[str, Any]]:
    qs = (
        ParkingSpot.objects.filter(
            status=ParkingSpot.SpotStatus.ACTIVE,
            lot__is_active=True,
            lot__is_approved=True,
        )
        .select_related("lot")
        .order_by("lot__stress_index", "hourly_price")
    )

    lat = params.get("lat")
    lng = params.get("lng")
    radius_km = params.get("radius_km") or 5
    budget = params.get("max_price") or params.get("budget")

    if params.get("has_ev"):
        qs = qs.filter(has_ev_charging=True)
    if params.get("covered"):
        qs = qs.filter(is_covered=True)
    if params.get("is_24_7"):
        qs = qs.filter(is_24_7=True)
    if budget:
        try:
            qs = qs.filter(hourly_price__lte=float(budget))
        except (TypeError, ValueError):
            pass

    results: list[dict[str, Any]] = []
    for spot in qs[:150]:
        distance = None
        if lat is not None and lng is not None and spot.lot.latitude and spot.lot.longitude:
            distance = haversine_distance_km(lat, lng, spot.lot.latitude, spot.lot.longitude)
            if distance is not None and distance > float(radius_km):
                continue
        results.append(_serialize_spot(spot, distance))
    return results[:50]


def get_availability(spot_id: str, time_range: dict[str, Any]) -> dict[str, Any]:
    spot = get_object_or_404(
        ParkingSpot,
        pk=spot_id,
        status=ParkingSpot.SpotStatus.ACTIVE,
        lot__is_active=True,
        lot__is_approved=True,
    )
    start_iso = time_range.get("start_at")
    end_iso = time_range.get("end_at")
    start_at = parse_datetime(start_iso) if start_iso else timezone.now()
    end_at = parse_datetime(end_iso) if end_iso else start_at + timedelta(hours=1)
    if start_at and timezone.is_naive(start_at):
        start_at = timezone.make_aware(start_at)
    if end_at and timezone.is_naive(end_at):
        end_at = timezone.make_aware(end_at)

    is_free = Booking.is_spot_available(spot, start_at, end_at)
    return {
        "spot": _serialize_spot(spot),
        "available": is_free,
        "start_at": start_at,
        "end_at": end_at,
        "occupancy_7d": float(spot.occupancy_7d or 0.0),
        "stress_index": float(spot.lot.stress_index or 0.0),
    }


def create_booking(
    user: User,
    spot_id: str,
    time_range: dict[str, Any],
    vehicle_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    flags: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if not user or not user.is_authenticated:
        raise ToolError("auth_required", "Нужно войти, чтобы бронировать.")

    spot = get_object_or_404(
        ParkingSpot,
        pk=spot_id,
        status=ParkingSpot.SpotStatus.ACTIVE,
        lot__is_active=True,
        lot__is_approved=True,
    )

    start_iso = time_range.get("start_at")
    end_iso = time_range.get("end_at")
    duration_hours = time_range.get("hours") or 1
    booking_type = time_range.get("booking_type") or Booking.BookingType.HOURLY

    start_at = parse_datetime(start_iso) if start_iso else timezone.now()
    if start_at and timezone.is_naive(start_at):
        start_at = timezone.make_aware(start_at)
    if end_iso:
        end_at = parse_datetime(end_iso)
    else:
        end_at = start_at + timedelta(hours=duration_hours)
    if end_at and timezone.is_naive(end_at):
        end_at = timezone.make_aware(end_at)

    if not Booking.is_spot_available(spot, start_at, end_at):
        raise ToolError("not_available", "Место занято в выбранный промежуток.")

    with transaction.atomic():
        booking = Booking.objects.create(
            user=user,
            spot=spot,
            vehicle_id=vehicle_id,
            booking_type=booking_type,
            start_at=start_at,
            end_at=end_at,
            status=Booking.Status.PENDING,
            total_price=0,
        )
        booking.calculate_price()
        if flags and flags.get("business_trip"):
            booking.ai_snapshot = {"business_trip": True}
        booking.status = Booking.Status.CONFIRMED if payment_method else Booking.Status.PENDING
        booking.save(update_fields=["total_price", "status", "ai_snapshot"])

    return {
        "booking_id": booking.id,
        "status": booking.status,
        "total_price": float(booking.total_price),
        "currency": booking.currency,
        "start_at": booking.start_at,
        "end_at": booking.end_at,
        "spot": _serialize_spot(spot),
    }


def extend_booking(user: User, booking_id: str, time_delta_minutes: int) -> dict[str, Any]:
    if not user or not user.is_authenticated:
        raise ToolError("auth_required", "Нужно войти, чтобы продлить бронь.")
    booking = get_object_or_404(Booking, pk=booking_id, user=user)
    if booking.has_ended:
        raise ToolError("already_finished", "Эту бронь уже нельзя продлить.")

    new_end = booking.end_at + timedelta(minutes=time_delta_minutes or 30)
    if not Booking.is_spot_available(booking.spot, booking.start_at, new_end, exclude_booking_id=booking.id):
        raise ToolError("not_available", "Перекрывается с другой бронью.")
    booking.end_at = new_end
    booking.calculate_price()
    booking.status = Booking.Status.CONFIRMED
    booking.save(update_fields=["end_at", "total_price", "status"])
    return {
        "booking_id": booking.id,
        "status": booking.status,
        "total_price": float(booking.total_price),
        "end_at": booking.end_at,
    }


def cancel_booking(user: User, booking_id: str) -> dict[str, Any]:
    if not user or not user.is_authenticated:
        raise ToolError("auth_required", "Нужно войти, чтобы отменять бронь.")
    booking = get_object_or_404(Booking, pk=booking_id, user=user)
    if booking.has_started:
        raise ToolError("already_started", "Нельзя отменить уже начавшуюся бронь.")
    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    return {"booking_id": booking.id, "status": booking.status}


def toggle_favorite(user: User, spot_id: str) -> dict[str, Any]:
    if not user or not user.is_authenticated:
        raise ToolError("auth_required", "Войдите, чтобы сохранять избранное.")
    spot = get_object_or_404(ParkingSpot, pk=spot_id)
    fav, created = FavoriteParkingSpot.objects.get_or_create(user=user, spot=spot)
    if not created:
        fav.delete()
    return {"spot_id": str(spot.id), "favorite": created}

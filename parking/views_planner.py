from __future__ import annotations

from typing import Any, List

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import haversine_distance_km
from .models import PlannerProfile, PlannerRun, ParkingSpot
from .serializers import PlannerPlanRequestSerializer, PlannerProfileSerializer


class PlannerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PlannerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PlannerProfile.objects.filter(user=self.request.user).order_by("-updated_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class PlannerPlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PlannerPlanRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        user = request.user

        profile = None
        profile_id = payload.get("profile_id")
        if profile_id:
            profile = PlannerProfile.objects.filter(id=profile_id, user=user).first()
            if profile:
                profile.last_used_at = timezone.now()
                profile.save(update_fields=["last_used_at", "updated_at"])

        # Простая эвристика: выбираем ближайшие споты и считаем "уверенность" как 1 - occupancy_7d
        spots_qs = (
            ParkingSpot.objects.filter(
                status=ParkingSpot.SpotStatus.ACTIVE,
                lot__is_active=True,
                lot__is_approved=True,
            )
            .select_related("lot")
            .order_by("-has_ev_charging", "-is_covered")
        )
        if payload.get("requires_ev_charging"):
            spots_qs = spots_qs.filter(has_ev_charging=True)
        if payload.get("requires_covered"):
            spots_qs = spots_qs.filter(is_covered=True)

        destination_lat = payload["destination_lat"]
        destination_lon = payload["destination_lon"]
        recommendations: List[dict[str, Any]] = []
        for spot in spots_qs[:20]:
            lot = spot.lot
            if lot.latitude is None or lot.longitude is None:
                continue
            distance_km = haversine_distance_km(destination_lat, destination_lon, lot.latitude, lot.longitude)
            recommendations.append(
                {
                    "spot_id": str(spot.id),
                    "lot_id": str(lot.id),
                    "lot_name": lot.name,
                    "address": lot.address,
                    "distance_km": round(float(distance_km), 2),
                    "hourly_price": float(spot.hourly_price),
                    "has_ev_charging": spot.has_ev_charging,
                    "is_covered": spot.is_covered,
                    "predicted_occupancy": float(spot.occupancy_7d or 0.0),
                    "confidence": round(1 - float(spot.occupancy_7d or 0.0), 2),
                }
            )
            if len(recommendations) >= 6:
                break

        run = PlannerRun.objects.create(
            user=user,
            profile=profile,
            arrival_at=payload.get("arrival_at"),
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            response={"count": len(recommendations)},
        )
        return Response(
            {
                "run_id": run.id,
                "profile_id": profile.id if profile else None,
                "recommendations": recommendations,
            },
            status=status.HTTP_200_OK,
        )


class PlannerPageView(LoginRequiredMixin, TemplateView):
    """Простая оболочка UI планировщика."""

    template_name = "parking/planner.html"

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        ctx["planner_bootstrap"] = {
            "profiles_endpoint": "/api/planner/profiles/",
            "plan_endpoint": "/api/planner/plan/",
        }
        return ctx

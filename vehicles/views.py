# vehicles/views.py

from rest_framework import permissions, viewsets

from core.permissions import IsOwnerObject
from .models import Vehicle
from .serializers import VehicleSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    """
    API для машин пользователя.

    - /api/vehicles/              (GET)   — список машин текущего пользователя
    - /api/vehicles/              (POST)  — создать машину (номер хэшируется)
    - /api/vehicles/{id}/         (GET)   — детали (только владелец)
    - /api/vehicles/{id}/         (PATCH/PUT/DELETE) — управление машиной (только владелец)
    """

    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerObject]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Vehicle.objects.none()
        return Vehicle.objects.filter(owner=user).order_by("-created_at")

    def perform_create(self, serializer: VehicleSerializer) -> None:
        # owner устанавливается в serializer.create()
        serializer.save()

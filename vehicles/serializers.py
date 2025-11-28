# vehicles/serializers.py

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from core.utils import hash_plate_digits
from .models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    """
    Сериализатор для машин.

    Вход:
    - plate_number (write_only) — строка номера, хэшируется на сервере;
    - label, vehicle_type.

    Выход:
    - id, label, vehicle_type, created_at.
    """

    plate_number = serializers.CharField(
        write_only=True,
        label=_("Госномер"),
        help_text=_(
            "Фактический номер будет преобразован в хэш и не будет храниться в открытом виде."
        ),
    )

    class Meta:
        model = Vehicle
        fields = ("id", "label", "vehicle_type", "plate_number", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_plate_number(self, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            raise serializers.ValidationError(
                _("Нужно указать хотя бы одну цифру номера.")
            )
        return value

    def create(self, validated_data: dict) -> Vehicle:
        request = self.context["request"]
        user = request.user
        plate_number = validated_data.pop("plate_number")
        plate_hash = hash_plate_digits(plate_number)
        if Vehicle.objects.filter(owner=user, plate_hash=plate_hash).exists():
            raise serializers.ValidationError(
                {
                    "plate_number": _(
                        "Машина с таким номером уже добавлена в ваш список."
                    )
                }
            )
        vehicle = Vehicle.objects.create(
            owner=user,
            plate_hash=plate_hash,
            **validated_data,
        )
        return vehicle

    def update(self, instance: Vehicle, validated_data: dict) -> Vehicle:
        # Номер менять нельзя (потребует создания нового объекта),
        # поэтому игнорируем plate_number при обновлении.
        validated_data.pop("plate_number", None)
        return super().update(instance, validated_data)

# parking/management/commands/seed_demo_parking.py

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from parking.models import ParkingLot, ParkingSpot


class Command(BaseCommand):
    help = "Создаёт демо-объект парковки и несколько мест для локальной разработки."

    def handle(self, *args, **options):
        User = get_user_model()

        # ---------- 1. Владелец парковки ----------
        role_cls = getattr(User, "Role", None)
        owner_role_value = getattr(role_cls, "OWNER", None) if role_cls else None

        owner_defaults = {
            "email": "demo-owner@example.com",
            "is_active": True,
        }
        if owner_role_value is not None:
            owner_defaults["role"] = owner_role_value

        owner, created_owner = User.objects.get_or_create(
            username="demo_owner",
            defaults=owner_defaults,
        )

        if created_owner:
            owner.set_password("demo_owner")
            owner.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(
                    "Создан пользователь-владелец demo_owner / пароль: demo_owner"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Найден владелец demo_owner (id={owner.pk})")
            )

        # ---------- 2. Объект парковки ----------
        with transaction.atomic():
            lot, created_lot = ParkingLot.objects.get_or_create(
                name="Демо-парковка ParkShare",
                city="Москва",
                address="ул. Примерная, д. 1",
                defaults={
                    "owner": owner,
                    "parking_type": "yard",  # см. choices в миграции
                    "latitude": 55.751244,
                    "longitude": 37.618423,
                    "is_active": True,
                    "is_approved": True,
                    "is_private": False,
                },
            )

            if not created_lot:
                # На всякий случай привязываем к нашему демо-владельцу
                if lot.owner_id != owner.id:
                    lot.owner = owner
                    lot.save(update_fields=["owner"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Используем существующую парковку (id={lot.pk})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Создана демо-парковка (id={lot.pk}) в Москве"
                    )
                )

            # ---------- 3. Парковочные места ----------
            spots_spec = [
                {
                    "name": "Место 1 — EV 24/7",
                    "description": "Рядом с въездом, есть зарядка для EV.",
                    "is_covered": False,
                    "has_ev_charging": True,
                    "is_24_7": True,
                    "hourly_price": Decimal("120.00"),
                    "allow_dynamic_pricing": True,
                    "occupancy_7d": 0.65,
                },
                {
                    "name": "Место 2 — крытое",
                    "description": "Крытое место на -1 этаже.",
                    "is_covered": True,
                    "has_ev_charging": False,
                    "is_24_7": True,
                    "hourly_price": Decimal("90.00"),
                    "allow_dynamic_pricing": False,
                    "occupancy_7d": 0.40,
                },
                {
                    "name": "Место 3 — бюджетное",
                    "description": "Самое дешёвое, но чуть дальше от выезда.",
                    "is_covered": False,
                    "has_ev_charging": False,
                    "is_24_7": True,
                    "hourly_price": Decimal("70.00"),
                    "allow_dynamic_pricing": True,
                    "occupancy_7d": 0.80,
                },
                {
                    "name": "Место 4 — премиум",
                    "description": "Широкое место, удобно для кроссоверов.",
                    "is_covered": True,
                    "has_ev_charging": True,
                    "is_24_7": True,
                    "hourly_price": Decimal("150.00"),
                    "allow_dynamic_pricing": True,
                    "occupancy_7d": 0.55,
                },
            ]

            created_count = 0
            for spec in spots_spec:
                spot, created_spot = ParkingSpot.objects.get_or_create(
                    lot=lot,
                    name=spec["name"],
                    defaults=spec,
                )
                if created_spot:
                    created_count += 1

            total_spots = ParkingSpot.objects.filter(lot=lot).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Готово: мест в демо-парковке сейчас {total_spots} "
                    f"(создано за этот запуск {created_count})."
                )
            )

        self.stdout.write(self.style.SUCCESS("seed_demo_parking: демо-данные готовы."))

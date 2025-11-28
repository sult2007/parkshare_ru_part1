from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from parking.models import Booking, ParkingLot, ParkingSpot


class BookingModelTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="owner",
            password="StrongPass123",
            role=User.Role.OWNER,
        )
        self.driver = User.objects.create_user(
            username="driver",
            password="StrongPass123",
            role=User.Role.DRIVER,
        )

        self.lot = ParkingLot.objects.create(
            owner=self.owner,
            name="Test Lot",
            city="Test City",
            address="Test street, 1",
        )
        self.spot = ParkingSpot.objects.create(
            lot=self.lot,
            name="A1",
            hourly_price=Decimal("100.00"),
        )

    def test_calculate_price_hourly_with_commission(self):
        now = timezone.now()
        booking = Booking(
            user=self.driver,
            spot=self.spot,
            booking_type=Booking.BookingType.HOURLY,
            start_at=now,
            end_at=now + timedelta(hours=1, minutes=30),
            total_price=Decimal("0.00"),
            currency="RUB",
        )
        total = booking.calculate_price()
        # 2 часа * 100 ₽ + 10% комиссии = 220
        self.assertEqual(total, Decimal("220.00"))

    def test_is_spot_available(self):
        now = timezone.now()
        existing = Booking.objects.create(
            user=self.driver,
            spot=self.spot,
            booking_type=Booking.BookingType.HOURLY,
            start_at=now,
            end_at=now + timedelta(hours=2),
            status=Booking.Status.CONFIRMED,
            total_price=Decimal("200.00"),
            currency="RUB",
        )

        # Пересекающийся интервал — недоступен
        self.assertFalse(
            Booking.is_spot_available(
                self.spot,
                now + timedelta(minutes=30),
                now + timedelta(hours=3),
            )
        )

        # Непересекающийся интервал — доступен
        self.assertTrue(
            Booking.is_spot_available(
                self.spot,
                existing.end_at + timedelta(minutes=1),
                existing.end_at + timedelta(hours=1),
            )
        )

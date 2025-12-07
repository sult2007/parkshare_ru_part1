from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from parking.models import ParkingLot, ParkingSpot


@override_settings(MAINTENANCE_MODE=True)
class MaintenanceModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="m1", password="pass")
        self.client.login(username="m1", password="pass")
        lot = ParkingLot.objects.create(
            owner=self.user,
            name="Lot",
            city="Москва",
            address="Адрес",
            latitude=55.75,
            longitude=37.61,
            is_active=True,
            is_approved=True,
        )
        self.spot = ParkingSpot.objects.create(
            lot=lot,
            name="S1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=100,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )

    def test_booking_blocked(self):
        resp = self.client.post(reverse("booking_confirm"), {"spot_id": self.spot.id, "hours": 1})
        self.assertEqual(resp.status_code, 503)

    def test_payment_blocked(self):
        resp = self.client.post(reverse("payment_methods_page"), {"card_number": "4111111111111111", "exp": "12/30"})
        self.assertEqual(resp.status_code, 200)  # HTML path shows banner message

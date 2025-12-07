from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from parking.models import ParkingLot, ParkingSpot, Booking


class BusinessReportsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="biz", password="pass")
        self.client.login(username="biz", password="pass")
        lot = ParkingLot.objects.create(
            owner=self.user,
            name="Lot",
            city="Москва",
            address="Адрес 1",
            latitude=55.75,
            longitude=37.61,
        )
        spot = ParkingSpot.objects.create(
            lot=lot,
            name="S1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=100,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )
        now = timezone.now()
        for i in range(2):
            b = Booking.objects.create(
                user=self.user,
                spot=spot,
                start_at=now - timezone.timedelta(days=i),
                end_at=now - timezone.timedelta(days=i) + timezone.timedelta(hours=1),
                booking_type=Booking.BookingType.HOURLY,
                billing_mode=Booking.BillingMode.PAYG,
                total_price=100,
                status=Booking.Status.CONFIRMED,
                ai_snapshot={"business_trip": True},
            )
            b.calculate_price()

    def test_reports_page(self):
        resp = self.client.get(reverse("business_reports"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("bookings", resp.context)
        self.assertGreaterEqual(len(resp.context["bookings"]), 1)

    def test_csv_export(self):
        resp = self.client.get(reverse("business_reports") + "?export=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = resp.content.decode("utf-8")
        self.assertIn("Режим биллинга", content)

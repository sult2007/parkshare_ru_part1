from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from ai.models import DeviceProfile, UiEvent, ChatSession
from parking.models import ParkingLot, ParkingSpot, Booking
from parking import analytics


class AnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="pass")
        self.profile = DeviceProfile.objects.create(user=self.user, device_id="devana")
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

    def test_compute_funnel_counts(self):
        UiEvent.objects.create(device_profile=self.profile, event_type="map_open")
        UiEvent.objects.create(device_profile=self.profile, event_type="spot_select")
        UiEvent.objects.create(device_profile=self.profile, event_type="booking_confirm_open")
        Booking.objects.create(
            user=self.user,
            spot=self.spot,
            start_at=timezone.now(),
            end_at=timezone.now() + timezone.timedelta(hours=1),
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PAYG,
            total_price=100,
            status=Booking.Status.CONFIRMED,
        )
        ChatSession.objects.create(user=self.user)
        data = analytics.compute_funnel(7)
        self.assertGreaterEqual(data["funnel"]["map_open"], 1)
        self.assertGreaterEqual(data["funnel"]["booking_created"], 1)
        self.assertGreaterEqual(data["assistant_sessions"], 1)

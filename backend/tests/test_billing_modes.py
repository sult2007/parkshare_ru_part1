from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from parking.models import ParkingLot, ParkingSpot, Booking


class BillingModesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass")
        self.lot = ParkingLot.objects.create(
            owner=self.user,
            name="Test Lot",
            city="Москва",
            address="Тестовая 1",
            latitude=55.75,
            longitude=37.61,
            is_approved=True,
            is_active=True,
        )
        self.spot = ParkingSpot.objects.create(
            lot=self.lot,
            name="A1",
            vehicle_type=ParkingSpot.VehicleType.CAR,
            hourly_price=100,
            status=ParkingSpot.SpotStatus.ACTIVE,
        )

    def test_payg_price(self):
        start = timezone.now()
        end = start + timezone.timedelta(hours=1)
        booking = Booking(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PAYG,
            total_price=0,
        )
        price = booking.calculate_price()
        self.assertEqual(float(price), 100.0)

    def test_payg_rounds_15_minutes(self):
        start = timezone.now()
        end = start + timezone.timedelta(minutes=20)
        booking = Booking(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PAYG,
            total_price=0,
        )
        price = booking.calculate_price()
        # 20 минут -> 0.5 часа
        self.assertEqual(float(price), 50.0)

    def test_prepaid_block_price_rounds_up(self):
        start = timezone.now()
        end = start + timezone.timedelta(hours=1)
        booking = Booking(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PREPAID_BLOCK,
            total_price=0,
        )
        # emulate block of 2 hours
        booking.end_at = start + timezone.timedelta(hours=2)
        price = booking.calculate_price()
        self.assertEqual(float(price), 200.0)

    def test_prepaid_block_to_four_hours(self):
        start = timezone.now()
        end = start + timezone.timedelta(hours=3, minutes=10)
        booking = Booking(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PREPAID_BLOCK,
            total_price=0,
        )
        price = booking.calculate_price()
        self.assertEqual(float(price), 400.0)

from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from parking.models import ParkingLot, ParkingSpot, Booking, PushSubscription
from parking.models_notification import NotificationSettings
from parking.notifications import bookings_expiring_within


class NotificationSchedulingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notif2", password="pass")
        NotificationSettings.objects.create(user=self.user)
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
        PushSubscription.objects.create(user=self.user, endpoint="e1", p256dh="p", auth="a")

    def test_booking_expiring_detected(self):
        start = timezone.now()
        end = start + timezone.timedelta(minutes=10)
        Booking.objects.create(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PAYG,
            total_price=100,
            status=Booking.Status.CONFIRMED,
        )
        eligible = bookings_expiring_within(15)
        self.assertEqual(len(eligible), 1)

    def test_disabled_notifications_not_selected(self):
        start = timezone.now()
        end = start + timezone.timedelta(minutes=10)
        Booking.objects.create(
            user=self.user,
            spot=self.spot,
            start_at=start,
            end_at=end,
            booking_type=Booking.BookingType.HOURLY,
            billing_mode=Booking.BillingMode.PAYG,
            total_price=100,
            status=Booking.Status.CONFIRMED,
        )
        self.user.notification_settings.notify_booking_expiry = False
        self.user.notification_settings.save()
        eligible = bookings_expiring_within(15)
        self.assertEqual(len(eligible), 0)

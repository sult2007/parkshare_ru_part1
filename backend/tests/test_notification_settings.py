from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from parking.models_notification import NotificationSettings


class NotificationSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notif", password="pass")
        self.client.login(username="notif", password="pass")

    def test_toggle_settings(self):
        resp = self.client.post(
            reverse("profile_settings"),
            {"notify_booking_expiry": "on", "notify_night_restrictions": "on"},
        )
        self.assertEqual(resp.status_code, 200)
        ns = NotificationSettings.objects.get(user=self.user)
        self.assertTrue(ns.notify_booking_expiry)
        self.assertTrue(ns.notify_night_restrictions)

from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from ai.models import DeviceProfile, UiEvent


class PreferencesViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="prefs", password="pass")
        self.client.login(username="prefs", password="pass")
        self.profile = DeviceProfile.objects.create(user=self.user, device_id="dev1")
        UiEvent.objects.create(device_profile=self.profile, event_type="preferences", payload={"prefers_ev": True})

    def test_get_shows_preferences(self):
        resp = self.client.get(reverse("profile_settings"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("preferences", resp.context)

    def test_reset_preferences(self):
        resp = self.client.post(reverse("profile_settings"), {"reset_prefs": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(UiEvent.objects.filter(device_profile=self.profile, event_type="preferences").count(), 0)

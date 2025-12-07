from django.test import TestCase
from django.urls import reverse
from accounts.models import User


class AccessControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")

    def test_metrics_requires_staff(self):
        self.client.login(username="user", password="pass")
        resp = self.client.get(reverse("metrics_dashboard"))
        self.assertEqual(resp.status_code, 302)

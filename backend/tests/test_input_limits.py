from django.test import TestCase
from django.urls import reverse
from accounts.models import User


class InputLimitsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="limit", password="pass")
        self.client.login(username="limit", password="pass")

    def test_promo_length_limit(self):
        code = "X" * 200
        resp = self.client.post(reverse("promo_activate"), {"code": code}, HTTP_ACCEPT="application/json")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["code"], "invalid_promo")

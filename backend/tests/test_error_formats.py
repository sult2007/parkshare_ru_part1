from django.test import TestCase
from django.urls import reverse
from accounts.models import User


class ErrorFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="err", password="pass")
        self.client.login(username="err", password="pass")

    def test_payment_invalid_card_error_shape(self):
        resp = self.client.post(
            reverse("payment_methods_page"),
            {"card_number": "123", "exp": "12/30"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("code", data)
        self.assertIn("message", data)

    def test_promo_invalid_error_shape(self):
        resp = self.client.post(reverse("promo_activate"), {"code": "NOPE"}, HTTP_ACCEPT="application/json")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["code"], "invalid_promo")

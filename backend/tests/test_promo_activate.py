from django.test import TestCase
from django.urls import reverse
from accounts.models import User, PromoReward


class PromoActivateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="promo", password="pass")
        self.client.login(username="promo", password="pass")
        self.reward = PromoReward.objects.create(code="PROMO1", description="Бонус")

    def test_activate_valid(self):
        resp = self.client.post(reverse("promo_activate"), {"code": "PROMO1"}, HTTP_ACCEPT="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, {"message": "Промокод применён: Бонус"})

    def test_activate_invalid(self):
        resp = self.client.post(reverse("promo_activate"), {"code": "BAD"}, HTTP_ACCEPT="application/json")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["code"], "invalid_promo")
        self.assertIn("Промокод недействителен", data["message"])

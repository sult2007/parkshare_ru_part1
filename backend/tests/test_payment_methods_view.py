from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from payments.models import PaymentMethod


class PaymentMethodsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pay", password="pass")
        self.client.login(username="pay", password="pass")

    def test_get_methods_page(self):
        resp = self.client.get(reverse("payment_methods_page"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("methods", resp.context)

    def test_add_and_delete_method(self):
        resp = self.client.post(
            reverse("payment_methods_page"),
            {"card_number": "4111111111111111", "exp": "12/30", "label": "Test"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PaymentMethod.objects.filter(user=self.user).count(), 1)
        pm = PaymentMethod.objects.get(user=self.user)
        resp_del = self.client.post(reverse("payment_methods_page"), {"delete_id": pm.id})
        self.assertEqual(resp_del.status_code, 200)
        self.assertEqual(PaymentMethod.objects.filter(user=self.user).count(), 0)

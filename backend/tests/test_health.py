from django.test import TestCase
from django.urls import reverse


class HealthChecksTests(TestCase):
    def test_healthz(self):
        resp = self.client.get(reverse("healthz"))
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, {"status": "ok"})

    def test_readyz(self):
        resp = self.client.get(reverse("readyz"))
        self.assertEqual(resp.status_code, 200)

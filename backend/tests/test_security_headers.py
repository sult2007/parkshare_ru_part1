from django.test import TestCase
from django.urls import reverse


class SecurityHeadersTests(TestCase):
    def test_headers_present(self):
        resp = self.client.get(reverse("landing"))
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("Referrer-Policy", resp.headers)

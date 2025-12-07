from django.test import TestCase
from django.urls import reverse
from django.template.loader import render_to_string


class OfflineOnboardingTests(TestCase):
    def test_offline_template_renders(self):
        resp = self.client.get(reverse("offline"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Оффлайн-режим")

    def test_base_has_onboarding_markup(self):
        html = render_to_string("base.html")
        self.assertIn("data-onboarding", html)

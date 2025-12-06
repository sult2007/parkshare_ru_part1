from django.test import Client, TestCase
from django.urls import reverse


class UIThemeTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_has_theme_toggle(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-theme-toggle")

    def test_map_page_renders(self):
        response = self.client.get(reverse("map_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-map-panel")


class ChatAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_chat_api_requires_messages(self):
        response = self.client.post("/api/chat/", data={}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_chat_api_returns_text(self):
        payload = {"messages": [{"role": "user", "content": "Привет"}]}
        response = self.client.post("/api/chat/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("Content-Type", ""))

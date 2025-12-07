from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class UIThemeTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_has_theme_toggle(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ParkShare")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "data-search-bar")
        self.assertContains(response, "data-map-panel")
        self.assertContains(response, "data-spots-list")
        self.assertContains(response, "Рекомендации")
        self.assertContains(response, 'data-nav="assistant"')
        self.assertContains(response, "data-geocode-input")

    def test_map_page_renders(self):
        response = self.client.get(reverse("map_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-map-panel")

    def test_assistant_page_renders(self):
        response = self.client.get(reverse("ai_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-ai-chat")
        self.assertContains(response, "ps-ai-prompts")
        self.assertContains(response, "data-ai-send")

    def test_bookings_page_for_user(self):
        User = get_user_model()
        user = User.objects.create_user(username="demo", password="pass")
        self.client.login(username="demo", password="pass")
        response = self.client.get(reverse("user_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-route=\"bookings\"")
        self.assertContains(response, "Мои бронирования")

    def test_owner_page_for_owner_role(self):
        User = get_user_model()
        owner = User.objects.create_user(username="owner", password="pass", role=User.Role.OWNER)
        self.client.login(username="owner", password="pass")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-route=\"parking\"")


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

    def test_chat_api_rejects_wrong_type(self):
        payload = {"messages": "not-a-list"}
        response = self.client.post("/api/chat/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

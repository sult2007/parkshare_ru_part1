from django.test import TestCase
from rest_framework.test import APIClient


class AuthApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.password = "StrongPass123"

    def test_register_and_login_by_username_email_and_phone(self):
        # Регистрация
        resp = self.client.post(
            "/api/accounts/users/register/",
            {
                "username": "demo",
                "password": self.password,
                "email": "demo@example.com",
                "phone": "+7 (999) 123-45-67",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.client.logout()

        # Логин по логину
        resp = self.client.post(
            "/api/accounts/users/login/",
            {"identifier": "demo", "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["username"], "demo")
        self.client.logout()

        # Логин по email
        resp = self.client.post(
            "/api/accounts/users/login/",
            {"identifier": "demo@example.com", "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.client.logout()

        # Логин по телефону (в любом удобном формате)
        resp = self.client.post(
            "/api/accounts/users/login/",
            {"identifier": "+7 999 123-45-67", "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

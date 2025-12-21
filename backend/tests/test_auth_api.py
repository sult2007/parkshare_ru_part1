from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthIdentity, LoginCode, User
from accounts.utils import hash_code


class AuthApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.password = "StrongPass123"
        self.user = User.objects.create_user(username="otp_user", password=self.password)

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

    def test_otp_login_links_auth_identity(self):
        self.user.email_plain = "otp@example.com"
        self.user.save()
        LoginCode.objects.create(
            user=self.user,
            channel=LoginCode.Channel.EMAIL,
            purpose=LoginCode.Purpose.LOGIN,
            code_hash=hash_code("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        resp = self.client.post(
            "/auth/otp/verify/",
            {"identifier": "otp@example.com", "code": "123456", "purpose": LoginCode.Purpose.LOGIN},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        identity = AuthIdentity.objects.get(provider=AuthIdentity.Provider.EMAIL_MAGIC)
        self.assertEqual(identity.user, self.user)
        self.assertEqual(identity.provider_user_id, "otp@example.com")

    @override_settings(
        SOCIAL_OAUTH_CONFIG={
            "google": {
                "client_id": "stub",
                "client_secret": "stub",
            }
        },
        SOCIAL_OAUTH_TEST_MODE=True,
    )
    def test_oauth_callback_creates_identity_in_test_mode(self):
        session = self.client.session
        session["oauth_state_google"] = "state123"
        session.save()

        resp = self.client.get(
            "/auth/oauth/google/callback/",
            {"state": "state123", "code": "test_demo"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        identity = AuthIdentity.objects.get(provider=AuthIdentity.Provider.GOOGLE)
        self.assertEqual(identity.provider_user_id, "demo")

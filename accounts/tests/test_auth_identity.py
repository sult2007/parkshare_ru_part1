from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthIdentity, LoginCode, User
from accounts.utils import hash_code


class AuthIdentityFlowsTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_email_otp_verification_creates_identity(self):
        user = User.objects.create_user(username="otp-email-user")
        user.email_plain = "otp@example.com"
        user.save()

        LoginCode.objects.create(
            user=user,
            channel=LoginCode.Channel.EMAIL,
            purpose=LoginCode.Purpose.LOGIN,
            code_hash=hash_code("123456"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        resp = self.client.post(
            reverse("auth_otp_verify"),
            {"identifier": "otp@example.com", "code": "123456", "purpose": LoginCode.Purpose.LOGIN},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        identity = AuthIdentity.objects.get(provider=AuthIdentity.Provider.EMAIL_MAGIC)
        self.assertEqual(identity.user, user)
        self.assertEqual(identity.provider_user_id, "otp@example.com")

    @override_settings(
        SOCIAL_OAUTH_CONFIG={
            "vk": {"client_id": "demo", "client_secret": "demo"},
            "yandex": {"client_id": "demo", "client_secret": "demo"},
            "google": {"client_id": "demo", "client_secret": "demo"},
        },
        SOCIAL_OAUTH_TEST_MODE=True,
    )
    def test_oauth_callback_links_auth_identity(self):
        session = self.client.session
        session["oauth_state_vk"] = "state123"
        session.save()

        resp = self.client.get(
            reverse("oauth_callback", args=["vk"]),
            {"state": "state123", "code": "test_vkuser"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        identity = AuthIdentity.objects.get(provider=AuthIdentity.Provider.VK)
        self.assertEqual(identity.provider_user_id, "vkuser")
        self.assertTrue(identity.user.email_plain.endswith("@vk.example"))

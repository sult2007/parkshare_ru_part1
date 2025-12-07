from __future__ import annotations

from datetime import timedelta

import pyotp
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from accounts.authentication import JWTAuthentication
from accounts.models import SocialAccount, User


class MFATestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.password = "StrongPass123"

    def _create_totp_user(self) -> tuple[User, str]:
        secret = pyotp.random_base32()
        user = User.objects.create_user(username="mfa_user", password=self.password)
        user.mfa_enabled = True
        user.mfa_method = User.MFAMethod.TOTP
        user.mfa_secret = secret
        user.save()
        return user, secret

    def test_totp_mfa_flow(self):
        user, secret = self._create_totp_user()

        resp = self.client.post(
            "/api/accounts/users/login/",
            {"identifier": user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("mfa_required"))

        code = pyotp.TOTP(secret).now()
        resp = self.client.post("/api/auth/mfa/verify/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["user"]["id"], str(user.pk))

    def test_totp_mfa_rejects_wrong_code(self):
        user, _ = self._create_totp_user()
        self.client.post(
            "/api/accounts/users/login/",
            {"identifier": user.username, "password": self.password},
            format="json",
        )
        resp = self.client.post(
            "/api/auth/mfa/verify/", {"code": "000000"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(SOCIAL_OAUTH_TEST_MODE=True)
    def test_oauth_callback_with_mfa_redirects(self):
        user, secret = self._create_totp_user()
        social = SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.VK,
            external_id="demo",
        )
        social.save()
        session = self.client.session
        session["oauth_state_vk"] = "abc"
        session.save()

        resp = self.client.get("/auth/oauth/vk/callback/?state=abc&code=test_demo")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/mfa/verify", resp["Location"])
        session = self.client.session
        self.assertEqual(session.get("pre_auth_user_id"), str(user.pk))

        code = pyotp.TOTP(secret).now()
        resp = self.client.post("/auth/mfa/verify/", {"code": code})
        self.assertIn(resp.status_code, (200, 302))

    def test_jwt_rejected_after_password_change(self):
        user = User.objects.create_user(username="jwt_user", password=self.password)
        user.last_password_change = timezone.now()
        user.save(update_fields=["last_password_change"])

        stale_token = {
            "user_id": str(user.id),
            "iat": int((timezone.now() - timedelta(days=1)).timestamp()),
        }
        auth = JWTAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.get_user(stale_token)

    def test_other_sessions_invalidated_on_password_change(self):
        user = User.objects.create_user(username="multi", password=self.password)

        client_a = APIClient()
        client_b = APIClient()
        for c in (client_a, client_b):
            resp = c.post(
                "/api/accounts/users/login/",
                {"identifier": user.username, "password": self.password},
                format="json",
            )
            self.assertEqual(resp.status_code, 200)

        resp = client_a.post(
            "/api/accounts/users/change-password/",
            {"old_password": self.password, "new_password": "NewPass123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        resp_after = client_b.get("/api/accounts/users/me/")
        self.assertEqual(resp_after.status_code, 403)

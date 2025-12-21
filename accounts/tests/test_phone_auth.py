from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthIdentity, LoginCode, User
from accounts.utils import hash_code


class PhoneOTPAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="phone-user")
        self.user.phone_plain = "+70000000000"
        self.user.save()

    def test_phone_otp_verification_creates_identity(self):
        LoginCode.objects.create(
            user=self.user,
            channel=LoginCode.Channel.PHONE,
            purpose=LoginCode.Purpose.LOGIN,
            code_hash=hash_code("654321"),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        resp = self.client.post(
            reverse("auth_otp_verify"),
            {"identifier": "+7 000 000-00-00", "code": "654321", "purpose": LoginCode.Purpose.LOGIN},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        identity = AuthIdentity.objects.get(provider=AuthIdentity.Provider.PHONE_SMS)
        self.assertEqual(identity.user, self.user)
        self.assertEqual(identity.provider_user_id, "+70000000000")

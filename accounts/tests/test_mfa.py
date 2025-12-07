from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

from accounts.authentication import JWTAuthentication
from accounts.models import User
from accounts.views import _otp_satisfies_mfa


class MFARulesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mfa_user", password="secret123")
        self.user.mfa_enabled = True
        self.user.mfa_method = User.MFAMethod.SMS
        self.user.phone_plain = "+70000000000"
        self.user.save()

    def test_sms_code_satisfies_mfa_when_method_matches(self):
        self.assertTrue(_otp_satisfies_mfa(self.user, "phone"))
        self.assertFalse(_otp_satisfies_mfa(self.user, "email"))

    def test_totp_always_requires_second_step(self):
        self.user.mfa_method = User.MFAMethod.TOTP
        self.user.save(update_fields=["mfa_method"])
        self.assertFalse(_otp_satisfies_mfa(self.user, "phone"))

    def test_jwt_invalidated_after_mfa_change(self):
        self.user.last_mfa_change = timezone.now()
        self.user.save(update_fields=["last_mfa_change"])
        token = AccessToken()
        token["user_id"] = str(self.user.pk)
        token["iat"] = int((timezone.now() - timezone.timedelta(minutes=5)).timestamp())
        with self.assertRaises(AuthenticationFailed):
            JWTAuthentication().get_user(token)

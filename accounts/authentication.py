from __future__ import annotations

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication


class JWTAuthentication(BaseJWTAuthentication):
    """
    Расширяем проверку simplejwt: токен, выпущенный до последней смены пароля,
    считается недействительным.
    """

    def get_user(self, validated_token):
        user = None
        if hasattr(super(), "get_user"):
            user = super().get_user(validated_token)  # type: ignore[arg-type]
        if user is None:
            user_model = get_user_model()
            try:
                user = user_model.objects.get(pk=validated_token.get("user_id"))
            except user_model.DoesNotExist:
                raise AuthenticationFailed("User not found", code="user_not_found")
        issued_at = validated_token.get("iat")
        if issued_at:
            issued_dt = datetime.fromtimestamp(int(issued_at), tz=timezone.utc)
            last_pw = getattr(user, "last_password_change", None)
            last_mfa = getattr(user, "last_mfa_change", None)
            boundary = max(filter(None, [last_pw, last_mfa]), default=None)
            if boundary and issued_dt < boundary:
                raise AuthenticationFailed("Token issued before last credential change.", code="token_stale")
        return user

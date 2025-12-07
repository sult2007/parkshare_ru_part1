# accounts/serializers.py

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from core.utils import normalize_phone
from .auth import find_user_by_identifier
from .models import LoginCode, SocialAccount, User
from .utils import (
    generate_username,
    hash_code,
    hash_email,
    hash_phone,
    invalidate_other_sessions,
    normalize_email,
)
from django.utils import timezone


class UserSerializer(serializers.ModelSerializer):
    """
    Базовое представление пользователя для админских API.
    Контактные данные не раскрываются.
    """

    has_email = serializers.SerializerMethodField()
    has_phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "role",
            "is_active",
            "date_joined",
            "has_email",
            "has_phone",
        )

    def get_has_email(self, obj: User) -> bool:
        return bool(obj.email_plain)

    def get_has_phone(self, obj: User) -> bool:
        return bool(obj.phone_plain)


class SocialAccountSerializer(serializers.ModelSerializer):
    """Вывод связанных соц-аккаунтов в профиле."""

    class Meta:
        model = SocialAccount
        fields = ("id", "provider", "external_id", "email", "display_name", "last_login_at")


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Профиль текущего пользователя.
    Здесь можно редактировать email/телефон.
    """

    email = serializers.CharField(
        source="email_plain",
        allow_blank=True,
        required=False,
    )
    phone = serializers.CharField(
        source="phone_plain",
        allow_blank=True,
        required=False,
    )
    social_accounts = SocialAccountSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "role",
            "email",
            "phone",
            "mfa_enabled",
            "mfa_method",
            "social_accounts",
        )

    def validate_phone(self, value: str) -> str:
        value = value or ""
        if not value:
            return ""

        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(_("Некорректный формат телефона."))

        phone_hash = hash_phone(normalized)
        user = self.instance
        qs = User.objects.filter(phone_hash=phone_hash)
        if user is not None:
            qs = qs.exclude(pk=user.pk)
        if phone_hash and qs.exists():
            raise serializers.ValidationError(
                _("Пользователь с таким телефоном уже существует.")
            )
        return normalized

    def validate_email(self, value: str) -> str:
        value = normalize_email(value)
        if not value:
            return ""

        email_hash = hash_email(value)
        user = self.instance
        qs = User.objects.filter(email_hash=email_hash)
        if user is not None:
            qs = qs.exclude(pk=user.pk)
        if email_hash and qs.exists():
            raise serializers.ValidationError(
                _("Пользователь с таким email уже существует.")
            )
        return value


class RegisterSerializer(serializers.Serializer):
    """
    Регистрация через API.
    """

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                _("Пользователь с таким логином уже существует.")
            )
        return value

    def validate_email(self, value: str) -> str:
        email = normalize_email(value)
        if not email:
            return ""
        email_hash = hash_email(email)
        if email_hash and User.objects.filter(email_hash=email_hash).exists():
            raise serializers.ValidationError(
                _("Пользователь с таким email уже зарегистрирован.")
            )
        return email

    def validate_phone(self, value: str) -> str:
        value = value or ""
        if not value:
            return ""
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(_("Некорректный формат телефона."))
        phone_hash = hash_phone(normalized)
        if phone_hash and User.objects.filter(phone_hash=phone_hash).exists():
            raise serializers.ValidationError(
                _("Пользователь с таким телефоном уже зарегистрирован.")
            )
        return normalized

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data: dict) -> User:
        email = validated_data.pop("email", "")
        phone = validated_data.pop("phone", "")

        user = User(username=validated_data["username"])
        user.set_password(validated_data["password"])

        if email:
            user.email_plain = email
        if phone:
            user.phone_plain = phone

        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """
    Логин через API (session-based).
    Позволяет использовать логин, email или телефон.
    """

    identifier = serializers.CharField(
        label=_("Логин / Email / Телефон"),
    )
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        if not identifier or not password:
            raise serializers.ValidationError(
                _("Необходимо указать логин и пароль."),
                code="authorization",
            )

        user = find_user_by_identifier(identifier)
        if user is None:
            raise serializers.ValidationError(
                _("Неверный логин/email/телефон или пароль."),
                code="authorization",
            )

        auth_user = authenticate(
            username=user.username,
            password=password,
        )
        if auth_user is None:
            raise serializers.ValidationError(
                _("Неверный логин/email/телефон или пароль."),
                code="authorization",
            )

        if not auth_user.is_active:
            raise serializers.ValidationError(
                _("Пользователь деактивирован."),
                code="authorization",
            )

        attrs["user"] = auth_user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Смена пароля текущего пользователя.
    """

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        validate_password(value, user=user)
        return value

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        old_password = attrs.get("old_password")
        if not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": _("Неверный текущий пароль.")}
            )
        return attrs

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save(update_fields=["password", "last_password_change"])

        request = self.context.get("request")
        if request and hasattr(request, "session"):
            invalidate_other_sessions(user, keep_session_key=request.session.session_key)
            request.session.cycle_key()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Запрос на сброс пароля по email (API).
    """

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        return normalize_email(value)


class OTPRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(label=_("Email или телефон"))
    purpose = serializers.ChoiceField(
        choices=LoginCode.Purpose.choices,
        default=LoginCode.Purpose.LOGIN,
    )

    def validate_identifier(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError(_("Укажите email или телефон."))
        if "@" in value:
            normalized = normalize_email(value)
            if not normalized:
                raise serializers.ValidationError(_("Некорректный email."))
            return normalized
        normalized_phone = normalize_phone(value)
        if not normalized_phone:
            raise serializers.ValidationError(_("Некорректный номер телефона. Используйте формат +7..."))
        return normalized_phone

    def get_channel(self) -> str:
        identifier = self.validated_data.get("identifier", "")
        if "@" in identifier:
            return LoginCode.Channel.EMAIL
        return LoginCode.Channel.PHONE


class OTPVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(label=_("Email или телефон"))
    code = serializers.CharField(label=_("Код из сообщения"), max_length=12)
    purpose = serializers.ChoiceField(
        choices=LoginCode.Purpose.choices,
        default=LoginCode.Purpose.LOGIN,
    )

    def validate_identifier(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError(_("Укажите email или телефон."))
        if "@" in value:
            normalized = normalize_email(value)
            if not normalized:
                raise serializers.ValidationError(_("Некорректный email."))
            return normalized
        normalized_phone = normalize_phone(value)
        if not normalized_phone:
            raise serializers.ValidationError(_("Некорректный номер телефона. Используйте формат +7..."))
        return normalized_phone

    def get_channel(self) -> str:
        identifier = self.validated_data.get("identifier", "")
        if "@" in identifier:
            return LoginCode.Channel.EMAIL
        return LoginCode.Channel.PHONE


class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField(label=_("Код подтверждения"), max_length=12)


class MFASetupSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=User.MFAMethod.choices,
        help_text=_("totp / sms / email"),
    )

    def validate_method(self, value: str) -> str:
        if value == User.MFAMethod.NONE:
            raise serializers.ValidationError(_("Выберите конкретный метод MFA."))
        return value


class MFAActivateSerializer(serializers.Serializer):
    code = serializers.CharField(label=_("Код подтверждения"), max_length=12)

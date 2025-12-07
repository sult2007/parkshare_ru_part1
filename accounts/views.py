# accounts/views.py

from __future__ import annotations

import logging
import random
import secrets
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urlencode

import pyotp
from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import UpdateView
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.observability import capture_exception
from core.permissions import IsSelfOrAdmin
from core.sms import get_sms_provider
from .auth import find_user_by_identifier
from .forms import LoginForm, ProfileForm, RegisterForm
from .models import LoginCode, SocialAccount, User
from .oauth import build_authorize_url, fetch_profile
from .serializers import (
    ChangePasswordSerializer,
    MFAActivateSerializer,
    MFASetupSerializer,
    MFAVerifySerializer,
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SocialAccountSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from .utils import (
    build_totp_uri,
    generate_username,
    hash_code,
    hash_email,
    hash_phone,
    invalidate_other_sessions,
    normalize_email,
    normalize_phone,
)

logger = logging.getLogger(__name__)


def _issue_tokens(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def _clear_pre_auth(session) -> None:
    for key in (
        "pre_auth_user_id",
        "pre_auth_primary_ok",
        "pre_auth_method",
        "pre_auth_reason",
        "post_auth_redirect",
        "oauth_next",
    ):
        session.pop(key, None)


def _finalize_auth(request: HttpRequest, user: User) -> dict[str, str]:
    """
    Завершает аутентификацию: чистит pre-auth, логинит через Django и выдаёт JWT.
    """
    _clear_pre_auth(request.session)
    auth_login(request, user)
    return _issue_tokens(user)


def _get_pre_auth_user(request: HttpRequest) -> Optional[User]:
    user_id = request.session.get("pre_auth_user_id")
    if not user_id:
        return None
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def _verify_totp(user: User, code: str) -> bool:
    if not user.mfa_secret:
        return False
    try:
        totp = pyotp.TOTP(user.mfa_secret)
    except Exception:
        return False
    return totp.verify(code, valid_window=1)


def _send_mfa_code(user: User) -> Optional[str]:
    """
    Отправляет одноразовый код для MFA по email или телефону.
    Возвращает строку канала (email/phone) либо None, если отправка не требуется.
    """
    method = user.mfa_method
    if method not in (User.MFAMethod.SMS, User.MFAMethod.EMAIL):
        return None

    channel = LoginCode.Channel.EMAIL if method == User.MFAMethod.EMAIL else LoginCode.Channel.PHONE
    identifier = user.email_plain if channel == LoginCode.Channel.EMAIL else user.phone_plain
    if not identifier:
        logger.warning("MFA %s requested but no identifier on user %s", method, user.pk)
        return None

    now = timezone.now()
    window_seconds = getattr(settings, "AUTH_OTP_WINDOW_SECONDS", 600)
    max_per_window = getattr(settings, "AUTH_OTP_MAX_PER_WINDOW", 5)
    window_start = now - timedelta(seconds=window_seconds)
    recent_count = (
        LoginCode.objects.filter(
            user=user,
            channel=channel,
            purpose=LoginCode.Purpose.MFA,
            created_at__gte=window_start,
        )
        .only("id")
        .count()
    )
    if recent_count >= max_per_window:
        return channel

    raw_code = f"{random.randint(0, 999999):06d}"
    code_hash = hash_code(raw_code)
    ttl_seconds = getattr(settings, "AUTH_OTP_CODE_TTL_SECONDS", 600)
    expires_at = now + timedelta(seconds=ttl_seconds)

    LoginCode.objects.create(
        user=user,
        channel=channel,
        purpose=LoginCode.Purpose.MFA,
        code_hash=code_hash,
        expires_at=expires_at,
    )

    try:
        if channel == LoginCode.Channel.EMAIL:
            subject = "Код подтверждения входа в ParkShare"
            message = (
                f"Ваш код подтверждения: {raw_code}\n"
                "Никогда не сообщайте его никому. Код действует несколько минут."
            )
            user.email_user(subject, message)
        else:
            text = f"ParkShare: код подтверждения входа {raw_code}"
            sms_provider = get_sms_provider()
            sms_provider.send_sms(identifier, text)
    except Exception as exc:
        capture_exception(
            exc,
            {
                "channel": channel,
                "user_id": str(user.pk),
                "context": "mfa_send",
            },
        )
    return channel


def _verify_mfa_code(user: User, code: str) -> bool:
    method = user.mfa_method
    code = (code or "").strip()
    if not code or method == User.MFAMethod.NONE:
        return False
    if method == User.MFAMethod.TOTP:
        return _verify_totp(user, code)

    channel = LoginCode.Channel.EMAIL if method == User.MFAMethod.EMAIL else LoginCode.Channel.PHONE
    qs = LoginCode.objects.filter(
        user=user,
        channel=channel,
        purpose=LoginCode.Purpose.MFA,
        is_used=False,
    ).order_by("-created_at")
    code_obj = qs.first()
    if not code_obj:
        return False

    max_attempts = getattr(settings, "AUTH_OTP_MAX_ATTEMPTS", 5)
    if code_obj.is_expired or code_obj.attempts >= max_attempts or code_obj.code_hash != hash_code(code):
        code_obj.attempts += 1
        if code_obj.attempts >= max_attempts:
            code_obj.is_used = True
            code_obj.status = "blocked"
        code_obj.save(update_fields=["attempts", "is_used", "status", "updated_at"])
        return False

    code_obj.is_used = True
    code_obj.attempts += 1
    code_obj.status = "used"
    code_obj.save(update_fields=["is_used", "status", "attempts", "updated_at"])
    return True


def _require_mfa(request: HttpRequest, user: User, reason: str = "login") -> dict[str, Any]:
    request.session["pre_auth_user_id"] = str(user.pk)
    request.session["pre_auth_primary_ok"] = True
    request.session["pre_auth_method"] = user.mfa_method
    request.session["pre_auth_reason"] = reason
    channel = _send_mfa_code(user)
    request.session.modified = True
    return {
        "mfa_required": True,
        "mfa_method": user.mfa_method,
        "mfa_channel": channel,
    }


class RegisterView(View):
    template_name = "accounts/register.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("user_dashboard")
        form = RegisterForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("user_dashboard")
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("user_dashboard")
        return render(request, self.template_name, {"form": form})


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("user_dashboard")

    def get_object(self, queryset=None) -> User:
        return self.request.user


class MFASettingsView(LoginRequiredMixin, View):
    """
    Простая HTML-страница для управления MFA (TOTP или SMS/Email).
    """

    template_name = "accounts/mfa_setup.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        user: User = request.user
        secret = request.session.get("mfa_setup_secret") or user.mfa_secret
        otpauth_url = None
        if secret and user.mfa_method == User.MFAMethod.TOTP:
            otpauth_url = build_totp_uri(user.username or str(user.pk), "ParkShare", secret)
        context = {
            "user": user,
            "secret": secret,
            "otpauth_url": otpauth_url,
            "method": user.mfa_method,
            "mfa_enabled": user.mfa_enabled,
            "status": request.GET.get("status"),
            "error": request.GET.get("error"),
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        user: User = request.user
        action = request.POST.get("action")
        status_msg = ""
        error_msg = ""

        if action == "start_totp":
            secret = pyotp.random_base32()
            user.mfa_secret = secret
            user.mfa_method = User.MFAMethod.TOTP
            user.mfa_enabled = False
            user.save(update_fields=["mfa_secret", "mfa_method", "mfa_enabled"])
            request.session["mfa_setup_secret"] = secret
            status_msg = "Секрет для TOTP сгенерирован. Просканируйте QR и введите код для активации."
        elif action == "start_sms":
            if not user.phone_plain:
                error_msg = "Добавьте номер телефона в профиле, чтобы включить SMS-MFA."
            else:
                user.mfa_method = User.MFAMethod.SMS
                user.mfa_enabled = False
                user.mfa_secret = None
                user.save(update_fields=["mfa_method", "mfa_enabled", "mfa_secret"])
                _send_mfa_code(user)
                status_msg = "Мы отправили код по SMS. Введите его ниже для активации."
        elif action == "start_email":
            if not user.email_plain:
                error_msg = "Добавьте email в профиле, чтобы включить MFA по email."
            else:
                user.mfa_method = User.MFAMethod.EMAIL
                user.mfa_enabled = False
                user.mfa_secret = None
                user.save(update_fields=["mfa_method", "mfa_enabled", "mfa_secret"])
                _send_mfa_code(user)
                status_msg = "Код отправлен на email. Проверьте почту и подтвердите ниже."
        elif action == "verify":
            code = request.POST.get("code", "")
            is_valid = _verify_totp(user, code) if user.mfa_method == User.MFAMethod.TOTP else _verify_mfa_code(user, code)
            if is_valid:
                user.mfa_enabled = True
                user.save(update_fields=["mfa_enabled"])
                request.session.pop("mfa_setup_secret", None)
                status_msg = "MFA успешно включена."
            else:
                error_msg = "Код не подошёл. Попробуйте снова."
        elif action == "disable":
            user.mfa_enabled = False
            user.mfa_method = User.MFAMethod.NONE
            user.mfa_secret = None
            user.save(update_fields=["mfa_enabled", "mfa_method", "mfa_secret"])
            request.session.pop("mfa_setup_secret", None)
            status_msg = "MFA выключена."

        params = {}
        if status_msg:
            params["status"] = status_msg
        if error_msg:
            params["error"] = error_msg
        query = f"?{urlencode(params)}" if params else ""
        return redirect(f"{reverse('accounts:mfa_setup')}{query}")


class MFAVerifyPageView(View):
    """
    HTML-страница ввода кода MFA после успешного первичного входа.
    """

    template_name = "accounts/mfa_verify.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        user = _get_pre_auth_user(request)
        if not user:
            return redirect("accounts:login")
        method = request.session.get("pre_auth_method") or user.mfa_method
        channel = "email" if method == User.MFAMethod.EMAIL else "sms" if method == User.MFAMethod.SMS else None
        context = {
            "method": method,
            "channel": channel,
            "username": getattr(user, "username", ""),
            "error": None,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        user = _get_pre_auth_user(request)
        if not user:
            return redirect("accounts:login")

        if request.POST.get("action") == "resend":
            _send_mfa_code(user)
            return redirect(f"{reverse('accounts:mfa_verify')}?status=resend")

        code = request.POST.get("code", "")
        if not _verify_mfa_code(user, code):
            method = request.session.get("pre_auth_method") or user.mfa_method
            channel = "email" if method == User.MFAMethod.EMAIL else "sms" if method == User.MFAMethod.SMS else None
            context = {
                "method": method,
                "channel": channel,
                "username": getattr(user, "username", ""),
                "error": "Код не подошёл. Попробуйте снова.",
            }
            return render(request, self.template_name, context, status=400)

        next_url = request.session.get("post_auth_redirect") or request.session.get("oauth_next")
        _finalize_auth(request, user)
        if next_url:
            return redirect(next_url)
        return redirect("user_dashboard")


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("user_dashboard")

    def get_object(self, queryset=None) -> User:
        return self.request.user


class CustomLoginView(DjangoLoginView):
    """
    Обёртка над стандартным LoginView с русским шаблоном и кастомной формой.
    """

    template_name = "accounts/login.html"
    form_class = LoginForm

    def get_success_url(self) -> str:
        return reverse("user_dashboard")

    def form_valid(self, form):
        user = form.get_user()
        if getattr(user, "mfa_enabled", False) and user.mfa_method != User.MFAMethod.NONE:
            self.request.session["post_auth_redirect"] = self.get_success_url()
            _require_mfa(self.request, user, reason="password")
            return redirect(reverse("accounts:mfa_verify"))
        return super().form_valid(form)


class SecurePasswordChangeView(auth_views.PasswordChangeView):
    """
    Перехватываем смену пароля, чтобы инвалидировать старые сессии и отметить время смены.
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        user: User = self.request.user
        user.last_password_change = timezone.now()
        user.save(update_fields=["last_password_change"])
        invalidate_other_sessions(user, keep_session_key=self.request.session.session_key)
        self.request.session.cycle_key()
        return response


def logout_view(request: HttpRequest) -> HttpResponse:
    _clear_pre_auth(request.session)
    auth_logout(request)
    return redirect("landing")


class UserViewSet(viewsets.ModelViewSet):
    """
    API для работы с пользователями.
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer

    def get_permissions(self) -> list[Any]:
        if self.action in ("register", "login", "reset_password"):
            permission_classes = [permissions.AllowAny]
        elif self.action in ("list", "destroy"):
            permission_classes = [permissions.IsAdminUser]
        elif self.action in ("me", "change_password", "logout", "social_accounts"):
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated, IsSelfOrAdmin]
        return [perm() for perm in permission_classes]

    def get_queryset(self):
        user: User = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        if user.is_superuser or getattr(user, "is_admin", False):
            return User.objects.all().order_by("-date_joined")
        return User.objects.filter(pk=user.pk)

    def perform_destroy(self, instance: User) -> None:
        super().perform_destroy(instance)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if request.method.lower() == "get":
            serializer = UserProfileSerializer(request.user)
            return Response(serializer.data)
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="social-accounts")
    def social_accounts(self, request):
        serializer = SocialAccountSerializer(
            request.user.social_accounts.all().order_by("provider"), many=True
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.save()
        auth_login(request, user)
        data = UserProfileSerializer(user).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="login")
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.validated_data["user"]
        if user.mfa_enabled and user.mfa_method != User.MFAMethod.NONE:
            request.session["post_auth_redirect"] = request.data.get("next")
            challenge = _require_mfa(request, user, reason="password")
            return Response(
                {
                    **challenge,
                    "detail": "Требуется подтверждение второго фактора.",
                },
                status=status.HTTP_200_OK,
            )

        auth_login(request, user)
        data = UserProfileSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        auth_logout(request)
        return Response(
            {"detail": "Вы вышли из системы."}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Пароль успешно изменён."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="reset-password")
    def reset_password(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        form = PasswordResetForm(data={"email": email})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="accounts/password_reset_email.txt",
                subject_template_name="accounts/password_reset_subject.txt",
            )

        return Response(
            {
                "detail": (
                    "Если пользователь с таким email существует, на него отправлена "
                    "инструкция по сбросу пароля."
                )
            },
            status=status.HTTP_200_OK,
        )


class TokenObtainPairView(APIView):
    """JWT-аутентификация по логину/email/телефону."""

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if user.mfa_enabled and user.mfa_method != User.MFAMethod.NONE:
            request.session["post_auth_redirect"] = request.data.get("next")
            challenge = _require_mfa(request, user, reason="jwt_login")
            return Response(
                {
                    **challenge,
                    "detail": "MFA требуется перед выдачей токенов.",
                },
                status=status.HTTP_200_OK,
            )

        tokens = _issue_tokens(user)
        return Response(
            {
                **tokens,
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshSlidingView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class AuthOTPRequestView(APIView):
    """
    Request one-time code for login/registration via email or phone (SMS).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        purpose = serializer.validated_data["purpose"]
        channel = serializer.get_channel()

        user = self._get_or_create_user(identifier, channel)

        now = timezone.now()
        window_seconds = getattr(settings, "AUTH_OTP_WINDOW_SECONDS", 600)
        max_per_window = getattr(settings, "AUTH_OTP_MAX_PER_WINDOW", 5)
        window_start = now - timedelta(seconds=window_seconds)
        recent_count = (
            LoginCode.objects.filter(
                user=user,
                channel=channel,
                purpose=purpose,
                created_at__gte=window_start,
            )
            .only("id")
            .count()
        )
        if recent_count >= max_per_window:
            return Response(
                {"detail": "Слишком много запросов кода. Попробуйте позже."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        raw_code = f"{random.randint(0, 999999):06d}"
        code_hash = hash_code(raw_code)
        ttl_seconds = getattr(settings, "AUTH_OTP_CODE_TTL_SECONDS", 600)
        expires_at = now + timedelta(seconds=ttl_seconds)

        LoginCode.objects.create(
            user=user,
            channel=channel,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
        )

        try:
            if channel == LoginCode.Channel.EMAIL:
                subject = "Код для входа в ParkShare"
                message = f"Ваш код для входа: {raw_code}\n\nСрок действия: {ttl_seconds // 60} минут."
                user.email_user(subject, message)
            else:
                text = f"Код для входа в ParkShare: {raw_code}. Не сообщайте его никому."
                sms_provider = get_sms_provider()
                sms_provider.send_sms(identifier, text)
        except Exception as exc:
            capture_exception(
                exc,
                {
                    "channel": channel,
                    "purpose": purpose,
                    "user_id": str(user.pk),
                },
            )

        return Response(
            {
                "detail": "Код отправлен.",
                "ttl_seconds": ttl_seconds,
                "channel": channel,
            },
            status=status.HTTP_200_OK,
        )

    def _get_or_create_user(self, identifier: str, channel: str) -> User:
        if channel == LoginCode.Channel.EMAIL:
            email_norm = normalize_email(identifier)
            email_hash = hash_email(email_norm)
            user = User.objects.filter(email_hash=email_hash).first()
            if user:
                return user
            user = User(username=generate_username("mail"))
            user.email_plain = email_norm
            user.save()
            return user

        phone_norm = normalize_phone(identifier)
        phone_hash = hash_phone(phone_norm)
        user = User.objects.filter(phone_hash=phone_hash).first()
        if user:
            return user
        user = User(username=generate_username("phone"))
        user.phone_plain = phone_norm
        user.save()
        return user


class AuthOTPVerifyView(APIView):
    """
    Verify one-time code and issue JWT tokens + session login.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        code = serializer.validated_data["code"]
        purpose = serializer.validated_data["purpose"]
        channel = serializer.get_channel()

        user = find_user_by_identifier(identifier)
        if not user:
            return Response(
                {"detail": "Пользователь не найден."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code_hash = hash_code(code)
        qs = LoginCode.objects.filter(
            user=user,
            purpose=purpose,
            channel=channel,
            is_used=False,
        ).order_by("-created_at")

        code_obj = qs.first()
        if not code_obj:
            return Response(
                {"detail": "Код не найден. Запросите новый."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_attempts = getattr(settings, "AUTH_OTP_MAX_ATTEMPTS", 5)
        if code_obj.is_expired or code_obj.attempts >= max_attempts or code_obj.code_hash != code_hash:
            code_obj.attempts += 1
            if code_obj.attempts >= max_attempts:
                code_obj.is_used = True
                code_obj.status = "blocked"
            code_obj.save(update_fields=["attempts", "is_used", "status", "updated_at"])
            return Response(
                {"detail": "Неверный или просроченный код."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code_obj.is_used = True
        code_obj.attempts += 1
        code_obj.status = "used"
        code_obj.save(update_fields=["is_used", "status", "attempts", "updated_at"])

        if user.mfa_enabled and user.mfa_method != User.MFAMethod.NONE:
            request.session["post_auth_redirect"] = request.data.get("next")
            challenge = _require_mfa(request, user, reason="otp_login")
            return Response(
                {
                    **challenge,
                    "detail": "Необходим второй фактор (MFA).",
                },
                status=status.HTTP_200_OK,
            )

        auth_login(request, user)
        tokens = _issue_tokens(user)
        return Response(tokens, status=status.HTTP_200_OK)


class AuthMFAVerifyView(APIView):
    """
    Verify MFA code (TOTP or SMS/email) after успешного первичного входа.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = _get_pre_auth_user(request)
        if not user or not request.session.get("pre_auth_primary_ok"):
            return Response(
                {"detail": "Сессия MFA не найдена или истекла."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]
        if not _verify_mfa_code(user, code):
            return Response({"detail": "Неверный код MFA."}, status=status.HTTP_400_BAD_REQUEST)

        next_url = request.session.get("post_auth_redirect") or request.session.get("oauth_next")
        tokens = _finalize_auth(request, user)
        payload = {
            "detail": "MFA подтверждена.",
            "user": UserProfileSerializer(user).data,
            **tokens,
        }
        if next_url:
            payload["next"] = next_url
        return Response(payload, status=status.HTTP_200_OK)


class AuthMFASetupView(APIView):
    """
    Инициирует подключение MFA для текущего пользователя.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MFASetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        method = serializer.validated_data["method"]
        user: User = request.user

        if method == User.MFAMethod.TOTP:
            secret = pyotp.random_base32()
            user.mfa_secret = secret
            user.mfa_method = User.MFAMethod.TOTP
            user.mfa_enabled = False
            user.save(update_fields=["mfa_secret", "mfa_method", "mfa_enabled"])
            request.session["mfa_setup_secret"] = secret
            otpauth_url = build_totp_uri(user.username or str(user.pk), "ParkShare", secret)
            return Response(
                {
                    "secret": secret,
                    "otpauth_url": otpauth_url,
                    "mfa_method": user.mfa_method,
                },
                status=status.HTTP_200_OK,
            )

        if method == User.MFAMethod.SMS and not user.phone_plain:
            return Response({"detail": "Добавьте телефон в профиле для SMS-MFA."}, status=status.HTTP_400_BAD_REQUEST)
        if method == User.MFAMethod.EMAIL and not user.email_plain:
            return Response({"detail": "Добавьте email в профиле для Email-MFA."}, status=status.HTTP_400_BAD_REQUEST)

        user.mfa_method = method
        user.mfa_enabled = False
        user.mfa_secret = None
        user.save(update_fields=["mfa_method", "mfa_enabled", "mfa_secret"])
        channel = _send_mfa_code(user)

        return Response(
            {
                "detail": "Код отправлен. Подтвердите его, чтобы включить MFA.",
                "channel": channel,
                "mfa_method": user.mfa_method,
            },
            status=status.HTTP_200_OK,
        )


class AuthMFAActivateView(APIView):
    """
    Завершает подключение MFA (ввод кода TOTP/SMS/email).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MFAActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = request.user
        if user.mfa_method == User.MFAMethod.NONE:
            return Response({"detail": "MFA не инициализирована."}, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data["code"]
        is_valid = _verify_totp(user, code) if user.mfa_method == User.MFAMethod.TOTP else _verify_mfa_code(user, code)
        if not is_valid:
            return Response({"detail": "Код не подошёл."}, status=status.HTTP_400_BAD_REQUEST)

        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        request.session.pop("mfa_setup_secret", None)
        return Response(
            {
                "detail": "MFA включена.",
                "mfa_method": user.mfa_method,
            },
            status=status.HTTP_200_OK,
        )


class AuthMFADisableView(APIView):
    """
    Отключает MFA, очищает секреты.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user: User = request.user
        user.mfa_enabled = False
        user.mfa_method = User.MFAMethod.NONE
        user.mfa_secret = None
        user.save(update_fields=["mfa_enabled", "mfa_method", "mfa_secret"])
        _clear_pre_auth(request.session)
        return Response({"detail": "MFA отключена."}, status=status.HTTP_200_OK)


class SocialOAuthStartView(View):
    """Стартуем OAuth-авторизацию: формируем state и редиректим на провайдера."""

    def get(self, request: HttpRequest, provider: str) -> HttpResponse:
        state = secrets.token_urlsafe(24)
        request.session[f"oauth_state_{provider}"] = state
        next_url = request.GET.get("next")
        if next_url:
            request.session["oauth_next"] = next_url

        redirect_uri = request.build_absolute_uri(
            reverse("oauth_callback", args=[provider])
        )
        try:
            url = build_authorize_url(provider, state, redirect_uri)
        except ValueError:
            return HttpResponseBadRequest("Unsupported provider")
        return redirect(url)


class SocialOAuthCallbackView(APIView):
    """Принимаем код, валидируем state, создаём/линкуем пользователя и соц-аккаунт."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, provider: str):
        state = request.GET.get("state")
        expected_state = request.session.pop(f"oauth_state_{provider}", None)
        if not expected_state or expected_state != state:
            return Response({"detail": "Некорректный state."}, status=status.HTTP_400_BAD_REQUEST)

        code = request.GET.get("code")
        if not code:
            return Response({"detail": "Не передан код авторизации."}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uri = request.build_absolute_uri(
            reverse("oauth_callback", args=[provider])
        )
        try:
            profile = fetch_profile(provider, code, redirect_uri)
        except Exception as exc:
            capture_exception(exc, {"provider": provider})
            return Response(
                {
                    "detail": f"{provider.title()} временно недоступен. Используйте другой способ входа.",
                    "provider": provider,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = self._resolve_user(request, profile)
        social_account, _ = SocialAccount.objects.update_or_create(
            provider=provider,
            external_id=profile["external_id"],
            defaults={
                "user": user,
                "email": profile.get("email"),
                "display_name": profile.get("display_name") or "",
                "extra_data": profile.get("raw") or {},
                "last_login_at": timezone.now(),
            },
        )
        social_account.save()

        next_url = request.session.get("oauth_next") or request.GET.get("next")

        if user.mfa_enabled and user.mfa_method != User.MFAMethod.NONE:
            request.session["post_auth_redirect"] = next_url
            _require_mfa(request, user, reason="oauth")
            return redirect(reverse("accounts:mfa_verify"))

        auth_login(request, user)
        tokens = _issue_tokens(user)
        request.session.pop("oauth_next", None)
        if next_url:
            return redirect(next_url)
        return Response(
            {
                "detail": "Вход выполнен через социальную сеть.",
                "user": UserProfileSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_200_OK,
        )

    def _resolve_user(self, request: HttpRequest, profile: dict) -> User:
        if request.user.is_authenticated:
            return request.user

        existing = SocialAccount.objects.filter(
            provider=profile["provider"], external_id=profile["external_id"]
        ).select_related("user").first()
        if existing:
            return existing.user

        email = normalize_email(profile.get("email"))
        if email:
            email_hash = hash_email(email)
            user = User.objects.filter(email_hash=email_hash).first()
            if user:
                return user
            user = User(username=generate_username(profile.get("provider", "social")))
            user.email_plain = email
            user.save()
            return user

        user = User(username=generate_username(profile.get("provider", "social")))
        display_name = profile.get("display_name")
        if display_name:
            user.first_name = display_name.split(" ")[0]
        user.save()
        return user


class SocialAccountDetailView(APIView):
    """Unlink social accounts from profile."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk: int):
        try:
            account = SocialAccount.objects.get(pk=pk, user=request.user)
        except SocialAccount.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

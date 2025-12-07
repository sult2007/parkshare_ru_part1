# accounts/views.py

from __future__ import annotations

import logging
import random
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
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
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SocialAccountSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from .utils import generate_username, hash_code, hash_email, hash_phone, normalize_email, normalize_phone

logger = logging.getLogger(__name__)


def _issue_tokens(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# ===== HTML-вьюхи (шаблонный интерфейс) =====


class RegisterView(View):
    """
    Регистрация пользователя через HTML-форму.
    """

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
    """
    Редактирование профиля (email/телефон) в HTML-интерфейсе.
    """

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


def logout_view(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("landing")


# ===== API (DRF) =====


class UserViewSet(viewsets.ModelViewSet):
    """
    API для работы с пользователями.

    Маршруты:
    - /api/accounts/users/                   (GET)   — список (только админ)
    - /api/accounts/users/{id}/              (GET)   — профиль (сам или админ)
    - /api/accounts/users/me/                (GET)   — профиль текущего пользователя
    - /api/accounts/users/me/                (PATCH) — обновление своего профиля
    - /api/accounts/users/register/          (POST)  — регистрация
    - /api/accounts/users/login/             (POST)  — логин (session-based)
    - /api/accounts/users/logout/            (POST)  — логаут
    - /api/accounts/users/change-password/   (POST)  — смена пароля (API)
    - /api/accounts/users/reset-password/    (POST)  — запрос сброса пароля по email
    - /api/accounts/users/social-accounts/   (GET)   — соц-связки текущего пользователя
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
        """
        Профиль текущего пользователя.
        GET — получить; PATCH — обновить email/телефон.
        """
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
        """Возвращает список соц-привязок текущего пользователя."""
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


# ===== Passwordless (OTP) =====


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

        auth_login(request, user)
        tokens = _issue_tokens(user)
        return Response(tokens, status=status.HTTP_200_OK)


# ===== OAuth (VK / Yandex / Google) =====


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
            return Response({"detail": "Не удалось получить профиль."}, status=status.HTTP_400_BAD_REQUEST)

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

        auth_login(request, user)
        tokens = _issue_tokens(user)
        next_url = request.session.pop("oauth_next", None) or request.GET.get("next")
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

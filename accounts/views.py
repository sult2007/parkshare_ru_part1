# accounts/views.py

from typing import Any

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import UpdateView
from rest_framework import permissions, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth import login as auth_login_session
from django.core.mail import send_mail

from core.permissions import IsSelfOrAdmin
from .forms import LoginForm, ProfileForm, RegisterForm
from .models import User, LoginCode
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
)
from .auth import find_user_by_identifier
from .utils import hash_email


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
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer

    def get_permissions(self) -> list[Any]:
        if self.action in ("register", "login", "reset_password"):
            permission_classes = [permissions.AllowAny]
        elif self.action in ("list", "destroy"):
            permission_classes = [permissions.IsAdminUser]
        elif self.action in ("me", "change_password", "logout"):
            permission_classes = [permissions.IsAuthenticated]
        else:
            # retrieve/update/partial_update — только сам пользователь или админ
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
        """
        Удалять пользователей может только админ — контролируется permissions.
        """
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

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        """
        Регистрация пользователя через API.
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.save()
        auth_login(request, user)
        data = UserProfileSerializer(user).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="login")
    def login(self, request):
        """
        Логин через API. Используются стандартные Django-сессии.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = serializer.validated_data["user"]
        auth_login(request, user)
        data = UserProfileSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        """
        Логаут через API (очистка сессии).
        """
        auth_logout(request)
        return Response(
            {"detail": "Вы вышли из системы."}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """
        Смена пароля текущего пользователя (API).
        """
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
        """
        Запрос на сброс пароля по email (API).

        Использует стандартный PasswordResetForm и отправляет письмо
        через настроенный EMAIL_BACKEND.
        """
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

        # Независимо от результата говорим одно и то же, чтобы не раскрывать,
        # существует ли пользователь с таким email.
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
    """JWT-аутентификация по логину/email/телефону.

    Возвращает пару access/refresh токенов и упрощает интеграцию с мобильными
    клиентами и PWA. Валидация и анти-брутфорс остаются в LoginSerializer.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshSlidingView(TokenRefreshView):
    """Упаковываем refresh endpoint в единый namespace accounts."""

    permission_classes = [permissions.AllowAny]


class AuthOTPRequestView(APIView):
    """
    POST /api/auth/request-code
    identifier: email/phone, purpose: login/register/reset_password
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        purpose = serializer.validated_data["purpose"]

        # Находим или создаём пользователя для регистрации
        user = find_user_by_identifier(identifier)
        if purpose == LoginCode.Purpose.REGISTER and user is None:
            # Создаём "сырого" пользователя с рандомным username
            username = f"user_{get_random_string(8)}"
            user = User.objects.create(username=username, is_active=True)
            if "@" in identifier:
                user.email_plain = identifier
            else:
                user.phone_plain = identifier
            user.save()
        if user is None:
            # Для login/reset_password не раскрываем факт отсутствия аккаунта
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Генерируем код и хэшируем его
        raw_code = get_random_string(6, allowed_chars="0123456789")
        code_hash = hash_email(raw_code)  # переиспользуем хэш (или заменить на свою функцию)

        expires_at = timezone.now() + timezone.timedelta(minutes=10)
        LoginCode.objects.create(
            user=user,
            channel=LoginCode.Channel.EMAIL if "@" in identifier else LoginCode.Channel.PHONE,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
        )

        # Отправка кода (для SMS тут будет интеграция с провайдером)
        if "@" in identifier:
            send_mail(
                subject="Ваш код ParkShare",
                message=f"Ваш код входа: {raw_code} (действителен 10 минут).",
                from_email=None,
                recipient_list=[identifier],
                fail_silently=True,
            )

        # Для демо возвращаем 204 без тела
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthOTPVerifyView(APIView):
    """
    POST /api/auth/verify-code
    identifier + code → логин (session + JWT).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        code = serializer.validated_data["code"]
        purpose = serializer.validated_data["purpose"]

        user = find_user_by_identifier(identifier)
        if user is None:
            return Response({"detail": "Неверный код или идентификатор."}, status=status.HTTP_400_BAD_REQUEST)

        code_hash = hash_email(code)
        qs = LoginCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).order_by("-created_at")

        code_obj = qs.first()
        if not code_obj or code_obj.code_hash != code_hash or code_obj.is_expired:
            return Response({"detail": "Неверный или просроченный код."}, status=status.HTTP_400_BAD_REQUEST)

        code_obj.is_used = True
        code_obj.save(update_fields=["is_used", "updated_at"])

        # Логиним пользователя (session + JWT)
        auth_login_session(request, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
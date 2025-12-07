# accounts/models.py

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_cryptography.fields import encrypt

from core.models import TimeStampedUUIDModel
from .utils import hash_email, hash_phone

class User(AbstractUser):
    """
    Кастомный пользователь:
    - UUID как первичный ключ;
    - роль (driver / owner / admin);
    - email/телефон в зашифрованном виде (django-cryptography-django5);
    - отдельные хэши email/телефона для безопасного поиска/уникальности.
    """

    class Role(models.TextChoices):
        DRIVER = "driver", _("Водитель")
        OWNER = "owner", _("Владелец парковки")
        ADMIN = "admin", _("Администратор")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    role = models.CharField(
        _("Роль"),
        max_length=16,
        choices=Role.choices,
        default=Role.DRIVER,
        help_text=_("Определяет права доступа в системе."),
    )

    # Шифрованные контактные поля
    email_encrypted = encrypt(
        models.EmailField(
            _("Email (зашифрованный)"),
            blank=True,
            null=True,
            help_text=_("Опциональный email, хранится в зашифрованном виде."),
        )
    )

    phone_encrypted = encrypt(
        models.CharField(
            _("Телефон (зашифрованный)"),
            max_length=32,
            blank=True,
            null=True,
            help_text=_("Опциональный телефон, хранится в зашифрованном виде."),
        )
    )

    # Отдельные хэши для поиска и проверки уникальности
    email_hash = models.CharField(
        _("Хэш нормализованного email"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_("Используется только для поиска и проверки уникальности email."),
    )

    phone_hash = models.CharField(
        _("Хэш нормализованного телефона"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_("Используется только для поиска и проверки уникальности телефона."),
    )

    owner_request_pending = models.BooleanField(
        _("Запрошено повышение до владельца"),
        default=False,
        help_text=_("Пользователь подал заявку на роль владельца парковки."),
    )

    class MFAMethod(models.TextChoices):
        NONE = "none", _("Без MFA")
        TOTP = "totp", _("TOTP (приложение)")
        SMS = "sms", _("SMS")
        EMAIL = "email", _("Email")

    mfa_enabled = models.BooleanField(
        _("MFA включена"), default=False, help_text=_("Требовать второй фактор при входе.")
    )
    mfa_method = models.CharField(
        _("Метод MFA"),
        max_length=16,
        choices=MFAMethod.choices,
        default=MFAMethod.NONE,
    )
    mfa_secret = models.CharField(
        _("Секрет TOTP"),
        max_length=64,
        blank=True,
        null=True,
        help_text=_("Используется только для TOTP-приложений."),
    )
    last_password_change = models.DateTimeField(
        _("Последняя смена пароля"),
        blank=True,
        null=True,
        help_text=_("Используется для инвалидирования сессий и JWT."),
    )
    last_mfa_change = models.DateTimeField(
        _("Последнее изменение MFA"),
        blank=True,
        null=True,
        help_text=_("Используется для инвалидирования сессий и токенов после изменения MFA."),
    )

    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")

    def __str__(self) -> str:
        return self.username

    @property
    def email_plain(self) -> str:
        return self.email_encrypted or ""

    @email_plain.setter
    def email_plain(self, value: str) -> None:
        self.email_encrypted = value or None

    @property
    def phone_plain(self) -> str:
        return self.phone_encrypted or ""

    @phone_plain.setter
    def phone_plain(self, value: str) -> None:
        self.phone_encrypted = value or None

    @property
    def is_driver(self) -> bool:
        return self.role == self.Role.DRIVER

    @property
    def is_owner(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def update_contact_hashes(self) -> None:
        self.email_hash = hash_email(self.email_plain)
        self.phone_hash = hash_phone(self.phone_plain)

    def save(self, *args, **kwargs) -> None:
        self.update_contact_hashes()
        super().save(*args, **kwargs)


class LoginCode(TimeStampedUUIDModel):
    """
    Одноразовый код для подтверждения email/телефона и входа.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", _("Email")
        PHONE = "phone", _("Телефон")

    class Purpose(models.TextChoices):
        REGISTER = "register", _("Регистрация")
        LOGIN = "login", _("Вход")
        RESET_PASSWORD = "reset_password", _("Сброс пароля")
        MFA = "mfa", _("MFA подтверждение")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_codes",
    )
    channel = models.CharField(
        _("Канал"),
        max_length=16,
        choices=Channel.choices,
    )
    purpose = models.CharField(
        _("Назначение"),
        max_length=32,
        choices=Purpose.choices,
    )
    code_hash = models.CharField(
        _("Хэш кода"),
        max_length=128,
        db_index=True,
    )
    expires_at = models.DateTimeField(_("Истекает в"))
    is_used = models.BooleanField(_("Использован"), default=False)
    attempts = models.PositiveSmallIntegerField(_("Попыток ввода"), default=0)
    status = models.CharField(
        _("Статус"),
        max_length=16,
        default="pending",
        help_text=_("pending/used/expired/blocked"),
    )

    class Meta:
        verbose_name = _("Код подтверждения")
        verbose_name_plural = _("Коды подтверждения")
        indexes = [
            models.Index(fields=["user", "purpose", "is_used"]),
        ]

    def __str__(self) -> str:
        return f"{self.purpose} code for {self.user_id}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        self.is_used = True
        self.status = "used"
        self.save(update_fields=["is_used", "status", "updated_at"])


class SocialAccount(models.Model):
    """
    Link between local User and external OAuth provider account.
    Intended for VK, Yandex ID, Google and similar providers.
    """

    class Provider(models.TextChoices):
        VK = "vk", "VK"
        YANDEX = "yandex", "Yandex"
        GOOGLE = "google", "Google"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
        verbose_name=_("Пользователь"),
    )
    provider = models.CharField(
        _("Провайдер"),
        max_length=32,
        choices=Provider.choices,
    )
    external_id = models.CharField(
        _("Внешний ID"),
        max_length=255,
        help_text=_("Уникальный идентификатор пользователя в системе провайдера."),
    )
    email = models.EmailField(_("Email из профиля"), blank=True, null=True)
    display_name = models.CharField(_("Имя в профиле"), max_length=255, blank=True)
    extra_data = models.JSONField(
        _("Сырой профиль"),
        default=dict,
        blank=True,
        help_text=_("Небольшой JSON с частью профиля, не содержащей чувствительные данные."),
    )
    last_login_at = models.DateTimeField(_("Последний вход"), default=timezone.now)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        verbose_name = _("Социальный аккаунт")
        verbose_name_plural = _("Социальные аккаунты")
        unique_together = [("provider", "external_id")]
        indexes = [
            models.Index(fields=["provider", "external_id"]),
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_provider_display()}:{self.external_id} → {self.user_id}"


class UserLevel(TimeStampedUUIDModel):
    name = models.CharField(max_length=64)
    threshold = models.PositiveIntegerField(default=0, help_text="Количество завершённых бронирований для уровня")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Уровень пользователя"
        verbose_name_plural = "Уровни пользователей"
        ordering = ("threshold",)

    def __str__(self) -> str:
        return self.name


class UserBadge(TimeStampedUUIDModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="badges", verbose_name="Пользователь"
    )
    title = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=64, blank=True)
    level = models.ForeignKey(
        UserLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badges",
    )

    class Meta:
        verbose_name = "Бейдж"
        verbose_name_plural = "Бейджи"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.title} — {self.user}"


class PromoReward(TimeStampedUUIDModel):
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Промо/бонус"
        verbose_name_plural = "Промо/бонусы"

    def __str__(self) -> str:
        return self.code

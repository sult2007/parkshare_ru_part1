# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LoginCode, PromoReward, SocialAccount, User, UserBadge, UserLevel


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Кастомная админка для пользователя с UUID-ID и ролями.
    """

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Дополнительно",
            {
                "fields": (
                    "role",
                    "email_encrypted",
                    "phone_encrypted",
                    "owner_request_pending",
                )
            },
        ),
    )

    list_display = (
        "username",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username",)


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "provider", "external_id", "email", "last_login_at")
    list_filter = ("provider",)
    search_fields = ("external_id", "email", "user__email", "user__username")
    autocomplete_fields = ("user",)


@admin.register(LoginCode)
class LoginCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "channel", "purpose", "expires_at", "is_used", "attempts")
    list_filter = ("channel", "purpose", "is_used")
    search_fields = ("user__username", "user__email_hash", "user__phone_hash")

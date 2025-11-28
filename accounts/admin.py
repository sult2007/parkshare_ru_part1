# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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

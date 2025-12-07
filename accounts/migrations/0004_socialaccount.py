# Generated for SocialAccount model

from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_userlevel_userbadge_promoreward"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(
                        choices=[("vk", "VK"), ("yandex", "Yandex"), ("google", "Google")],
                        max_length=32,
                        verbose_name="Провайдер",
                    ),
                ),
                (
                    "external_id",
                    models.CharField(
                        help_text="Уникальный идентификатор пользователя в системе провайдера.",
                        max_length=255,
                        verbose_name="Внешний ID",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        null=True,
                        verbose_name="Email из профиля",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Имя в профиле",
                    ),
                ),
                (
                    "extra_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Небольшой JSON с частью профиля, не содержащей чувствительные данные.",
                        verbose_name="Сырой профиль",
                    ),
                ),
                (
                    "last_login_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="Последний вход",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="Создано",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name="Обновлено",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="social_accounts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Социальный аккаунт",
                "verbose_name_plural": "Социальные аккаунты",
                "unique_together": {("provider", "external_id")},
            },
        ),
        migrations.AddIndex(
            model_name="socialaccount",
            index=models.Index(fields=["provider", "external_id"], name="accounts_so_provide_3a0cdb_idx"),
        ),
        migrations.AddIndex(
            model_name="socialaccount",
            index=models.Index(fields=["user", "provider"], name="accounts_so_user_id_3f2c3e_idx"),
        ),
    ]

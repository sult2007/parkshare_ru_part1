from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_logincode_attempts_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_password_change",
            field=models.DateTimeField(
                blank=True,
                help_text="Используется для инвалидирования сессий и JWT.",
                null=True,
                verbose_name="Последняя смена пароля",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Требовать второй фактор при входе.",
                verbose_name="MFA включена",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_method",
            field=models.CharField(
                choices=[
                    ("none", "Без MFA"),
                    ("totp", "TOTP (приложение)"),
                    ("sms", "SMS"),
                    ("email", "Email"),
                ],
                default="none",
                max_length=16,
                verbose_name="Метод MFA",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="mfa_secret",
            field=models.CharField(
                blank=True,
                help_text="Используется только для TOTP-приложений.",
                max_length=64,
                null=True,
                verbose_name="Секрет TOTP",
            ),
        ),
    ]

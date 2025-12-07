# Generated to add attempts/status to LoginCode for OTP hardening
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_socialaccount"),
    ]

    operations = [
        migrations.AddField(
            model_name="logincode",
            name="attempts",
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name="Попыток ввода"
            ),
        ),
        migrations.AddField(
            model_name="logincode",
            name="status",
            field=models.CharField(
                default="pending",
                help_text="pending/used/expired/blocked",
                max_length=16,
                verbose_name="Статус",
            ),
        ),
    ]

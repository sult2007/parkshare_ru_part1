from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("parking", "0006_booking_billing_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notify_booking_expiry", models.BooleanField(default=True, verbose_name="Напоминать о завершении брони")),
                ("notify_night_restrictions", models.BooleanField(default=False, verbose_name="Напоминать о ночных ограничениях")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Настройки уведомлений",
                "verbose_name_plural": "Настройки уведомлений",
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parking", "0007_notificationsettings"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="parkinglot",
            index=models.Index(fields=["city"], name="parkinglot_city_idx"),
        ),
        migrations.AddIndex(
            model_name="parkingspot",
            index=models.Index(fields=["status", "has_ev_charging", "is_covered"], name="spot_status_ev_cov_idx"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["start_at", "end_at"], name="booking_time_idx"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["billing_mode"], name="booking_billing_mode_idx"),
        ),
    ]

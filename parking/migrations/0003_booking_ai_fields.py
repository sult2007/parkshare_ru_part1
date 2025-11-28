from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("parking", "0002_parkinglot_stress_index_parkingspot_occupancy_7d"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="ai_snapshot",
            field=models.JSONField(blank=True, help_text="Данные решений AI (цены, доступность, риски)", null=True, verbose_name="AI snapshot"),
        ),
        migrations.AddField(
            model_name="booking",
            name="dynamic_pricing_applied",
            field=models.BooleanField(default=False, verbose_name="Динамическое ценообразование"),
        ),
    ]

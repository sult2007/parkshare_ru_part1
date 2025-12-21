from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("parking", "0009_remove_booking_booking_time_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("name", models.CharField(max_length=160, verbose_name="Название профиля")),
                ("destination_lat", models.FloatField(verbose_name="Широта назначения")),
                ("destination_lon", models.FloatField(verbose_name="Долгота назначения")),
                ("preferred_arrival_time", models.TimeField(blank=True, null=True, verbose_name="Предпочтительное время прибытия")),
                ("near_metro", models.BooleanField(default=False, verbose_name="Рядом с метро")),
                ("max_price_level", models.PositiveSmallIntegerField(default=0, help_text="0 — любой, 1..5 — ограничение по бюджету", verbose_name="Допустимый уровень цены")),
                ("requires_ev_charging", models.BooleanField(default=False, verbose_name="Нужна зарядка")),
                ("requires_covered", models.BooleanField(default=False, verbose_name="Требуется крытое место")),
                ("vehicle_type", models.CharField(blank=True, default="car", max_length=16, verbose_name="Тип транспорта")),
                ("notes", models.CharField(blank=True, max_length=255, verbose_name="Заметки")),
                ("last_used_at", models.DateTimeField(blank=True, null=True, verbose_name="Последний запуск")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="planner_profiles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Профиль планировщика",
                "verbose_name_plural": "Профили планировщика",
                "ordering": ("-updated_at", "-created_at"),
            },
        ),
        migrations.CreateModel(
            name="PlannerRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("run_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Когда запущено")),
                ("arrival_at", models.DateTimeField(blank=True, null=True, verbose_name="Запрошенное время прибытия")),
                ("destination_lat", models.FloatField(verbose_name="Широта назначения")),
                ("destination_lon", models.FloatField(verbose_name="Долгота назначения")),
                ("selected_lot_id", models.CharField(blank=True, max_length=64, verbose_name="Выбранный лот")),
                ("predicted_occupancy", models.FloatField(blank=True, null=True, verbose_name="Прогноз занятости")),
                ("walk_time_minutes", models.PositiveIntegerField(blank=True, null=True, verbose_name="Время пешком, мин")),
                ("confidence", models.FloatField(blank=True, null=True, verbose_name="Уверенность")),
                ("response", models.JSONField(blank=True, default=dict, verbose_name="Ответ сервиса")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="parking.plannerprofile")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="planner_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Запуск планировщика",
                "verbose_name_plural": "Запуски планировщика",
                "ordering": ("-run_at",),
            },
        ),
    ]

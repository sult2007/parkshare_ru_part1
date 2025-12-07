# Generated for FeatureFlag/ApiKey/AuditLog models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
                ("name", models.CharField(max_length=128)),
                ("prefix", models.CharField(db_index=True, max_length=8)),
                ("key_hash", models.CharField(db_index=True, max_length=128)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "API-ключ",
                "verbose_name_plural": "API-ключи",
            },
        ),
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
                ("name", models.CharField(max_length=64, unique=True)),
                ("description", models.TextField(blank=True)),
                ("enabled", models.BooleanField(default=False)),
                ("rollout_percentage", models.PositiveSmallIntegerField(default=100, help_text="0-100, deterministic по пользователю")),
                ("conditions", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "Фича-флаг",
                "verbose_name_plural": "Фича-флаги",
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
                ("action", models.CharField(max_length=128)),
                ("target_type", models.CharField(blank=True, max_length=64)),
                ("target_id", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Аудит",
                "verbose_name_plural": "Аудит-лог",
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action"], name="core_audit_action_6abf09_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["target_type", "target_id"], name="core_audit_target__e9a95a_idx"),
        ),
    ]

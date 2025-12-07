from django.contrib import admin

from .models import ApiKey, AuditLog, FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "rollout_percentage", "updated_at")
    search_fields = ("name",)
    list_filter = ("enabled",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "revoked_at", "last_used_at", "created_at")
    search_fields = ("name", "prefix")
    list_filter = ("revoked_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "created_at")
    search_fields = ("action", "target_type", "target_id")
    list_filter = ("action",)

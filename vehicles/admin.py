# vehicles/admin.py

from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("label", "owner", "vehicle_type", "created_at")
    list_filter = ("vehicle_type", "created_at")
    search_fields = ("label", "owner__username")
    readonly_fields = ("plate_hash", "created_at")

    def has_view_or_change_permission(self, request, obj=None):
        """
        В админку по умолчанию имеет доступ только персонал,
        так что дополнительных ограничений не вводим.
        """
        return super().has_view_or_change_permission(request, obj)

# backend/parking/admin.py

from django.contrib import admin

from .models import Booking, Complaint, ParkingLot, ParkingSpot, WaitlistEntry


@admin.register(ParkingLot)
class ParkingLotAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "owner", "parking_type", "is_active", "is_approved")
    list_filter = ("city", "parking_type", "is_active", "is_approved")
    search_fields = ("name", "city", "address", "owner__username")
    autocomplete_fields = ("owner",)


@admin.register(ParkingSpot)
class ParkingSpotAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "lot",
        "vehicle_type",
        "is_covered",
        "has_ev_charging",
        "status",
        "hourly_price",
    )
    list_filter = (
        "vehicle_type",
        "is_covered",
        "has_ev_charging",
        "status",
        "lot__city",
    )
    search_fields = ("name", "lot__name", "lot__city")
    autocomplete_fields = ("lot",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "spot",
        "user",
        "booking_type",
        "status",
        "start_at",
        "end_at",
        "total_price",
        "is_paid",
    )
    list_filter = ("booking_type", "status", "start_at", "spot__lot__city")
    search_fields = ("spot__name", "spot__lot__name", "user__username")
    autocomplete_fields = ("spot", "user", "vehicle")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "spot", "status", "auto_book", "created_at")
    list_filter = ("status", "auto_book", "created_at")
    search_fields = ("user__username", "spot__name")
    autocomplete_fields = ("user", "spot")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "category", "status", "created_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("author__username", "description")
    autocomplete_fields = ("author", "booking", "spot")

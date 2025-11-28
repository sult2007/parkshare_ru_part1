from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "payer",
        "provider",
        "provider_payment_id",
        "amount",
        "currency",
        "status",
        "success",
        "failure",
        "created_at",
    )
    list_filter = (
        "provider",
        "status",
        "success",
        "failure",
        "created_at",
    )
    search_fields = ("provider_payment_id", "booking__id", "payer__username")
    autocomplete_fields = ("booking", "payer")

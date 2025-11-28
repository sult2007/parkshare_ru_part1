from django.contrib import admin

from .models import ChatFeedback, ChatMessage, ChatSession, DeviceProfile, UiEvent


@admin.register(DeviceProfile)
class DeviceProfileAdmin(admin.ModelAdmin):
    list_display = ("device_id", "user", "layout_profile", "theme", "created_at")
    search_fields = ("device_id", "user__username")


@admin.register(UiEvent)
class UiEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "device_profile", "created_at")
    list_filter = ("event_type",)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "last_activity_at")
    search_fields = ("id", "user__username")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("text",)


@admin.register(ChatFeedback)
class ChatFeedbackAdmin(admin.ModelAdmin):
    list_display = ("message", "rating", "created_at")
    list_filter = ("rating",)

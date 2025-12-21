# core/context_processors.py

from __future__ import annotations

from django.conf import settings


def global_settings(request):
    """
    Глобальные настройки, которые нужны во всех шаблонах:
    регион, карта, ключи и дефолтный центр.
    """
    return {
        "REGION_PROFILE": getattr(settings, "REGION_PROFILE", "RU"),
        "PLATFORM_MODE": getattr(settings, "PLATFORM_MODE", "RU"),
        "MAP_PROVIDER": getattr(settings, "MAP_PROVIDER", "yandex"),
        "MAP_PROVIDER_FALLBACK": getattr(settings, "MAP_PROVIDER_FALLBACK", "leaflet"),
        "YANDEX_MAP_API_KEY": getattr(settings, "YANDEX_MAP_API_KEY", ""),
        "MAPBOX_TOKEN": getattr(settings, "MAPBOX_TOKEN", ""),
        "MAP_DEFAULT_CENTER": getattr(
            settings,
            "MAP_DEFAULT_CENTER",
            [55.75, 37.61],
        ),
        "MAP_DEFAULT_ZOOM": getattr(settings, "MAP_DEFAULT_ZOOM", 11),
        "ENABLE_AI_CHAT": getattr(settings, "ENABLE_AI_CHAT", False),
    }

from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # ВАЖНО: здесь должен быть реальный путь до пакета приложения
    # Папка называется "ai", лежит в корне проекта -> name = "ai"
    name = "ai"
    verbose_name = "AI и рекомендации ParkShare"

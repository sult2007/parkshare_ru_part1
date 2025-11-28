# backend/backend/config/celery.py

from __future__ import annotations

import os

from celery import Celery


# Устанавливаем DJANGO_SETTINGS_MODULE до импорта Django.
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module:
    # Позволяет запускать Celery локально без эксплицитного экспорта переменной.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.local")

# Создаём Celery-приложение, конфигурацию читаем из Django settings с префиксом CELERY_.
app = Celery("backend")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Авто-обнаружение tasks.py во всех Django-приложениях.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self) -> None:
    print(f"Debug task: Request: {self.request!r}")

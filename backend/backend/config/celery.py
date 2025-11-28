# backend/backend/config/celery.py

from __future__ import annotations

import os

from celery import Celery


# 1) Проверяем, что DJANGO_SETTINGS_MODULE задан извне
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module:
    raise RuntimeError(
        "DJANGO_SETTINGS_MODULE не задан. "
        "Укажи backend.settings.local (dev) или backend.settings.production (prod) "
        "в переменных окружения (например, в .env или unit-файле systemd)."
    )

# 2) Создаём Celery-приложение
app = Celery("backend")

# 3) Читаем конфиг из Django settings, все переменные с префиксом CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# 4) Авто-обнаружение tasks.py во всех django-приложениях
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self) -> None:
    print(f"Debug task: Request: {self.request!r}")

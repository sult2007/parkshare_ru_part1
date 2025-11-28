"""Django config package for ASGI/WSGI and Celery app exposure."""

import os

# Гарантируем, что Celery и Django получают настройки даже при запуске воркеров напрямую.
# Используем полный путь, чтобы избежать ModuleNotFoundError при вызове Celery/uvicorn.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings.local")

from .celery import app as celery_app  # noqa: E402

__all__ = ("celery_app",)
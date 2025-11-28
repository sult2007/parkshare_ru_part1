"""Django config package for ASGI/WSGI and Celery app exposure."""

import os

# Гарантируем, что Celery и Django получают настройки даже при запуске воркеров напрямую.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.local")

from .celery import app as celery_app  # noqa: E402

__all__ = ("celery_app",)

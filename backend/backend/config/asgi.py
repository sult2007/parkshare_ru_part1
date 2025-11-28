import os

from django.core.asgi import get_asgi_application

settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module:
    raise RuntimeError(
        "DJANGO_SETTINGS_MODULE не задан. "
        "Укажи backend.backend.settings.local (dev) или backend.backend.settings.production (prod)."
    )

application = get_asgi_application()


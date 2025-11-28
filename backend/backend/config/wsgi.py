import os

from django.core.wsgi import get_wsgi_application

settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module:
    raise RuntimeError(
        "DJANGO_SETTINGS_MODULE не задан. "
        "Укажи backend.settings.local (dev) или backend.settings.production (prod)."
    )

application = get_wsgi_application()


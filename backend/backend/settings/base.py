import os
from datetime import timedelta
from pathlib import Path
from typing import List

import environ

from .regions import REGION_PROFILES

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

# BASE_DIR — корень репозитория: C:\Users\Sultan\Downloads\parkshare_ru_part1
BASE_DIR = Path(__file__).resolve().parents[3]

# Тут главная правка: больше не уходим на уровень выше
PROJECT_ROOT = BASE_DIR  # C:\Users\Sultan\Downloads\parkshare_ru_part1


# ---------------------------------------------------------------------------
# Окружение
# ---------------------------------------------------------------------------

env = environ.Env(
    DEBUG=(bool, False),
)

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

DEBUG: bool = env.bool("DEBUG", default=False)
# ОБЯЗАТЕЛЬНО: ключ только из переменной окружения / .env
SECRET_KEY: str = env("SECRET_KEY", default=env("DJANGO_SECRET_KEY", default=""))
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required. Set SECRET_KEY in environment.")

ALLOWED_HOSTS: List[str] = env.list(
    "ALLOWED_HOSTS", default=["localhost", "127.0.0.1"]
)

# Маркет/регион: RU — по умолчанию, GLOBAL — международный профиль.
PLATFORM_MODE: str = env("PLATFORM_MODE", default="RU").upper()

# ---------------------------------------------------------------------------
# Региональные профили / карты
# ---------------------------------------------------------------------------

REGION_PROFILE: str = env("REGION_PROFILE", default="RU")
REGION = REGION_PROFILES.get(REGION_PROFILE, REGION_PROFILES["RU"])

# Провайдер карты можно переопределить через MAP_PROVIDER,
# иначе берём primary из профиля.
MAP_PROVIDER: str = env("MAP_PROVIDER", default=REGION["maps"]["primary"])
MAP_PROVIDER_FALLBACK: str = env(
    "MAP_PROVIDER_FALLBACK", default=REGION["maps"].get("fallback", "leaflet")
)
YANDEX_MAP_API_KEY: str = env("YANDEX_MAP_API_KEY", default="")
MAPBOX_TOKEN: str = env("MAPBOX_TOKEN", default="")

MAP_DEFAULT_CENTER = REGION["maps"].get("default_center", [55.75, 37.61])
MAP_DEFAULT_ZOOM = REGION["maps"].get("default_zoom", 11)

# ---------------------------------------------------------------------------
# Приложения
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Сторонние
    "rest_framework",
    "corsheaders",
    "django_cryptography",
    "drf_spectacular",

    # Проектные
    "accounts",
    "vehicles",
    "parking",
    "payments",
    "ai",
    "core",
]

MIDDLEWARE = [
    "core.middleware.RateLimitMiddleware",
    "core.metrics.RequestMetricsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "core.middleware.MaintenanceModeMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.backend.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Глобальные настройки ParkShare: регион, карта и т.д.
                "core.context_processors.global_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.backend.config.wsgi.application"
ASGI_APPLICATION = "backend.backend.config.asgi.application"

# ---------------------------------------------------------------------------
# Базы данных
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

# Если используем PostgreSQL — переключаемся на PostGIS
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# Опциональный read-replica для разгрузки чтения (RDS read replicas и т.п.).
DATABASE_REPLICA_URL = env("DATABASE_REPLICA_URL", default="")
if DATABASE_REPLICA_URL:
    DATABASES["replica"] = env.db("DATABASE_REPLICA_URL")
    if DATABASES["replica"]["ENGINE"] == "django.db.backends.postgresql":
        DATABASES["replica"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# DB router отправляет чтение в реплику, если она настроена.
DATABASE_ROUTERS = (
    ["core.db_router.ReadReplicaRouter"] if "replica" in DATABASES else []
)

# ---------------------------------------------------------------------------
# Пользователь / аутентификация
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---------------------------------------------------------------------------
# Локализация
# ---------------------------------------------------------------------------

LANGUAGE_CODE = env("LANGUAGE_CODE", default="ru-ru")
TIME_ZONE = env("TIME_ZONE", default="Europe/Moscow")
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Статика / медиа
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# PWA
# ---------------------------------------------------------------------------

PWA_APP_NAME = "ParkShare RU"
PWA_APP_SHORT_NAME = "ParkShare"
PWA_THEME_COLOR = "#0d6efd"
PWA_BACKGROUND_COLOR = "#050816"

# ---------------------------------------------------------------------------
# DRF / OpenAPI
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ParkShare RU API",
    "DESCRIPTION": "API сервиса бронирования парковочных мест ParkShare RU.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "UPDATE_LAST_LOGIN": True,
}

# ---------------------------------------------------------------------------
# Redis / Celery
# ---------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "expire_unpaid_bookings": {
        "task": "parking.tasks.expire_unpaid_bookings",
        "schedule": 60 * 10,  # каждые 10 минут
    },
    "update_ai_models": {
        "task": "ai.tasks.update_models",
        "schedule": 60 * 60,  # раз в час
    },
    "check_stale_payments": {
        "task": "payments.tasks.check_stale_payments",
        "schedule": 60 * 15,  # каждые 15 минут
    },
}

# ---------------------------------------------------------------------------
# Логи
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "parkshare": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ai": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "services": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Feature / maintenance flags
# ---------------------------------------------------------------------------

MAINTENANCE_MODE = env.bool("MAINTENANCE_MODE", default=False)
ENABLE_EXPERIMENTAL_ASSISTANT = env.bool("ENABLE_EXPERIMENTAL_ASSISTANT", default=True)
ENABLE_AB_VARIANTS = env.bool("ENABLE_AB_VARIANTS", default=True)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="ParkShare RU <noreply@example.com>",
)
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# ---------------------------------------------------------------------------
# Безопасность (базовый уровень, детали переопределяются в production.py)
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CONTENT_SECURITY_POLICY = env(
    "CONTENT_SECURITY_POLICY",
    default=(
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self' https: data:; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    ),
)

if DEBUG:
    X_FRAME_OPTIONS = "SAMEORIGIN"
    CONTENT_SECURITY_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https: http://localhost:3000 http://127.0.0.1:3000; "
        "font-src 'self' https: data:; "
        "frame-src 'self' http://localhost:3000 http://127.0.0.1:3000; "
        "frame-ancestors 'self'; "
        "form-action 'self';"
    )

REFERRER_POLICY = env("REFERRER_POLICY", default="strict-origin-when-cross-origin")
PERMISSIONS_POLICY = env(
    "PERMISSIONS_POLICY",
    # Разрешаем геолокацию только себе, остальное по умолчанию запрещено
    default="geolocation=(self), camera=(), microphone=(), payment=()",
)

# COOP / COEP / CORP — по умолчанию выключены, чтобы не ломать
# внешние ресурсы (карты, CDN, платёжные виджеты и т.п.).
# Если понадобится SharedArrayBuffer и строгая изоляция — включишь
# явно через .env.
CROSS_ORIGIN_OPENER_POLICY = env(
    "CROSS_ORIGIN_OPENER_POLICY", default=""
)
CROSS_ORIGIN_EMBEDDER_POLICY = env(
    "CROSS_ORIGIN_EMBEDDER_POLICY", default=""
)
CROSS_ORIGIN_RESOURCE_POLICY = env(
    "CROSS_ORIGIN_RESOURCE_POLICY", default=""
)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_CACHE = env("RATE_LIMIT_CACHE", default="default")
RATE_LIMIT_WINDOW = env.int("RATE_LIMIT_WINDOW", default=60)
RATE_LIMIT_REQUESTS = env.int("RATE_LIMIT_REQUESTS", default=120)
RATE_LIMIT_WHITELIST = env.list(
    "RATE_LIMIT_WHITELIST", default=["127.0.0.1", "::1"]
)

# ---------------------------------------------------------------------------
# django-cryptography
# ---------------------------------------------------------------------------

DJANGO_CRYPTography_KEY = SECRET_KEY

# ---------------------------------------------------------------------------
# Бизнес-настройки
# ---------------------------------------------------------------------------

VEHICLE_PLATE_SALT = env("VEHICLE_PLATE_SALT", default="change_me_vehicle_salt")

YOOKASSA_SHOP_ID = env("YOOKASSA_SHOP_ID", default="")
YOOKASSA_SECRET_KEY = env("YOOKASSA_SECRET_KEY", default="")
YOOKASSA_RETURN_URL = env("YOOKASSA_RETURN_URL", default="")
YOOKASSA_WEBHOOK_SECRET = env("YOOKASSA_WEBHOOK_SECRET", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
DEFAULT_PAYMENT_PROVIDER = env(
    "PAYMENT_PROVIDER",
    default="yookassa" if PLATFORM_MODE == "RU" else "stripe",
)

SERVICE_COMMISSION_PERCENT = env.int("SERVICE_COMMISSION_PERCENT", default=10)

# This block is appended near the bottom of base.py, after business and AI settings.
# ---------------------------------------------------------------------------
# OTP / SMS / Metrics / Social auth
# ---------------------------------------------------------------------------

AUTH_OTP_CODE_TTL_SECONDS = env.int("AUTH_OTP_CODE_TTL_SECONDS", default=600)
AUTH_OTP_WINDOW_SECONDS = env.int("AUTH_OTP_WINDOW_SECONDS", default=600)
AUTH_OTP_MAX_PER_WINDOW = env.int("AUTH_OTP_MAX_PER_WINDOW", default=5)
AUTH_OTP_MAX_ATTEMPTS = env.int("AUTH_OTP_MAX_ATTEMPTS", default=5)

SMS_PROVIDER = env.str("SMS_PROVIDER", default="console")
SMS_DEFAULT_FROM = env.str("SMS_DEFAULT_FROM", default="ParkShare")

ENABLE_METRICS = env.bool("ENABLE_METRICS", default=True)

SOCIAL_OAUTH_CONFIG = {
    "vk": {
        "client_id": env.str("VK_OAUTH_CLIENT_ID", default=""),
        "client_secret": env.str("VK_OAUTH_CLIENT_SECRET", default=""),
    },
    "yandex": {
        "client_id": env.str("YANDEX_OAUTH_CLIENT_ID", default=""),
        "client_secret": env.str("YANDEX_OAUTH_CLIENT_SECRET", default=""),
    },
    "google": {
        "client_id": env.str("GOOGLE_OAUTH_CLIENT_ID", default=""),
        "client_secret": env.str("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
    },
}
SOCIAL_OAUTH_TEST_MODE = env.bool("SOCIAL_OAUTH_TEST_MODE", default=False)




# ---------------------------------------------------------------------------
# Кэш по умолчанию — in-memory (в продакшене можно переключить на Redis)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "parkshare_cache",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

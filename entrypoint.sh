#!/bin/sh
set -e

# Если DJANGO_SETTINGS_MODULE не задан, по умолчанию считаем, что это прод.
: "${DJANGO_SETTINGS_MODULE:=backend.settings.production}"
export DJANGO_SETTINGS_MODULE

echo "Using DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}"

# Миграции
python backend/manage.py migrate --noinput

# Сбор статики
python backend/manage.py collectstatic --noinput

# Запуск gunicorn
exec gunicorn backend.config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}"

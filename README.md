# ParkShare RU — Django + PWA

Единственная продакшн-UI поверхность — Django-шаблоны (карта, ассистент, бронирования, PWA).

## Архитектура (коротко)
- Backend: Django + DRF (parking/search/booking/payments/metrics/notifications).
- Карта: Yandex/Leaflet абстракция, без Google Maps.
- Ассистент: /api/chat/ (streaming) + ai/tools.py (search/booking/favorite/prefs), preference-aware.
- Биллинг: booking_confirm с billing_mode (pay_as_you_go 15м слоты, prepaid_block 2/4/24h), бизнес-флаг и отчёты.
- Платежи/промо/награды: PaymentMethod, PromoReward, UserLevel/Badge.
- PWA: сервис-воркер, offline shell, onboarding, push, NotificationSettings + send_expiry_notifications.
- Метрики/A-B: UiEvent/Booking/ChatSession, staff dashboard (metrics) с 7/30-дневным срезом и вариантами A/B.

## Запуск (локально)
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Настройки
- Используйте `DJANGO_SETTINGS_MODULE` (`backend.backend.settings.local`/`production`) для выбора профиля.
- Общие параметры лежат в `backend/backend/settings/base.py`; dev/prod наследуют.

## Уведомления
- Включение флагов: профиль → уведомления.
- Отправка напоминаний: `python manage.py send_expiry_notifications --minutes 30`

## Тесты
```bash
python manage.py test
```

## Линт/типизация
```bash
ruff check .
mypy ai parking
```

## Полезные команды
- `make test` — все тесты
- `make lint` — ruff
- `make typecheck` — mypy на основных пакетах
- `python manage.py send_expiry_notifications --minutes 30` — напоминания о завершении брони
- health/ready: `/healthz`, `/readyz`

## Конфигурация (env)
- MAP_PROVIDER / YANDEX_MAP_API_KEY
- LLM_PROVIDER / LLM_API_URL / LLM_API_KEY (для ассистента)
- PUSH_PUBLIC_KEY / PUSH_PRIVATE_KEY (если используете WebPush)
- Billing/Payments: провайдеры/ключи (YooKassa и др.) из `.env`
- Флаги: MAINTENANCE_MODE, ENABLE_EXPERIMENTAL_ASSISTANT, ENABLE_AB_VARIANTS

## Основные ссылки
- Карта: `/`
- Полная карта: `/map/`
- Ассистент: `/assistant/`
- Бронирование: `/booking/confirm/`
- Платежи: `/payments/methods/`
- Предпочтения/уведомления: `/profile/settings/`
- Промокоды: `/promos/activate/`
- Бизнес-отчёты: `/business/reports/`
- Метрики (staff): `/admin/metrics-lite/`

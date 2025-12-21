# Auth, MFA и социальный вход

## Модель данных
- `accounts.User` расширен полями `display_name`, `mfa_enabled`, `mfa_method` (`none|totp|sms|email`), `mfa_secret`, `last_password_change`, `created_at/updated_at`.
- `AuthIdentity` — единая связь пользователя с провайдером (`email_magic`, `phone_sms`, `vk`, `yandex`, `google`): `provider_user_id`, опциональные `access_token/refresh_token/expires_at`, `metadata`. Уникальный ключ (`provider`, `provider_user_id`).
- `LoginCode` используется для OTP/многие факторы (`purpose=login/register/reset_password/mfa`).
- `SocialAccount` сохранён для обратной совместимости и UI, но привязка теперь дублируется в `AuthIdentity`.

## Потоки входа
- **OTP вход/регистрация**:
  - Запрос кода: `POST /auth/otp/request/` или `/api/auth/otp/request/` с `identifier` (email/телефон). Создаётся `LoginCode`, отправка через email/SMS, лимиты: `AUTH_OTP_WINDOW_SECONDS`, `AUTH_OTP_MAX_PER_WINDOW`.
  - Подтверждение: `POST /auth/otp/verify/` или `/api/auth/otp/verify/` с `identifier`, `code`, `purpose`. При успехе создаётся/обновляется `User` (email/phone заполняются), привязывается `AuthIdentity` (`email_magic` или `phone_sms`), выдаются JWT + httpOnly cookie. Если MFA включена и канал не удовлетворяет MFA, возвращается `mfa_required`.
- **Пароль**: классический логин через `/api/accounts/users/login/`; при включённой MFA возвращает `mfa_required` и ждёт `POST /auth/mfa/verify/`.
- **Проверка MFA**: `POST /auth/mfa/verify/` (или `/api/auth/mfa/verify/`) с `code`. TOTP через `pyotp`; SMS/email — последний неиспользованный `LoginCode` с `purpose=mfa`. Успех = полноценная сессия + JWT.
- **OAuth (VK/Яндекс/Google)**: `GET /auth/oauth/<provider>/start` → редирект на провайдера. Callback `/auth/oauth/<provider>/callback` обменивает `code`, тащит профиль, создаёт/линкует `AuthIdentity` и `SocialAccount`. MFA проверяется аналогично: при включении — редирект/ответ с `mfa_required`.

## Подключение/отключение MFA
- HTML: `/accounts/mfa/setup/` — выбор метода, генерация TOTP QR, ввод кода для активации, кнопка отключения.
- API: `/auth/mfa/setup/` (POST `{method}`) генерирует секрет/отправляет код; `/auth/mfa/activate/` (POST `{code}`) включает; `/auth/mfa/disable/` отключает.
- Для TOTP используется `pyotp.random_base32()` и otpauth:// URI из `accounts.utils.build_totp_uri`.

## Безопасность сессий и JWT
- При смене пароля (`change-password` API и HTML) обновляется `last_password_change`, удаляются чужие сессии пользователя и ротируется текущий ключ.
- Кастомный `accounts.authentication.JWTAuthentication` отклоняет токены с `iat` старше `last_password_change`.
- В продакшене включены защищённые cookie-флаги: secure, httpOnly (кроме CSRF), samesite=Lax.

## Клиентское хранение
- Вместо открытого `localStorage` данные пользователя шифруются в `frontend/next-app/lib/authStorage.ts` (AES-GCM, ключ `NEXT_PUBLIC_AUTH_ENC_KEY`).
- При ошибке дешифрования хранилище очищается автоматически.

## Социальный вход UI
- **Next.js**: компонент `SocialLoginButtons` с полноширинными баннерами Google/VK/Yandex, подсказками о правах и состоянием загрузки.
- **Django PWA**: на странице входа брендовские баннеры, подсказки, блок про недоступность провайдеров.
- MFA запрашивается после любого OAuth, если включена.

## Как включить MFA для пользователя
1. В профиле на сайте откройте `/accounts/mfa/setup/`, выберите метод.
2. Для TOTP — отсканируйте QR, введите код, дождитесь подтверждения.
3. Для SMS/email — отправьте код и подтвердите его.
4. При потере устройства отключите MFA тем же экраном и подключите заново.

## Настройка переменных
- Базовые: `SECRET_KEY`, `DJANGO_SETTINGS_MODULE`, `DATABASE_URL`, `REDIS_URL`.
- OTP/MFA: `AUTH_OTP_CODE_TTL_SECONDS`, `AUTH_OTP_WINDOW_SECONDS`, `AUTH_OTP_MAX_PER_WINDOW`, `AUTH_OTP_MAX_ATTEMPTS`.
- SMS: `SMS_PROVIDER` (`console` по умолчанию), плюс провайдер‑специфичные ключи.
- Email: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS/SSL`.
- OAuth ключи: `VK_OAUTH_CLIENT_ID/SECRET`, `YANDEX_OAUTH_CLIENT_ID/SECRET`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`; в dev включите `SOCIAL_OAUTH_TEST_MODE=true` чтобы использовать коды вида `test_<user>`.
- Frontend: `NEXT_PUBLIC_ENABLE_AI_CHAT` (по умолчанию false), `NEXT_PUBLIC_AUTH_ENC_KEY` — 32+ символа для AES-GCM.
- Куки и безопасность: `AUTH_ACCESS_COOKIE_AGE`, `AUTH_REFRESH_COOKIE_AGE`, `AUTH_COOKIE_SECURE`, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`.

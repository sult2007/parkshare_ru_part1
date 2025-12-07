# Auth, MFA и социальный вход

## Модель данных
- `accounts.User` расширен полями `mfa_enabled`, `mfa_method` (`none|totp|sms|email`), `mfa_secret`, `last_password_change`.
- `LoginCode.Purpose` содержит `mfa` для одноразовых кодов второго фактора.
- `SocialAccount` без изменений, но OAuth теперь учитывает MFA.

## Потоки входа
- **Пароль/OTP**: после первичной проверки мы не логиним сразу, если `mfa_enabled=True`. В сессии сохраняется `pre_auth_user_id`, `pre_auth_primary_ok`, `pre_auth_method`, `post_auth_redirect`. Ответ API содержит `mfa_required=true`.
- **Проверка MFA**: POST `/auth/mfa/verify/` (или `/api/auth/mfa/verify/`) с полем `code`. Для TOTP проверяется `mfa_secret` через `pyotp`; для SMS/email — последний неиспользованный `LoginCode` c `purpose=mfa`. При успехе создаётся полноценная сессия и JWT.
- **OAuth**: после успешного callback, если у пользователя включена MFA, происходит редирект на `/accounts/mfa/verify/` с сохранением `next` в сессии.

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
- `NEXT_PUBLIC_AUTH_ENC_KEY` — 32+ символа для AES-GCM на фронтенде.
- OAuth ключи: `VK_OAUTH_CLIENT_ID/SECRET`, `YANDEX_OAUTH_CLIENT_ID/SECRET`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`.
- OTP/MFA лимиты: `AUTH_OTP_CODE_TTL_SECONDS`, `AUTH_OTP_WINDOW_SECONDS`, `AUTH_OTP_MAX_PER_WINDOW`, `AUTH_OTP_MAX_ATTEMPTS`.

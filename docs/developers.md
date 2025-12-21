# ParkShare RU — Developer Guide

## Quick start (local)
- Python 3.11+, Node 18+, Redis.  
- `cp .env.example .env` and adjust DB/Redis. Ensure `NEXT_PUBLIC_ENABLE_AI_CHAT=false` unless you re-enable chat.  
- Install backend deps: `pip install -r requirements.txt`. Run migrations: `python manage.py migrate`. Start server: `python manage.py runserver`.
- Frontend: `cd frontend/next-app && npm install && npm run dev`.
- Local ML/FastAPI services (optional for planner heuristics): `python api_server.py` or start via docker-compose.

## Auth & OTP
- Email/phone OTP: `/api/auth/otp/request` then `/api/auth/otp/verify`; creates `AuthIdentity` (`email_magic`/`phone_sms`). Configure rate limits via `AUTH_OTP_*` env vars.
- Social OAuth (VK/Yandex/Google): start at `/auth/oauth/<provider>/start`. Use `SOCIAL_OAUTH_TEST_MODE=true` with codes `test_<user>` in dev. OAuth secrets come from env (`VK_OAUTH_CLIENT_ID`, etc.).
- Frontend storage uses AES-GCM; set `NEXT_PUBLIC_AUTH_ENC_KEY` (32+ chars).

## Smart Parking Planner
- Endpoints: `GET/POST /api/planner/profiles/` (auth), `POST /api/planner/plan/` (auth).
- Django UI: `/planner/` (templates/parking/planner.html). Next.js UI: `/planner` route.
- Current recommendation uses simple proximity/occupancy heuristic; integrate with ML services by calling them inside `parking/views_planner.py`.

## Feature flags
- `ENABLE_AI_CHAT` (backend) / `NEXT_PUBLIC_ENABLE_AI_CHAT` (frontend) — chat off by default. Keep disabled unless configured.

## Testing
- Backend: `python manage.py test` (covers auth/OTP/OAuth, planner smoke tests, bookings, etc.).
- Frontend: `cd frontend/next-app && npm test` for component/Jest tests; `npm run lint`/`npm run typecheck`.

## Production notes
- Set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, secure cookies (`AUTH_COOKIE_SECURE=True`), real DB/Redis URLs.
- Configure OAuth secrets, email SMTP, SMS provider keys, payment providers (YooKassa/Stripe) via env only.
- Run migrations and `collectstatic` in CI/CD; ensure service/health checks (`/healthz`, `/readyz`) are wired in Kubernetes/Compose.

from __future__ import annotations

import hashlib
from typing import Optional

from django.conf import settings
from django.utils.crypto import get_random_string

from core.utils import normalize_phone as core_normalize_phone


def normalize_email(email: Optional[str]) -> str:
    if not email:
        return ""
    return email.strip().lower()


def normalize_phone(phone: Optional[str]) -> str:
    return core_normalize_phone(phone)


def _hash_value(kind: str, value: str) -> str:
    payload = f"{kind}:{value}:{settings.SECRET_KEY}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email:
        return ""
    return _hash_value("email", email)


def hash_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return ""
    return _hash_value("phone", phone)


def hash_code(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    return _hash_value("otp", code)


def generate_username(prefix: str = "user") -> str:
    return f"{prefix}_{get_random_string(10)}"


def invalidate_other_sessions(user, keep_session_key: str | None = None) -> None:
    from django.contrib.sessions.models import Session  # локальный импорт
    from django.utils import timezone

    now = timezone.now()
    for session in Session.objects.filter(expire_date__gt=now):
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) != str(user.pk):
            continue
        if keep_session_key and session.session_key == keep_session_key:
            continue
        session.delete()


def build_totp_uri(username: str, issuer: str, secret: str) -> str:
    from urllib.parse import quote

    label = quote(f"{issuer}:{username}")
    issuer_q = quote(issuer)
    secret_q = quote(secret)
    return f"otpauth://totp/{label}?secret={secret_q}&issuer={issuer_q}&digits=6"

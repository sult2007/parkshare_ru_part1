from __future__ import annotations

import hashlib
from typing import Optional

from django.conf import settings
from django.utils.crypto import get_random_string

from core.utils import normalize_phone as core_normalize_phone


def normalize_email(email: Optional[str]) -> str:
    """
    Приводим email к каноничному виду:
    - trim пробелы;
    - приводим к нижнему регистру.
    """
    if not email:
        return ""
    return email.strip().lower()


def normalize_phone(phone: Optional[str]) -> str:
    """Проксируем в core.utils.normalize_phone, чтобы не дублировать логику."""
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
    """
    Хэширует одноразовый код (SMS / email OTP).

    Отдельный namespace «otp», чтобы независимая ротация не затрагивала
    хэши email/phone.
    """
    code = (code or "").strip()
    if not code:
        return ""
    return _hash_value("otp", code)


def generate_username(prefix: str = "user") -> str:
    """Быстрый генератор уникоподобного username для passwordless-флоу."""
    return f"{prefix}_{get_random_string(10)}"

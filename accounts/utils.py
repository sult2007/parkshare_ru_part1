from __future__ import annotations

from typing import Optional
import hashlib

from django.conf import settings

from core.utils import normalize_phone


def normalize_email(email: Optional[str]) -> str:
    """
    Приводим email к каноничному виду:
    - str.strip()
    - .lower()
    """
    if not email:
        return ""
    return email.strip().lower()


def _hash_value(kind: str, value: str) -> str:
    """
    Внутренняя функция хэширования с солью на базе SECRET_KEY.
    kind: 'email' или 'phone' (на будущее можно расширять).
    """
    if not value:
        return ""
    salted = f"{settings.SECRET_KEY}:{kind}:{value}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def hash_email(email: str) -> str:
    """
    Хэш нормализованного email.
    В БД хранится только хэш, сам email — в зашифрованном поле.
    """
    normalized = normalize_email(email)
    if not normalized:
        return ""
    return _hash_value("email", normalized)


def hash_phone(phone: str) -> str:
    """
    Хэш нормализованного телефона.
    В БД хранится только хэш, сам телефон — в зашифрованном поле.
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return ""
    return _hash_value("phone", normalized)

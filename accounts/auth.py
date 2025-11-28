# accounts/auth.py

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from core.utils import normalize_phone
from .utils import normalize_email, hash_email, hash_phone

User = get_user_model()


def _get_first_or_none(qs):
    try:
        return qs.first()
    except Exception:
        return None


def find_user_by_identifier(identifier: str) -> Optional[User]:
    """
    Ищем пользователя по:
    1) username (регистронезависимо);
    2) email (нормализованный, через email_hash);
    3) телефону (нормализованный, через phone_hash).

    В БД никогда не фильтруем по зашифрованным полям.
    """
    if not identifier:
        return None

    ident = identifier.strip()
    qs = User.objects.filter(is_active=True)

    # 1) Логин (username)
    try:
        return qs.get(username__iexact=ident)
    except User.DoesNotExist:
        pass
    except User.MultipleObjectsReturned:
        return _get_first_or_none(qs.filter(username__iexact=ident).order_by("date_joined"))

    # 2) Email
    if "@" in ident:
        email = normalize_email(ident)
        if not email:
            return None
        email_hash = hash_email(email)
        if not email_hash:
            return None
        try:
            return qs.get(email_hash=email_hash)
        except User.DoesNotExist:
            pass
        except User.MultipleObjectsReturned:
            return _get_first_or_none(qs.filter(email_hash=email_hash).order_by("date_joined"))
        return None

    # 3) Телефон
    phone = normalize_phone(ident)
    if not phone:
        return None
    phone_hash = hash_phone(phone)
    if not phone_hash:
        return None

    try:
        return qs.get(phone_hash=phone_hash)
    except User.DoesNotExist:
        return None
    except User.MultipleObjectsReturned:
        return _get_first_or_none(qs.filter(phone_hash=phone_hash).order_by("date_joined"))

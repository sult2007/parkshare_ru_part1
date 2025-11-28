# backend/core/utils.py

import hashlib
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings


def hash_plate_digits(plate: str) -> str:
    """
    Хэширует только цифры госномера с солью (SHA‑256).
    Буквы и пробелы игнорируются.
    В БД мы сохраняем только этот хэш.
    """
    if not plate:
        return ""
    digits = "".join(ch for ch in plate if ch.isdigit())
    salted = f"{settings.VEHICLE_PLATE_SALT}:{digits}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def mask_plate_for_display(plate: str) -> str:
    """
    Возвращает маску номера для отображения (если вдруг нужно выводить).
    Фактический номер мы нигде не храним, поэтому функция может применяться
    только к введённому пользователем значению до хэширования.
    """
    digits = "".join(ch for ch in plate if ch.isdigit())
    if not digits:
        return ""
    if len(digits) <= 2:
        return "*" * len(digits)
    return "*" * (len(digits) - 2) + digits[-2:]


def normalize_phone(phone: Optional[str]) -> str:
    """
    Нормализация телефона:

    - убираем все символы кроме цифр и '+';
    - для РФ приводим к формату +7XXXXXXXXXX, если возможно;
    - для остальных стран просто добавляем '+' перед цифрами.
    """
    if not phone:
        return ""
    raw = phone.strip()

    # Оставляем плюс только в начале
    plus = "+" if raw.startswith("+") else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ""

    # РФ: 10 или 11 цифр, начинающихся с 8/7
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits

    if plus or digits.startswith("7"):
        return "+" + digits
    return "+" + digits  # простой фолбэк


def haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Расстояние между двумя точками на сфере Земли (км).

    Используем для поиска парковок «рядом» без обязательной привязки
    к PostGIS (работает и на SQLite).
    """
    try:
        lat1_f = float(lat1)
        lon1_f = float(lon1)
        lat2_f = float(lat2)
        lon2_f = float(lon2)
    except (TypeError, ValueError):
        return 0.0

    radius = 6371.0  # км

    d_lat = math.radians(lat2_f - lat1_f)
    d_lon = math.radians(lon2_f - lon1_f)
    r_lat1 = math.radians(lat1_f)
    r_lat2 = math.radians(lat2_f)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def parse_float(value: Optional[str]) -> Optional[float]:
    """
    Аккуратно парсит строку в float, возвращая None при ошибке.
    Удобно для работы с query‑параметрами API.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_price(value: float | Decimal, step: float = 10.0) -> float:
    """
    Округляет цену к ближайшему шагу (step), по умолчанию — 10 ₽.

    Используется в AI-модуле ценообразования.
    """
    if step <= 0:
        return float(Decimal(str(value)).quantize(Decimal("0.01")))

    v = Decimal(str(value))
    step_dec = Decimal(str(step))
    scaled = (v / step_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    result = scaled * step_dec
    return float(result)

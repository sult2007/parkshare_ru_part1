from __future__ import annotations

"""
Региональные профили ParkShare.

RU — основной профиль (ParkShare RU) с Яндекс.Картами, российскими платёжками
и провайдерами аутентификации.

EU/US — заготовки для будущих рынков.
"""

REGION_PROFILES = {
    "RU": {
        "code": "RU",
        "name": "Russia",
        "maps": {
            # Важно: логические идентификаторы, а не "маркетинговые" названия
            "primary": "yandex",
            "fallback": "leaflet",
            "language": "ru_RU",
            "default_center": [55.75, 37.61],  # Москва
            "default_zoom": 11,
        },
        "payments": {
            "required": [
                "sberbank_online",
                "tinkoff",
                "yoomoney",
                "mir_pay",
                "qiwi",
            ],
        },
        "auth": [
            "gosuslugi",
            "vk_id",
            "yandex_id",
            "sber_id",
        ],
        "holidays": {
            "provider": "ru_holidays",
        },
    },
    "EU": {
        "code": "EU",
        "name": "European Union",
        "maps": {
            "primary": "leaflet",
            "fallback": "leaflet",
            "language": "en_US",
            "default_center": [52.52, 13.405],  # Берлин как условный центр
            "default_zoom": 11,
        },
        "payments": {
            "required": [
                "visa_mastercard",
            ],
        },
        "auth": ["email_password"],
        "holidays": {
            "provider": "eu_holidays",
        },
    },
    "US": {
        "code": "US",
        "name": "United States",
        "maps": {
            "primary": "leaflet",
            "fallback": "leaflet",
            "language": "en_US",
            "default_center": [40.7128, -74.0060],  # Нью-Йорк
            "default_zoom": 11,
        },
        "payments": {
            "required": [
                "visa_mastercard",
                "apple_pay",
                "google_pay",
            ],
        },
        "auth": ["email_password"],
        "holidays": {
            "provider": "us_holidays",
        },
    },
}

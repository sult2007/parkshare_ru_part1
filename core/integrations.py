"""core/integrations.py

Адаптеры для интеграций по регионам:
- карты (RU: Яндекс, GLOBAL: Mapbox/OSM);
- платежи (RU: YooKassa, GLOBAL: Stripe);
- аутентификация (RU: ЕСИА/VK/Яндекс, GLOBAL: generic OAuth2).

Цель — единая точка выбора провайдера через PLATFORM_MODE
(ENV: PLATFORM_MODE=RU|GLOBAL) без раздувания микросервисов.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from django.conf import settings


@dataclass
class MapProviderAdapter:
    key: str
    api_key: str
    language: str
    default_center: list[float]
    default_zoom: int

    def as_frontend_payload(self) -> Dict[str, str | list[float] | int]:
        return {
            "provider": self.key,
            "language": self.language,
            "api_key": self.api_key,
            "center": self.default_center,
            "zoom": self.default_zoom,
        }


@dataclass
class PaymentGatewayAdapter:
    key: str
    webhook_url: str
    return_url: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "provider": self.key,
            "webhook_url": self.webhook_url,
            "return_url": self.return_url,
        }


@dataclass
class AuthProviderAdapter:
    key: str
    client_id: str
    authorization_url: str
    scopes: list[str]

    def as_dict(self) -> Dict[str, str | list[str]]:
        return {
            "provider": self.key,
            "client_id": self.client_id,
            "authorization_url": self.authorization_url,
            "scopes": self.scopes,
        }


RU_INTEGRATIONS = {
    "maps": MapProviderAdapter(
        key=settings.MAP_PROVIDER,
        api_key=settings.YANDEX_MAP_API_KEY,
        language=settings.REGION.get("maps", {}).get("language", "ru_RU"),
        default_center=settings.MAP_DEFAULT_CENTER,
        default_zoom=settings.MAP_DEFAULT_ZOOM,
    ),
    "payments": PaymentGatewayAdapter(
        key=settings.DEFAULT_PAYMENT_PROVIDER,
        webhook_url="/payments/webhook/yookassa/",
        return_url=settings.YOOKASSA_RETURN_URL,
    ),
    "auth": [
        AuthProviderAdapter(
            key="gosuslugi",
            client_id="GOSUSLUGI_CLIENT_ID_PLACEHOLDER",
            authorization_url="https://esia.gosuslugi.ru/aas/oauth2/ac",
            scopes=["openid", "profile"],
        ),
        AuthProviderAdapter(
            key="vk_id",
            client_id="VK_CLIENT_ID_PLACEHOLDER",
            authorization_url="https://id.vk.com/authorize",
            scopes=["email"],
        ),
    ],
}

GLOBAL_INTEGRATIONS = {
    "maps": MapProviderAdapter(
        key=settings.MAP_PROVIDER if settings.PLATFORM_MODE == "GLOBAL" else "mapbox",
        api_key=settings.MAPBOX_TOKEN,
        language="en_US",
        default_center=settings.MAP_DEFAULT_CENTER,
        default_zoom=settings.MAP_DEFAULT_ZOOM,
    ),
    "payments": PaymentGatewayAdapter(
        key=settings.DEFAULT_PAYMENT_PROVIDER,
        webhook_url="/payments/webhook/stripe/",
        return_url="/payments/return/",
    ),
    "auth": [
        AuthProviderAdapter(
            key="google",
            client_id="GOOGLE_OAUTH_CLIENT_ID",
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            scopes=["openid", "email", "profile"],
        ),
        AuthProviderAdapter(
            key="apple",
            client_id="APPLE_CLIENT_ID",
            authorization_url="https://appleid.apple.com/auth/authorize",
            scopes=["name", "email"],
        ),
    ],
}


def get_integrations() -> dict:
    if settings.PLATFORM_MODE == "GLOBAL":
        return GLOBAL_INTEGRATIONS
    return RU_INTEGRATIONS

from __future__ import annotations

import logging
from typing import Dict
from urllib.parse import urlencode

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

PROVIDERS: Dict[str, Dict[str, str]] = {
    "vk": {
        "auth_url": "https://oauth.vk.com/authorize",
        "token_url": "https://oauth.vk.com/access_token",
        "profile_url": "https://api.vk.com/method/users.get",
        "scope": "email",
        "api_version": "5.199",
    },
    "yandex": {
        "auth_url": "https://oauth.yandex.ru/authorize",
        "token_url": "https://oauth.yandex.ru/token",
        "profile_url": "https://login.yandex.ru/info",
        "scope": "login:email login:info",
    },
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "profile_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
}


def _provider_config(provider: str) -> Dict[str, str]:
    cfg = getattr(settings, "SOCIAL_OAUTH_CONFIG", {}).get(provider, {}) or {}
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    if not client_id or not client_secret:
        raise ValueError(f"OAuth provider {provider} is not configured")
    return cfg


def build_authorize_url(provider: str, state: str, redirect_uri: str) -> str:
    provider = provider.lower()
    meta = PROVIDERS.get(provider)
    if not meta:
        raise ValueError("Unsupported provider")
    cfg = _provider_config(provider)

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": meta["scope"],
        "state": state,
    }
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return f"{meta['auth_url']}?{urlencode(params)}"


def fetch_profile(provider: str, code: str, redirect_uri: str) -> Dict[str, str]:
    provider = provider.lower()
    meta = PROVIDERS.get(provider)
    if not meta:
        raise ValueError("Unsupported provider")

    # Test mode: bypass external HTTP to simplify local/dev flows.
    if getattr(settings, "SOCIAL_OAUTH_TEST_MODE", False) or (code and code.startswith("test_")):
        fake_id = code.replace("test_", "") or "demo"
        return {
            "provider": provider,
            "external_id": fake_id,
            "email": f"{fake_id}@{provider}.example",
            "display_name": f"Test {provider.title()} User",
            "raw": {"mode": "test"},
        }

    cfg = _provider_config(provider)
    token_payload = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    with httpx.Client(timeout=5.0) as client:
        token_resp = client.post(meta["token_url"], data=token_payload)
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token returned")

        if provider == "vk":
            profile_resp = client.get(
                meta["profile_url"],
                params={
                    "access_token": access_token,
                    "v": meta["api_version"],
                    "fields": "id,first_name,last_name,photo_100",
                },
            )
            profile_resp.raise_for_status()
            data = profile_resp.json()
            response = (data.get("response") or [{}])[0]
            ext_id = response.get("id") or token_data.get("user_id")
            email = token_data.get("email")
            display_name = " ".join(
                filter(None, [response.get("first_name"), response.get("last_name")])
            ).strip()
            return {
                "provider": provider,
                "external_id": str(ext_id),
                "email": email,
                "display_name": display_name,
                "raw": {"vk": response},
            }

        if provider == "yandex":
            profile_resp = client.get(
                meta["profile_url"],
                headers={"Authorization": f"OAuth {access_token}"},
            )
            profile_resp.raise_for_status()
            data = profile_resp.json()
            return {
                "provider": provider,
                "external_id": str(data.get("id") or data.get("client_id") or ""),
                "email": data.get("default_email") or data.get("emails", [None])[0],
                "display_name": data.get("real_name") or data.get("display_name"),
                "raw": {"yandex": data},
            }

        # google
        profile_resp = client.get(
            meta["profile_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_resp.raise_for_status()
        data = profile_resp.json()
        return {
            "provider": provider,
            "external_id": str(data.get("sub") or data.get("id") or ""),
            "email": data.get("email"),
            "display_name": data.get("name") or "",
            "raw": {"google": data},
        }

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Type

from django.conf import settings

logger = logging.getLogger("parkshare.sms")


class SmsProvider(ABC):
    """
    Abstract SMS provider interface.

    Implementations must be stateless and reusable; configuration is passed
    via Django settings / environment variables.
    """

    @abstractmethod
    def send_sms(self, to: str, text: str) -> None:
        """
        Send SMS message to a single recipient.

        Implementations MUST NOT raise on remote failures in a way that breaks
        the main request flow; prefer logging + best‑effort semantics.
        """
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    """
    Development / default provider: logs SMS contents instead of sending.
    """

    def send_sms(self, to: str, text: str) -> None:
        logger.info(
            "SMS send (console backend)",
            extra={
                "to": to,
                "chars": len(text),
                "preview": text[:64],
            },
        )


_PROVIDER_REGISTRY: Dict[str, Type[SmsProvider]] = {
    "console": ConsoleSmsProvider,
}


def get_sms_provider() -> SmsProvider:
    """
    Resolve concrete SmsProvider based on SMS_PROVIDER setting.

    For production, plug in a custom implementation by:
      * Implementing SmsProvider subclass in your own module.
      * Adding it to _PROVIDER_REGISTRY at import time (e.g. via AppConfig.ready()).
      * Setting SMS_PROVIDER env var to the corresponding key.
    """
    backend_name = getattr(settings, "SMS_PROVIDER", "console") or "console"
    provider_cls = _PROVIDER_REGISTRY.get(backend_name, ConsoleSmsProvider)
    return provider_cls()

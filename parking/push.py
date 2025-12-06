"""Lightweight push notification service wrapper.

The module intentionally avoids binding to a specific provider. It validates
payloads and envelopes and provides a single entry point that backend code can
call without caring about transport details.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Optional

from parking.models import PushSubscription

logger = logging.getLogger(__name__)


class PushTransportError(Exception):
    """Raised when the configured push transport fails."""


def _vapid_keys() -> tuple[Optional[str], Optional[str]]:
    return os.getenv("PUSH_VAPID_PUBLIC_KEY"), os.getenv("PUSH_VAPID_PRIVATE_KEY")


def send_parking_notification(user, payload: dict, subscriptions: Optional[Iterable[PushSubscription]] = None) -> int:
    """Send a WebPush notification to the provided subscriptions.

    The function is transport-agnostic; actual integration with a provider
    (VAPID/FCM/etc.) should be added where marked. Returns number of successfully
    queued notifications.
    """

    public_key, private_key = _vapid_keys()
    if not public_key or not private_key:
        logger.info("Push skipped: VAPID keys are not configured")
        return 0

    subs = list(subscriptions or [])
    if not subs and user:
        subs = list(PushSubscription.objects.filter(user=user))
    if not subs:
        return 0

    # Normalize payload to expected shape consumed by service worker
    normalized = {
        "title": payload.get("title") or "ParkShare",
        "body": payload.get("body") or "Новые события по бронированиям",
        "data": payload.get("data") or {},
        "actions": payload.get("actions") or [],
    }

    delivered = 0
    for sub in subs:
        try:
            # TODO: plug in concrete push provider here (pywebpush/FCM/etc.)
            logger.debug("Would send push to %s", sub.endpoint)
            _ = json.dumps(normalized, ensure_ascii=False)  # payload validation
            delivered += 1
        except Exception as exc:  # pragma: no cover - integration placeholder
            logger.warning("Push delivery failed, dropping subscription %s: %s", sub.id, exc)
            sub.delete()
    return delivered

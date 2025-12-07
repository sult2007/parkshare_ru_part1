from __future__ import annotations

import hashlib
import logging
from typing import Optional

from django.conf import settings

from .models import FeatureFlag

logger = logging.getLogger(__name__)


def _hit(identifier: str, percentage: int) -> bool:
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    h = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) % 100
    return bucket < percentage


def is_feature_enabled(flag_name: str, user=None, request=None) -> bool:
    """
    Deterministic процентные флаги. При отсутствии записи возвращает False,
    чтобы новые флаги не включались случайно.
    """
    try:
        flag = FeatureFlag.objects.get(name=flag_name)
    except FeatureFlag.DoesNotExist:
        return False

    if not flag.enabled:
        return False

    identifier = "anonymous"
    if user and getattr(user, "pk", None):
        identifier = str(user.pk)
    elif request:
        identifier = request.META.get("REMOTE_ADDR") or "anonymous"

    hit = _hit(identifier, flag.rollout_percentage)
    if settings.DEBUG:
        logger.debug("feature_flag", extra={"flag": flag.name, "hit": hit, "id": identifier})
    return hit

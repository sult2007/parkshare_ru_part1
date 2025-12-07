from datetime import datetime, timedelta
from collections import defaultdict
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ai.models import UiEvent, ChatSession
from parking.models import Booking

User = get_user_model()


def variant_for_user(user):
    return "B" if (hash(str(user.id)) % 2) else "A"


def _daterange(days: int):
    end = timezone.now().date()
    start = end - timedelta(days=days)
    return start, end


def compute_funnel(days: int = 7):
    cache_key = f"analytics:funnel:{days}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    start, end = _daterange(days)
    events = UiEvent.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    funnel = {"map_open": 0, "spot_select": 0, "booking_confirm_open": 0, "booking_created": 0, "repeat_visit": 0}
    assistant_sessions = 0
    variant_counts = {"A": defaultdict(int), "B": defaultdict(int)}

    for ev in events.select_related("device_profile__user"):
        etype = ev.event_type
        if etype in funnel:
            funnel[etype] += 1
            v = variant_for_user(ev.device_profile.user) if ev.device_profile and ev.device_profile.user else "A"
            variant_counts[v][etype] += 1

    bookings = Booking.objects.filter(start_at__date__gte=start, start_at__date__lte=end).select_related("user")
    funnel["booking_created"] = bookings.count()
    for b in bookings:
        v = variant_for_user(b.user)
        variant_counts[v]["booking_created"] += 1

    repeat_users = [u for u in set(bookings.values_list("user", flat=True)) if bookings.filter(user_id=u).count() > 1]
    funnel["repeat_visit"] = len(repeat_users)
    for uid in repeat_users:
        user = User.objects.filter(id=uid).first()
        v = variant_for_user(user) if user else "A"
        variant_counts[v]["repeat_visit"] += 1

    assistant_sessions = ChatSession.objects.filter(created_at__date__gte=start, created_at__date__lte=end).count()

    def pct(n, d):
        return 0 if d == 0 else round((n / d) * 100, 1)

    conversions = {
        "map_to_spot": pct(funnel["spot_select"], funnel["map_open"]),
        "spot_to_confirm": pct(funnel["booking_confirm_open"], funnel["spot_select"]),
        "confirm_to_booking": pct(funnel["booking_created"], funnel["booking_confirm_open"]),
    }

    payload = {
        "range": {"start": start, "end": end},
        "funnel": funnel,
        "conversions": conversions,
        "assistant_sessions": assistant_sessions,
        "variants": variant_counts,
    }
    cache.set(cache_key, payload, 300)  # 5 minutes cache
    return payload

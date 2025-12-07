# backend/parking/models.py

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_UP
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel
from .models_notification import NotificationSettings


# PointField с fallback для SQLite: храним JSON {"lat": ..., "lng": ...}
_db_settings = getattr(settings, "DATABASES", {})
_default_db = _db_settings.get("default") or {}
_default_engine = _default_db.get("ENGINE", "")


if _default_engine.endswith("sqlite3"):
    class PointField(models.JSONField):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            kwargs.pop("geography", None)
            super().__init__(*args, **kwargs)
else:  # PostGIS / другие GIS-бэкенды
    from django.contrib.gis.db.models import PointField  # type: ignore[assignment]


class ParkingLot(TimeStampedModel):
    """
    Объект парковки (двор, подземный паркинг, офисный паркинг и т.д.).
    """

    class ParkingType(models.TextChoices):
        YARD = "yard", "Дворовая парковка"
        UNDERGROUND = "underground", "Подземная парковка"
        MULTILEVEL = "multilevel", "Многоуровневая парковка"
        STREET = "street", "Уличная парковка"
        OFFICE = "office", "Офисная парковка"
        HOME = "home", "Домашнее место"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parking_lots",
        verbose_name="Владелец",
    )
    name = models.CharField("Название", max_length=255)
    city = models.CharField("Город", max_length=100)
    address = models.CharField("Адрес", max_length=255)
    parking_type = models.CharField(
        "Тип парковки",
        max_length=32,
        choices=ParkingType.choices,
        default=ParkingType.YARD,
    )
    description = models.TextField("Описание", blank=True)

    location = PointField("Точка на карте", geography=True, null=True, blank=True)
    latitude = models.FloatField("Широта", null=True, blank=True)
    longitude = models.FloatField("Долгота", null=True, blank=True)

    is_active = models.BooleanField("Активен", default=True)
    is_approved = models.BooleanField(
        "Одобрен модерацией",
        default=False,
        help_text="Одобряется администратором перед публикацией.",
    )
    is_private = models.BooleanField(
        "Приватный",
        default=False,
        help_text="Если включено, объект виден только по прямым ссылкам/владельцу.",
    )

    stress_index = models.FloatField(
        "Индекс загруженности (0..1)",
        default=0.0,
        help_text=(
            "Средняя загруженность мест за последние 7 дней. "
            "Обновляется фоновыми задачами AI."
        ),
    )

    class Meta:
        verbose_name = "Объект парковки"
        verbose_name_plural = "Объекты парковки"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"

    @property
    def owner_username(self) -> str:
        return getattr(self.owner, "username", "")

    def set_coordinates(self, lat: Optional[float], lng: Optional[float]) -> None:
        """
        Устанавливает координаты и PointField (если доступен GeoDjango).
        """
        self.latitude = lat
        self.longitude = lng
        if lat is None or lng is None:
            self.location = None
            return

        try:
            from django.contrib.gis.geos import Point  # type: ignore[import]
        except Exception:
            # SQLite/JSON fallback
            self.location = {"lat": lat, "lng": lng}
        else:
            self.location = Point(lng, lat)


class ParkingSpot(TimeStampedModel):
    """
    Конкретное парковочное место внутри ParkingLot.
    """

    class SpotStatus(models.TextChoices):
        ACTIVE = "active", "Активно"
        INACTIVE = "inactive", "Неактивно"

    class VehicleType(models.TextChoices):
        CAR = "car", "Легковой автомобиль"
        MOTO = "moto", "Мотоцикл"
        COMMERCIAL = "commercial", "Коммерческий транспорт"

    lot = models.ForeignKey(
        ParkingLot,
        on_delete=models.CASCADE,
        related_name="spots",
        verbose_name="Объект парковки",
    )
    name = models.CharField("Название/номер места", max_length=64)
    description = models.TextField("Описание", blank=True)

    vehicle_type = models.CharField(
        "Тип транспорта",
        max_length=16,
        choices=VehicleType.choices,
        default=VehicleType.CAR,
    )

    is_covered = models.BooleanField("Крытое место", default=False)
    has_ev_charging = models.BooleanField("Есть зарядка", default=False)
    is_24_7 = models.BooleanField("Круглосуточно", default=True)
    max_height_m = models.DecimalField(
        "Максимальная высота (м)",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )

    hourly_price = models.DecimalField(
        "Цена за час, ₽", max_digits=8, decimal_places=2
    )
    nightly_price = models.DecimalField(
        "Цена за ночь, ₽", max_digits=8, decimal_places=2, null=True, blank=True
    )
    daily_price = models.DecimalField(
        "Цена за сутки, ₽", max_digits=8, decimal_places=2, null=True, blank=True
    )
    monthly_price = models.DecimalField(
        "Цена за месяц, ₽", max_digits=9, decimal_places=2, null=True, blank=True
    )

    allow_dynamic_pricing = models.BooleanField(
        "Динамическая цена (AI)",
        default=False,
        help_text="Если включено, тариф может корректироваться рекомендациями AI.",
    )

    status = models.CharField(
        "Статус",
        max_length=16,
        choices=SpotStatus.choices,
        default=SpotStatus.ACTIVE,
    )

    occupancy_7d = models.FloatField(
        "Загруженность за 7 дней (0..1)",
        default=0.0,
        help_text=(
            "Доля времени, когда место было занято за последние 7 дней. "
            "Обновляется фоновыми задачами AI."
        ),
    )

    class Meta:
        verbose_name = "Парковочное место"
        verbose_name_plural = "Парковочные места"
        ordering = ("lot__name", "name")

    def __str__(self) -> str:
        return f"{self.lot.name} — {self.name}"

    @property
    def owner(self):
        """
        Для IsOwnerObject из core.permissions: владелец места = владелец ParkingLot.
        """
        return self.lot.owner

    @property
    def city(self) -> str:
        return self.lot.city

    @property
    def is_active(self) -> bool:
        return (
            self.status == self.SpotStatus.ACTIVE
            and self.lot.is_active
            and self.lot.is_approved
        )


class Booking(TimeStampedModel):
    """
    Бронирование парковочного места.
    """

    class BillingMode(models.TextChoices):
        PAYG = "pay_as_you_go", "Поминутно/почасово"
        PREPAID_BLOCK = "prepaid_block", "Предоплата блоком"
        WALLET = "wallet", "Оплата кошельком"

    class BookingType(models.TextChoices):
        HOURLY = "hourly", "Почасовая"
        DAILY = "daily", "Суточная"
        NIGHT = "night", "Ночная"
        WEEKLY = "weekly", "Недельная"
        MONTHLY = "monthly", "Месячная"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        CONFIRMED = "confirmed", "Подтверждена"
        ACTIVE = "active", "Активна"
        COMPLETED = "completed", "Завершена"
        CANCELLED = "cancelled", "Отменена"
        EXPIRED = "expired", "Истекла"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Пользователь",
    )
    spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Парковочное место",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.SET_NULL,
        related_name="bookings",
        verbose_name="Транспорт",
        null=True,
        blank=True,
    )

    booking_type = models.CharField(
        "Тип бронирования",
        max_length=16,
        choices=BookingType.choices,
        default=BookingType.HOURLY,
    )
    billing_mode = models.CharField(
        "Режим биллинга",
        max_length=32,
        choices=BillingMode.choices,
        default=BillingMode.PAYG,
    )

    start_at = models.DateTimeField("Начало брони")
    end_at = models.DateTimeField("Окончание брони")

    status = models.CharField(
        "Статус",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_price = models.DecimalField(
        "Итоговая стоимость, ₽", max_digits=10, decimal_places=2
    )
    currency = models.CharField("Валюта", max_length=8, default="RUB")
    is_paid = models.BooleanField("Оплачено", default=False)
    dynamic_pricing_applied = models.BooleanField(
        "Динамическое ценообразование", default=False
    )
    ai_snapshot = models.JSONField(
        "AI snapshot",
        null=True,
        blank=True,
        help_text="Данные решений AI (цены, доступность, риски)",
    )

    external_payment_id = models.CharField(
        "ID платежа провайдера",
        max_length=64,
        blank=True,
        help_text="Связка с платежом у провайдера (например, YooKassa payment_id).",
    )

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ("-start_at",)

    def __str__(self) -> str:
        return f"Бронь #{self.pk} — {self.spot} ({self.start_at} → {self.end_at})"

    @property
    def owner(self):
        """
        Для удобства — владелец места, по которому идёт бронь.
        """
        return self.spot.lot.owner

    @staticmethod
    def is_spot_available(
        spot: ParkingSpot,
        start_at,
        end_at,
        exclude_booking_id: Optional[int] = None,
    ) -> bool:
        """
        Проверка пересечения интервалов с существующими бронями.
        """
        qs = Booking.objects.filter(spot=spot).exclude(
            status__in=[Booking.Status.CANCELLED, Booking.Status.EXPIRED]
        )
        if exclude_booking_id:
            qs = qs.exclude(id=exclude_booking_id)
        # Пересечение интервалов: (start1 < end2) и (end1 > start2)
        overlap = qs.filter(start_at__lt=end_at, end_at__gt=start_at).exists()
        return not overlap

    def calculate_price(self) -> Decimal:
        """
        Простая модель расчёта цены на основе тарифов ParkingSpot и типа брони.
        """

        if not self.spot:
            return Decimal("0.00")

        delta = self.end_at - self.start_at
        total_seconds = Decimal(delta.total_seconds())
        total_hours = total_seconds / Decimal(3600)
        total_days = total_seconds / Decimal(86400)

        billing_mode = getattr(self, "billing_mode", self.BillingMode.PAYG)
        if billing_mode == self.BillingMode.PAYG:
            # Округляем вверх до 15-минутных слотов для поминутной/почасовой оплаты
            slots = (total_seconds / Decimal(900)).to_integral_value(rounding=ROUND_UP)
            total_hours = (slots * Decimal("0.25")).quantize(Decimal("0.25"))
        elif billing_mode == self.BillingMode.PREPAID_BLOCK:
            hours = float(total_hours)
            if hours <= 2:
                total_hours = Decimal("2")
            elif hours <= 4:
                total_hours = Decimal("4")
            elif hours <= 24:
                total_hours = Decimal("24")
            else:
                days = (Decimal(hours) / Decimal("24")).to_integral_value(rounding=ROUND_UP)
                total_hours = days * Decimal("24")

        base_price = Decimal("0.00")

        if self.booking_type == self.BookingType.HOURLY:
            hourly = self.spot.hourly_price
            units = max(
                Decimal("1"),
                total_hours.to_integral_value(rounding=ROUND_UP),
            )
            base_price = hourly * units
        elif self.booking_type == self.BookingType.DAILY:
            daily = self.spot.daily_price or (self.spot.hourly_price * Decimal("24"))
            units = max(
                Decimal("1"),
                total_days.to_integral_value(rounding=ROUND_UP),
            )
            base_price = daily * units
        elif self.booking_type == self.BookingType.NIGHT:
            nightly = self.spot.nightly_price or (
                self.spot.hourly_price * Decimal("10")
            )
            base_price = nightly
        elif self.booking_type == self.BookingType.WEEKLY:
            daily = self.spot.daily_price or (self.spot.hourly_price * Decimal("24"))
            units = max(
                Decimal("1"),
                (total_days / Decimal("7")).to_integral_value(rounding=ROUND_UP),
            )
            base_price = daily * Decimal("7") * units
        elif self.booking_type == self.BookingType.MONTHLY:
            monthly = self.spot.monthly_price or (
                (self.spot.daily_price or self.spot.hourly_price * Decimal("24"))
                * Decimal("30")
            )
            units = max(
                Decimal("1"),
                (total_days / Decimal("30")).to_integral_value(rounding=ROUND_UP),
            )
            base_price = monthly * units
        else:
            base_price = self.spot.hourly_price * max(
                Decimal("1"),
                total_hours.to_integral_value(rounding=ROUND_UP),
            )

        base_price = base_price.quantize(Decimal("0.01"))

        commission_percent = getattr(settings, "SERVICE_COMMISSION_PERCENT", 0)
        commission = (
            base_price * Decimal(commission_percent) / Decimal("100")
        ).quantize(Decimal("0.01"))
        total = (base_price + commission).quantize(Decimal("0.01"))
        self.total_price = total
        return total

    def mark_paid(self, payment_id: str | None = None) -> None:
        """
        Отметить бронь как оплаченную (вызывается из модуля payments по webhook).
        """
        self.is_paid = True
        self.status = self.Status.CONFIRMED
        if payment_id:
            self.external_payment_id = payment_id
        self.save(update_fields=["is_paid", "status", "external_payment_id"])

    @property
    def has_started(self) -> bool:
        return self.start_at <= timezone.now()

    @property
    def has_ended(self) -> bool:
        return self.end_at <= timezone.now()

    @property
    def duration(self) -> timedelta:
        return self.end_at - self.start_at


class WaitlistEntry(TimeStampedModel):
    """
    Запись в листе ожидания для занятого места.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидает"
        NOTIFIED = "notified", "Уведомлён"
        BOOKED = "booked", "Авто‑бронирование создано"
        CANCELLED = "cancelled", "Отменено"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
        verbose_name="Пользователь",
    )
    spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
        verbose_name="Парковочное место",
    )
    desired_start = models.DateTimeField("Желаемое начало")
    desired_end = models.DateTimeField("Желаемое окончание")
    auto_book = models.BooleanField(
        "Авто‑бронирование",
        default=False,
        help_text="Если включено, при освобождении места будет создана бронь автоматически.",
    )
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=Status.choices,
        default=Status.WAITING,
    )

    class Meta:
        verbose_name = "Запись в листе ожидания"
        verbose_name_plural = "Лист ожидания"
        ordering = ("-created_at",)
        unique_together = ("user", "spot", "desired_start", "desired_end")

    def __str__(self) -> str:
        return f"Waitlist #{self.pk} — {self.user} → {self.spot}"


class Complaint(TimeStampedModel):
    """
    Жалоба по бронированию/месту:
    - чужая машина;
    - пользователь не приехал;
    - частые отмены и т.п.
    """

    class Category(models.TextChoices):
        FOREIGN_CAR = "foreign_car", "Чужая машина на месте"
        NO_SHOW = "no_show", "Пользователь не приехал"
        NO_FREE_SPOT = "no_free_spot", "Не нашёл свободного места"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        RESOLVED = "resolved", "Решена"
        REJECTED = "rejected", "Отклонена"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="complaints",
        verbose_name="Автор",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        related_name="complaints",
        null=True,
        blank=True,
        verbose_name="Бронирование",
    )
    spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        related_name="complaints",
        null=True,
        blank=True,
        verbose_name="Парковочное место",
    )

    category = models.CharField(
        "Категория",
        max_length=32,
        choices=Category.choices,
        default=Category.OTHER,
    )
    description = models.TextField("Описание", blank=True)

    status = models.CharField(
        "Статус",
        max_length=16,
        choices=Status.choices,
        default=Status.NEW,
    )

    class Meta:
        verbose_name = "Жалоба"
        verbose_name_plural = "Жалобы"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Жалоба #{self.pk} ({self.get_category_display()})"


class FavoriteParkingSpot(TimeStampedModel):
    """Избранные парковочные места пользователя."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_spots",
    )
    spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    note = models.CharField("Заметка", max_length=120, blank=True)

    class Meta:
        verbose_name = "Избранное место"
        verbose_name_plural = "Избранные места"
        ordering = ("-created_at",)
        unique_together = ("user", "spot")

    def __str__(self) -> str:
        return f"{self.user} → {self.spot}"


class SavedPlace(TimeStampedModel):
    """Сохранённые точки (дом/офис) для быстрого поиска."""

    class PlaceType(models.TextChoices):
        HOME = "home", "Дом"
        WORK = "work", "Офис"
        CUSTOM = "custom", "Другое"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_places",
    )
    title = models.CharField("Название", max_length=64)
    place_type = models.CharField(
        "Тип точки",
        max_length=16,
        choices=PlaceType.choices,
        default=PlaceType.CUSTOM,
    )
    latitude = models.FloatField("Широта")
    longitude = models.FloatField("Долгота")

    class Meta:
        verbose_name = "Сохранённая точка"
        verbose_name_plural = "Сохранённые точки"
        ordering = ("title",)
        unique_together = ("user", "title")

    def __str__(self) -> str:
        return f"{self.title} ({self.user})"


class PushSubscription(TimeStampedModel):
    """Хранение WebPush‑подписок для уведомлений."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        null=True,
        blank=True,
    )
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    platform = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Push-подписка"
        verbose_name_plural = "Push-подписки"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.user or 'guest'} {self.endpoint[:32]}"

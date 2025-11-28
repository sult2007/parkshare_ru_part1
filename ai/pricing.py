from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor

from core.utils import round_price
from parking.models import ParkingSpot
from .features import bookings_dataframe

MODEL_PATH = Path(getattr(settings, "BASE_DIR", ".")) / "ai_models" / "pricing_model.pkl"


def train_pricing_model(df=None) -> Optional[RandomForestRegressor]:
    """
    Обучает простую RandomForest-модель для оценки цены за час.
    """
    if df is None:
        df = bookings_dataframe()
    if df.empty or len(df) < 20:
        return None

    df = df.copy()
    df["price_per_hour"] = df["price"] / df["duration_hours"].clip(lower=0.5)
    X = df[["hour", "dow", "is_weekend"]].values
    y = df["price_per_hour"].values

    model = RandomForestRegressor(
        n_estimators=50,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return model


def load_pricing_model() -> Optional[RandomForestRegressor]:
    if not MODEL_PATH.exists():
        return None
    try:
        model: RandomForestRegressor = joblib.load(MODEL_PATH)
        return model
    except Exception:
        return None


def recommend_price_for_spot(spot: ParkingSpot) -> Optional[Dict[str, Any]]:
    """
    Возвращает диапазон рекомендованных цен для владельца места.
    Учитывает:
    - базовую цену;
    - загрузку места за 7 дней (occupancy_7d);
    - (по возможности) предсказание ML‑модели.
    """
    base_price = float(spot.hourly_price or 0.0)
    if base_price <= 0:
        return None

    now = timezone.now()
    features = np.array([[now.hour, now.weekday(), 1 if now.weekday() >= 5 else 0]])

    model = load_pricing_model()
    predicted = None
    if model is not None:
        try:
            predicted_value = float(model.predict(features)[0])
            if predicted_value > 0:
                predicted = predicted_value
        except Exception:
            predicted = None

    occupancy = float(getattr(spot, "occupancy_7d", 0.0) or 0.0)
    factor = 1.0
    reason_parts = []

    if occupancy > 0.8:
        factor += 0.15
        reason_parts.append("место часто занято (высокая загрузка)")
    elif occupancy < 0.3:
        factor -= 0.1
        reason_parts.append("место простаивает (низкая загрузка)")

    if predicted is not None:
        ai_price = round_price(predicted, step=5.0)
        reason_parts.append("ML‑модель учитывает исторические цены по району")
    else:
        ai_price = base_price

    recommended = round_price(ai_price * factor, step=5.0)
    min_price = round_price(recommended * 0.9, step=5.0)
    max_price = round_price(recommended * 1.1, step=5.0)

    if not reason_parts:
        reason_parts.append("используется базовая ставка и средняя загрузка")

    reason = "На основе: " + "; ".join(reason_parts) + "."
    return {
        "base_price": base_price,
        "recommended_price": recommended,
        "min_price": min_price,
        "max_price": max_price,
        "reason": reason,
    }

# database.py
from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

DB_PATH = Path(__file__).parent / "ai_data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS parking_lot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            near_metro INTEGER NOT NULL,
            price_level INTEGER NOT NULL,
            has_covered INTEGER NOT NULL,
            has_ev_charging INTEGER NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS occupancy_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            occupancy REAL NOT NULL,
            temperature REAL NOT NULL,
            is_rain INTEGER NOT NULL,
            is_event INTEGER NOT NULL,
            FOREIGN KEY (lot_id) REFERENCES parking_lot(id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            rating REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES app_user(id),
            FOREIGN KEY (lot_id) REFERENCES parking_lot(id)
        );
        """
    )

    conn.commit()
    conn.close()


@dataclass
class LotSpec:
    name: str
    base_lat: float
    base_lon: float
    near_metro: int
    price_level: int
    has_covered: int
    has_ev_charging: int


def generate_synthetic_data(
    num_lots: int = 30,
    num_users: int = 50,
    days_back: int = 30,
) -> None:
    """
    Генерация синтетических:
    - парковок
    - истории занятости
    - пользователей
    - оценок пользователей
    """
    random.seed(42)

    conn = get_connection()
    cur = conn.cursor()

    # Чистим старые данные
    cur.execute("DELETE FROM user_rating;")
    cur.execute("DELETE FROM app_user;")
    cur.execute("DELETE FROM occupancy_history;")
    cur.execute("DELETE FROM parking_lot;")
    conn.commit()

    # Базовые точки вокруг Москвы
    center_lat, center_lon = 55.7558, 37.6173

    lots: List[int] = []
    for i in range(num_lots):
        near_metro = 1 if random.random() < 0.5 else 0
        price_level = random.choice([1, 2, 3])  # 1 — дешево, 3 — дорого
        has_covered = 1 if random.random() < 0.4 else 0
        has_ev = 1 if random.random() < 0.3 else 0

        # Немного раскидываем точки вокруг центра
        lat = center_lat + random.uniform(-0.05, 0.05)
        lon = center_lon + random.uniform(-0.1, 0.1)

        cur.execute(
            """
            INSERT INTO parking_lot (
                name, latitude, longitude, near_metro,
                price_level, has_covered, has_ev_charging
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"Лот #{i+1}",
                lat,
                lon,
                near_metro,
                price_level,
                has_covered,
                has_ev,
            ),
        )
        lots.append(cur.lastrowid)

    # История занятости — каждые 2 часа за days_back дней
    now = datetime.now()
    start_ts = now - timedelta(days=days_back)

    weather_states = ["sunny", "cloudy", "rainy"]

    for lot_id in lots:
        ts = start_ts
        while ts < now:
            dow = ts.weekday()
            hour = ts.hour

            is_event = 1 if (dow in (4, 5) and hour >= 18 and random.random() < 0.3) else 0
            weather = random.choice(weather_states)
            is_rain = 1 if weather == "rainy" else 0
            temperature = random.uniform(-10, 30)

            # Базовая занятость зависит от часа и дня недели
            base_occ = 0.2
            if 8 <= hour <= 11:
                base_occ = 0.6
            elif 17 <= hour <= 20:
                base_occ = 0.7
            elif 0 <= hour <= 5:
                base_occ = 0.1

            if dow >= 5:
                base_occ += 0.1

            if is_event:
                base_occ += 0.2
            if is_rain:
                base_occ += 0.1

            base_occ = max(0.0, min(base_occ + random.uniform(-0.1, 0.1), 1.0))

            cur.execute(
                """
                INSERT INTO occupancy_history (
                    lot_id, ts, occupancy, temperature, is_rain, is_event
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    lot_id,
                    ts.isoformat(),
                    base_occ,
                    temperature,
                    is_rain,
                    is_event,
                ),
            )

            ts += timedelta(hours=2)

    # Пользователи
    users = []
    for i in range(num_users):
        cur.execute(
            "INSERT INTO app_user (name) VALUES (?);",
            (f"user_{i+1}",),
        )
        users.append(cur.lastrowid)

    # Оценки пользователей парковок
    for user_id in users:
        # Каждый пользователь оценит 5–15 парковок
        k = random.randint(5, min(15, len(lots)))
        rated_lots = random.sample(lots, k)
        for lot_id in rated_lots:
            # Рейтинг зависит от price_level и случайности
            base_rating = 4.5 - 0.5 * (random.randint(1, 3) - 1)
            rating = max(1.0, min(5.0, base_rating + random.uniform(-1.0, 1.0)))
            cur.execute(
                """
                INSERT INTO user_rating (user_id, lot_id, rating)
                VALUES (?, ?, ?)
                """,
                (user_id, lot_id, rating),
            )

    conn.commit()
    conn.close()
    print("Синтетические данные сгенерированы в", DB_PATH)


if __name__ == "__main__":
    init_db()
    generate_synthetic_data()

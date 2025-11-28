# model_training.py
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVC

from database import DB_PATH, get_connection, init_db, generate_synthetic_data

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "ai_models"
MODELS_DIR.mkdir(exist_ok=True)


# ---------- 1. Модель предсказания загруженности парковок ----------


def load_occupancy_dataframe() -> pd.DataFrame:
    conn = get_connection()
    query = """
        SELECT
            oh.lot_id,
            oh.ts,
            oh.occupancy,
            oh.temperature,
            oh.is_rain,
            oh.is_event,
            pl.near_metro,
            pl.price_level,
            pl.has_covered,
            pl.has_ev_charging
        FROM occupancy_history oh
        JOIN parking_lot pl ON pl.id = oh.lot_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df["ts"] = pd.to_datetime(df["ts"])
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.weekday
    df["lot_id_str"] = df["lot_id"].astype(str)

    return df


def train_occupancy_model() -> None:
    df = load_occupancy_dataframe()
    if df.empty:
        raise RuntimeError("Нет данных для обучения occupancy-модели")

    feature_cols = [
        "hour",
        "dow",
        "temperature",
        "is_rain",
        "is_event",
        "near_metro",
        "price_level",
        "has_covered",
        "has_ev_charging",
        "lot_id_str",
    ]

    X = df[feature_cols].copy()
    y = df["occupancy"].astype(float)

    numeric_features = [
        "hour",
        "dow",
        "temperature",
        "is_rain",
        "is_event",
        "near_metro",
        "price_level",
        "has_covered",
        "has_ev_charging",
    ]
    categorical_features = ["lot_id_str"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=80,
        random_state=42,
        n_jobs=-1,
    )

    pipe = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", model),
        ]
    )

    pipe.fit(X, y)

    model_path = MODELS_DIR / "occupancy_model.pkl"
    joblib.dump(
        {
            "pipeline": pipe,
            "feature_cols": feature_cols,
        },
        model_path,
    )
    print("occupancy_model.pkl сохранён в", model_path)


# ---------- 2. NLP: интенты и парсинг пользовательских запросов ----------


def build_nlp_training_data() -> pd.DataFrame:
    data = [
        ("рядом с метро", "near_metro"),
        ("парковка около метро", "near_metro"),
        ("парковка возле метро", "near_metro"),
        ("где припарковаться у метро курская", "near_metro"),
        ("найди парковку у метро", "near_metro"),
        ("самая дешевая парковка", "cheap"),
        ("дешевые парковки утром", "cheap"),
        ("недорогая парковка рядом", "cheap"),
        ("дешево припарковаться", "cheap"),
        ("недорогие места для машины", "cheap"),
        ("парковка с зарядкой для электромобиля", "ev"),
        ("нужна зарядка для электрокара", "ev"),
        ("парковка с ev charging", "ev"),
        ("крытая парковка", "covered"),
        ("подземная парковка", "covered"),
        ("парковка в паркинге", "covered"),
        ("парковка ночью", "time_night"),
        ("парковка утром", "time_morning"),
        ("парковка вечером", "time_evening"),
        ("парковка днем", "time_day"),
        ("найди парковку", "general"),
        ("показать все парковки", "general"),
        ("где можно припарковаться", "general"),
        ("парковка в центре", "general"),
        ("парковка возле офиса", "general"),
    ]
    return pd.DataFrame(data, columns=["text", "intent"])


def train_nlp_model() -> None:
    df = build_nlp_training_data()
    X = df["text"].values
    y = df["intent"].values

    pipe = Pipeline(
        steps=[
            (
                "vec",
                CountVectorizer(
                    ngram_range=(1, 2),
                    analyzer="word",
                ),
            ),
            ("clf", LinearSVC()),
        ]
    )

    pipe.fit(X, y)

    model_path = MODELS_DIR / "nlp_intent.pkl"
    joblib.dump(pipe, model_path)
    print("nlp_intent.pkl сохранён в", model_path)


# ---------- 3. Рекомендательная система (collab + content) ----------


def train_recommender() -> None:
    """
    Простейшая item-based collaborative filtering + content-based фолбэк.
    """
    conn = get_connection()

    ratings = pd.read_sql_query("SELECT * FROM user_rating;", conn)
    lots = pd.read_sql_query("SELECT * FROM parking_lot;", conn)

    if ratings.empty or lots.empty:
        raise RuntimeError("Нет данных для обучения рекомендера")

    # user-item матрица
    user_item = (
        ratings.pivot(index="user_id", columns="lot_id", values="rating")
        .fillna(0.0)
        .astype(float)
    )

    # Нормируем по пользователям
    user_norms = np.linalg.norm(user_item.values, axis=1, keepdims=True)
    user_norms[user_norms == 0] = 1.0
    user_item_norm = user_item.values / user_norms

    # item-item similarity (cosine)
    sim_matrix = cosine_similarity(user_item_norm.T)
    item_ids = user_item.columns.tolist()
    item_sim = pd.DataFrame(sim_matrix, index=item_ids, columns=item_ids)

    # Content-features
    lot_features = lots.set_index("id")[
        ["near_metro", "price_level", "has_covered", "has_ev_charging", "latitude", "longitude"]
    ].copy()

    model_path = MODELS_DIR / "recommender.pkl"
    joblib.dump(
        {
            "user_item": user_item,
            "item_sim": item_sim,
            "lot_features": lot_features,
        },
        model_path,
    )
    print("recommender.pkl сохранён в", model_path)
    conn.close()


def main() -> None:
    # На случай чистой установки
    init_db()
    generate_synthetic_data()

    print("=== Обучение occupancy-модели ===")
    train_occupancy_model()

    print("=== Обучение NLP-модели ===")
    train_nlp_model()

    print("=== Обучение рекомендательной системы ===")
    train_recommender()

    print("Готово: все модели обучены и сохранены в", MODELS_DIR)


if __name__ == "__main__":
    main()

# api_server.py
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_connection

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "ai_models"

# --- Загрузка моделей ---

occ_bundle: Dict[str, Any] = joblib.load(MODELS_DIR / "occupancy_model.pkl")
OCC_PIPE = occ_bundle["pipeline"]
OCC_FEATURE_COLS = occ_bundle["feature_cols"]

NLP_PIPE = joblib.load(MODELS_DIR / "nlp_intent.pkl")

rec_bundle: Dict[str, Any] = joblib.load(MODELS_DIR / "recommender.pkl")
USER_ITEM: pd.DataFrame = rec_bundle["user_item"]
ITEM_SIM: pd.DataFrame = rec_bundle["item_sim"]
LOT_FEATURES: pd.DataFrame = rec_bundle["lot_features"]

# --- FastAPI ---

app = FastAPI(title="ParkShare Local AI", version="1.0.0")

DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _split_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


AI_CORS_ALLOW_ORIGINS = _split_env_list(os.getenv("AI_CORS_ALLOW_ORIGINS"))
AI_CORS_ALLOW_METHODS = _split_env_list(os.getenv("AI_CORS_ALLOW_METHODS")) or ["GET", "POST", "OPTIONS"]
AI_CORS_ALLOW_HEADERS = _split_env_list(os.getenv("AI_CORS_ALLOW_HEADERS")) or ["*"]
AI_CORS_ALLOW_CREDENTIALS = os.getenv("AI_CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=AI_CORS_ALLOW_ORIGINS or DEFAULT_ORIGINS,
    allow_credentials=AI_CORS_ALLOW_CREDENTIALS,
    allow_methods=AI_CORS_ALLOW_METHODS,
    allow_headers=AI_CORS_ALLOW_HEADERS,
)


# ---------- Схемы ----------


class Lot(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    near_metro: bool
    price_level: int
    has_covered: bool
    has_ev_charging: bool
    predicted_occupancy: float


class SearchResult(BaseModel):
    query: str
    intent: str
    time_of_day: Optional[str]
    near_metro: Optional[bool]
    max_price_level: Optional[int]
    has_ev_charging: Optional[bool]
    has_covered: Optional[bool]
    lots: List[Lot]


class OccupancyPredictionResponse(BaseModel):
    lot_id: int
    ts: dt.datetime
    predicted_occupancy: float


class Recommendation(BaseModel):
    lot: Lot
    score: float


class RecommendationsResponse(BaseModel):
    user_id: Optional[int]
    variant: str  # 'A' или 'B' для A/B теста
    recommendations: List[Recommendation]


# ---------- Утилиты ----------


def parse_dt_iso(value: Optional[str]) -> dt.datetime:
    if not value:
        return dt.datetime.now()
    try:
        return dt.datetime.fromisoformat(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Неверный формат datetime: {value}") from exc


def nlp_extract_entities(text: str) -> Dict[str, Any]:
    s = text.lower()

    time_of_day = None
    if "утр" in s:
        time_of_day = "morning"
    elif "днем" in s or "днём" in s:
        time_of_day = "day"
    elif "вечер" in s:
        time_of_day = "evening"
    elif "ноч" in s:
        time_of_day = "night"

    near_metro = "метро" in s

    max_price_level: Optional[int] = None
    if "дешев" in s or "недорог" in s:
        max_price_level = 1
    elif "средн" in s:
        max_price_level = 2
    elif "дорог" in s:
        max_price_level = 3

    has_ev = "электро" in s or "зарядк" in s or "ev" in s
    has_covered = "крыт" in s or "подзем" in s or "паркинг" in s

    return {
        "time_of_day": time_of_day,
        "near_metro": near_metro if near_metro else None,
        "max_price_level": max_price_level,
        "has_ev_charging": has_ev if has_ev else None,
        "has_covered": has_covered if has_covered else None,
    }


def build_occ_feature_df(lot_row: Dict[str, Any], ts: dt.datetime) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "hour": ts.hour,
                "dow": ts.weekday(),
                "temperature": 15.0,  # без реальной погоды
                "is_rain": 0,
                "is_event": 0,
                "near_metro": lot_row["near_metro"],
                "price_level": lot_row["price_level"],
                "has_covered": lot_row["has_covered"],
                "has_ev_charging": lot_row["has_ev_charging"],
                "lot_id_str": str(lot_row["id"]),
            }
        ]
    )[OCC_FEATURE_COLS]


def predict_occupancy_for_lot(lot_row: Dict[str, Any], ts: dt.datetime) -> float:
    df = build_occ_feature_df(lot_row, ts)
    pred = float(OCC_PIPE.predict(df)[0])
    return max(0.0, min(pred, 1.0))


def fetch_lots(filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()

    base_query = """
        SELECT
            id, name, latitude, longitude,
            near_metro, price_level, has_covered, has_ev_charging
        FROM parking_lot
        WHERE 1=1
    """
    params: List[Any] = []

    if filters:
        if filters.get("near_metro") is not None:
            base_query += " AND near_metro = ?"
            params.append(1 if filters["near_metro"] else 0)
        if filters.get("max_price_level") is not None:
            base_query += " AND price_level <= ?"
            params.append(int(filters["max_price_level"]))
        if filters.get("has_ev_charging") is not None:
            base_query += " AND has_ev_charging = ?"
            params.append(1 if filters["has_ev_charging"] else 0)
        if filters.get("has_covered") is not None:
            base_query += " AND has_covered = ?"
            params.append(1 if filters["has_covered"] else 0)

    base_query += " ORDER BY price_level ASC, near_metro DESC"

    cur.execute(base_query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------- Эндпоинты ----------


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/lots", response_model=List[Lot])
def api_list_lots(
    ts: Optional[str] = Query(default=None, description="ISO datetime, по умолчанию — сейчас"),
) -> List[Lot]:
    dt_value = parse_dt_iso(ts)
    lots = fetch_lots()

    result: List[Lot] = []
    for row in lots:
        occ = predict_occupancy_for_lot(row, dt_value)
        result.append(
            Lot(
                id=row["id"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                near_metro=bool(row["near_metro"]),
                price_level=row["price_level"],
                has_covered=bool(row["has_covered"]),
                has_ev_charging=bool(row["has_ev_charging"]),
                predicted_occupancy=occ,
            )
        )
    return result


@app.get("/api/occupancy/predict", response_model=OccupancyPredictionResponse)
def api_predict_occupancy(
    lot_id: int = Query(...),
    ts: Optional[str] = Query(default=None),
) -> OccupancyPredictionResponse:
    dt_value = parse_dt_iso(ts)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, latitude, longitude,
               near_metro, price_level, has_covered, has_ev_charging
        FROM parking_lot
        WHERE id = ?
        """,
        (lot_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Парковка не найдена")
    d = dict(row)
    occ = predict_occupancy_for_lot(d, dt_value)
    return OccupancyPredictionResponse(
        lot_id=lot_id,
        ts=dt_value,
        predicted_occupancy=occ,
    )


@app.get("/api/search", response_model=SearchResult)
def api_search(
    query: str = Query(..., min_length=1),
    ts: Optional[str] = Query(default=None),
    limit: int = Query(default=15, ge=1, le=100),
) -> SearchResult:
    dt_value = parse_dt_iso(ts)

    intent = NLP_PIPE.predict([query])[0]
    entities = nlp_extract_entities(query)

    filters: Dict[str, Any] = {}
    if entities["near_metro"]:
        filters["near_metro"] = True
    if entities["max_price_level"] is not None:
        filters["max_price_level"] = entities["max_price_level"]
    if entities["has_ev_charging"] is not None:
        filters["has_ev_charging"] = entities["has_ev_charging"]
    if entities["has_covered"] is not None:
        filters["has_covered"] = entities["has_covered"]

    if intent == "near_metro":
        filters["near_metro"] = True
    if intent == "cheap" and "max_price_level" not in filters:
        filters["max_price_level"] = 1

    lots = fetch_lots(filters)
    lots = lots[:limit]

    lot_models: List[Lot] = []
    for row in lots:
        occ = predict_occupancy_for_lot(row, dt_value)
        lot_models.append(
            Lot(
                id=row["id"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                near_metro=bool(row["near_metro"]),
                price_level=row["price_level"],
                has_covered=bool(row["has_covered"]),
                has_ev_charging=bool(row["has_ev_charging"]),
                predicted_occupancy=occ,
            )
        )

    return SearchResult(
        query=query,
        intent=intent,
        time_of_day=entities["time_of_day"],
        near_metro=filters.get("near_metro"),
        max_price_level=filters.get("max_price_level"),
        has_ev_charging=filters.get("has_ev_charging"),
        has_covered=filters.get("has_covered"),
        lots=lot_models,
    )


def _recommend_item_based(user_id: int, top_n: int = 10) -> List[int]:
    if user_id not in USER_ITEM.index:
        return []

    user_ratings = USER_ITEM.loc[user_id]
    rated_items = user_ratings[user_ratings > 0].index.tolist()
    if not rated_items:
        return []

    scores = pd.Series(0.0, index=USER_ITEM.columns)

    for item_id in rated_items:
        sim_vec = ITEM_SIM.loc[item_id]
        scores += sim_vec * float(user_ratings[item_id])

    scores = scores.drop(rated_items)
    scores = scores.sort_values(ascending=False)
    return scores.head(top_n).index.tolist()


def _recommend_content_based(top_n: int = 10) -> List[int]:
    df = LOT_FEATURES.copy()
    df["score"] = 0.0

    df["score"] += (1 - (df["price_level"] - 1) / 2)  # дешёвые выше
    df["score"] += df["near_metro"] * 0.5
    df["score"] += df["has_ev_charging"] * 0.3
    df["score"] += df["has_covered"] * 0.2

    df = df.sort_values("score", ascending=False)
    return df.head(top_n).index.tolist()


@app.get("/api/recommendations", response_model=RecommendationsResponse)
def api_recommendations(
    user_id: Optional[int] = Query(default=None),
    variant: Optional[str] = Query(
        default=None,
        description="A или B — для A/B тестирования (A=collab, B=content)",
    ),
    limit: int = Query(default=10, ge=1, le=50),
    ts: Optional[str] = Query(default=None),
) -> RecommendationsResponse:
    dt_value = parse_dt_iso(ts)

    chosen_variant = variant or ("A" if user_id else "B")

    if chosen_variant == "A" and user_id is not None:
        item_ids = _recommend_item_based(user_id, top_n=limit)
        if not item_ids:
            chosen_variant = "B"
    if chosen_variant == "B" or user_id is None:
        item_ids = _recommend_content_based(top_n=limit)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, latitude, longitude,
               near_metro, price_level, has_covered, has_ev_charging
        FROM parking_lot
        WHERE id IN ({",".join(["?"] * len(item_ids))})
        """,
        item_ids,
    )
    rows = {r["id"]: dict(r) for r in cur.fetchall()}
    conn.close()

    recs: List[Recommendation] = []
    for lot_id in item_ids:
        row = rows.get(lot_id)
        if not row:
            continue
        occ = predict_occupancy_for_lot(row, dt_value)
        lot = Lot(
            id=row["id"],
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            near_metro=bool(row["near_metro"]),
            price_level=row["price_level"],
            has_covered=bool(row["has_covered"]),
            has_ev_charging=bool(row["has_ev_charging"]),
            predicted_occupancy=occ,
        )
        # простая метрика: обратная занятость + бонус за метро и цену
        score = (1.0 - occ) + (1 - (row["price_level"] - 1) / 2) + (0.3 if row["near_metro"] else 0.0)
        recs.append(Recommendation(lot=lot, score=float(score)))

    return RecommendationsResponse(
        user_id=user_id,
        variant=chosen_variant,
        recommendations=recs,
    )


if __name__ == "__main__":
    import os
    import uvicorn

    host = os.environ.get("AI_API_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("AI_API_PORT", "8001"))
    except (TypeError, ValueError):
        port = 8001

    uvicorn.run("api_server:app", host=host, port=port, reload=True)

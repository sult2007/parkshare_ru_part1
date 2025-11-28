from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field, root_validator

app = FastAPI(
    title="ParkShare CV Service",
    version="0.1.0",
    description=(
        "Заглушечный CV‑сервис ParkMate AI. "
        "Интерфейс готов под интеграцию OpenCV/ONNX/WebGPU‑моделей."
    ),
)


class LicensePlateRequest(BaseModel):
    image_url: Optional[str] = Field(
        None,
        description="URL до кадра/фото с номером автомобиля (если используется серверная загрузка).",
    )
    image_base64: Optional[str] = Field(
        None,
        description="Base64‑кодированное изображение (если отправляем напрямую).",
    )
    region: str = Field("RU", description="Код региона/страны (например, RU, EU, US).")

    @root_validator
    def validate_source(cls, values):
        if not values.get("image_url") and not values.get("image_base64"):
            raise ValueError("Нужно передать либо image_url, либо image_base64.")
        return values


class LicensePlateResponse(BaseModel):
    plate: str
    normalized_plate: str
    region: str
    confidence: float


class ParkingOccupancyRequest(BaseModel):
    image_url: Optional[str] = Field(
        None,
        description="URL до кадра камеры с парковкой.",
    )
    camera_id: Optional[str] = Field(
        None,
        description="ID камеры/потока в вашем домене.",
    )
    total_slots: Optional[int] = Field(
        None,
        gt=0,
        description="Общее количество мест (если известно заранее).",
    )

    @root_validator
    def validate_source(cls, values):
        if not values.get("image_url") and not values.get("camera_id"):
            raise ValueError("Нужно указать image_url или camera_id.")
        return values


class ParkingOccupancyResponse(BaseModel):
    occupied_slots: int
    total_slots: int
    occupancy_rate: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/v1/cv/license-plate",
    response_model=LicensePlateResponse,
    tags=["cv"],
    summary="Распознавание госномера (заглушка)",
)
def recognize_plate(payload: LicensePlateRequest) -> LicensePlateResponse:
    """
    Заглушка для распознавания госномера.
    Реальная логика должна вызывать модель (OpenCV+ONNX и т.п.).
    """
    # TODO: заменить на вызов реальной модели/сервиса
    fake_plate = "A000AA197"
    normalized = fake_plate.replace(" ", "")
    return LicensePlateResponse(
        plate=fake_plate,
        normalized_plate=normalized,
        region=payload.region,
        confidence=0.85,
    )


@app.post(
    "/api/v1/cv/parking-occupancy",
    response_model=ParkingOccupancyResponse,
    tags=["cv"],
    summary="Оценка заполненности парковки по кадру (заглушка)",
)
def parking_occupancy(payload: ParkingOccupancyRequest) -> ParkingOccupancyResponse:
    """
    Заглушка для оценки заполненности парковки:
    - если total_slots известен, считаем примерно 50% занятости;
    - если нет, предполагаем 20 мест и 40% занято.
    """
    total_slots = payload.total_slots or 20
    occupied_slots = max(1, int(total_slots * 0.4))
    occupancy_rate = occupied_slots / float(total_slots)
    return ParkingOccupancyResponse(
        occupied_slots=occupied_slots,
        total_slots=total_slots,
        occupancy_rate=round(occupancy_rate, 3),
        timestamp=datetime.now(timezone.utc),
    )

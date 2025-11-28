/**
 * ParkMate AI — фронтовый контракт мультимодального ассистента ParkShare.
 * Файл можно использовать как исходник для будущего SPA/PWA на TypeScript.
 *
 * Соответствует backend‑эндпоинтам:
 *  - GET  /api/ai/parkmate/config/
 *  - POST /api/ai/parkmate/price-forecast/
 *  - POST /api/ai/parkmate/availability/
 *  - POST /api/ai/departure-assistant/
 *  - POST /api/ai/cv/license-plate/        (через cv_service)
 *  - POST /api/ai/cv/parking-occupancy/    (через cv_service)
 */

export interface ParkMateVoiceCommands {
  booking: string;
  navigation: string;
  payment: string;
  support: string;
}

export interface ParkMateComputerVision {
  licensePlateRecognition: string;
  parkingSpotDetection: string;
  damageDetection: string;
  occupancyAnalytics: string;
}

export interface ParkMatePredictions {
  arrivalTime: string;
  priceForecast: string;
  availability: string;
}

export interface ParkMateAI {
  voiceCommands: ParkMateVoiceCommands;
  computerVision: ParkMateComputerVision;
  predictions: ParkMatePredictions;
}

/**
 * Базовый конфиг под RU‑профиль (ParkShare RU).
 * Значения URL должны совпадать с Django‑эндпоинтами.
 */
export const parkMateConfig: ParkMateAI = {
  voiceCommands: {
    booking: "Забронировать парковку рядом",
    navigation: "Построить маршрут до парковки",
    payment: "Оплатить текущую парковку",
    support: "Связаться с поддержкой ParkShare",
  },
  computerVision: {
    licensePlateRecognition: "/api/ai/cv/license-plate/",
    parkingSpotDetection: "/api/ai/cv/parking-occupancy/",
    damageDetection: "/api/ai/cv/vehicle-damage/", // зарезервировано на будущее
    occupancyAnalytics: "/api/ai/stress-index/",
  },
  predictions: {
    arrivalTime: "/api/ai/departure-assistant/",
    priceForecast: "/api/ai/parkmate/price-forecast/",
    availability: "/api/ai/parkmate/availability/",
  },
};

// --------- Типы для REST‑ответов ParkMate ---------

export interface PriceForecastRequestPayload {
  spotId: string;
}

export interface PriceForecastResponse {
  spot_id: string;
  lot_id: string;
  currency: string;
  base_price: number;
  recommended_price: number;
  min_price: number;
  max_price: number;
  discount_percent: number;
  is_discount: boolean;
  reason: string;
}

export interface AvailabilityForecastRequestPayload {
  spotId?: string;
  occupancy_7d?: number;
  stress_index?: number;
}

export interface AvailabilityForecastResponse {
  spot_id: string | null;
  occupancy_7d: number;
  stress_index: number;
  as_of: string;
  availability: {
    next_1h: number;
    next_3h: number;
    next_24h: number;
  };
}

// --------- Helper‑функции для фронта ---------

async function jsonFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const resp = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Request failed ${resp.status}: ${text}`);
  }

  return (await resp.json()) as T;
}

export async function getPriceForecast(
  payload: PriceForecastRequestPayload
): Promise<PriceForecastResponse> {
  return jsonFetch<PriceForecastResponse>(
    parkMateConfig.predictions.priceForecast,
    {
      method: "POST",
      body: JSON.stringify({ spot_id: payload.spotId }),
    }
  );
}

export async function getAvailabilityForecast(
  payload: AvailabilityForecastRequestPayload
): Promise<AvailabilityForecastResponse> {
  return jsonFetch<AvailabilityForecastResponse>(
    parkMateConfig.predictions.availability,
    {
      method: "POST",
      body: JSON.stringify({
        spot_id: payload.spotId,
        occupancy_7d: payload.occupancy_7d,
        stress_index: payload.stress_index,
      }),
    }
  );
}
export async function fetchPriceForecast(
  payload: PriceForecastRequestPayload
): Promise<PriceForecastResponse> {
  return jsonFetch<PriceForecastResponse>(
    parkMateConfig.predictions.priceForecast,
    {
      method: "POST",
      body: JSON.stringify({ spot_id: payload.spotId }),
    }
  );
}

export async function fetchAvailabilityForecast(
  payload: AvailabilityForecastRequestPayload
): Promise<AvailabilityForecastResponse> {
  return jsonFetch<AvailabilityForecastResponse>(
    parkMateConfig.predictions.availability,
    {
      method: "POST",
      body: JSON.stringify({
        spot_id: payload.spotId,
        occupancy_7d: payload.occupancy_7d,
        stress_index: payload.stress_index,
      }),
    }
  );
}


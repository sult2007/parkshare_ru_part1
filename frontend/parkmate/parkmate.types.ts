// frontend/parkmate/parkmate.types.ts

export interface ParkMateAI {
  voiceCommands: {
    booking: string;
    navigation: string;
    payment: string;
    support: string;
  };
  computerVision: {
    licensePlateRecognition: string;
    parkingSpotDetection: string;
    damageDetection: string;
    occupancyAnalytics: string;
  };
  predictions: {
    arrivalTime: string;
    priceForecast: string;
    availability: string;
  };
}

/**
 * Базовый конфиг ParkMate, который фронтенд может запросить с бэка.
 * На следующей фазе мы добавим endpoint вроде /api/ai/parkmate/config/.
 */
export const defaultParkMateConfig: ParkMateAI = {
  voiceCommands: {
    booking: "Забронируй ближайшее свободное место на 2 часа",
    navigation: "Построй маршрут до моего места парковки",
    payment: "Оплати мою текущую парковку",
    support: "Соедини с поддержкой ParkShare",
  },
  computerVision: {
    licensePlateRecognition: "/api/ai/cv/license-plate/",
    parkingSpotDetection: "/api/ai/cv/parking-spots/",
    damageDetection: "/api/ai/cv/damage/",
    occupancyAnalytics: "/api/ai/cv/occupancy/",
  },
  predictions: {
    arrivalTime: "/api/ai/predict/arrival-time/",
    priceForecast: "/api/ai/predict/pricing/",
    availability: "/api/ai/predict/availability/",
  },
};

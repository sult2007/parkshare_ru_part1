export type PlannerPlanPayload = {
  destination_lat: number;
  destination_lon: number;
  arrival_at?: string | null;
  requires_ev_charging?: boolean;
  requires_covered?: boolean;
  max_price_level?: number;
};

export type PlannerRecommendation = {
  spot_id: string;
  lot_name: string;
  address: string;
  distance_km: number;
  predicted_occupancy: number;
  has_ev_charging: boolean;
  is_covered: boolean;
  hourly_price: number;
  confidence: number;
};

export async function planParking(payload: PlannerPlanPayload) {
  const resp = await fetch("/api/planner/plan/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!resp.ok) {
    throw new Error("Не удалось получить планирование");
  }
  return resp.json() as Promise<{ recommendations: PlannerRecommendation[] }>;
}

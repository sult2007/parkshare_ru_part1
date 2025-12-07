export type Coordinates = { lat: number; lng: number };

export interface SpotSummary {
  id: string;
  title: string;
  price?: number;
  tags?: string[];
  coords?: Coordinates;
}

export interface BookingSession {
  id: string;
  spot_id: string;
  spot_name: string;
  lot_name: string;
  status: string;
  end_at: string;
  remaining_seconds: number;
  is_paid?: boolean;
}

export type AssistantActionType = 'focus_map' | 'book' | 'booking_start' | 'booking_extend' | 'booking_stop';

export interface AssistantAction {
  type: AssistantActionType;
  spot_id?: string;
  booking_id?: string;
  coords?: Coordinates;
  title?: string;
  price?: number;
  duration_minutes?: number;
  extend_minutes?: number;
}

export interface AssistantAlert {
  type: string;
  booking_id?: string;
  spot?: string;
  minutes_left?: number;
}

export interface AssistantResponse {
  reply: string;
  suggestions: SpotSummary[];
  actions: AssistantAction[];
  sessions?: BookingSession[];
  alerts?: AssistantAlert[];
}

export interface SearchResponse {
  count: number;
  results: SpotSummary[];
}


const STORAGE_KEY = 'ps.pwa.state.v2';
const OFFLINE_QUEUE_LIMIT = 50;
const OFFLINE_QUEUE_TTL = 24 * 60 * 60 * 1000;

const initialState = {
  appVersion: '2024.09.0',
  isOnline: navigator.onLine,
  lastKnownPosition: null,
  mapView: { center: null, zoom: 11, features: [] },
  filters: {
    priceMax: null,
    onlyFree: false,
    ev: false,
    covered: false,
    is_24_7: false,
    ai_recommended: false,
    distance_km: 5,
  },
  pagination: {
    next: null,
    previous: null,
    count: 0,
    page_size: 20,
  },
  spots: [],
  favorites: [],
  savedPlaces: [],
  offlineQueue: [],
  profile: { id: null, role: 'guest', layout_profile: 'comfortable', theme: 'light', platform: 'web' },
  pushOptIn: false,
};

let state = loadState();
const subscribers = new Set();

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...initialState };
    const parsed = JSON.parse(raw);
    const now = Date.now();
    const hydratedQueue = (parsed.offlineQueue || []).filter((item) =>
      item && item.created_at && now - item.created_at < OFFLINE_QUEUE_TTL
    );
    return {
      ...initialState,
      ...parsed,
      filters: { ...initialState.filters, ...(parsed.filters || {}) },
      mapView: { ...initialState.mapView, ...(parsed.mapView || {}) },
      profile: { ...initialState.profile, ...(parsed.profile || {}) },
      offlineQueue: hydratedQueue.slice(-OFFLINE_QUEUE_LIMIT),
    };
  } catch (err) {
    console.warn('[PWA] failed to load state', err);
    return { ...initialState };
  }
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    console.warn('[PWA] failed to persist state', err);
  }
}

function setState(patch) {
  state = { ...state, ...patch };
  persist();
  subscribers.forEach((cb) => cb(state));
}

export function subscribe(callback) {
  subscribers.add(callback);
  callback(state);
  return () => subscribers.delete(callback);
}

export function getState() {
  return state;
}

export function updateFilters(patch) {
  setState({ filters: { ...state.filters, ...patch } });
}

export function updatePagination(meta) {
  setState({ pagination: { ...state.pagination, ...meta } });
}

export function setSpots(spots) {
  setState({ spots });
}

export function appendSpots(spots) {
  setState({ spots: [...state.spots, ...spots] });
}

export function setConnectionStatus(isOnline) {
  setState({ isOnline });
}

export function setMapView(patch) {
  setState({ mapView: { ...state.mapView, ...patch } });
}

export function setFavorites(favorites) {
  setState({ favorites });
}

export function toggleFavorite(id) {
  const exists = state.favorites.includes(id);
  const updated = exists ? state.favorites.filter((item) => item !== id) : [...state.favorites, id];
  setState({ favorites: updated });
}

export function setSavedPlaces(items) {
  setState({ savedPlaces: items });
}

export function queueAction(action) {
  const now = Date.now();
  const entry = {
    id: action.id || `${now}-${Math.random().toString(16).slice(2, 8)}`,
    type: action.type,
    payload: action.payload || {},
    status: 'pending',
    attempts: action.attempts || 0,
    created_at: action.created_at || now,
  };
  const freshQueue = state.offlineQueue.filter((item) => now - item.created_at < OFFLINE_QUEUE_TTL);
  const offlineQueue = [...freshQueue.slice(-(OFFLINE_QUEUE_LIMIT - 1)), entry];
  setState({ offlineQueue });
  return entry.id;
}

export function flushQueue(predicate) {
  const now = Date.now();
  const kept = state.offlineQueue
    .filter((item) => now - item.created_at < OFFLINE_QUEUE_TTL)
    .filter((item) => !(predicate ? predicate(item) : false));
  setState({ offlineQueue: kept });
}

export function markQueueItem(id, patch) {
  const queue = state.offlineQueue.map((item) => (item.id === id ? { ...item, ...patch } : item));
  setState({ offlineQueue: queue });
}

export function setProfile(profile) {
  setState({ profile: { ...state.profile, ...profile } });
}

export function setThemeConfig(config) {
  const profile = {
    ...state.profile,
    layout_profile: config.layout_profile || state.profile.layout_profile,
    theme: config.theme || state.profile.theme,
    platform: config.platform || state.profile.platform,
  };
  setState({ profile });
}

export function setMapFeatures(features) {
  setState({ mapView: { ...state.mapView, features } });
}

export function setPushOptIn(optIn) {
  setState({ pushOptIn: optIn });
}

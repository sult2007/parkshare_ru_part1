const STORAGE_KEY = 'ps.pwa.state.v2';

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
    return {
      ...initialState,
      ...parsed,
      filters: { ...initialState.filters, ...(parsed.filters || {}) },
      mapView: { ...initialState.mapView, ...(parsed.mapView || {}) },
      profile: { ...initialState.profile, ...(parsed.profile || {}) },
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
  const offlineQueue = [...state.offlineQueue, action];
  setState({ offlineQueue });
}

export function flushQueue(predicate) {
  const kept = state.offlineQueue.filter((item) => !predicate(item));
  setState({ offlineQueue: kept });
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

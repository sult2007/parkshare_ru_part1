import {
  appendSpots,
  flushQueue,
  getState,
  queueAction,
  setConnectionStatus,
  setMapFeatures,
  setSavedPlaces,
  setFavorites,
  setSpots,
  setThemeConfig,
  updatePagination,
  markQueueItem,
} from './state-store.js';

const API_ROOT = '/api/parking';
const AI_ROOT = '/api/ai';
const datasetCache = new Map();
const aiCache = new Map();

async function apiFetch(path, { method = 'GET', body, params } = {}) {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      url.searchParams.set(key, value);
    });
  }
  const headers = { 'Content-Type': 'application/json' };
  const options = { method, headers, credentials: 'include' };
  if (body) options.body = JSON.stringify(body);

  try {
    const response = await fetch(url.toString(), options);
    setConnectionStatus(true);
    if (!response.ok) throw new Error(`API ${response.status}`);
    return await response.json();
  } catch (err) {
    setConnectionStatus(false);
    throw err;
  }
}

export async function loadSpots({ append = false, filters = {}, page = 1, pageSize = 50 }) {
  const params = {
    page,
    page_size: Math.min(pageSize || 50, 100),
    ...filters,
  };
  const cacheKey = `spots:${JSON.stringify(params)}`;
  try {
    const payload = await cachedApiFetch(`${API_ROOT}/spots/`, { params }, cacheKey, 300000);
    const { results, next, previous, count } = payload;
    if (append) {
      appendSpots(results);
    } else {
      setSpots(results);
    }
    updatePagination({ next, previous, count, page_size: params.page_size });
    cacheDataset('spots', payload);
  } catch (err) {
    const cached = readDataset('spots') || datasetCache.get(cacheKey);
    if (cached) {
      const { results, next, previous, count } = cached;
      if (append) {
        appendSpots(results);
      } else {
        setSpots(results);
      }
      updatePagination({ next, previous, count, page_size: params.page_size });
    } else {
      console.warn('[PWA] failed to load spots and no cache', err);
    }
  }
}

export async function loadFavorites() {
  try {
    const payload = await apiFetch(`${API_ROOT}/favorites/`);
    setFavorites(payload.results ? payload.results.map((item) => item.spot) : payload.map((i) => i.spot));
    cacheDataset('favorites', payload);
  } catch (err) {
    const cached = readDataset('favorites');
    if (cached) {
      setFavorites(cached.results ? cached.results.map((i) => i.spot) : cached.map((i) => i.spot));
    }
  }
}

export async function saveFavorite(spotId) {
  if (!navigator.onLine) {
    queueAction({ type: 'favorite:toggle', payload: { spotId } });
    return toggleLocalFavorite(spotId);
  }
  await apiFetch(`${API_ROOT}/favorites/`, {
    method: 'POST',
    body: { spot: spotId },
  });
  toggleLocalFavorite(spotId);
}

function toggleLocalFavorite(spotId) {
  const current = getState().favorites || [];
  if (current.includes(spotId)) {
    setFavorites(current.filter((id) => id !== spotId));
  } else {
    setFavorites([...current, spotId]);
  }
}

export async function loadSavedPlaces() {
  try {
    const payload = await apiFetch(`${API_ROOT}/saved-places/`);
    const items = payload.results || payload;
    setSavedPlaces(items);
    cacheDataset('saved_places', payload);
  } catch (err) {
    const cached = readDataset('saved_places');
    if (cached) {
      setSavedPlaces(cached.results || cached);
    }
  }
}

export async function syncOfflineQueue() {
  const { offlineQueue } = getState();
  if (!offlineQueue.length || !navigator.onLine) return;
  for (const item of offlineQueue) {
    try {
      if (item.type === 'favorite:toggle') {
        await saveFavorite(item.payload.spotId);
        markQueueItem(item.id, { status: 'synced' });
      }
      if (item.type === 'saved_place:create') {
        await createSavedPlace(item.payload.place, { skipQueue: true });
        markQueueItem(item.id, { status: 'synced' });
      }
    } catch (err) {
      const attempts = (item.attempts || 0) + 1;
      if (attempts >= 3) {
        markQueueItem(item.id, { status: 'failed', attempts });
      } else {
        markQueueItem(item.id, { attempts });
      }
    }
  }
  flushQueue((item) => item.status === 'synced' || item.status === 'failed');
}

export async function loadProfile() {
  try {
    const payload = await apiFetch('/api/ai/parkmate/config/');
    setThemeConfig(payload);
  } catch (_) {
    /* ignore */
  }
}

export async function loadMapFeatures(filters = {}) {
  const params = { ...filters };
  const cacheKey = `map:${JSON.stringify(params)}`;
  try {
    const payload = await cachedApiFetch('/api/parking/map/', { params }, cacheKey, 300000);
    setMapFeatures(payload.features || []);
  } catch (err) {
    const cached = datasetCache.get(cacheKey) || readDataset('map_features');
    if (cached?.features) {
      setMapFeatures(cached.features);
    }
  }
}

export async function registerPushSubscription(subscription) {
  await apiFetch('/api/parking/push-subscriptions/', { method: 'POST', body: subscription });
}

export async function loadAiRecommendations(filters = {}) {
  const params = {
    city: filters.city,
    limit: Math.min(filters.limit || 20, 50),
  };
  const cacheKey = `ai:rec:${JSON.stringify(params)}`;
  try {
    const payload = await cachedAiFetch(`${AI_ROOT}/recommendations/`, { params }, cacheKey, 300000);
    return payload?.results || [];
  } catch (err) {
    const cached = readDataset(cacheKey) || aiCache.get(cacheKey)?.payload;
    if (cached) return cached.results || cached;
    throw err;
  }
}

export async function loadAiStressIndex(filters = {}) {
  const params = { city: filters.city };
  const cacheKey = `ai:stress:${JSON.stringify(params)}`;
  try {
    return await cachedAiFetch(`${AI_ROOT}/stress-index/`, { params }, cacheKey, 180000);
  } catch (err) {
    const cached = readDataset(cacheKey) || aiCache.get(cacheKey)?.payload;
    if (cached) return cached;
    throw err;
  }
}

export async function createSavedPlace(place, { skipQueue = false } = {}) {
  const body = {
    title: place.title,
    place_type: place.place_type || 'custom',
    latitude: place.latitude,
    longitude: place.longitude,
  };
  if (!navigator.onLine && !skipQueue) {
    queueAction({ type: 'saved_place:create', payload: { place: body } });
    setSavedPlaces([...(getState().savedPlaces || []), { ...body, id: `local-${Date.now()}` }]);
    return;
  }
  await apiFetch(`${API_ROOT}/saved-places/`, { method: 'POST', body });
  await loadSavedPlaces();
}

async function cachedApiFetch(path, opts, cacheKey, ttlMs = 120000) {
  if (datasetCache.has(cacheKey)) {
    const cached = datasetCache.get(cacheKey);
    if (cached.expires > Date.now()) {
      return cached.payload;
    }
  }
  const payload = await apiFetch(path, opts);
  datasetCache.set(cacheKey, { payload, expires: Date.now() + ttlMs });
  cacheDataset(cacheKey, payload);
  return payload;
}

function cacheDataset(name, payload) {
  try {
    localStorage.setItem(`ps.pwa.cache.${name}`, JSON.stringify(payload));
  } catch (_) {}
}

function readDataset(name) {
  try {
    const raw = localStorage.getItem(`ps.pwa.cache.${name}`);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

async function cachedAiFetch(path, opts, cacheKey, ttlMs = 180000) {
  if (aiCache.has(cacheKey)) {
    const cached = aiCache.get(cacheKey);
    if (cached.expires > Date.now()) {
      return cached.payload;
    }
  }
  const payload = await apiFetch(path, opts);
  aiCache.set(cacheKey, { payload, expires: Date.now() + ttlMs });
  cacheDataset(cacheKey, payload);
  return payload;
}

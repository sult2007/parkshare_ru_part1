import { subscribe, toggleFavorite, setMapView } from './state-store.js';
import { loadSpots, saveFavorite, loadAiRecommendations } from './api-client.js';
import { renderSkeletonCards, renderSpotCard } from './ui-kit.js';

let loading = false;
let aiCacheKey = null;
let aiHints = new Map();

export function initSpotsView() {
  const list = document.querySelector('[data-spots-list]');
  if (!list) return;

  subscribe((state) => {
    renderSpots(list, state.spots, state.favorites);
  });

  const loadMoreBtn = document.querySelector('[data-spots-load-more]');
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => fetchMore());
  }

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition((pos) => {
      const center = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      setMapView({ center });
      fetchInitial({ lat: center.lat, lng: center.lng });
    }, () => fetchInitial({}));
  } else {
    fetchInitial({});
  }
}

async function fetchInitial(filters) {
  if (loading) return;
  loading = true;
  renderSkeletonCards(document.querySelector('[data-spots-list]'));
  await Promise.all([loadSpots({ filters, page: 1 }), primeAiHints(filters)]);
  loading = false;
}

async function fetchMore() {
  if (loading) return;
  loading = true;
  const next = document.querySelector('[data-spots-load-more]');
  const page = next?.dataset.page ? Number(next.dataset.page) : 1;
  await loadSpots({ append: true, page: page + 1 });
  if (next) next.dataset.page = page + 1;
  loading = false;
}

function renderSpots(container, spots, favorites) {
  if (!spots || !spots.length) {
    container.innerHTML = '<div class="ps-empty">Нет парковок поблизости или вы офлайн. Проверьте соединение или выберите другой район.</div>';
    return;
  }
  container.innerHTML = '';
  const scoredSpots = [...spots].sort((a, b) => getAiScore(b.id) - getAiScore(a.id));
  scoredSpots.forEach((spot) => {
    const aiHint = aiHints.get(spot.id);
    const card = renderSpotCard(spot, {
      favorite: favorites?.includes(spot.id),
      aiHint,
      onFavorite: () => handleFavorite(spot.id),
    });
    container.appendChild(card);
  });
}

async function handleFavorite(spotId) {
  toggleFavorite(spotId);
  try {
    await saveFavorite(spotId);
  } catch (err) {
    console.warn('[PWA] favorite queued', err);
  }
}

async function primeAiHints(filters) {
  const key = JSON.stringify(filters || {});
  if (aiCacheKey === key && aiHints.size) return;
  aiCacheKey = key;
  try {
    const recommendations = await loadAiRecommendations({ city: filters?.city, limit: 40 });
    aiHints = new Map();
    recommendations.forEach((rec, index) => {
      const spotId = Number(rec.spot_id || rec.spotId);
      if (!spotId) return;
      aiHints.set(spotId, {
        label: index < 3 ? 'Рекомендуем' : 'AI',
        score: 100 - index * 2 + (rec.ai_discount_percent || 0),
        reason: rec.ai_reason || rec.address || '',
      });
    });
  } catch (err) {
    aiHints = new Map();
    console.warn('[PWA] AI hints unavailable', err);
  }
}

function getAiScore(spotId) {
  const hint = aiHints.get(spotId);
  return hint ? hint.score || 0 : 0;
}

import { subscribe, toggleFavorite, setMapView } from './state-store.js';
import { loadSpots, saveFavorite } from './api-client.js';

let loading = false;

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
  await loadSpots({ filters, page: 1 });
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
    container.innerHTML = '<div class="ps-empty">Места будут показаны после загрузки карты.</div>';
    return;
  }
  container.innerHTML = '';
  spots.forEach((spot) => {
    const card = document.createElement('article');
    card.className = 'ps-card ps-card--spot';
    card.dataset.spotId = spot.id;
    card.innerHTML = `
      <div class="ps-card-header">
        <div class="ps-card-title">${spot.lot?.city || ''} ${spot.lot?.name || ''} — ${spot.name}</div>
        <button class="ps-icon-btn" type="button" aria-label="В избранное" data-fav-toggle>
          ${favorites?.includes(spot.id) ? '★' : '☆'}
        </button>
      </div>
      <div class="ps-card-body">
        <div class="ps-card-line">от ${spot.hourly_price} ₽/час</div>
        <div class="ps-card-line ps-card-line--muted">${spot.lot?.address || 'Адрес уточняется'}</div>
      </div>
    `;
    const favBtn = card.querySelector('[data-fav-toggle]');
    favBtn.addEventListener('click', () => handleFavorite(spot.id));
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

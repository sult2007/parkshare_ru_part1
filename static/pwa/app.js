import { initRouter, bindConnectionBanner } from './router.js';
import { initSpotsView } from './spots-view.js';
import {
  getState,
  setConnectionStatus,
  setMapView,
  subscribe,
} from './state-store.js';
<<<<<<< ours
<<<<<<< ours
import { loadFavorites, loadSavedPlaces, syncOfflineQueue } from './api-client.js';
=======
=======
>>>>>>> theirs
import {
  loadFavorites,
  loadMapFeatures,
  loadProfile,
  loadSavedPlaces,
  syncOfflineQueue,
} from './api-client.js';
import { initPushUI } from './ui-kit.js';
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs

const APP_VERSION = '2024.09.0';

function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker
    .register('/service-worker.js', { updateViaCache: 'none' })
    .then((reg) => {
      console.log('[SW] registered', reg.scope);
      if (reg.waiting) {
        notifyUpdate(reg.waiting);
      }
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (!newWorker) return;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            notifyUpdate(newWorker);
          }
        });
      });
    })
    .catch((err) => console.warn('[SW] registration failed', err));
}

function notifyUpdate(worker) {
  const banner = document.querySelector('[data-sw-update]');
  if (!banner) {
    worker.postMessage('SW_APPLY_UPDATE');
    return;
  }
  banner.hidden = false;
  const btn = banner.querySelector('button');
  btn?.addEventListener('click', () => {
    worker.postMessage('SW_APPLY_UPDATE');
    worker.addEventListener('statechange', () => {
      if (worker.state === 'activated') {
        window.location.reload();
      }
    });
  });
}

function hydrateUI() {
  bindConnectionBanner();
  initRouter();
  initSpotsView();
  loadFavorites();
  loadSavedPlaces();
<<<<<<< ours
<<<<<<< ours
=======
  loadProfile();
  loadMapFeatures();
  initPushUI();
>>>>>>> theirs
=======
  loadProfile();
  loadMapFeatures();
  initPushUI();
>>>>>>> theirs
}

function wireConnectivity() {
  window.addEventListener('online', () => {
    setConnectionStatus(true);
    syncOfflineQueue();
  });
  window.addEventListener('offline', () => setConnectionStatus(false));
}

function hydrateMeta() {
  const counter = document.querySelector('[data-spots-count]');
  subscribe((state) => {
    if (counter) counter.textContent = state.spots.length || state.pagination.count || 0;
  });
}

function init() {
  console.log('[PWA] booting', APP_VERSION);
  registerServiceWorker();
  hydrateUI();
  wireConnectivity();
  hydrateMeta();

  const map = getState().mapView;
  if (map?.center) {
    setMapView(map);
  }
}

document.addEventListener('DOMContentLoaded', init);

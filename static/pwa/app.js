import { getState, setConnectionStatus, setMapView, subscribe } from './state-store.js';
import { loadFavorites, loadMapFeatures, loadProfile, loadSavedPlaces, syncOfflineQueue } from './api-client.js';
import { initPushUI, initLazyMedia } from './ui-kit.js';

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

async function hydrateUI() {
  initLazyMedia();
  loadFavorites();
  loadSavedPlaces();
  loadProfile();
  initPushUI();

  const needsMap = document.querySelector('[data-spots-list]') || document.querySelector('[data-route="map"]');
  if (needsMap) {
    const [{ initRouter, bindConnectionBanner }, { initSpotsView }] = await Promise.all([
      import('./router.js'),
      import('./spots-view.js'),
    ]);
    bindConnectionBanner();
    initRouter();
    initSpotsView();
    loadMapFeatures();
  }
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

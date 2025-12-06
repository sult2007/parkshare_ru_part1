// static/service-worker.js — production-grade PWA cache with app versioning
const APP_VERSION = '2024.09.0';
const CACHE_PREFIX = 'parkshare-';
const RUNTIME_CACHE = `${CACHE_PREFIX}runtime-${APP_VERSION}`;
const STATIC_CACHE = `${CACHE_PREFIX}static-${APP_VERSION}`;
const SHELL_CACHE = `${CACHE_PREFIX}shell-${APP_VERSION}`;
const API_CACHE = `${CACHE_PREFIX}api-${APP_VERSION}`;
const PRIVATE_API_CACHE = `${CACHE_PREFIX}api-private-${APP_VERSION}`;
const MAP_CACHE = `${CACHE_PREFIX}map-${APP_VERSION}`;
const OFFLINE_URL = '/offline/';
const APP_SHELL = [
  '/',
  '/map/',
  '/личный-кабинет/',
  '/кабинет-владельца/',
  OFFLINE_URL,
  '/manifest.webmanifest',
];

const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/map.js',
  '/static/js/quantum-theme-manager.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-72.png',
  '/static/pwa/app.js',
  '/static/pwa/api-client.js',
  '/static/pwa/state-store.js',
  '/static/pwa/router.js',
  '/static/pwa/spots-view.js',
  '/static/pwa/ui-kit.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL)),
      caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
    ]).catch((err) => {
      console.warn('[SW] install cache error', err);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter(
            (key) =>
              key.startsWith(CACHE_PREFIX) &&
              ![
                RUNTIME_CACHE,
                STATIC_CACHE,
                SHELL_CACHE,
                API_CACHE,
                PRIVATE_API_CACHE,
                MAP_CACHE,
              ].includes(key)
          )
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('message', (event) => {
  if (event.data === 'SW_APPLY_UPDATE') {
    self.skipWaiting();
    return;
  }
  if (event.data && event.data.type === 'PRIME_SHELL') {
    precacheShell();
  }
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isSameOrigin = url.origin === self.location.origin;

  if (request.headers.get('accept')?.includes('text/html')) {
    if (isSameOrigin) {
      event.respondWith(networkFirst(request, SHELL_CACHE, OFFLINE_URL));
      return;
    }
  }

  if (isApiRequest(url)) {
    if (request.headers.get('authorization')) {
      event.respondWith(networkFirst(request, PRIVATE_API_CACHE));
      return;
    }
    event.respondWith(staleWhileRevalidate(request, API_CACHE));
    return;
  }

  if (isMapTile(url)) {
    event.respondWith(limitCacheSize(cacheFirst(request, MAP_CACHE), 150));
    return;
  }

  if (isAsset(url)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  event.respondWith(staleWhileRevalidate(request, RUNTIME_CACHE));
});

self.addEventListener('sync', (event) => {
  if (event.tag === 'ps-sync-queue') {
    event.waitUntil(flushOfflineQueue());
  }
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'ParkShare';
  const body = data.body || 'Новые события по вашим бронированиям';
  const url = data.url || '/map/';
  const actions = data.actions || [];
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { url },
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-72.png',
      actions,
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  const targetUrl = event.notification?.data?.url || '/map/';
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});

async function precacheShell() {
  const cache = await caches.open(SHELL_CACHE);
  await cache.addAll(APP_SHELL);
}

function isApiRequest(url) {
  return url.pathname.startsWith('/api/');
}

function isMapTile(url) {
  return url.hostname.includes('tile') || url.pathname.includes('/tiles/') || url.pathname.match(/\/(\d+)\/(\d+)\/(\d+)\.png/);
}

function isAsset(url) {
  return (
    url.pathname.startsWith('/static/') ||
    url.pathname.match(/\.(?:js|css|png|svg|webp|jpg|jpeg|woff2?)$/)
  );
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

async function networkFirst(request, cacheName, fallbackUrl) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (fallbackUrl) {
      const fallback = await caches.match(fallbackUrl);
      if (fallback) return fallback;
    }
    throw err;
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

async function limitCacheSize(responsePromise, maxEntries = 150) {
  const response = await responsePromise;
  const cache = await caches.open(MAP_CACHE);
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    await cache.delete(keys[0]);
  }
  return response;
}

async function flushOfflineQueue() {
  const queue = await loadQueue();
  const stillPending = [];
  for (const item of queue) {
    try {
      await fetch(item.url, item.options);
    } catch (err) {
      stillPending.push(item);
    }
  }
  await saveQueue(stillPending);
}

async function loadQueue() {
  try {
    const cache = await caches.open(RUNTIME_CACHE);
    const stored = await cache.match('ps-offline-queue');
    if (!stored) return [];
    return await stored.json();
  } catch (_) {
    return [];
  }
}

async function saveQueue(payload) {
  const cache = await caches.open(RUNTIME_CACHE);
  await cache.put('ps-offline-queue', new Response(JSON.stringify(payload)));
}

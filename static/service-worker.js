// static/service-worker.js — production-grade PWA cache with app versioning
const APP_VERSION = '2024.09.1';
const CACHE_PREFIX = 'parkshare-';
const PUBLIC_STATIC_CACHE = `${CACHE_PREFIX}static-${APP_VERSION}`;
const PUBLIC_PAGE_CACHE = `${CACHE_PREFIX}pages-${APP_VERSION}`;
const PUBLIC_API_CACHE = `${CACHE_PREFIX}api-${APP_VERSION}`;
const PRIVATE_API_CACHE = `${CACHE_PREFIX}api-private-${APP_VERSION}`;
const MAP_CACHE = `${CACHE_PREFIX}map-${APP_VERSION}`;
const RUNTIME_CACHE = `${CACHE_PREFIX}runtime-${APP_VERSION}`;
const OFFLINE_URL = '/offline/';

const PRIVATE_TTL_MS = 5 * 60 * 1000;
const PRIVATE_MAX_ENTRIES = 30;
const SHELL_ROUTES = ['/map/', '/app/', '/личный-кабинет/', '/кабинет-владельца/'];
const APP_SHELL = [...SHELL_ROUTES, OFFLINE_URL, '/manifest.webmanifest'];

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
      caches.open(PUBLIC_PAGE_CACHE).then((cache) => cache.addAll(APP_SHELL)),
      caches.open(PUBLIC_STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
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
                PUBLIC_STATIC_CACHE,
                PUBLIC_PAGE_CACHE,
                PUBLIC_API_CACHE,
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
      const targetCache = isPwaShell(url) ? PUBLIC_PAGE_CACHE : null;
      event.respondWith(handleHtmlRequest(request, targetCache));
      return;
    }
  }

  if (isApiRequest(url)) {
    if (isPrivateApi(url)) {
      event.respondWith(networkFirstPrivate(request, PRIVATE_API_CACHE));
      return;
    }
    event.respondWith(staleWhileRevalidate(request, PUBLIC_API_CACHE));
    return;
  }

  if (isMapTile(url)) {
    event.respondWith(limitCacheSize(cacheFirst(request, MAP_CACHE), 150));
    return;
  }

  if (isAsset(url)) {
    event.respondWith(cacheFirst(request, PUBLIC_STATIC_CACHE));
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
  const url = data.data?.url || data.url || '/map/';
  const actions = data.actions || [];
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { url, ...data.data },
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
  const cache = await caches.open(PUBLIC_PAGE_CACHE);
  await cache.addAll(APP_SHELL);
}

function isApiRequest(url) {
  return url.pathname.startsWith('/api/');
}

function isPrivateApi(url) {
  if (!isApiRequest(url)) return false;
  return (
    url.pathname.includes('/favorites/') ||
    url.pathname.includes('/saved-places/') ||
    url.pathname.includes('/push-subscriptions/') ||
    url.pathname.includes('/accounts/profile') ||
    url.pathname.includes('/ai/parkmate/config')
  );
}

function isPwaShell(url) {
  return SHELL_ROUTES.some((route) => url.pathname.startsWith(route));
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

async function networkFirstPrivate(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const stamped = stampResponse(response);
      await cache.put(request, stamped.clone());
      await trimCache(cacheName, PRIVATE_MAX_ENTRIES);
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached && !isExpired(cached, PRIVATE_TTL_MS)) return cached;
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

async function handleHtmlRequest(request, cacheName) {
  if (!cacheName) {
    return fetch(request).catch(async () => (await caches.match(OFFLINE_URL)) || Response.error());
  }
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    const cached = await cache.match(request);
    if (cached) return cached;
    const fallback = await caches.match(OFFLINE_URL);
    if (fallback) return fallback;
    return Response.error();
  }
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
      if ((item.attempts || 0) < 3) {
        stillPending.push({ ...item, attempts: (item.attempts || 0) + 1 });
      }
    }
  }
  await saveQueue(stillPending);
}

async function loadQueue() {
  try {
    const cache = await caches.open(RUNTIME_CACHE);
    const stored = await cache.match('ps-offline-queue');
    if (!stored) return [];
    const payload = await stored.json();
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    return (payload || []).filter((item) => (item.created_at || 0) > cutoff).slice(-50);
  } catch (_) {
    return [];
  }
}

async function saveQueue(payload) {
  const cache = await caches.open(RUNTIME_CACHE);
  const limited = (payload || []).slice(-50);
  await cache.put('ps-offline-queue', new Response(JSON.stringify(limited)));
}

function stampResponse(response) {
  const headers = new Headers(response.headers);
  headers.set('X-SW-Timestamp', Date.now().toString());
  return new Response(response.clone().body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function isExpired(response, ttlMs) {
  const ts = Number(response.headers.get('X-SW-Timestamp') || 0);
  if (!ts) return true;
  return Date.now() - ts > ttlMs;
}

async function trimCache(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    await cache.delete(keys[0]);
  }
}

// static/service-worker.js — production-grade PWA cache
const CACHE_VERSION = 'v5';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const HTML_CACHE = `html-${CACHE_VERSION}`;
const API_CACHE = `api-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline/';

const STATIC_ASSETS = [
  '/',
  OFFLINE_URL,
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/map.js',  // ← добавить эту строку
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => null)
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => ![STATIC_CACHE, HTML_CACHE, API_CACHE].includes(key))
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

const isGet = (req) => req.method === 'GET';
const isApi = (req) => new URL(req.url).pathname.startsWith('/api/');
const isHtml = (req) => req.headers.get('accept')?.includes('text/html');
const sameOrigin = (req) => self.location.origin === new URL(req.url).origin;

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (!isGet(request)) return;

  if (isApi(request)) {
    event.respondWith(staleWhileRevalidate(request, API_CACHE));
    return;
  }

  if (sameOrigin(request) && isHtml(request)) {
    event.respondWith(networkFirst(request, HTML_CACHE, OFFLINE_URL));
    return;
  }

  event.respondWith(cacheFirst(request, STATIC_CACHE));
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    if (isHtml(request)) {
      const fallback = await caches.match(OFFLINE_URL);
      if (fallback) return fallback;
    }
    throw err;
  }
}

async function networkFirst(request, cacheName, fallbackUrl) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
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
      if (response && response.status === 200) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

const CACHE_NAME = 'ps-concierge-v2';
const CORE_ASSETS = ['/', '/offline.html', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.map((key) => {
            if (key !== CACHE_NAME) {
              return caches.delete(key);
            }
            return undefined;
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

const staticAssetMatch = (url) =>
  url.pathname.startsWith('/_next/') ||
  url.pathname.startsWith('/icons/') ||
  url.pathname.endsWith('.css') ||
  url.pathname.endsWith('.js') ||
  url.pathname.endsWith('.woff2') ||
  url.pathname.endsWith('.png') ||
  url.pathname.endsWith('.svg');

const staleWhileRevalidate = async (request) => {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  try {
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  } catch (error) {
    return cached || Promise.reject(error);
  }
};

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (url.pathname.startsWith('/api')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((match) => match || caches.match('/offline.html')))
    );
    return;
  }

  if (staticAssetMatch(url)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

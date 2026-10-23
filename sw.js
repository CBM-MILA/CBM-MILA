/* CBM Mila 1936 — Official PWA Service Worker (v4) */
'use strict';

try {
  importScripts('./config.js');
} catch (e) {}

const CACHE_VERSION = self.CBM_BUILD_VERSION || '2026.10.23.v4';
const STATIC_CACHE = `cbm-static-${CACHE_VERSION}`;
const DATA_CACHE = `cbm-data-${CACHE_VERSION}`;
const EXPECTED_CACHES = new Set([STATIC_CACHE, DATA_CACHE]);

const STATIC_ASSETS = [
  './',
  './index.html',
  './style.css',
  './config.js',
  './qrcode.min.js',
  './app.js',
  './manifest.webmanifest',
  './cairo-bold.woff2',
  './cairo-regular.woff2',
  './logo.png',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

const NETWORK_FIRST_SHELL_PATHS = new Set([
  '/',
  '/index.html',
  '/app.js',
  '/config.js',
  '/style.css'
]);

function isShellAsset(pathname) {
  for (const suffix of NETWORK_FIRST_SHELL_PATHS) {
    if (pathname === suffix || pathname.endsWith(suffix)) return true;
  }
  return false;
}

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => Promise.allSettled(STATIC_ASSETS.map(url => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => {
        const hadOldCaches = keys.some(key => !EXPECTED_CACHES.has(key));
        return Promise.all(
          keys.map(key => EXPECTED_CACHES.has(key) ? Promise.resolve() : caches.delete(key))
        ).then(() => hadOldCaches);
      })
      .then(async hadOldCaches => {
        await self.clients.claim();
        if (hadOldCaches) {
          const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
          for (const client of clients) {
            client.postMessage({ type: 'CBM_SW_UPDATED', version: CACHE_VERSION });
          }
        }
      })
  );
});

async function networkFirstData(request) {
  const cache = await caches.open(DATA_CACHE);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const response = await fetch(request, { cache: 'no-cache', signal: ctrl.signal });
    clearTimeout(timer);
    if (response && response.ok) {
      cache.put('./data/data.json', response.clone());
    }
    return response;
  } catch (err) {
    clearTimeout(timer);
    const cached = await cache.match('./data/data.json') || await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    throw err;
  }
}

async function networkFirstShell(request) {
  const cache = await caches.open(STATIC_CACHE);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 4000);
  try {
    const response = await fetch(request, { cache: 'no-cache', signal: ctrl.signal });
    clearTimeout(timer);
    if (response && response.ok && response.type === 'basic') {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    clearTimeout(timer);
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    if (request.mode === 'navigate') {
      const fallback = await cache.match('./index.html') || await cache.match('./');
      if (fallback) return fallback;
    }
    return new Response('Offline — CBM Mila 1936', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  const networkPromise = fetch(request)
    .then(response => {
      if (response && response.ok && response.type === 'basic') {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cached) return cached;
  const networkResponse = await networkPromise;
  if (networkResponse) return networkResponse;
  return new Response('Offline — CBM Mila 1936', {
    status: 503,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' }
  });
}

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.endsWith('/data/data.json') || url.pathname.endsWith('/data.json')) {
    event.respondWith(networkFirstData(request));
    return;
  }
  if (request.mode === 'navigate' || isShellAsset(url.pathname)) {
    event.respondWith(networkFirstShell(request));
    return;
  }
  event.respondWith(staleWhileRevalidate(request));
});

self.addEventListener('push', event => {
  let payload = {
    title: 'شباب ميلة · CBM Mila 1936 🔴⚪',
    body: 'تحديث جديد لمباريات شباب ميلة',
    icon: './icon-192.png',
    badge: './icon-192.png',
    tag: 'cbm-match',
    url: './#/home'
  };
  if (event.data) {
    try {
      const parsed = event.data.json();
      if (parsed && typeof parsed === 'object') payload = { ...payload, ...parsed };
    } catch (e) {
      payload.body = event.data.text() || payload.body;
    }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: payload.icon || './icon-192.png',
      badge: payload.badge || './icon-192.png',
      tag: payload.tag || 'cbm-match',
      dir: 'auto',
      data: { url: payload.url || './#/home' }
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || './#/home';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (const client of windowClients) {
        if ('focus' in client) {
          client.navigate(targetUrl).catch(() => {});
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    })
  );
});

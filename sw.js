// CBM Mila Service Worker (v15) — أداء فائق ودعم العمل بدون إنترنت (Offline-First)
const V = 'v15';
const SHELL_C = 'cbm-shell-' + V;
const DATA_C = 'cbm-data-' + V;
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png',
  './card-template.jpg',
  './config.js'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_C)
      .then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k !== SHELL_C && k !== DATA_C) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', e => {
  const r = e.request;
  const u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;

  const key = u.origin + u.pathname;
  if (u.pathname.endsWith('/data/data.json')) {
    e.respondWith((async () => {
      try {
        const net = await fetch(r);
        if (net.ok) {
          const cache = await caches.open(DATA_C);
          cache.put(key, net.clone());
        }
        return net;
      } catch (err) {
        const cached = await caches.match(key);
        if (cached) return cached;
        throw err;
      }
    })());
    return;
  }

  e.respondWith((async () => {
    const cached = await caches.match(key) || (r.mode === 'navigate' ? await caches.match('./index.html') : null);
    const netPromise = fetch(r).then(n => {
      if (n.ok) caches.open(SHELL_C).then(x => x.put(key, n.clone()));
      return n;
    }).catch(() => cached);
    return cached || netPromise;
  })());
});

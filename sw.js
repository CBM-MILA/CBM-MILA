// CBM Mila Service Worker (v18) — Offline-First + Web Push Notifications
const V = 'v18';
const SHELL_C = 'cbm-shell-' + V;
const DATA_C = 'cbm-data-' + V;

const SHELL = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './config.js',
  './qrcode.min.js',
  './manifest.webmanifest',
  './logo.png',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png',
  './card-template.jpg',
  './hero-bg.jpg',
  './share-image.jpg',
  './fonts/cairo-regular.woff2',
  './fonts/cairo-bold.woff2'
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

// استقبال الإشعارات الفورية (Web Push) حتى لو كان التطبيق مغلقاً
self.addEventListener('push', e => {
  let payload = {
    title: 'شباب ميلة · CBM Mila 1936',
    body: 'تحديث جديد في منصة شباب ميلة الرسمية 🔴⚪',
    icon: './icon-192.png',
    badge: './icon-192.png',
    tag: 'cbm-match-alert',
    url: './#/home'
  };
  if (e.data) {
    try {
      const parsed = e.data.json();
      payload = Object.assign(payload, parsed);
    } catch (err) {
      payload.body = e.data.text() || payload.body;
    }
  }
  e.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: payload.icon || './icon-192.png',
      badge: payload.badge || './icon-192.png',
      dir: 'auto',
      vibrate: [200, 100, 200],
      tag: payload.tag || 'cbm-match-alert',
      renotify: true,
      data: { url: payload.url || './#/home' }
    })
  );
});

// فتح التطبيق عند الضغط على الإشعار في شاشة القفل
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const targetUrl = (e.notification.data && e.notification.data.url) || './#/home';
  e.waitUntil((async () => {
    const allClients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of allClients) {
      if ('focus' in client) {
        await client.focus();
        if (targetUrl.includes('#')) {
          client.postMessage({ type: 'NAVIGATE', url: targetUrl });
        }
        return;
      }
    }
    if (self.clients.openWindow) {
      await self.clients.openWindow(targetUrl);
    }
  })());
});

self.addEventListener('fetch', e => {
  const r = e.request;
  const u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;

  const key = u.origin + u.pathname;

  if (u.pathname.endsWith('/data/data.json') || u.pathname.endsWith('/data.json')) {
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

  const isAppCode =
    r.mode === 'navigate' ||
    u.pathname.endsWith('/') ||
    u.pathname.endsWith('/index.html') ||
    u.pathname.endsWith('/app.js') ||
    u.pathname.endsWith('/style.css') ||
    u.pathname.endsWith('/config.js');

  if (isAppCode) {
    e.respondWith((async () => {
      try {
        const net = await fetch(r);
        if (net.ok) {
          const cache = await caches.open(SHELL_C);
          cache.put(key, net.clone());
        }
        return net;
      } catch (err) {
        const cached = await caches.match(key) || (r.mode === 'navigate' ? await caches.match('./index.html') : null);
        if (cached) return cached;
        throw err;
      }
    })());
    return;
  }

  e.respondWith((async () => {
    const cached = await caches.match(key);
    const netPromise = fetch(r).then(n => {
      if (n.ok) caches.open(SHELL_C).then(x => x.put(key, n.clone()));
      return n;
    }).catch(() => cached);
    return cached || netPromise;
  })());
});

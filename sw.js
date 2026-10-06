// Service worker بدون أي تخزين مؤقت: مطلوب فقط لتثبيت الموقع كتطبيق، ولا يوفّر عملاً دون إنترنت.
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil((async()=>{
  for(const k of await caches.keys())await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener('fetch',()=>{}); // يترك كل الطلبات تذهب للشبكة مباشرة

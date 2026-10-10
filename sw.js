// CBM Mila service worker. غيّر رقم النسخة V عند الحاجة لإجبار الأجهزة على تنظيف التخزين القديم
const V='v19',SHELL_C='cbm-shell-'+V,DATA_C='cbm-data-'+V;
const SHELL=['./','./index.html','./manifest.webmanifest','./icon-192.png','./icon-512.png','./apple-touch-icon.png','./card-template.jpg','./match-bg.jpg','./qr.png','./config.js'];
// التثبيت لا يفشل أبدًا حتى لو غاب أحد الملفات
self.addEventListener('install',e=>e.waitUntil(caches.open(SHELL_C).then(c=>Promise.all(SHELL.map(u=>c.add(u).catch(()=>{})))).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil((async()=>{
  for(const k of await caches.keys())if(k!==SHELL_C&&k!==DATA_C)await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener('fetch',e=>{
  const r=e.request,u=new URL(r.url);
  if(r.method!=='GET'||u.origin!==location.origin)return; // طلبات السجل (Google) تمر مباشرة
  const key=u.origin+u.pathname;
  if(u.pathname.endsWith('/data/data.json')||u.pathname.endsWith('/config.js')){ // البيانات والإعدادات: الشبكة أولاً ثم آخر نسخة محفوظة
    e.respondWith((async()=>{try{const n=await fetch(r);if(n.ok)(await caches.open(DATA_C)).put(key,n.clone());return n}
      catch(err){const c=await caches.match(key);if(c)return c;throw err}})());return}
  e.respondWith((async()=>{ // الواجهة: الكاش أولاً مع تحديث صامت في الخلفية
    const c=await caches.match(key)||(r.mode==='navigate'?await caches.match('./index.html'):null);
    const net=fetch(r).then(n=>{if(n.ok)caches.open(SHELL_C).then(x=>x.put(key,n.clone()));return n}).catch(()=>c);
    return c||net})());
});

// Service worker minimal pour EmploiCentral (PWA installable + cache léger).
// Stratégie volontairement prudente pour éviter de servir un SPA périmé :
// - navigations / HTML  -> réseau d'abord, repli cache (offline = dernière page connue)
// - assets hashés (JS/CSS/img) -> cache d'abord (immuables grâce au hash de build)
const CACHE = 'emploicentral-v6';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Purge les anciens caches lors d'une nouvelle version.
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  // Ne jamais intercepter l'API : toujours du réseau direct.
  if (url.pathname.startsWith('/api/')) return;

  const isNavigation =
    request.mode === 'navigate' ||
    (request.headers.get('accept') || '').includes('text/html');

  if (isNavigation) {
    // Réseau d'abord (évite un index.html périmé), repli cache si hors-ligne.
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(request).then((r) => r || caches.match('/')))
    );
    return;
  }

  // Assets : cache d'abord, sinon réseau (et on met en cache au passage).
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
          }
          return res;
        })
    )
  );
});

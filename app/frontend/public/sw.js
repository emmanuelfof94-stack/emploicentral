// Service worker minimal pour EmploiCentral (PWA installable + cache léger).
// Stratégie volontairement prudente pour éviter de servir un SPA périmé :
// - navigations / HTML  -> réseau d'abord, repli cache (offline = dernière page connue)
// - assets hashés (JS/CSS/img) -> cache d'abord (immuables grâce au hash de build)
const CACHE = 'emploicentral-v11';

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

// Notifications push (nouvelles offres). Le serveur envoie {title, body, url, tag}.
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'EmploiCentral', {
      body: data.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      tag: data.tag || 'emploicentral',
      renotify: true,
      data: { url: data.url || '/jobs' },
    })
  );
});

// Clic sur la notification : réutilise un onglet ouvert de l'appli, sinon en ouvre un.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || '/jobs', self.location.origin).href;
  event.waitUntil(
    (async () => {
      const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const w of wins) {
        if (new URL(w.url).origin === self.location.origin && 'focus' in w) {
          await w.focus();
          if ('navigate' in w) await w.navigate(target);
          return;
        }
      }
      await self.clients.openWindow(target);
    })()
  );
});

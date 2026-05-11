/* =========================================================
   SHIKSHA · Mira-App · Service Worker
   - Cache-first für statische Assets (App-Shell, Icons, Manifest)
   - Network-first für API-Calls (Anthropic, Backend)
   - Notification-Click → App öffnen
   - Push-Event-Handler (vorbereitet, braucht Server)
   ========================================================= */

const CACHE_NAME = 'shiksha-mira-v1';
const APP_SHELL = [
  './mira_app.html',
  './mira_manifest.json',
  './mira_icon.svg',
  './mira_icon_maskable.svg',
  './shiksha-hero.mp4'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // App-Shell cachen — Fehler einzelner Files nicht propagieren
      return Promise.allSettled(
        APP_SHELL.map(url => cache.add(url).catch(() => null))
      );
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API-Calls: immer ans Netz, niemals cachen
  if (url.hostname === 'api.anthropic.com' ||
      url.hostname.endsWith('.shiksha.tun.zone')) {
    return;
  }

  // Statische Assets: Cache-first
  if (event.request.method === 'GET') {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((res) => {
          // Erfolgreich geladen → in Cache schreiben
          if (res && res.ok && res.type === 'basic') {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return res;
        }).catch(() => cached);
      })
    );
  }
});

// ===================================================================
// NOTIFICATIONS
// ===================================================================

// Klick auf eine Notification: App öffnen / fokussieren
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Wenn schon ein Tab offen: fokussieren
      for (const client of clientList) {
        if (client.url.includes('mira_app.html') && 'focus' in client) {
          return client.focus();
        }
      }
      // Sonst neuen Tab öffnen
      if (self.clients.openWindow) {
        return self.clients.openWindow('./mira_app.html');
      }
    })
  );
});

// Push-Event (für späteren Server-Push)
// Wird heute nicht genutzt — App nutzt lokale Notifications.
// Wenn Server-Push aktiviert wird:
//   - VAPID-Keys generieren (Server-side)
//   - PushManager.subscribe() im Frontend
//   - Server schickt Push-Payload mit { title, body, tag }
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data = {};
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: 'Shiksha', body: event.data.text() };
  }

  const title = data.title || 'Shiksha';
  const options = {
    body: data.body || 'Ich höre zu.',
    icon: data.icon || './mira_icon.svg',
    badge: data.badge || './mira_icon.svg',
    tag: data.tag || 'shiksha-default',
    data: data.url || './mira_app.html'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

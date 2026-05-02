/**
 * SHIKSHA · Service Worker mit Web-Push-Handler
 * Wird unter /opt/shiksha/ui/kita/service-worker.js abgelegt und ersetzt
 * den bestehenden minimalen Service-Worker.
 */

const CACHE = "shiksha-v3";

self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(clients.claim());
});

// Optional: einfache Pass-Through-Strategie (kein aggressives Caching)
self.addEventListener("fetch", (e) => {
  // Standard-Browser-Verhalten
});

// =============================================================
// PUSH-HANDLER
// =============================================================
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "SHIKSHA", body: event.data ? event.data.text() : "" };
  }

  const title = data.title || "SHIKSHA";
  const options = {
    body: data.body || "",
    icon: data.icon || "/accounting/ui/kita/app-icon.svg",
    badge: data.icon || "/accounting/ui/kita/app-icon.svg",
    tag: data.tag || "shiksha",
    data: { url: data.url || "/" },
    requireInteraction: !!data.requireInteraction,
    vibrate: [100, 50, 100],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Klick auf Benachrichtigung → App öffnen / fokussieren
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil((async () => {
    const all = await clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of all) {
      if (c.url.includes(targetUrl.split("?")[0]) && "focus" in c) {
        c.focus();
        return;
      }
    }
    if (clients.openWindow) await clients.openWindow(targetUrl);
  })());
});

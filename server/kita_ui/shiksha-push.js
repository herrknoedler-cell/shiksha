/**
 * SHIKSHA · Push-Subscribe-Helper
 * Klein-Wrapper um Web-Push-API. In jede PWA als <script> einbinden.
 *
 * Verwendung:
 *   ShikshaPush.init({ audience: "paedagogin", personType: "staff", personId: 4 });
 *   ShikshaPush.subscribe();   // ruft Permission an + speichert Subscription auf Server
 *   ShikshaPush.isEnabled();   // → true wenn aktiv
 *   ShikshaPush.unsubscribe();
 *
 * Wichtig: Auf iOS funktioniert Push NUR wenn die PWA via "Zum Home-Bildschirm
 * hinzufügen" installiert wurde. Wir blenden den Subscribe-Button entsprechend ein.
 */

(function () {
  const API = "/kita/push";
  let _opts = { audience: "traegerin", personType: "system", personId: null };

  function urlB64ToUint8Array(b64) {
    const padding = "=".repeat((4 - b64.length % 4) % 4);
    const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches
        || window.navigator.standalone === true;
  }

  function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  }

  function init(opts) {
    Object.assign(_opts, opts || {});
  }

  function isSupported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  async function isEnabled() {
    if (!isSupported()) return false;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return !!sub && Notification.permission === "granted";
  }

  async function subscribe() {
    if (!isSupported()) {
      throw new Error("Push wird in diesem Browser nicht unterstützt.");
    }
    if (isIOS() && !isStandalone()) {
      throw new Error("Auf dem iPhone bitte zuerst „Zum Home-Bildschirm hinzufügen" — danach in der App-Version Push aktivieren.");
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") {
      throw new Error("Benachrichtigungen wurden vom Browser blockiert.");
    }
    const reg = await navigator.serviceWorker.ready;

    // Public Key vom Server holen
    const r = await fetch(`${API}/vapid-public-key`);
    if (!r.ok) throw new Error("Server liefert keinen VAPID-Key.");
    const { public_key } = await r.json();

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(public_key),
      });
    }

    // An Server schicken
    const sr = await fetch(`${API}/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        audience: _opts.audience,
        person_type: _opts.personType,
        person_id: _opts.personId,
        subscription: sub.toJSON(),
        user_agent: navigator.userAgent,
      }),
    });
    if (!sr.ok) throw new Error("Server-Registrierung fehlgeschlagen.");
    return true;
  }

  async function unsubscribe() {
    if (!isSupported()) return;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    const endpoint = sub.endpoint;
    await sub.unsubscribe();
    await fetch(`${API}/unsubscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint }),
    });
  }

  window.ShikshaPush = { init, subscribe, unsubscribe, isEnabled, isSupported, isIOS, isStandalone };
})();

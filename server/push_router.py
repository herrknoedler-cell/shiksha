"""
SHIKSHA · Web-Push-Router
Endpoints:
  GET  /push/vapid-public-key         — Public-Key fürs Frontend
  POST /push/subscribe                — Browser-Subscription speichern
  POST /push/unsubscribe              — Subscription löschen
  POST /push/send                     — Notification an Audience senden (Trägerin)
  GET  /push/log                      — Send-Log

Voraussetzungen (im venv):
  pip install pywebpush

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
"""

import os as _push_os
import json as _push_json
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = _push_os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = _push_os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT     = _push_os.environ.get("VAPID_SUBJECT", "mailto:thomas@shiksha.tun.zone")


@kita_router.get("/push/vapid-public-key")
async def push_get_vapid_pub():
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(503, "VAPID_PUBLIC_KEY nicht gesetzt")
    return {"public_key": VAPID_PUBLIC_KEY}


@kita_router.post("/push/subscribe")
async def push_subscribe(payload: dict = Body(...)):
    """
    Erwartet:
      {
        "audience": "paedagogin" | "eltern" | "traegerin",
        "person_type": "staff" | "parent" | "system",
        "person_id": "...",          // optional
        "subscription": {
            "endpoint": "...",
            "keys": {"p256dh": "...", "auth": "..."}
        },
        "user_agent": "..."
      }
    """
    sub = payload.get("subscription") or {}
    keys = sub.get("keys") or {}
    endpoint = sub.get("endpoint")
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(400, "Subscription unvollständig")

    audience = payload.get("audience") or "traegerin"
    with engine.begin() as conn:
        # Upsert
        existing = conn.execute(sa.text("SELECT id FROM push_subscriptions WHERE endpoint = :e"),
                                {"e": endpoint}).first()
        if existing:
            conn.execute(sa.text("""
                UPDATE push_subscriptions
                   SET p256dh_key = :p, auth_key = :a, audience = :au,
                       person_type = :pt, person_id = :pid,
                       user_agent = :ua, active = true, last_used_at = NOW()
                 WHERE id = :id
            """), {"p": keys["p256dh"], "a": keys["auth"], "au": audience,
                   "pt": payload.get("person_type"), "pid": str(payload.get("person_id") or ""),
                   "ua": payload.get("user_agent"), "id": existing[0]})
            return {"id": existing[0], "updated": True}
        result = conn.execute(sa.text("""
            INSERT INTO push_subscriptions
              (audience, person_type, person_id, endpoint, p256dh_key, auth_key, user_agent)
            VALUES (:au, :pt, :pid, :e, :p, :a, :ua)
            RETURNING id
        """), {"au": audience, "pt": payload.get("person_type"),
               "pid": str(payload.get("person_id") or ""),
               "e": endpoint, "p": keys["p256dh"], "a": keys["auth"],
               "ua": payload.get("user_agent")})
    return {"id": result.scalar(), "created": True}


@kita_router.post("/push/unsubscribe")
async def push_unsubscribe(payload: dict = Body(...)):
    endpoint = payload.get("endpoint")
    if not endpoint:
        raise HTTPException(400, "endpoint fehlt")
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE push_subscriptions SET active = false WHERE endpoint = :e"),
                     {"e": endpoint})
    return {"ok": True}


def _push_send_one(sub_row, payload):
    """Sende an eine Subscription. Returnt (ok, error_msg)."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub_row["endpoint"],
                "keys": {"p256dh": sub_row["p256dh_key"], "auth": sub_row["auth_key"]},
            },
            data=_push_json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True, None
    except WebPushException as e:
        # 410 Gone → Subscription abgelaufen → deaktivieren
        return False, str(e)


@kita_router.post("/push/send")
async def push_send(payload: dict = Body(...)):
    """
    Sendet eine Notification.
      {
        "audience": "paedagogin" | "eltern" | "traegerin" | "all",
        "person_id": "..."           // optional, gezielt einzelne Person
        "title": "...",
        "body":  "...",
        "url":   "/accounting/ui/paedagogen/app",   // Click-Ziel
        "icon":  "...",                              // optional
        "tag":   "termin-erinnerung"                 // optional, gruppiert auf iOS
      }
    """
    if not VAPID_PRIVATE_KEY:
        raise HTTPException(503, "VAPID_PRIVATE_KEY nicht gesetzt")
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title Pflicht")

    audience = payload.get("audience") or "all"
    person_id = payload.get("person_id")
    notif_payload = {
        "title": title,
        "body": payload.get("body") or "",
        "url": payload.get("url") or "/",
        "icon": payload.get("icon") or "/accounting/ui/kita/app-icon.svg",
        "tag": payload.get("tag") or "shiksha",
    }

    where = ["active = true"]
    params = {}
    if audience != "all":
        where.append("audience = :au")
        params["au"] = audience
    if person_id:
        where.append("person_id = :pid")
        params["pid"] = str(person_id)

    sql = f"SELECT id, endpoint, p256dh_key, auth_key FROM push_subscriptions WHERE {' AND '.join(where)}"
    sent, failed = 0, 0
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).mappings().fetchall()

    for row in rows:
        ok, err = _push_send_one(row, notif_payload)
        if ok:
            sent += 1
            with engine.begin() as conn:
                conn.execute(sa.text("UPDATE push_subscriptions SET last_used_at = NOW(), last_error = NULL WHERE id = :id"),
                             {"id": row["id"]})
        else:
            failed += 1
            with engine.begin() as conn:
                # Bei 410 Gone direkt deaktivieren
                if "410" in (err or "") or "404" in (err or ""):
                    conn.execute(sa.text("UPDATE push_subscriptions SET active = false, last_error = :e WHERE id = :id"),
                                 {"e": err[:500], "id": row["id"]})
                else:
                    conn.execute(sa.text("UPDATE push_subscriptions SET last_error = :e WHERE id = :id"),
                                 {"e": err[:500], "id": row["id"]})

    # Log
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO push_send_log
              (audience_filter, title, body, url, sent_count, failed_count, sender)
            VALUES (:af, :t, :b, :u, :sc, :fc, :sd)
        """), {"af": audience, "t": title, "b": notif_payload["body"],
               "u": notif_payload["url"], "sc": sent, "fc": failed,
               "sd": payload.get("sender", "system")})

    return {"sent": sent, "failed": failed, "total": len(rows)}


@kita_router.get("/push/log")
async def push_log(limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT * FROM push_send_log ORDER BY sent_at DESC LIMIT :l
        """), {"l": limit}).mappings().fetchall()
    return {"count": len(rows), "log": [dict(r) for r in rows]}

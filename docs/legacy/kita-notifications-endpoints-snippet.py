"""
SHIKSHA · KITA · kita_notifications_endpoints.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 29.04.2026 via deploy-Skript an
/opt/shiksha/kita_compliance_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/kita_compliance_router.py  (omnibus router, ~5389 Zeilen)

Bei einer späteren Modul-Trennung kann dieses Snippet zurück nach
server/kita_notifications_endpoints.py wandern.

Original: cowork/outputs/kita/server/kita_notifications_endpoints.py (2026-04-29)
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
SHIKSHA · KITA · Notifications + Eltern-Accounts + Bestätigungs-Mails
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import os as _kn_os
import secrets as _kn_secrets
import smtplib as _kn_smtp
from email.mime.multipart import MIMEMultipart as _kn_MIME
from email.mime.text import MIMEText as _kn_MIMEText


# ============================================================
# E-MAIL-VERSAND
# ============================================================

KITA_BASE_URL = _kn_os.environ.get("KITA_BASE_URL", "https://shiksha.tun.zone")
SMTP_HOST = _kn_os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(_kn_os.environ.get("SMTP_PORT", "587"))
SMTP_USER = _kn_os.environ.get("SMTP_USER", "")
SMTP_PASS = _kn_os.environ.get("SMTP_PASS", "")
MAIL_FROM = _kn_os.environ.get("KITA_MAIL_FROM", "kita@shiksha.tun.zone")
MAIL_FROM_NAME = _kn_os.environ.get("KITA_MAIL_FROM_NAME", "SHIKSHA · KITA")


def _kn_send_mail(to_email: str, subject: str, body_html: str, body_text: str = None) -> tuple[bool, str]:
    """E-Mail-Versand. Returns (success, error_msg)."""
    if not to_email:
        return False, "keine Empfänger-E-Mail"
    if not SMTP_HOST:
        # Demo-Modus: Mail-Body in Logs
        print(f"[kita-mail-demo] Würde senden an {to_email}:")
        print(f"  Subject: {subject}")
        print(f"  Body: {body_html[:200]}...")
        return True, "demo-mode"
    msg = _kn_MIME("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"] = to_email
    if body_text:
        msg.attach(_kn_MIMEText(body_text, "plain", "utf-8"))
    msg.attach(_kn_MIMEText(body_html, "html", "utf-8"))
    try:
        with _kn_smtp.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True, ""
    except Exception as e:
        print(f"[kita-mail] SMTP-Fehler: {e}")
        return False, str(e)


def _kn_holi_mail_template(content_html: str, footer_html: str = "") -> str:
    """Wrapper-Template mit Holi-Look für alle KITA-Mails."""
    return f"""<!DOCTYPE html>
<html><body style="margin:0; padding:0; background:#fff8f0; font-family:-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#fff8f0 0%,#ffe4f0 50%,#e4f8ff 100%); padding:24px 12px;">
<tr><td align="center">
  <table width="100%" style="max-width:540px;" cellpadding="0" cellspacing="0">
    <tr><td style="padding:20px 0;">
      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="background:linear-gradient(135deg,#ff4d8d 0%,#a855f7 100%); width:44px; height:44px; border-radius:14px; text-align:center; color:#fff; font-weight:700; font-size:22px;">K</td>
          <td style="padding-left:12px;">
            <div style="font-size:18px; font-weight:700; color:#2a2530;">SHIKSHA · KITA</div>
            <div style="font-size:12px; color:#9a8e9e;">Spielgruppen · Kindergarten · Hort</div>
          </td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="background:#ffffff; border-radius:20px; padding:28px 24px; box-shadow:0 4px 16px rgba(255,77,141,0.10);">
      {content_html}
    </td></tr>
    <tr><td style="padding:20px 8px; text-align:center; font-size:11px; color:#9a8e9e;">
      {footer_html or 'Geschützt durch <strong style="color:#ff4d8d;">SHIKSHA · KITA</strong> · Daten in der EU'}
    </td></tr>
  </table>
</td></tr>
</table>
</body></html>"""


# ============================================================
# ELTERN-ACCOUNTS + AUTO-CREATE BEI ANMELDUNG
# ============================================================

def _kn_create_or_update_parent(conn, full_name: str, email: str, phone: str, role: str,
                                 enrollment_id: str, child_name: str, doc_id: str) -> str:
    """Legt Eltern-Account an oder erweitert bestehenden um neues Kind."""
    if not full_name or not email:
        return None
    existing = conn.execute(sa.text("""
        SELECT id, enrollment_ids, child_names FROM kita_parent_accounts WHERE LOWER(email)=LOWER(:e) LIMIT 1
    """), {"e": email}).first()

    token = _kn_secrets.token_urlsafe(32)

    if existing:
        # Update: Kind ergänzen
        existing_eids = list(existing[1] or [])
        existing_names = (existing[2] or "").strip()
        if enrollment_id and enrollment_id not in existing_eids:
            existing_eids.append(enrollment_id)
        if child_name and child_name not in existing_names:
            existing_names = (existing_names + ", " + child_name) if existing_names else child_name
        conn.execute(sa.text("""
            UPDATE kita_parent_accounts SET
              enrollment_ids = :eids, child_names = :cn,
              login_token = :tok, token_expires_at = NOW() + INTERVAL '90 days',
              updated_at = NOW()
            WHERE id = :id
        """), {"eids": existing_eids, "cn": existing_names, "tok": token, "id": existing[0]})
        return existing[0]
    else:
        pid = _new_id("par")
        conn.execute(sa.text("""
            INSERT INTO kita_parent_accounts
              (id, full_name, email, phone, role, enrollment_ids, child_names,
               source_doc_id, consent_given, login_token, token_expires_at)
            VALUES (:id, :n, :e, :p, :r, :eids, :cn, :sd, true, :tok, NOW() + INTERVAL '90 days')
        """), {
            "id": pid, "n": full_name, "e": email, "p": phone, "r": role,
            "eids": [enrollment_id] if enrollment_id else [],
            "cn": child_name, "sd": doc_id, "tok": token,
        })
        return pid


# ============================================================
# BESTÄTIGUNGS-MAIL (nach Anmeldung)
# ============================================================

def _kn_send_anmeldung_confirmation(parent_email: str, parent_name: str, child_name: str,
                                     modules: dict, hours: float, login_token: str,
                                     enrolled_from: str = None):
    """Schöne Bestätigungs-Mail mit App-Link + Install-Anleitung."""
    if not parent_email:
        return False

    # Module-Liste menschenlesbar
    weekday_de = {"monday": "Mo", "tuesday": "Di", "wednesday": "Mi", "thursday": "Do", "friday": "Fr"}
    slot_de = {"07:15-11:30": "Vormittag", "11:30-12:30": "Mittagsbetreuung",
               "12:30-13:30": "Mittagsruhe", "13:30-17:30": "Nachmittag"}
    module_lines = []
    for day, slots in (modules or {}).items():
        for slot in slots:
            module_lines.append(f"<li><strong>{weekday_de.get(day, day)}</strong> · {slot_de.get(slot, slot)} <small style=\"color:#9a8e9e;\">({slot})</small></li>")
    modules_html = "<ul style='padding-left:20px; margin:0;'>" + "".join(module_lines) + "</ul>" if module_lines else "<em>keine Module gewählt</em>"

    eltern_app_url = f"{KITA_BASE_URL}/accounting/ui/kita/eltern?t={login_token}"

    content = f"""
    <h1 style="margin:0 0 8px; font-size:24px; background:linear-gradient(120deg,#ff4d8d,#a855f7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
      Anmeldung bestätigt 🎉
    </h1>
    <p style="margin:0 0 18px; color:#5a5060; font-size:15px;">
      Hallo {parent_name},<br>
      vielen Dank für die Anmeldung von <strong>{child_name}</strong>. Wir freuen uns!
    </p>

    <div style="background:#fffbf0; border:2px dashed #ffd93d; border-radius:14px; padding:16px; margin-bottom:18px;">
      <strong style="color:#2a2530;">📋 Eure Anmelde-Daten</strong>
      <table style="width:100%; margin-top:8px; font-size:14px;">
        <tr><td style="color:#9a8e9e; padding:4px 0;">Kind:</td><td><strong>{child_name}</strong></td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0;">Vertrag ab:</td><td>{enrolled_from or '—'}</td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0; vertical-align:top;">Module:</td><td>{modules_html}</td></tr>
        <tr><td style="color:#9a8e9e; padding:4px 0;">Wochenstunden:</td><td><strong style="color:#2d7a5f;">{hours:.1f} h</strong></td></tr>
      </table>
    </div>

    <div style="background:linear-gradient(135deg,#ff4d8d 0%,#a855f7 100%); color:#fff; padding:20px; border-radius:16px; margin-bottom:18px; text-align:center;">
      <strong style="display:block; font-size:13px; opacity:0.9; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;">📱 Eltern-App</strong>
      <p style="margin:0 0 14px; font-size:14px;">
        Krankmeldungen, Mitteilungen, wichtige Updates — alles in der App.
      </p>
      <a href="{eltern_app_url}" style="display:inline-block; padding:12px 24px; background:#fff; color:#a855f7; text-decoration:none; border-radius:10px; font-weight:700; font-size:14px;">
        App öffnen →
      </a>
    </div>

    <details style="margin-bottom:14px;">
      <summary style="cursor:pointer; font-weight:600; color:#2a2530; padding:8px 0;">📲 So installiert ihr die App auf dem Handy</summary>
      <div style="padding:12px; background:#f9f4ec; border-radius:10px; font-size:13px; color:#5a5060;">
        <p style="margin:0 0 8px;"><strong>iPhone (Safari):</strong></p>
        <ol style="padding-left:20px; margin:0 0 12px;">
          <li>Den App-Link oben in Safari öffnen</li>
          <li>Auf das Teilen-Symbol tippen ⬆️</li>
          <li>„Zum Home-Bildschirm" wählen</li>
          <li>Mit „Hinzufügen" bestätigen</li>
        </ol>
        <p style="margin:0 0 8px;"><strong>Android (Chrome):</strong></p>
        <ol style="padding-left:20px; margin:0;">
          <li>Den App-Link oben in Chrome öffnen</li>
          <li>Drei Punkte oben rechts ⋮</li>
          <li>„App installieren" oder „Zum Startbildschirm" wählen</li>
          <li>Bestätigen</li>
        </ol>
      </div>
    </details>

    <p style="color:#9a8e9e; font-size:12px; margin:16px 0 0; line-height:1.6;">
      Der Link oben ist persönlich für euch und 90 Tage gültig. Bei Fragen einfach in der KITA melden.
    </p>
    """
    html = _kn_holi_mail_template(content)
    text = f"""Hallo {parent_name},

vielen Dank für die Anmeldung von {child_name}.

Wochenstunden: {hours:.1f}h
Vertrag ab: {enrolled_from or '—'}

Eltern-App: {eltern_app_url}

(Link 90 Tage gültig)

SHIKSHA · KITA"""
    ok, err = _kn_send_mail(parent_email, f"Anmeldung bestätigt: {child_name}", html, text)
    return ok


# ============================================================
# ENDPOINTS — ELTERN-ACCOUNTS
# ============================================================

@kita_router.get("/eltern/me")
async def kita_eltern_me(t: str = ""):
    """Token-Login: Eltern öffnen App via Link mit ?t=XYZ aus Mail."""
    if not t:
        raise HTTPException(401, "kein Token")
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT id, full_name, email, phone, role, enrollment_ids, child_names,
                   notification_email_optin, notification_push_optin
            FROM kita_parent_accounts
            WHERE login_token = :t AND (token_expires_at IS NULL OR token_expires_at > NOW())
            LIMIT 1
        """), {"t": t}).first()
    if not row:
        raise HTTPException(401, "Token ungültig oder abgelaufen")
    return {
        "id": row[0], "full_name": row[1], "email": row[2], "phone": row[3], "role": row[4],
        "enrollment_ids": list(row[5] or []), "child_names": row[6],
        "notification_email_optin": row[7],
        "notification_push_optin": row[8],
    }


@kita_router.get("/eltern/notifications")
async def kita_eltern_notifications(t: str = ""):
    """Mitteilungen, die diesen Eltern zugestellt wurden."""
    if not t:
        raise HTTPException(401, "kein Token")
    with engine.connect() as conn:
        parent = conn.execute(sa.text("SELECT id FROM kita_parent_accounts WHERE login_token=:t LIMIT 1"),
                              {"t": t}).first()
        if not parent:
            raise HTTPException(401, "Token ungültig")
        rows = conn.execute(sa.text("""
            SELECT n.id, n.title, n.body, n.body_html, n.priority, n.sent_at, r.opened_at
            FROM kita_notification_recipients r
            JOIN kita_notifications n ON n.id = r.notification_id
            WHERE r.parent_id = :pid AND n.status = 'sent'
            ORDER BY n.sent_at DESC LIMIT 50
        """), {"pid": parent[0]}).fetchall()
    return {
        "count": len(rows),
        "notifications": [
            {
                "id": r[0], "title": r[1], "body": r[2], "body_html": r[3],
                "priority": r[4],
                "sent_at": r[5].isoformat() if r[5] else None,
                "opened_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ],
    }


# ============================================================
# ENDPOINTS — BENACHRICHTIGUNGEN (Trägerin)
# ============================================================

@kita_router.get("/notifications")
async def kita_notif_list(limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT n.id, n.title, n.body, n.target_type, n.target_group_id, n.target_enrollment_ids,
                   n.target_parent_ids, n.include_staff, n.priority, n.status, n.sent_at, n.created_at,
                   (SELECT COUNT(*) FROM kita_notification_recipients WHERE notification_id = n.id) AS recip_count,
                   (SELECT COUNT(*) FROM kita_notification_recipients WHERE notification_id = n.id AND delivery_status = 'sent') AS sent_count
            FROM kita_notifications n
            ORDER BY n.created_at DESC LIMIT :lim
        """), {"lim": limit}).fetchall()
    return {
        "count": len(rows),
        "notifications": [
            {
                "id": r[0], "title": r[1], "body": r[2],
                "target_type": r[3], "target_group_id": r[4],
                "target_enrollment_count": len(r[5] or []),
                "target_parent_count": len(r[6] or []),
                "include_staff": r[7], "priority": r[8],
                "status": r[9],
                "sent_at": r[10].isoformat() if r[10] else None,
                "created_at": r[11].isoformat() if r[11] else None,
                "recipients_total": r[12], "recipients_sent": r[13],
            }
            for r in rows
        ],
    }


@kita_router.post("/notifications")
async def kita_notif_create(payload: dict = Body(...)):
    """Erstellt eine Mitteilung als Draft (noch nicht versendet)."""
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title or not body:
        raise HTTPException(400, "title + body Pflicht")
    target_type = payload.get("target_type", "all")
    if target_type not in ("all", "group", "children", "parent"):
        raise HTTPException(400, "target_type muss all|group|children|parent sein")

    nid = _new_id("notif")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_notifications
              (id, title, body, body_html, target_type, target_group_id,
               target_enrollment_ids, target_parent_ids, include_staff,
               send_via_email, priority, status, created_by)
            VALUES (:id, :t, :b, :bh, :tt, :tg, :te, :tp, :is_, :em, :pr, 'draft', :cb)
        """), {
            "id": nid, "t": title, "b": body, "bh": payload.get("body_html"),
            "tt": target_type, "tg": payload.get("target_group_id"),
            "te": payload.get("target_enrollment_ids", []),
            "tp": payload.get("target_parent_ids", []),
            "is_": bool(payload.get("include_staff", False)),
            "em": bool(payload.get("send_via_email", True)),
            "pr": payload.get("priority", "normal"),
            "cb": payload.get("created_by", "kita-leitung"),
        })
    return {"id": nid, "status": "draft"}


@kita_router.post("/notifications/{nid}/send")
async def kita_notif_send(nid: str):
    """Resolves Empfänger, erstellt recipient-Datensätze, schickt E-Mails."""
    with engine.begin() as conn:
        n = conn.execute(sa.text("""
            SELECT id, title, body, body_html, target_type, target_group_id,
                   target_enrollment_ids, target_parent_ids, include_staff,
                   send_via_email, priority, status
            FROM kita_notifications WHERE id=:id
        """), {"id": nid}).first()
        if not n:
            raise HTTPException(404, "Mitteilung nicht gefunden")
        if n[11] == "sent":
            raise HTTPException(400, "Bereits versendet")

        # Empfänger ermitteln
        recipients = []  # list of (parent_id, email, full_name, child_names)
        if n[4] == "all":
            rows = conn.execute(sa.text("""
                SELECT id, email, full_name, child_names FROM kita_parent_accounts
                WHERE notification_email_optin = true AND email IS NOT NULL AND email != ''
            """)).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "group" and n[5]:
            rows = conn.execute(sa.text("""
                SELECT DISTINCT pa.id, pa.email, pa.full_name, pa.child_names
                FROM kita_parent_accounts pa,
                     unnest(pa.enrollment_ids) AS eid
                JOIN kita_child_enrollments ce ON ce.id = eid
                WHERE ce.group_id = :g AND pa.notification_email_optin = true
            """), {"g": n[5]}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "children" and n[6]:
            target_eids = list(n[6] or [])
            rows = conn.execute(sa.text("""
                SELECT DISTINCT pa.id, pa.email, pa.full_name, pa.child_names
                FROM kita_parent_accounts pa,
                     unnest(pa.enrollment_ids) AS eid
                WHERE eid = ANY(:eids) AND pa.notification_email_optin = true
            """), {"eids": target_eids}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]
        elif n[4] == "parent" and n[7]:
            target_pids = list(n[7] or [])
            rows = conn.execute(sa.text("""
                SELECT id, email, full_name, child_names FROM kita_parent_accounts
                WHERE id = ANY(:pids) AND notification_email_optin = true
            """), {"pids": target_pids}).fetchall()
            recipients = [(r[0], r[1], r[2], r[3]) for r in rows]

        # Optional: Mitarbeiter (Betreuer)
        staff_recipients = []
        if n[8]:
            srows = conn.execute(sa.text("""
                SELECT id, full_name FROM kita_staff_members WHERE left_at IS NULL
            """)).fetchall()
            staff_recipients = [(r[0], r[1]) for r in srows]

        # Insert recipient-Datensätze
        for pid, email, name, child in recipients:
            conn.execute(sa.text("""
                INSERT INTO kita_notification_recipients
                  (id, notification_id, recipient_type, parent_id, email, delivery_status)
                VALUES (:id, :nid, 'parent', :p, :e, 'pending')
            """), {"id": _new_id("rec"), "nid": nid, "p": pid, "e": email})
        for sid, sname in staff_recipients:
            conn.execute(sa.text("""
                INSERT INTO kita_notification_recipients
                  (id, notification_id, recipient_type, staff_id, delivery_status)
                VALUES (:id, :nid, 'staff', :s, 'pending')
            """), {"id": _new_id("rec"), "nid": nid, "s": sid})

        conn.execute(sa.text("UPDATE kita_notifications SET status='sending' WHERE id=:id"), {"id": nid})

    # E-Mails versenden
    sent_count = 0
    failed_count = 0
    if n[9]:  # send_via_email
        title, body, body_html = n[1], n[2], n[3]
        priority = n[10]
        prio_emoji = {"urgent": "🚨", "high": "⚠️", "normal": "📩", "low": "💬"}.get(priority, "📩")
        for pid, email, name, child in recipients:
            if not email:
                continue
            content_html = (body_html or f"<p>{body}</p>")
            full_html = _kn_holi_mail_template(f"""
                <h1 style="margin:0 0 8px; font-size:22px; color:#2a2530;">
                  {prio_emoji} {title}
                </h1>
                <p style="margin:0 0 4px; color:#9a8e9e; font-size:13px;">Hallo {name or 'Eltern'},</p>
                <div style="font-size:15px; color:#2a2530; line-height:1.7; margin:14px 0;">
                  {content_html}
                </div>
                <p style="margin:18px 0 0; color:#9a8e9e; font-size:12px;">
                  Diese Mitteilung betrifft: <strong>{child or 'eure Familie'}</strong>
                </p>
            """)
            ok, err = _kn_send_mail(email, f"{prio_emoji} {title}", full_html, body)
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    UPDATE kita_notification_recipients
                    SET delivery_status = :st, sent_at = NOW(), error_message = :err
                    WHERE notification_id = :nid AND parent_id = :pid
                """), {"st": "sent" if ok else "failed", "err": err if not ok else None,
                       "nid": nid, "pid": pid})
            if ok:
                sent_count += 1
            else:
                failed_count += 1

    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE kita_notifications SET status='sent', sent_at=NOW() WHERE id=:id"),
                     {"id": nid})

    return {
        "id": nid, "status": "sent",
        "recipients_total": len(recipients) + len(staff_recipients),
        "emails_sent": sent_count, "emails_failed": failed_count,
    }


@kita_router.get("/notifications/{nid}/recipients")
async def kita_notif_recipients(nid: str):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT r.id, r.recipient_type, r.email, r.delivery_status, r.sent_at, r.opened_at,
                   COALESCE(p.full_name, s.full_name) AS name
            FROM kita_notification_recipients r
            LEFT JOIN kita_parent_accounts p ON p.id = r.parent_id
            LEFT JOIN kita_staff_members s ON s.id = r.staff_id
            WHERE r.notification_id = :nid
            ORDER BY r.delivery_status DESC, name
        """), {"nid": nid}).fetchall()
    return {
        "count": len(rows),
        "recipients": [
            {
                "id": r[0], "type": r[1], "email": r[2],
                "status": r[3],
                "sent_at": r[4].isoformat() if r[4] else None,
                "opened_at": r[5].isoformat() if r[5] else None,
                "name": r[6],
            }
            for r in rows
        ],
    }


@kita_router.delete("/notifications/{nid}")
async def kita_notif_delete(nid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_notifications WHERE id=:id"), {"id": nid})
        if result.rowcount == 0:
            raise HTTPException(404, "Mitteilung nicht gefunden")
    return {"id": nid, "deleted": True}


# ============================================================
# HOOK: Bestätigungs-Mail nach Anmeldung
# ============================================================

def _kn_post_anmeldung_hook(doc_id: str, payload: dict, modules: dict, hours: float):
    """
    Wird in submit_anmeldung am Ende aufgerufen.
    Legt Eltern-Account(s) an, schickt Bestätigungs-Mail.
    """
    child_name = payload.get("child_name") or payload.get("child_first_name", "") + " " + payload.get("child_last_name", "")
    enrolled_from = payload.get("enrolled_from")

    with engine.begin() as conn:
        for role, name_key, email_key, phone_key in [
            ("mutter", "mother_name", "mother_email", "mother_phone"),
            ("vater", "father_name", "father_email", "father_phone"),
        ]:
            email = (payload.get(email_key) or "").strip()
            name = (payload.get(name_key) or "").strip()
            if not email or not name:
                continue
            phone = (payload.get(phone_key) or "").strip()
            pid = _kn_create_or_update_parent(
                conn, full_name=name, email=email, phone=phone, role=role,
                enrollment_id=None,  # noch keine — bei "apply" gesetzt
                child_name=child_name, doc_id=doc_id,
            )
            # Token holen für Mail
            row = conn.execute(sa.text(
                "SELECT login_token FROM kita_parent_accounts WHERE id=:id"
            ), {"id": pid}).first()
            token = row[0] if row else None
            if token:
                _kn_send_anmeldung_confirmation(
                    parent_email=email, parent_name=name, child_name=child_name,
                    modules=modules, hours=hours, login_token=token,
                    enrolled_from=enrolled_from,
                )

"""
SHIKSHA · KITA · Compliance · Daily Monitoring Cron

Läuft täglich 06:00 (per systemd timer oder cron):
- Berechnet aktuellen Monat-Snapshot pro Gruppe
- Bei Risiko über Schwelle: E-Mail an KITA-Leitung
- Schreibt persistierten Snapshot in DB für historische Audits

Aufruf:
  /opt/shiksha/venv/bin/python /opt/shiksha/kita_compliance_cron.py

Stand: 28.04.2026
"""
from __future__ import annotations
import os
import smtplib
import sys
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, "/opt/shiksha")
from main import engine
from kita_compliance_router import _compute_monthly_snapshot

# ============================================================
# KONFIG
# ============================================================
ALERT_THRESHOLD_EUR = 500
MAIL_FROM = os.environ.get("KITA_MAIL_FROM", "shiksha@tun.zone")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")


def send_alert(to_email: str, subject: str, body_html: str):
    """E-Mail an KITA-Leitung schicken."""
    if not SMTP_HOST or not to_email:
        print(f"[cron] kein SMTP konfiguriert oder kein Empfänger — würde senden an {to_email}: {subject}")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[cron] SMTP-Fehler: {e}")
        return False


def render_alert_html(snapshots: list, leitung_name: str = "KITA-Leitung") -> str:
    """HTML-Mail mit Risiko-Übersicht."""
    rows = ""
    total_risk = 0
    for s in snapshots:
        total_risk += s["funding_at_risk_eur"]
        risk_color = "#a0391f" if s["risk_level"] == "red" else "#8a6a2a" if s["risk_level"] == "yellow" else "#2d7a5f"
        rows += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #e6e4de;"><strong>{s['group_name']}</strong></td>
            <td style="padding:8px; border-bottom:1px solid #e6e4de; text-align:center;">{s['fte_required']:.2f}</td>
            <td style="padding:8px; border-bottom:1px solid #e6e4de; text-align:center;">{s['fte_actual']:.2f}</td>
            <td style="padding:8px; border-bottom:1px solid #e6e4de; text-align:center; color:{risk_color}; font-weight:600;">
                {s['fte_gap']:.2f}
            </td>
            <td style="padding:8px; border-bottom:1px solid #e6e4de; text-align:right; font-weight:700;">
                {s['funding_at_risk_eur']:.2f} €
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 20px auto;">
    <h2 style="color: #a0391f;">⚠ KITA Compliance-Warnung</h2>
    <p>Hallo {leitung_name},</p>
    <p>der laufende Monat zeigt ein <strong>Förder-Rückforderungs-Risiko von {total_risk:.2f}€</strong>.</p>
    <p>Konkrete Lücken:</p>

    <table style="width:100%; border-collapse:collapse; font-size:13px;">
        <thead style="background:#fafaf8;">
            <tr>
                <th style="padding:8px; text-align:left;">Gruppe</th>
                <th style="padding:8px;">Soll-FTE</th>
                <th style="padding:8px;">Ist-FTE</th>
                <th style="padding:8px;">Gap</th>
                <th style="padding:8px; text-align:right;">Risiko</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>

    <p style="margin-top:20px;">
        <a href="https://shiksha.tun.zone/kita/ui/dashboard"
           style="display:inline-block; padding:10px 20px; background:#1a1a1a; color:#fff; text-decoration:none; border-radius:6px;">
            Detail-Audit ansehen
        </a>
    </p>
    <p style="font-size:12px; color:#7a7a74; margin-top:30px;">
        Diese Warnung wurde automatisch erstellt.<br>
        SHIKSHA · KITA · Compliance · Vorarlberg KBBG · {datetime.now().strftime('%d.%m.%Y %H:%M')}
    </p>
</body></html>"""


def daily_check():
    """Hauptroutine."""
    today = date.today()
    snapshot_month = today.replace(day=1)

    print(f"[cron] {datetime.now()} — Compliance-Check für {snapshot_month}")

    flagged_snapshots = []
    with engine.connect() as conn:
        groups = conn.execute(sa.text(
            "SELECT id, name, group_type FROM kita_groups WHERE closed_at IS NULL"
        )).fetchall()

        for g in groups:
            group_dict = {"id": g[0], "name": g[1], "group_type": g[2]}
            snap = _compute_monthly_snapshot(conn, group_dict, snapshot_month)
            print(f"  · {g[1]}: Risiko {snap['funding_at_risk_eur']:.2f}€, {snap['days_undercov']} Lücken-Tage")

            if snap["funding_at_risk_eur"] >= ALERT_THRESHOLD_EUR:
                flagged_snapshots.append(snap)

            # Snapshot persistieren (für historischen Vergleich)
            with engine.begin() as wconn:
                wconn.execute(sa.text("""
                    INSERT INTO kita_compliance_snapshots
                      (id, group_id, snapshot_month, children_avg, fte_actual, fte_required,
                       ruleset_id, fte_gap, days_undercov, funding_at_risk_eur, risk_level,
                       computed_at, rule_versions_used)
                    VALUES (:id, :g, :m, :ca, :fa, :fr, :rs, :gap, :du, :risk, :rl, NOW(), :rv::jsonb)
                    ON CONFLICT (group_id, snapshot_month) DO UPDATE SET
                      children_avg = EXCLUDED.children_avg,
                      fte_actual = EXCLUDED.fte_actual,
                      fte_required = EXCLUDED.fte_required,
                      fte_gap = EXCLUDED.fte_gap,
                      days_undercov = EXCLUDED.days_undercov,
                      funding_at_risk_eur = EXCLUDED.funding_at_risk_eur,
                      risk_level = EXCLUDED.risk_level,
                      computed_at = NOW()
                """), {
                    "id": f"snap_{g[0]}_{snapshot_month.isoformat()}",
                    "g": g[0], "m": snapshot_month,
                    "ca": snap["children_avg"], "fa": snap["fte_actual"], "fr": snap["fte_required"],
                    "rs": list(snap["rule_versions_used"].values())[0] if snap["rule_versions_used"] else None,
                    "gap": snap["fte_gap"], "du": snap["days_undercov"],
                    "risk": snap["funding_at_risk_eur"], "rl": snap["risk_level"],
                    "rv": str(snap["rule_versions_used"]).replace("'", '"'),
                })

    # Alert wenn nötig
    if flagged_snapshots:
        leitung_email = os.environ.get("KITA_LEITUNG_EMAIL", "")
        if leitung_email:
            total = sum(s["funding_at_risk_eur"] for s in flagged_snapshots)
            html = render_alert_html(flagged_snapshots)
            ok = send_alert(
                to_email=leitung_email,
                subject=f"⚠ KITA Compliance: {len(flagged_snapshots)} Gruppe(n) mit Risiko {total:.0f}€",
                body_html=html,
            )
            print(f"[cron] Alert {'gesendet' if ok else 'wäre versendet'} an {leitung_email}")
    else:
        print("[cron] Alles ok, kein Alert nötig.")


if __name__ == "__main__":
    daily_check()

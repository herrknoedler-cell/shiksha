#!/usr/bin/env python3
"""
SHIKSHA · Insights-Cron
Wird täglich (z.B. 3:00 morgens) per systemd-timer oder klassischem cron
ausgeführt. Schreibt frische Insights in die Tabelle shiksha_insights.

  /etc/cron.d/shiksha-insights:
  0 3 * * *  root  /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py >> /var/log/shiksha-insights.log 2>&1

Idempotent: pro insight_key wird nur ein Eintrag pro Tag erzeugt.
"""

import os
import sys
import json as _ins_json
from datetime import date, timedelta, datetime
import sqlalchemy as sa

# Database connection — zentral aus database.py (env-driven, hard-fail)
from database import engine


def _upsert_insight(conn, key, audience, severity, icon, title, body,
                    action_label=None, action_url=None, valid_days=7, metadata=None):
    """Idempotent: derselbe insight_key wird nicht doppelt erzeugt."""
    valid_until = date.today() + timedelta(days=valid_days)
    conn.execute(sa.text("""
        INSERT INTO shiksha_insights
          (insight_key, audience, severity, icon, title, body,
           action_label, action_url, valid_until, metadata, active, generated_at)
        VALUES (:k, :a, :s, :ic, :t, :b, :al, :au, :vu, CAST(:m AS jsonb), true, NOW())
        ON CONFLICT (insight_key) DO UPDATE SET
          severity = EXCLUDED.severity,
          title = EXCLUDED.title,
          body = EXCLUDED.body,
          valid_until = EXCLUDED.valid_until,
          metadata = EXCLUDED.metadata,
          active = true,
          generated_at = NOW()
    """), {
        "k": key, "a": audience, "s": severity, "ic": icon,
        "t": title, "b": body,
        "al": action_label, "au": action_url, "vu": valid_until,
        "m": _ins_json.dumps(metadata or {}),
    })


def _expire_stale(conn):
    """Insights, deren valid_until vorbei ist, deaktivieren."""
    conn.execute(sa.text("""
        UPDATE shiksha_insights SET active = false
        WHERE valid_until < CURRENT_DATE AND active = true
    """))


# ============================================================
# INSIGHT-GENERATOREN
# ============================================================

def gen_attendance_anomaly(conn):
    """Wenn Anwesenheits-Quote heute auffällig niedrig oder hoch ist."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    try:
        avg_present = conn.execute(sa.text("""
            SELECT AVG(daily) FROM (
              SELECT COUNT(DISTINCT legacy_child_id) AS daily
              FROM kita_daily_assignments
              WHERE work_date BETWEEN :a AND :b
                AND status = 'present' AND person_type = 'child'
              GROUP BY work_date
            ) sub
        """), {"a": week_ago, "b": today - timedelta(days=1)}).scalar()
        today_present = conn.execute(sa.text("""
            SELECT COUNT(DISTINCT legacy_child_id)
            FROM kita_daily_assignments
            WHERE work_date = :d AND status = 'present' AND person_type = 'child'
        """), {"d": today}).scalar()
    except Exception:
        return
    if not avg_present or not today_present:
        return
    avg_present = float(avg_present)
    today_present = int(today_present)
    diff_pct = ((today_present - avg_present) / avg_present) * 100 if avg_present else 0
    if diff_pct <= -25:
        _upsert_insight(conn,
            key=f"attendance-low-{today.isoformat()}",
            audience="traegerin", severity="notice", icon="📉",
            title="Heute auffällig wenige Kinder",
            body=f"Aktuell sind {today_present} Kinder anwesend, im 7-Tage-Schnitt waren es {round(avg_present)}. Krankheitswelle? Brückentag?",
            action_label="Anwesenheit prüfen",
            action_url="/accounting/ui/paedagogen/app",
            valid_days=1,
            metadata={"today": today_present, "avg": round(avg_present)})


def gen_weekday_pattern(conn):
    """Wenn an einem bestimmten Wochentag die Personalbesetzung typischerweise knapp ist."""
    today = date.today()
    cutoff = today - timedelta(days=56)  # 8 Wochen
    try:
        rows = conn.execute(sa.text("""
            SELECT EXTRACT(DOW FROM work_date) AS dow,
                   COUNT(DISTINCT legacy_staff_id) AS staff_count,
                   work_date
            FROM kita_daily_assignments
            WHERE work_date >= :a AND person_type = 'staff' AND status = 'present'
            GROUP BY work_date
        """), {"a": cutoff}).mappings().fetchall()
    except Exception:
        rows = []
    if not rows:
        return
    # Avg pro Wochentag
    by_dow = {}
    for r in rows:
        by_dow.setdefault(int(r["dow"]), []).append(int(r["staff_count"]))
    if not by_dow:
        return
    overall_avg = sum(sum(v)/len(v) for v in by_dow.values()) / len(by_dow)
    for dow, counts in by_dow.items():
        avg = sum(counts) / len(counts)
        if avg < overall_avg * 0.85:  # 15% unter Schnitt
            day_names = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
            day = day_names[dow]
            _upsert_insight(conn,
                key=f"weekday-staff-low-{dow}",
                audience="traegerin", severity="notice", icon="📅",
                title=f"{day}s ist die Personaldecke oft knapp",
                body=f"In den letzten 8 Wochen war {day}s im Schnitt nur {round(avg, 1)} Pädagog:innen im Dienst — verglichen mit {round(overall_avg, 1)} im Gesamtschnitt. Soll ich eine Plan-Erinnerung anlegen?",
                action_label="Im Plan prüfen",
                valid_days=14,
                metadata={"weekday": dow, "avg": round(avg, 1), "overall_avg": round(overall_avg, 1)})


def gen_birthdays_upcoming(conn):
    """Wenn Geburtstage in den nächsten 7 Tagen anstehen."""
    today = date.today()
    end = today + timedelta(days=7)
    try:
        rows = conn.execute(sa.text("""
            SELECT id, name, birth_date FROM kita_legacy_children
            WHERE active = true AND birth_date IS NOT NULL
            UNION ALL
            SELECT id, name, birth_date FROM kita_legacy_staff
            WHERE active = true AND birth_date IS NOT NULL
        """)).mappings().fetchall()
    except Exception:
        rows = []
    upcoming = []
    for r in rows:
        bd = r["birth_date"]
        try:
            this_year = bd.replace(year=today.year)
        except ValueError:
            continue
        if today <= this_year <= end:
            upcoming.append({"name": r["name"], "date": this_year.isoformat()})
    if upcoming:
        names = ", ".join(u["name"] for u in upcoming[:3])
        more = f" und {len(upcoming)-3} weitere" if len(upcoming) > 3 else ""
        _upsert_insight(conn,
            key=f"birthdays-{today.isoformat()}",
            audience="all", severity="info", icon="🎂",
            title=f"{len(upcoming)} Geburtstag{'e' if len(upcoming) != 1 else ''} diese Woche",
            body=f"{names}{more} feiern in den nächsten Tagen.",
            action_label="Im Kalender öffnen",
            action_url="/accounting/ui/kita/calendar",
            valid_days=7,
            metadata={"count": len(upcoming), "names": [u["name"] for u in upcoming]})


def gen_compliance_st(conn):
    """Wenn ST% unter Soll fällt."""
    try:
        row = conn.execute(sa.text("""
            SELECT st_prozent_actual, st_prozent_required, calculation_date
            FROM kita_st_prozent_calculations
            ORDER BY calculation_date DESC LIMIT 1
        """)).mappings().first()
    except Exception:
        return
    if not row:
        return
    actual = float(row.get("st_prozent_actual") or 0)
    required = float(row.get("st_prozent_required") or 0)
    if required and actual < required:
        gap = required - actual
        _upsert_insight(conn,
            key=f"st-prozent-gap-{row['calculation_date']}",
            audience="traegerin", severity="warn" if gap > 5 else "notice", icon="📊",
            title=f"ST% liegt {round(gap, 1)} Punkte unter Soll",
            body=f"Aktuell {round(actual, 1)}% von {round(required, 1)}% Stellenbedarf erfüllt. Soll ich Vorschläge zur Schließung der Lücke berechnen?",
            action_label="ST%-Modul öffnen",
            action_url="/accounting/ui/kita/dashboard",
            valid_days=14,
            metadata={"actual": actual, "required": required, "gap": gap})


def gen_audit_open_findings(conn):
    """Wenn der letzte Audit-Run offene Findings hatte."""
    try:
        row = conn.execute(sa.text("""
            SELECT findings_count, run_at FROM kita_audit_runs
            ORDER BY run_at DESC LIMIT 1
        """)).mappings().first()
    except Exception:
        return
    if not row or not row.get("findings_count"):
        return
    cnt = int(row["findings_count"])
    if cnt > 0:
        _upsert_insight(conn,
            key=f"audit-findings-{row['run_at'].date().isoformat()}",
            audience="traegerin",
            severity="warn" if cnt >= 5 else "notice",
            icon="🛡",
            title=f"{cnt} offene Audit-Findings",
            body=f"Beim letzten Audit-Run wurden {cnt} Punkte zur Klärung gefunden. Möchten Sie sich diese ansehen?",
            action_label="Audit öffnen",
            action_url="/accounting/ui/kita/dashboard",
            valid_days=14,
            metadata={"findings": cnt})


def gen_quiet_celebration(conn):
    """Belohnender Insight: wenn alles ruhig läuft, das auch sagen."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    try:
        sick = conn.execute(sa.text("""
            SELECT COUNT(*) FROM kita_daily_assignments
            WHERE work_date BETWEEN :a AND :b AND status = 'sick'
        """), {"a": week_ago, "b": today}).scalar() or 0
        # Audit ohne findings, ST% erfüllt → Lob
        st = conn.execute(sa.text("""
            SELECT st_prozent_actual >= st_prozent_required AS ok
            FROM kita_st_prozent_calculations
            ORDER BY calculation_date DESC LIMIT 1
        """)).scalar()
    except Exception:
        return
    if sick <= 2 and st:
        _upsert_insight(conn,
            key=f"quiet-celebration-{today.isoformat()}",
            audience="traegerin", severity="info", icon="🌿",
            title="Eine ruhige, gute Woche",
            body=f"Die letzten 7 Tage liefen rund — kaum Krankheitsausfälle, ST% im grünen Bereich. Gute Arbeit vom Team!",
            valid_days=2)


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"[{datetime.now().isoformat()}] SHIKSHA Insights-Cron startet")
    with engine.begin() as conn:
        _expire_stale(conn)
        for fn in (gen_attendance_anomaly, gen_weekday_pattern,
                   gen_birthdays_upcoming, gen_compliance_st,
                   gen_audit_open_findings, gen_quiet_celebration):
            try:
                fn(conn)
                print(f"  ✓ {fn.__name__}")
            except Exception as e:
                print(f"  ✗ {fn.__name__}: {e}")
    print("Fertig.")


if __name__ == "__main__":
    main()

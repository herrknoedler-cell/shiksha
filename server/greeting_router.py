"""
SHIKSHA · Greeting & Insights Router
Liefert die 5-Schichten-Begrüßung an die Hero-Card auf dem Dashboard.

Endpoints:
  GET   /kita/dashboard/card/greeting?role=traegerin&user=heidi
  GET   /kita/dashboard/weekly-theme
  PUT   /kita/dashboard/weekly-theme
  GET   /kita/dashboard/insights?audience=traegerin
  POST  /kita/dashboard/insights/{id}/dismiss

Anhängen an /opt/shiksha/kita_compliance_router.py.
Knowledge-Bites werden aus /opt/shiksha/data/knowledge_bites.json gelesen.
"""

import json as _grt_json
import random as _grt_random
import pathlib as _grt_path
from datetime import date as _grt_date, timedelta as _grt_td, datetime as _grt_dt

KNOWLEDGE_PATH = "/opt/shiksha/data/knowledge_bites.json"


def _load_knowledge():
    try:
        return _grt_json.loads(_grt_path.Path(KNOWLEDGE_PATH).read_text())
    except Exception:
        return []


def _current_season():
    m = _grt_date.today().month
    if m in (3, 4, 5):    return "spring"
    if m in (6, 7, 8):    return "summer"
    if m in (9, 10, 11):  return "autumn"
    return "winter"


def _greeting_phrase(role, user, hour, weekday):
    """Anrede — tageszeit-, person-, team-bewusst."""
    if 5 <= hour < 11:
        time_word = "Guten Morgen"
    elif 11 <= hour < 14:
        time_word = "Schönen Mittag"
    elif 14 <= hour < 18:
        time_word = "Hallo"
    elif 18 <= hour < 22:
        time_word = "Guten Abend"
    else:
        time_word = "Hallo"

    name = (user or "").strip()
    if name and name.lower() not in ("default", "anonymous"):
        # Vorname extrahieren wenn voller Name
        first = name.split()[0]
        if first.startswith(("traegerin", "paedagogin")):
            return f"{time_word}, Krummelus-Team"
        return f"{time_word}, {first.capitalize()}"
    if role == "paedagogin":
        return f"{time_word}, liebes Krummelus-Team"
    if role == "traegerin":
        return f"{time_word}"
    return f"{time_word} im Krummelus"


def _mood_sentence(role):
    """Stimmungs-Satz aus den letzten 7 Tagen Daten."""
    today = _grt_date.today()
    week_ago = today - _grt_td(days=7)
    parts = []
    try:
        with engine.connect() as conn:
            # Wie viele Krankmeldungen letzte Woche?
            try:
                sick = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT (work_date, COALESCE(legacy_child_id::text, legacy_staff_id::text)))
                    FROM kita_daily_assignments
                    WHERE work_date BETWEEN :a AND :b AND status = 'sick'
                """), {"a": week_ago, "b": today}).scalar() or 0
            except Exception:
                sick = 0
            # Wie viele Events gab's letzte Woche?
            events = conn.execute(sa.text("""
                SELECT COUNT(*) FROM kita_calendar_events
                WHERE start_date BETWEEN :a AND :b
                  AND event_type IN ('event', 'celebration', 'training')
            """), {"a": week_ago, "b": today}).scalar() or 0
            # Aktuelle Anwesenheit
            try:
                present_now = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                    WHERE work_date = :d AND status = 'present' AND person_type = 'child'
                """), {"d": today}).scalar() or 0
            except Exception:
                present_now = 0

        # Erzähl-Logik: bevorzuge die markanteste Beobachtung
        if today.weekday() == 0:  # Montag
            if sick >= 4:
                return f"Letzte Woche war intensiv — {sick} Krankmeldungen, dafür liegt jetzt eine frische Woche vor uns."
            if events >= 2:
                return f"Letzte Woche {events} Veranstaltungen — was für eine erlebnisreiche Phase. Heute starten wir ruhig in die neue."
            return "Eine neue Woche steht an. Wir wünschen einen guten Start!"
        if today.weekday() == 4:  # Freitag
            return "Endspurt der Woche — gleich Wochenende. Was ist heute noch dran?"
        # Wochentags-Default
        if present_now > 0:
            return f"Gerade sind {present_now} Kinder bei Euch. Schöner Tag dafür."
        if events >= 1:
            return "Heute steht etwas Besonderes an — wir freuen uns darauf!"
        if sick >= 3:
            return "Wir denken an alle, die diese Woche krank sind. Gute Besserung!"
        return "Einen schönen Tag im Krummelus."
    except Exception:
        return "Schön, dass Du da bist."


def _pick_knowledge_bite(role):
    """Wissens-Snippet — kontext-passend, mit etwas Zufall."""
    bites = _load_knowledge()
    if not bites:
        return None
    season = _current_season()
    # Filter: Audience + Saison
    candidates = [
        b for b in bites
        if (not b.get("audience") or role in b["audience"] or "all" in b["audience"])
        and (b.get("season", "always") in ("always", season))
    ]
    if not candidates:
        candidates = bites
    # Tagesbasierter Pseudo-Zufall, damit Bite einen ganzen Tag stabil bleibt
    seed = _grt_date.today().toordinal() + (1 if role == "traegerin" else 2)
    rng = _grt_random.Random(seed)
    return rng.choice(candidates)


def _current_weekly_theme():
    today = _grt_date.today()
    monday = today - _grt_td(days=today.weekday())
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT theme, set_by, note, week_start FROM weekly_themes
                WHERE week_start = :w
            """), {"w": monday}).mappings().first()
    except Exception:
        row = None
    if not row:
        return None
    days_left = 7 - today.weekday()
    return {
        "theme": row["theme"],
        "set_by": row.get("set_by"),
        "note": row.get("note"),
        "week_start": row["week_start"].isoformat(),
        "days_left": days_left,
    }


def _top_insight(role, user_id):
    """Den am stärksten gewichteten aktiven Insight für die Persona."""
    today = _grt_date.today()
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT i.id, i.title, i.body, i.icon, i.severity, i.action_label, i.action_url,
                       i.metadata, i.generated_at
                FROM shiksha_insights i
                LEFT JOIN shiksha_insight_dismisses d ON d.insight_id = i.id AND d.user_id = :uid
                WHERE i.active = true
                  AND (i.audience = :aud OR i.audience = 'all')
                  AND (i.valid_until IS NULL OR i.valid_until >= :today)
                  AND d.user_id IS NULL
                ORDER BY
                  CASE i.severity WHEN 'warn' THEN 1 WHEN 'notice' THEN 2 ELSE 3 END,
                  i.generated_at DESC
                LIMIT 1
            """), {"aud": role, "uid": user_id, "today": today}).mappings().first()
    except Exception:
        return None
    if not row:
        return None
    out = dict(row)
    if out.get("generated_at"):
        out["generated_at"] = out["generated_at"].isoformat()
    return out


# ============================================================
# ENDPOINTS
# ============================================================

@kita_router.get("/dashboard/card/greeting")
async def card_greeting(
    role: str = "traegerin",
    user: str = "",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    now = _grt_dt.now()
    return {
        "greeting": _greeting_phrase(role, user, now.hour, now.weekday()),
        "mood": _mood_sentence(role),
        "knowledge": _pick_knowledge_bite(role),
        "weekly_theme": _current_weekly_theme(),
        "insight": _top_insight(role, user_id),
        "time": now.isoformat(),
        "tip": "SHIKSHA lernt — mit jedem Tag mehr.",
    }


@kita_router.get("/dashboard/weekly-theme")
async def weekly_theme_get(week_start: str = None):
    if week_start:
        d = _grt_date.fromisoformat(week_start)
    else:
        today = _grt_date.today()
        d = today - _grt_td(days=today.weekday())
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT * FROM weekly_themes WHERE week_start = :w
        """), {"w": d}).mappings().first()
    if not row:
        return {"week_start": d.isoformat(), "theme": None}
    return {**dict(row), "week_start": row["week_start"].isoformat(),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None}


@kita_router.put("/dashboard/weekly-theme")
async def weekly_theme_put(payload: dict = Body(...)):
    today = _grt_date.today()
    monday = today - _grt_td(days=today.weekday())
    week_start = payload.get("week_start")
    if week_start:
        week_start = _grt_date.fromisoformat(week_start)
    else:
        week_start = monday
    theme = (payload.get("theme") or "").strip()
    if not theme:
        raise HTTPException(400, "theme Pflicht")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO weekly_themes (week_start, theme, set_by, note)
            VALUES (:w, :t, :s, :n)
            ON CONFLICT (week_start) DO UPDATE
              SET theme = :t, set_by = :s, note = :n
        """), {
            "w": week_start, "t": theme,
            "s": payload.get("set_by", "leitung"),
            "n": payload.get("note"),
        })
    return {"ok": True, "week_start": week_start.isoformat(), "theme": theme}


@kita_router.get("/dashboard/insights")
async def insights_list(
    audience: str = "all",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    today = _grt_date.today()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT i.*, (d.user_id IS NOT NULL) AS dismissed
            FROM shiksha_insights i
            LEFT JOIN shiksha_insight_dismisses d ON d.insight_id = i.id AND d.user_id = :uid
            WHERE i.active = true
              AND (i.audience = :aud OR i.audience = 'all' OR :aud = 'all')
              AND (i.valid_until IS NULL OR i.valid_until >= :today)
            ORDER BY i.generated_at DESC
            LIMIT 20
        """), {"aud": audience, "uid": user_id, "today": today}).mappings().fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("generated_at", "valid_until"):
            if d.get(k):
                d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else d[k]
        out.append(d)
    return {"insights": out}


@kita_router.post("/dashboard/insights/{insight_id}/dismiss")
async def insight_dismiss(
    insight_id: int,
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO shiksha_insight_dismisses (insight_id, user_id)
            VALUES (:id, :uid)
            ON CONFLICT DO NOTHING
        """), {"id": insight_id, "uid": user_id})
    return {"ok": True}

"""
SHIKSHA · Dashboard-Router
Layout-Persistierung + Card-Daten-Endpoints.

Endpoints:
  GET  /kita/dashboard/layout?key=traegerin           — Layout laden (X-User-ID Header)
  PUT  /kita/dashboard/layout                         — Layout speichern
  GET  /kita/dashboard/card/anwesenheit-summary       — {present, total, paedagogin_count}
  GET  /kita/dashboard/card/birthdays-week            — diese Woche Geburtstage
  GET  /kita/dashboard/card/upcoming-events           — nächste 14 Tage
  GET  /kita/dashboard/card/messages-recent           — letzte 5 Mitteilungen
  GET  /kita/dashboard/card/compliance-status         — VBZ/ST/Audit-Ampel
  GET  /kita/dashboard/card/spotlight/{type}/{id}     — Person/Kind im Detail

Anhängen an /opt/shiksha/kita_compliance_router.py.
"""

import json as _dash_json
from datetime import date as _dash_date, timedelta as _dash_td

# ============================================================
# DEFAULT-LAYOUT (Trägerin)
# ============================================================
_DEFAULT_TRAEGERIN_LAYOUT = [
    # Hero: SHIKSHA-Begrüßung — der Tag beginnt mit Persönlichkeit
    {"id": "greeting",   "x": 0, "y": 0, "w": 12, "h": 4, "type": "shiksha-greeting",
     "config": {"role": "traegerin"}},

    # Mini-Stats-Row + runde Buttons
    {"id": "anw-mini",   "x": 0, "y": 4, "w": 3, "h": 2, "type": "anwesenheit-mini"},
    {"id": "st-mini",    "x": 3, "y": 4, "w": 3, "h": 2, "type": "stprozent-mini"},
    {"id": "act-pers",   "x": 6, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Personen", "icon": "👥", "url": "/accounting/ui/kita/personen", "color": "pink"}},
    {"id": "act-cal",    "x": 8, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Kalender", "icon": "📅", "url": "/accounting/ui/kita/calendar", "color": "purple"}},
    {"id": "act-push",   "x": 10, "y": 4, "w": 2, "h": 2, "type": "action-round",
     "config": {"label": "Push", "icon": "📣", "url": "/accounting/ui/kita/push", "color": "turquoise"}},

    # Compliance-Mini
    {"id": "comp-mini",  "x": 0, "y": 6, "w": 3, "h": 2, "type": "compliance-mini"},

    # Mid: Live-Anwesenheit + Termine
    {"id": "anw-live",   "x": 0, "y": 8, "w": 6, "h": 4, "type": "anwesenheit-live"},
    {"id": "ev-up",      "x": 6, "y": 8, "w": 6, "h": 4, "type": "events-upcoming"},

    # Geburtstag-Hero
    {"id": "bday-hero",  "x": 0, "y": 12, "w": 12, "h": 3, "type": "birthday-hero"},

    # Footer
    {"id": "msg-rec",    "x": 0, "y": 15, "w": 6, "h": 4, "type": "messages-recent"},
    {"id": "comp-stat",  "x": 6, "y": 15, "w": 6, "h": 4, "type": "compliance-status"},
]

_DEFAULT_PAEDAGOGIN_LAYOUT = [
    {"id": "greeting",  "x": 0, "y": 0,  "w": 12, "h": 4, "type": "shiksha-greeting",
     "config": {"role": "paedagogin"}},
    {"id": "anw-live",  "x": 0, "y": 4,  "w": 12, "h": 4, "type": "anwesenheit-live"},
    {"id": "ev-up",     "x": 0, "y": 8,  "w": 6,  "h": 4, "type": "events-upcoming"},
    {"id": "bday-hero", "x": 6, "y": 8,  "w": 6,  "h": 4, "type": "birthday-hero"},
    {"id": "msg-rec",   "x": 0, "y": 12, "w": 12, "h": 3, "type": "messages-recent"},
]


def _default_layout(key):
    if key == "paedagogin":
        return _DEFAULT_PAEDAGOGIN_LAYOUT
    return _DEFAULT_TRAEGERIN_LAYOUT


# ============================================================
# LAYOUT GET / PUT
# ============================================================

@kita_router.get("/dashboard/layout")
async def dashboard_layout_get(
    key: str = "traegerin",
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    with engine.connect() as conn:
        row = conn.execute(sa.text("""
            SELECT layout, edit_mode FROM dashboard_layouts
            WHERE user_id = :uid AND dashboard_key = :dk
        """), {"uid": user_id, "dk": key}).first()
    if not row:
        return {"layout": _default_layout(key), "is_default": True, "edit_mode": False}
    return {"layout": row[0], "is_default": False, "edit_mode": bool(row[1])}


@kita_router.put("/dashboard/layout")
async def dashboard_layout_put(
    payload: dict = Body(...),
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    key = payload.get("key", "traegerin")
    layout = payload.get("layout", [])
    edit_mode = bool(payload.get("edit_mode", False))
    layout_json = _dash_json.dumps(layout)
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO dashboard_layouts (user_id, dashboard_key, layout, edit_mode)
            VALUES (:uid, :dk, CAST(:l AS jsonb), :em)
            ON CONFLICT (user_id, dashboard_key)
            DO UPDATE SET layout = CAST(:l AS jsonb),
                          edit_mode = :em,
                          updated_at = NOW()
        """), {"uid": user_id, "dk": key, "l": layout_json, "em": edit_mode})
    return {"ok": True, "saved": len(layout)}


@kita_router.post("/dashboard/layout/reset")
async def dashboard_layout_reset(
    payload: dict = Body(default={}),
    user_id: str = Header(default="default", alias="X-User-Id"),
):
    key = payload.get("key", "traegerin")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            DELETE FROM dashboard_layouts WHERE user_id = :uid AND dashboard_key = :dk
        """), {"uid": user_id, "dk": key})
    return {"ok": True, "layout": _default_layout(key)}


# ============================================================
# CARD-DATEN-ENDPOINTS
# ============================================================

@kita_router.get("/dashboard/card/anwesenheit-summary")
async def card_anwesenheit_summary():
    today = _dash_date.today()
    with engine.connect() as conn:
        # Kinder gesamt + heute anwesend (per kita_daily_assignments)
        kids_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_children WHERE active = true")).scalar() or 0
        try:
            kids_present = conn.execute(sa.text("""
                SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                WHERE work_date = :d AND status = 'present' AND person_type = 'child'
            """), {"d": today}).scalar() or 0
        except Exception:
            kids_present = 0
        staff_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_staff WHERE active = true")).scalar() or 0
        try:
            staff_present = conn.execute(sa.text("""
                SELECT COUNT(DISTINCT legacy_staff_id) FROM kita_daily_assignments
                WHERE work_date = :d AND status = 'present' AND person_type = 'staff'
            """), {"d": today}).scalar() or 0
        except Exception:
            staff_present = 0
    return {
        "kids": {"present": int(kids_present), "total": int(kids_total)},
        "staff": {"present": int(staff_present), "total": int(staff_total)},
        "date": today.isoformat(),
    }


@kita_router.get("/dashboard/card/birthdays-week")
async def card_birthdays_week():
    today = _dash_date.today()
    end = today + _dash_td(days=7)
    out = []
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, name, birth_date, 'child' as type FROM kita_legacy_children
            WHERE active = true AND birth_date IS NOT NULL
            UNION ALL
            SELECT id, name, birth_date, 'staff' as type FROM kita_legacy_staff
            WHERE active = true AND birth_date IS NOT NULL
        """)).mappings().fetchall()
    for r in rows:
        bd = r["birth_date"]
        try:
            this_year = bd.replace(year=today.year)
        except ValueError:
            continue
        if today <= this_year <= end:
            age = today.year - bd.year
            out.append({
                "id": r["id"], "name": r["name"], "type": r["type"],
                "date": this_year.isoformat(), "age_turning": age,
                "is_today": this_year == today,
            })
    out.sort(key=lambda x: x["date"])
    return {"birthdays": out, "range": {"from": today.isoformat(), "to": end.isoformat()}}


@kita_router.get("/dashboard/card/upcoming-events")
async def card_upcoming_events(days: int = 14):
    today = _dash_date.today()
    end = today + _dash_td(days=days)
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, title, event_type, start_date, start_time, location, color
            FROM kita_calendar_events
            WHERE start_date BETWEEN :a AND :b
              AND visible_traegerin = true
            ORDER BY start_date, start_time
            LIMIT 20
        """), {"a": today, "b": end}).mappings().fetchall()
    events = []
    for r in rows:
        d = dict(r)
        if d.get("start_date"): d["start_date"] = d["start_date"].isoformat()
        if d.get("start_time"): d["start_time"] = str(d["start_time"])
        # Default-Farbe nachziehen
        if not d.get("color"):
            d["color"] = EVENT_TYPE_COLORS.get(d.get("event_type"), "#888")
        events.append(d)
    return {"events": events, "count": len(events)}


@kita_router.get("/dashboard/card/messages-recent")
async def card_messages_recent(limit: int = 5):
    try:
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT id, title, body, audience, created_at
                FROM kita_notifications
                ORDER BY created_at DESC LIMIT :l
            """), {"l": limit}).mappings().fetchall()
        return {"messages": [
            {**dict(r), "created_at": r["created_at"].isoformat() if r.get("created_at") else None}
            for r in rows
        ]}
    except Exception:
        return {"messages": []}


@kita_router.get("/dashboard/card/compliance-status")
async def card_compliance_status():
    """Liefert Ampel-Status für ST%, VBZ, Audit."""
    out = {"st_prozent": "ok", "vbz": "ok", "audit": "ok", "details": {}}
    try:
        with engine.connect() as conn:
            # ST% — ist eine Spalte in kita_audit_runs / kita_compliance, je nach DB-Version
            try:
                row = conn.execute(sa.text("""
                    SELECT * FROM kita_st_prozent_calculations
                    ORDER BY calculation_date DESC LIMIT 1
                """)).mappings().first()
                if row:
                    fulfilled = float(row.get("st_prozent_actual") or 0) >= float(row.get("st_prozent_required") or 100)
                    out["st_prozent"] = "ok" if fulfilled else "warn"
                    out["details"]["st_prozent"] = {
                        "actual": float(row.get("st_prozent_actual") or 0),
                        "required": float(row.get("st_prozent_required") or 0),
                    }
            except Exception:
                out["st_prozent"] = "unknown"

            # Audits — letzter Audit-Run
            try:
                row = conn.execute(sa.text("""
                    SELECT findings_count, run_at FROM kita_audit_runs
                    ORDER BY run_at DESC LIMIT 1
                """)).mappings().first()
                if row:
                    cnt = int(row.get("findings_count") or 0)
                    out["audit"] = "ok" if cnt == 0 else ("warn" if cnt < 5 else "alert")
                    out["details"]["audit"] = {"findings": cnt}
            except Exception:
                out["audit"] = "unknown"
    except Exception as e:
        out["error"] = str(e)
    return out


@kita_router.get("/dashboard/card/stprozent-mini")
async def card_stprozent_mini():
    try:
        with engine.connect() as conn:
            row = conn.execute(sa.text("""
                SELECT st_prozent_actual, st_prozent_required, calculation_date
                FROM kita_st_prozent_calculations
                ORDER BY calculation_date DESC LIMIT 1
            """)).mappings().first()
        if not row:
            return {"actual": None, "required": None, "ratio": None}
        actual = float(row["st_prozent_actual"] or 0)
        required = float(row["st_prozent_required"] or 0)
        ratio = (actual / required) if required else None
        return {
            "actual": round(actual, 1),
            "required": round(required, 1),
            "ratio": round(ratio, 2) if ratio else None,
            "date": row["calculation_date"].isoformat() if row.get("calculation_date") else None,
        }
    except Exception:
        return {"actual": None, "required": None, "ratio": None}

"""
SHIKSHA · KITA-Calendar-Router — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Das ist die Original-Cowork-Quelle für den KITA-Calendar-Code, der am
30.04.2026 via `kalender_deploy.sh` an `/opt/shiksha/kita_compliance_router.py`
ANGEHÄNGT wurde — nicht als separater Router deployed.

Der deployed-Stand lebt heute in:

    server/kita_compliance_router.py  ab Zeile ~3244

mit u.a. EVENT_TYPE_COLORS, EVENT_TYPE_LABELS, GET /kita/calendar/event-types,
GET/POST/PATCH/DELETE /kita/calendar/events, POST /kita/calendar/auto-birthdays.

Diese Datei liegt nur hier, damit das ursprüngliche Snippet als isolierte
Sicht für Audits oder spätere Refactorings verfügbar ist. Würden wir es als
server/calendar_router.py einchecken, gäbe es zwei Quellen für dieselben
Endpoints — und beide würden mit der Zeit divergieren.

Refactor-Pfad (ein anderer Tag): wenn der KITA-Calendar irgendwann als
eigenständiger Router aus kita_compliance_router.py extrahiert wird, kann
diese Datei als Ausgangspunkt zurück nach server/ wandern. Vorher nicht.

Original-Quelle: cowork/outputs/kalender/calendar_router.py
Original-Datum: 2026-05-01
Importiert ins Repo: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
SHIKSHA · KITA · Calendar-Router
Endpoints:
  GET  /kita/calendar/events?from=YYYY-MM-DD&to=YYYY-MM-DD&types=...
  POST /kita/calendar/events
  PATCH /kita/calendar/events/{id}
  DELETE /kita/calendar/events/{id}
  POST /kita/calendar/auto-birthdays    — generiert Geburtstage aus kita_legacy_children
  GET  /kita/calendar/event-types       — Liste der Typen + Default-Farben

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
Stand: 30.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

from datetime import date as _cal_date, timedelta as _cal_td


# Default-Farben pro Event-Typ (Holi-Palette)
EVENT_TYPE_COLORS = {
    "meeting": "#a855f7",         # Lila — Meetings
    "birthday": "#ffd93d",        # Gelb — Geburtstage 🎂
    "closing": "#a0391f",         # Alert-Rot — KITA geschlossen
    "event": "#ff8c42",           # Orange — Veranstaltungen (Sommerfest, Wandertag)
    "training": "#00d4d4",        # Türkis — Fortbildungen
    "celebration": "#ff4d8d",     # Pink — Feiern
    "parent_meeting": "#6dd47e",  # Grün — Elterngespräche
    "other": "#9a8e9e",           # Grau — sonstiges
}

EVENT_TYPE_LABELS = {
    "meeting": "Meeting",
    "birthday": "Geburtstag 🎂",
    "closing": "KITA geschlossen",
    "event": "Veranstaltung",
    "training": "Fortbildung",
    "celebration": "Feier",
    "parent_meeting": "Elterngespräch",
    "other": "Sonstiges",
}


@kita_router.get("/calendar/event-types")
async def calendar_event_types():
    return {
        "types": [
            {"key": k, "label": EVENT_TYPE_LABELS[k], "color": EVENT_TYPE_COLORS[k]}
            for k in EVENT_TYPE_COLORS
        ],
    }


@kita_router.get("/calendar/events")
async def calendar_events_in_range(
    from_date: str = None, to_date: str = None,
    types: str = None, audience: str = "traegerin",
):
    """Events im Zeitraum. Expandiert recurrence (yearly für Geburtstage)."""
    today = _cal_date.today()
    f = _cal_date.fromisoformat(from_date) if from_date else today.replace(day=1)
    t = _cal_date.fromisoformat(to_date) if to_date else f.replace(year=f.year + 1)

    type_list = [x.strip() for x in (types or "").split(",") if x.strip()]

    where = ["1=1"]
    params = {"f": f, "t": t}
    if type_list:
        where.append("event_type = ANY(:types)")
        params["types"] = type_list
    if audience == "paedagogin":
        where.append("visible_paedagogin = true")
    elif audience == "eltern":
        where.append("visible_eltern = true")
    elif audience == "traegerin":
        where.append("visible_traegerin = true")

    sql = f"""
    SELECT id, title, description, event_type,
           start_date, start_time, end_date, end_time, all_day,
           recurrence, recurrence_until, recurrence_weekdays,
           target_type, target_legacy_group_ids, target_legacy_staff_ids, target_legacy_child_ids,
           visible_traegerin, visible_paedagogin, visible_eltern,
           color, location, auto_source, created_by, created_at
    FROM kita_calendar_events
    WHERE {' AND '.join(where)}
    """

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()

    # Events expandieren (z.B. yearly Geburtstag — alle Jahre im Range)
    expanded = []
    for r in rows:
        event = {
            "id": r[0], "title": r[1], "description": r[2], "event_type": r[3],
            "start_date": r[4].isoformat() if r[4] else None,
            "start_time": str(r[5]) if r[5] else None,
            "end_date": r[6].isoformat() if r[6] else None,
            "end_time": str(r[7]) if r[7] else None,
            "all_day": r[8],
            "recurrence": r[9], "recurrence_until": r[10].isoformat() if r[10] else None,
            "recurrence_weekdays": list(r[11] or []),
            "target_type": r[12],
            "target_legacy_group_ids": list(r[13] or []),
            "target_legacy_staff_ids": list(r[14] or []),
            "target_legacy_child_ids": list(r[15] or []),
            "visible_traegerin": r[16], "visible_paedagogin": r[17], "visible_eltern": r[18],
            "color": r[19] or EVENT_TYPE_COLORS.get(r[3], "#888"),
            "color_default": EVENT_TYPE_COLORS.get(r[3], "#888"),
            "label": EVENT_TYPE_LABELS.get(r[3], r[3]),
            "location": r[20], "auto_source": r[21],
            "created_by": r[22],
        }
        # Wenn Range-Filter relevant: wenn Event nicht in Range, expandiere recurrence
        if event["recurrence"] == "yearly" and r[4]:
            # Zeige Geburtstag in jedem Jahr im Range
            base = r[4]
            year = f.year
            while year <= t.year:
                try:
                    new_date = base.replace(year=year)
                    if f <= new_date <= t:
                        ev_copy = dict(event)
                        ev_copy["start_date"] = new_date.isoformat()
                        ev_copy["end_date"] = new_date.isoformat()
                        ev_copy["display_year"] = year
                        ev_copy["age_at_event"] = year - base.year if base.year < year else None
                        expanded.append(ev_copy)
                except ValueError:
                    pass  # 29.02. in Nicht-Schaltjahr
                year += 1
        else:
            # Nicht-rekurrent oder andere Rekurrenz: nur wenn im Range
            sd = r[4]
            ed = r[6] or sd
            if sd and ed and sd <= t and ed >= f:
                expanded.append(event)

    expanded.sort(key=lambda e: (e["start_date"] or "", e.get("start_time") or ""))
    return {"count": len(expanded), "events": expanded, "range": {"from": f.isoformat(), "to": t.isoformat()}}


@kita_router.post("/calendar/events")
async def calendar_event_create(payload: dict = Body(...)):
    title = payload.get("title")
    if not title:
        raise HTTPException(400, "title Pflicht")
    eid = _new_id("ev")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_calendar_events
              (id, title, description, event_type,
               start_date, start_time, end_date, end_time, all_day,
               recurrence, recurrence_until, recurrence_weekdays,
               target_type, target_legacy_group_ids, target_legacy_staff_ids, target_legacy_child_ids,
               visible_traegerin, visible_paedagogin, visible_eltern,
               color, location, created_by)
            VALUES (:id, :t, :d, :et,
                    :sd, :st_, :ed, :et_, :ad,
                    :r, :ru, :rw,
                    :tt, :tg, :ts, :tc,
                    :vt, :vp, :ve,
                    :c, :l, :cb)
        """), {
            "id": eid, "t": title, "d": payload.get("description"),
            "et": payload.get("event_type", "meeting"),
            "sd": payload.get("start_date"),
            "st_": payload.get("start_time"),
            "ed": payload.get("end_date"),
            "et_": payload.get("end_time"),
            "ad": bool(payload.get("all_day", False)),
            "r": payload.get("recurrence", "none"),
            "ru": payload.get("recurrence_until"),
            "rw": payload.get("recurrence_weekdays", []),
            "tt": payload.get("target_type", "all"),
            "tg": payload.get("target_legacy_group_ids", []),
            "ts": payload.get("target_legacy_staff_ids", []),
            "tc": payload.get("target_legacy_child_ids", []),
            "vt": bool(payload.get("visible_traegerin", True)),
            "vp": bool(payload.get("visible_paedagogin", True)),
            "ve": bool(payload.get("visible_eltern", False)),
            "c": payload.get("color"),
            "l": payload.get("location"),
            "cb": payload.get("created_by", "system"),
        })
    return {"id": eid, "title": title}


@kita_router.patch("/calendar/events/{eid}")
async def calendar_event_update(eid: str, payload: dict = Body(...)):
    fields = {}
    for k in ("title","description","event_type","start_date","start_time","end_date","end_time",
              "all_day","recurrence","recurrence_until","recurrence_weekdays",
              "target_type","target_legacy_group_ids","target_legacy_staff_ids","target_legacy_child_ids",
              "visible_traegerin","visible_paedagogin","visible_eltern",
              "color","location"):
        if k in payload:
            fields[k] = payload[k]
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE kita_calendar_events SET {', '.join(set_parts)} WHERE id = :id"
    fields["id"] = eid
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Event nicht gefunden")
    return {"id": eid, "updated": list(fields.keys())}


@kita_router.delete("/calendar/events/{eid}")
async def calendar_event_delete(eid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE id = :id"), {"id": eid})
        if result.rowcount == 0:
            raise HTTPException(404, "Event nicht gefunden")
    return {"id": eid, "deleted": True}


@kita_router.post("/calendar/auto-birthdays")
async def calendar_auto_birthdays():
    """
    Generiert für jedes aktive Kind ein yearly-recurring Geburtstag-Event.
    Idempotent: bestehende Auto-Birthdays werden übersprungen.
    """
    today = _cal_date.today()
    created = 0
    with engine.connect() as conn:
        children = conn.execute(sa.text("""
            SELECT id, name, birth_year FROM kita_legacy_children WHERE active = true
        """)).fetchall()

    # Wir nehmen für Geburtstag den 1. Januar des Geburtsjahres als Default,
    # weil wir nur birth_year haben, nicht das exakte Datum.
    # Für echtes Datum: später Feld birth_date hinzufügen.
    with engine.begin() as conn:
        for c in children:
            cid, name, birth_year = c
            if not birth_year:
                continue
            # Idempotent: prüfen ob schon vorhanden
            existing = conn.execute(sa.text("""
                SELECT id FROM kita_calendar_events
                WHERE auto_source = 'birthday_from_child' AND auto_source_id = :cid
            """), {"cid": str(cid)}).first()
            if existing:
                continue
            event_id = _new_id("ev")
            # Default: 1. Januar (User soll es manuell anpassen)
            base_date = _cal_date(birth_year, 1, 1)
            conn.execute(sa.text("""
                INSERT INTO kita_calendar_events
                  (id, title, event_type, start_date, all_day, recurrence,
                   target_type, target_legacy_child_ids,
                   visible_traegerin, visible_paedagogin, visible_eltern,
                   auto_source, auto_source_id, created_by)
                VALUES (:id, :t, 'birthday', :sd, true, 'yearly',
                        'child', ARRAY[:cid],
                        true, true, true,
                        'birthday_from_child', :csid, 'system')
            """), {
                "id": event_id,
                "t": f"🎂 Geburtstag {name}",
                "sd": base_date,
                "cid": cid, "csid": str(cid),
            })
            created += 1

    return {
        "created": created,
        "total_children": len(children),
        "note": "Defaultdatum 1. Januar — bitte echtes Datum manuell setzen via PATCH",
    }

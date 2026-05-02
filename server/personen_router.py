"""
SHIKSHA · KITA · Personen-Stammdaten Router
Endpoints:
  GET    /kita/staff                  — Liste aller Mitarbeiter
  POST   /kita/staff                  — anlegen
  GET    /kita/staff/{id}             — Detail
  PATCH  /kita/staff/{id}             — bearbeiten
  DELETE /kita/staff/{id}             — soft-delete (active=false)
  GET    /kita/children               — Liste aller Kinder
  POST   /kita/children               — anlegen
  GET    /kita/children/{id}          — Detail
  PATCH  /kita/children/{id}          — bearbeiten
  DELETE /kita/children/{id}          — soft-delete
  POST   /kita/children/{id}/sync-birthday  — manuelle Re-Sync des Geburtstag-Events

Side-Effects:
  - Anlegen/Bearbeiten/Löschen eines Kindes synct automatisch das
    Geburtstag-Event in kita_calendar_events (idempotent).
  - Mitarbeiter:innen-Geburtstage genauso (visible_paedagogin = true).

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.
Stand: 01.05.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import json as _pers_json


def _sync_birthday_event(conn, person_type, person_id, name, birth_date, active):
    """
    Idempotenter Birthday-Sync:
    - Existiert kein Event → anlegen (wenn aktiv + birth_date)
    - Existiert Event → updaten (Datum/Titel) bzw. löschen wenn inaktiv/kein Datum
    """
    auto_source = f"birthday_from_{person_type}"  # 'birthday_from_child' / 'birthday_from_staff'
    existing = conn.execute(sa.text("""
        SELECT id FROM kita_calendar_events
        WHERE auto_source = :src AND auto_source_id = :pid
    """), {"src": auto_source, "pid": str(person_id)}).first()

    if not active or not birth_date:
        if existing:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE id = :id"),
                         {"id": existing[0]})
        return None

    emoji_title = "🎂 Geburtstag " + name
    target_field = "target_legacy_child_ids" if person_type == "child" else "target_legacy_staff_ids"
    target_type = "child" if person_type == "child" else "staff"

    if existing:
        conn.execute(sa.text(f"""
            UPDATE kita_calendar_events
            SET title = :t, start_date = :sd, updated_at = NOW(),
                {target_field} = ARRAY[:pid]::INTEGER[],
                target_type = :tt
            WHERE id = :id
        """), {"t": emoji_title, "sd": birth_date, "id": existing[0],
               "pid": int(person_id), "tt": target_type})
        return existing[0]
    else:
        new_id = _new_id("ev")
        conn.execute(sa.text(f"""
            INSERT INTO kita_calendar_events
              (id, title, event_type, start_date, all_day, recurrence,
               target_type, {target_field},
               visible_traegerin, visible_paedagogin, visible_eltern,
               auto_source, auto_source_id, created_by)
            VALUES (:id, :t, 'birthday', :sd, true, 'yearly',
                    :tt, ARRAY[:pid]::INTEGER[],
                    true, true, :ve,
                    :src, :sid, 'system')
        """), {"id": new_id, "t": emoji_title, "sd": birth_date,
               "tt": target_type, "pid": int(person_id),
               "ve": (person_type == "child"),  # Eltern sehen nur Kinder-Geb.
               "src": auto_source, "sid": str(person_id)})
        return new_id


# ============================================================
# MITARBEITER:INNEN
# ============================================================

@kita_router.get("/staff")
async def staff_list(active_only: bool = True):
    sql = "SELECT * FROM kita_legacy_staff"
    if active_only:
        sql += " WHERE active = true"
    sql += " ORDER BY name"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql)).mappings().fetchall()
    return {"count": len(rows), "staff": [dict(r) for r in rows]}


@kita_router.get("/staff/{sid}")
async def staff_detail(sid: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM kita_legacy_staff WHERE id = :id"),
                           {"id": sid}).mappings().first()
    if not row:
        raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
    return dict(row)


@kita_router.post("/staff")
async def staff_create(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name Pflicht")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO kita_legacy_staff
              (name, role, weekly_hours, birth_date, email, phone, address,
               emergency_contact, employment_start, employment_end, contract_type,
               qualification, notes, active)
            VALUES (:n, :r, :wh, :bd, :em, :ph, :ad,
                    :ec, :es, :ee, :ct, :q, :no, true)
            RETURNING id
        """), {
            "n": name, "r": payload.get("role", "educator"),
            "wh": payload.get("weekly_hours") or 0,
            "bd": payload.get("birth_date"),
            "em": payload.get("email"), "ph": payload.get("phone"),
            "ad": payload.get("address"), "ec": payload.get("emergency_contact"),
            "es": payload.get("employment_start"), "ee": payload.get("employment_end"),
            "ct": payload.get("contract_type"), "q": payload.get("qualification"),
            "no": payload.get("notes"),
        })
        new_id = result.scalar()
        # Birthday-Sync
        if payload.get("birth_date"):
            _sync_birthday_event(conn, "staff", new_id, name, payload["birth_date"], True)
    return {"id": new_id, "name": name}


@kita_router.patch("/staff/{sid}")
async def staff_update(sid: int, payload: dict = Body(...)):
    allowed = ("name","role","weekly_hours","birth_date","email","phone","address",
               "emergency_contact","employment_start","employment_end","contract_type",
               "qualification","notes","active")
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE kita_legacy_staff SET {', '.join(set_parts)} WHERE id = :id RETURNING name, birth_date, active"
    fields["id"] = sid
    with engine.begin() as conn:
        row = conn.execute(sa.text(sql), fields).first()
        if not row:
            raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
        # Birthday-Sync (immer durchziehen — _sync entscheidet)
        _sync_birthday_event(conn, "staff", sid, row[0], row[1], row[2])
    return {"id": sid, "updated": list(fields.keys())}


@kita_router.delete("/staff/{sid}")
async def staff_delete(sid: int, hard: bool = False):
    with engine.begin() as conn:
        if hard:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE auto_source='birthday_from_staff' AND auto_source_id=:p"),
                         {"p": str(sid)})
            r = conn.execute(sa.text("DELETE FROM kita_legacy_staff WHERE id = :id"), {"id": sid})
        else:
            r = conn.execute(sa.text("UPDATE kita_legacy_staff SET active=false, updated_at=NOW() WHERE id = :id RETURNING name, birth_date"),
                             {"id": sid})
            row = r.first()
            if row:
                _sync_birthday_event(conn, "staff", sid, row[0], row[1], False)
        if r.rowcount == 0:
            raise HTTPException(404, "Mitarbeiter:in nicht gefunden")
    return {"id": sid, "deleted": True, "hard": hard}


# ============================================================
# KINDER
# ============================================================

@kita_router.get("/children")
async def children_list(active_only: bool = True):
    sql = "SELECT * FROM kita_legacy_children"
    if active_only:
        sql += " WHERE active = true"
    sql += " ORDER BY name"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql)).mappings().fetchall()
    return {"count": len(rows), "children": [dict(r) for r in rows]}


@kita_router.get("/children/{cid}")
async def children_detail(cid: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM kita_legacy_children WHERE id = :id"),
                           {"id": cid}).mappings().first()
    if not row:
        raise HTTPException(404, "Kind nicht gefunden")
    return dict(row)


@kita_router.post("/children")
async def children_create(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name Pflicht")
    birth_date = payload.get("birth_date")
    birth_year = payload.get("birth_year")
    if birth_date and not birth_year:
        # auto-derivate
        try:
            birth_year = int(birth_date[:4])
        except Exception:
            pass
    parents_json = _pers_json.dumps(payload.get("parents") or [])
    pickup_json = _pers_json.dumps(payload.get("pickup_authorized") or [])

    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO kita_legacy_children
              (name, birth_year, birth_date, gender, address, nationality,
               native_language, allergies, medications, medical_notes, dietary_notes,
               entry_date, exit_date, parents, pickup_authorized,
               emergency_contact, notes, photo_consent, active)
            VALUES (:n, :by, :bd, :g, :ad, :nat,
                    :lang, :al, :med, :mn, :dn,
                    :ed, :xd, CAST(:par AS jsonb), CAST(:pk AS jsonb),
                    :ec, :no, :pc, true)
            RETURNING id
        """), {
            "n": name, "by": birth_year, "bd": birth_date,
            "g": payload.get("gender"), "ad": payload.get("address"),
            "nat": payload.get("nationality"), "lang": payload.get("native_language"),
            "al": payload.get("allergies"), "med": payload.get("medications"),
            "mn": payload.get("medical_notes"), "dn": payload.get("dietary_notes"),
            "ed": payload.get("entry_date"), "xd": payload.get("exit_date"),
            "par": parents_json, "pk": pickup_json,
            "ec": payload.get("emergency_contact"), "no": payload.get("notes"),
            "pc": bool(payload.get("photo_consent", False)),
        })
        new_id = result.scalar()
        if birth_date:
            _sync_birthday_event(conn, "child", new_id, name, birth_date, True)
    return {"id": new_id, "name": name}


@kita_router.patch("/children/{cid}")
async def children_update(cid: int, payload: dict = Body(...)):
    # JSONB-Felder gesondert behandeln
    json_cols = {"parents", "pickup_authorized"}
    plain_cols = ("name","birth_year","birth_date","gender","address","nationality",
                  "native_language","allergies","medications","medical_notes","dietary_notes",
                  "entry_date","exit_date","emergency_contact","notes","photo_consent","active")

    fields = {}
    set_parts = []
    for k in plain_cols:
        if k in payload:
            fields[k] = payload[k]
            set_parts.append(f"{k} = :{k}")
    for k in json_cols:
        if k in payload:
            fields[k] = _pers_json.dumps(payload[k] or [])
            set_parts.append(f"{k} = CAST(:{k} AS jsonb)")
    if not set_parts:
        raise HTTPException(400, "keine Felder")

    # birth_year aus birth_date ableiten falls fehlt
    if "birth_date" in fields and "birth_year" not in fields and fields["birth_date"]:
        try:
            fields["birth_year"] = int(str(fields["birth_date"])[:4])
            set_parts.append("birth_year = :birth_year")
        except Exception:
            pass

    set_parts.append("updated_at = NOW()")
    fields["id"] = cid
    sql = f"UPDATE kita_legacy_children SET {', '.join(set_parts)} WHERE id = :id RETURNING name, birth_date, active"

    with engine.begin() as conn:
        row = conn.execute(sa.text(sql), fields).first()
        if not row:
            raise HTTPException(404, "Kind nicht gefunden")
        _sync_birthday_event(conn, "child", cid, row[0], row[1], row[2])
    return {"id": cid, "updated": [k for k in fields if k != "id"]}


@kita_router.delete("/children/{cid}")
async def children_delete(cid: int, hard: bool = False):
    with engine.begin() as conn:
        if hard:
            conn.execute(sa.text("DELETE FROM kita_calendar_events WHERE auto_source='birthday_from_child' AND auto_source_id=:p"),
                         {"p": str(cid)})
            r = conn.execute(sa.text("DELETE FROM kita_legacy_children WHERE id = :id"), {"id": cid})
        else:
            r = conn.execute(sa.text("UPDATE kita_legacy_children SET active=false, updated_at=NOW() WHERE id = :id RETURNING name, birth_date"),
                             {"id": cid})
            row = r.first()
            if row:
                _sync_birthday_event(conn, "child", cid, row[0], row[1], False)
        if r.rowcount == 0:
            raise HTTPException(404, "Kind nicht gefunden")
    return {"id": cid, "deleted": True, "hard": hard}


@kita_router.post("/children/{cid}/sync-birthday")
async def children_sync_birthday(cid: int):
    with engine.begin() as conn:
        row = conn.execute(sa.text("SELECT name, birth_date, active FROM kita_legacy_children WHERE id = :id"),
                           {"id": cid}).first()
        if not row:
            raise HTTPException(404, "Kind nicht gefunden")
        eid = _sync_birthday_event(conn, "child", cid, row[0], row[1], row[2])
    return {"event_id": eid, "synced": True}

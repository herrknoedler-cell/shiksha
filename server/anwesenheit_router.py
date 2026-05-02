"""
SHIKSHA · KITA · Anwesenheit + Daily Assignments + Archiv

Endpoints:
  GET  /kita/anwesenheit/today         — Live-Snapshot für Polling (15s)
  GET  /kita/anwesenheit?date=YYYY-MM-DD
  POST /kita/anwesenheit/assign        — Person zu Bereich/Gruppe zuordnen
  PATCH /kita/anwesenheit/{id}/status  — Status ändern (anwesend/krank/...)
  GET  /kita/group-merges              — aktive Gruppen-Merges (Sommersprossen)
  POST /kita/group-merges              — Merge anlegen
  GET  /archive/documents              — Cross-Edition Archiv-Liste
  GET  /archive/documents/{id}/file    — Original mit Audit-Log
  POST /archive/snapshot/attendance    — On-demand PDF generieren

Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 30.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import hashlib as _aw_hash
import json as _aw_json
from datetime import date as _aw_date, datetime as _aw_dt, time as _aw_time, timedelta as _aw_td
from pathlib import Path as _aw_Path
from fastapi.responses import FileResponse as _aw_FileResponse


ARCHIVE_DIR = _aw_Path("/opt/shiksha/archive")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


# Bereich-Reihenfolge + Default-Farben (Holi-Palette)
AREA_ORDER = ["vormittag", "mittagessen", "ruhe", "nachmittag", "vbz", "pause", "kuechendienst"]
AREA_COLORS = {
    "vormittag": "#ffd93d",      # Yellow
    "mittagessen": "#ff8c42",    # Orange
    "ruhe": "#a855f7",           # Purple
    "nachmittag": "#00d4d4",     # Turquoise
    "vbz": "#c8e6c0",            # Green-Soft
    "pause": "#d8d4ce",          # Grey-Soft
    "kuechendienst": "#c76b30",  # Brown-Red
}
STATUS_COLORS = {
    "planned": "#9a8e9e",
    "present": "#6dd47e",
    "absent": "#9a8e9e",
    "sick": "#ff4d8d",
    "vacation": "#ffd93d",
    "course": "#a855f7",
    "other": "#9a8e9e",
}


# ============================================================
# ANWESENHEIT — heutiger Snapshot
# ============================================================

@kita_router.get("/anwesenheit/today")
async def kita_anwesenheit_today():
    """Live-Snapshot pro Gruppe + Mitarbeiter, optimiert für 15s-Polling."""
    today = _aw_date.today()
    return await _aw_anwesenheit_for_date(today)


@kita_router.get("/anwesenheit")
async def kita_anwesenheit_for_date(date: str):
    target = _aw_date.fromisoformat(date)
    return await _aw_anwesenheit_for_date(target)


async def _aw_anwesenheit_for_date(target: _aw_date):
    """Zentrale Logik — gibt Sektionen pro Gruppe zurück mit Avatar-Daten."""
    weekday_key = target.strftime("%A").lower()  # 'monday', 'tuesday', ...

    with engine.connect() as conn:
        # 1. Aktive Gruppen-Merges für diesen Tag
        merges_today = conn.execute(sa.text("""
            SELECT id, merged_name, from_group_legacy_ids, time_from, time_to, weekdays
            FROM kita_group_merges
            WHERE active = true
              AND (valid_from_date IS NULL OR valid_from_date <= :d)
              AND (valid_to_date IS NULL OR valid_to_date >= :d)
              AND (:wd = ANY(weekdays) OR weekdays IS NULL)
        """), {"d": target, "wd": weekday_key}).fetchall()

        # 2. Alle aktiven Gruppen (Legacy)
        groups = conn.execute(sa.text("""
            SELECT id, name, capacity FROM kita_legacy_groups WHERE active = true ORDER BY name
        """)).fetchall()

        # 3. Alle Daily-Assignments für heute
        assigns = conn.execute(sa.text("""
            SELECT da.id, da.person_type, da.legacy_staff_id, da.legacy_child_id,
                   da.group_legacy_id, da.area, da.status,
                   da.time_from, da.time_to, da.note, da.note_visible_to_parents
            FROM kita_daily_assignments da
            WHERE da.work_date = :d
        """), {"d": target}).fetchall()

        # 4. Stammdaten Mitarbeiter + Kinder (alle aktiv)
        staff = {r[0]: {"id": r[0], "name": r[1], "role": r[2], "weekly_hours": r[3], "group_id": r[4]}
                 for r in conn.execute(sa.text("""
                     SELECT id, name, role, weekly_hours, group_id
                     FROM kita_legacy_staff WHERE active = true
                 """)).fetchall()}
        children = {r[0]: {"id": r[0], "name": r[1], "birth_year": r[2], "group_id": r[3]}
                    for r in conn.execute(sa.text("""
                        SELECT id, name, birth_year, group_id
                        FROM kita_legacy_children WHERE active = true
                    """)).fetchall()}

    # Hilfsfunktion: Slices für eine Person aus den Assignments bauen
    def _slices_for_person(person_type: str, person_id: int):
        slices = []
        for a in assigns:
            pt = a[1]
            if pt != person_type:
                continue
            pid = a[2] if pt == "staff" else a[3]
            if pid != person_id:
                continue
            slices.append({
                "area": a[5], "status": a[6],
                "time_from": str(a[7]) if a[7] else None,
                "time_to": str(a[8]) if a[8] else None,
                "note": a[9],
                "note_visible_to_parents": bool(a[10]),
                "color": AREA_COLORS.get(a[5], "#888"),
                "status_color": STATUS_COLORS.get(a[6], "#888"),
            })
        # Sort by AREA_ORDER
        slices.sort(key=lambda x: AREA_ORDER.index(x["area"]) if x["area"] in AREA_ORDER else 99)
        return slices

    # Ist diese Gruppe aktuell in einem Merge enthalten?
    def _check_merge(group_id: int) -> dict | None:
        for m in merges_today:
            from_ids = list(m[2] or [])
            if group_id in from_ids:
                return {
                    "merge_id": m[0],
                    "merged_name": m[1],
                    "time_from": str(m[3]) if m[3] else None,
                    "time_to": str(m[4]) if m[4] else None,
                }
        return None

    # 5. Sektionen aufbauen pro Gruppe
    sections = []
    for g in groups:
        gid, gname, gcap = g[0], g[1], g[2]
        merge_info = _check_merge(gid)

        # Mitarbeiter dieser Gruppe (über kita_legacy_staff.group_id ODER tagesaktuelle Zuordnung)
        section_staff = []
        for sid, sdata in staff.items():
            slices = _slices_for_person("staff", sid)
            assigned_to_group_today = any(
                a[1] == "staff" and a[2] == sid and a[4] == gid for a in assigns
            )
            if sdata["group_id"] == gid or assigned_to_group_today:
                # Initial = erstes Zeichen Vorname
                initial = (sdata["name"] or "?").split()[0][:1].upper()
                section_staff.append({
                    "id": sid, "name": sdata["name"], "initial": initial,
                    "role": sdata["role"], "weekly_hours": sdata["weekly_hours"],
                    "type": "staff",
                    "slices": slices,
                    "is_paedagoge": sdata["role"] == "educator",
                })

        section_children = []
        for cid, cdata in children.items():
            slices = _slices_for_person("child", cid)
            assigned_to_group_today = any(
                a[1] == "child" and a[3] == cid and a[4] == gid for a in assigns
            )
            if cdata["group_id"] == gid or assigned_to_group_today:
                initial = (cdata["name"] or "?")[:1].upper()
                section_children.append({
                    "id": cid, "name": cdata["name"], "initial": initial,
                    "birth_year": cdata["birth_year"],
                    "type": "child",
                    "slices": slices,
                })

        # Counts
        present_kids = sum(1 for c in section_children if any(s["status"] == "present" for s in c["slices"]))
        present_staff = sum(1 for s in section_staff if any(sl["status"] == "present" for sl in s["slices"]))
        has_paedagoge = any(s["is_paedagoge"] and any(sl["status"] == "present" for sl in s["slices"]) for s in section_staff)

        sections.append({
            "group_id": gid,
            "group_name": gname,
            "capacity": gcap,
            "merged_into": merge_info,
            "staff": section_staff,
            "children": section_children,
            "counts": {
                "kids_total": len(section_children),
                "kids_present": present_kids,
                "staff_total": len(section_staff),
                "staff_present": present_staff,
                "has_paedagoge": has_paedagoge,
            },
        })

    return {
        "date": target.isoformat(),
        "weekday": weekday_key,
        "sections": sections,
        "merges_active_today": [
            {"id": m[0], "merged_name": m[1], "time_from": str(m[3]) if m[3] else None,
             "time_to": str(m[4]) if m[4] else None}
            for m in merges_today
        ],
        "areas": AREA_ORDER,
        "area_colors": AREA_COLORS,
        "status_colors": STATUS_COLORS,
    }


# ============================================================
# DAILY-ASSIGNMENTS CRUD
# ============================================================

@kita_router.post("/anwesenheit/assign")
async def kita_anwesenheit_assign(payload: dict = Body(...)):
    """Person zu Bereich/Gruppe zuordnen."""
    work_date = payload.get("work_date") or _aw_date.today().isoformat()
    person_type = payload.get("person_type")
    if person_type not in ("staff", "child"):
        raise HTTPException(400, "person_type muss 'staff' oder 'child' sein")

    aid = _new_id("dassign")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_daily_assignments
              (id, work_date, person_type,
               legacy_staff_id, new_staff_id, legacy_child_id, new_enrollment_id,
               group_legacy_id, group_new_id,
               area, status, time_from, time_to, note, note_visible_to_parents, created_by)
            VALUES (:id, :d, :pt,
                    :ls, :ns, :lc, :ne,
                    :gl, :gn,
                    :a, :s, :tf, :tt, :n, :nvp, :cb)
        """), {
            "id": aid, "d": work_date, "pt": person_type,
            "ls": payload.get("legacy_staff_id"), "ns": payload.get("new_staff_id"),
            "lc": payload.get("legacy_child_id"), "ne": payload.get("new_enrollment_id"),
            "gl": payload.get("group_legacy_id"), "gn": payload.get("group_new_id"),
            "a": payload.get("area", "vormittag"),
            "s": payload.get("status", "planned"),
            "tf": payload.get("time_from"), "tt": payload.get("time_to"),
            "n": payload.get("note"),
            "nvp": payload.get("note_visible_to_parents", False),
            "cb": payload.get("created_by", "system"),
        })
    return {"id": aid}


@kita_router.patch("/anwesenheit/{aid}/status")
async def kita_anwesenheit_status(aid: str, payload: dict = Body(...)):
    new_status = payload.get("status")
    if new_status not in ("planned", "present", "absent", "sick", "vacation", "course", "other"):
        raise HTTPException(400, f"Ungültiger Status: {new_status}")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE kita_daily_assignments SET status = :s, updated_at = NOW() WHERE id = :id
        """), {"s": new_status, "id": aid})
        if result.rowcount == 0:
            raise HTTPException(404, "Assignment nicht gefunden")
    return {"id": aid, "status": new_status}


@kita_router.delete("/anwesenheit/{aid}")
async def kita_anwesenheit_delete(aid: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("DELETE FROM kita_daily_assignments WHERE id = :id"),
                              {"id": aid})
        if result.rowcount == 0:
            raise HTTPException(404, "Assignment nicht gefunden")
    return {"id": aid, "deleted": True}


# ============================================================
# GROUP-MERGES
# ============================================================

@kita_router.get("/group-merges")
async def kita_group_merges_list():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, merged_name, from_group_legacy_ids, valid_from_date, valid_to_date,
                   weekdays, time_from, time_to, room_id, notes, active
            FROM kita_group_merges WHERE active = true
        """)).fetchall()
    return {
        "count": len(rows),
        "merges": [
            {
                "id": r[0], "merged_name": r[1], "from_group_ids": list(r[2] or []),
                "valid_from": r[3].isoformat() if r[3] else None,
                "valid_to": r[4].isoformat() if r[4] else None,
                "weekdays": list(r[5] or []),
                "time_from": str(r[6]) if r[6] else None,
                "time_to": str(r[7]) if r[7] else None,
                "room_id": r[8], "notes": r[9], "active": r[10],
            }
            for r in rows
        ],
    }


@kita_router.post("/group-merges")
async def kita_group_merge_create(payload: dict = Body(...)):
    name = payload.get("merged_name")
    if not name:
        raise HTTPException(400, "merged_name Pflicht")
    mid = _new_id("merge")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_group_merges
              (id, merged_name, from_group_legacy_ids, weekdays, time_from, time_to, room_id, notes)
            VALUES (:id, :n, :fg, :wd, :tf, :tt, :r, :no)
        """), {
            "id": mid, "n": name,
            "fg": payload.get("from_group_legacy_ids", []),
            "wd": payload.get("weekdays", ["monday","tuesday","wednesday","thursday","friday"]),
            "tf": payload.get("time_from", "13:30:00"),
            "tt": payload.get("time_to", "17:30:00"),
            "r": payload.get("room_id"), "no": payload.get("notes"),
        })
    return {"id": mid, "merged_name": name}


# ============================================================
# ARCHIV-MODUL
# ============================================================

def _aw_archive_save(edition: str, doc_type: str, target_id: str | None,
                     content_bytes: bytes, file_name: str, mime: str = "application/pdf",
                     period_from: _aw_date | None = None, period_to: _aw_date | None = None,
                     snapshot_for: _aw_date | None = None,
                     metadata: dict | None = None,
                     retention_years: int = 7,
                     legal_basis: str = "KBBG-Aufbewahrungsfrist"):
    """Speichert Datei im Archiv mit SHA256-Hash + Retention."""
    # Pfad-Konvention: archive/YYYY/MM/DD/
    today = snapshot_for or _aw_date.today()
    folder = ARCHIVE_DIR / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)

    doc_id = _new_id("arc")
    safe_name = "".join(c for c in file_name if c.isalnum() or c in "._-")[:80]
    disk_path = folder / f"{doc_id}_{safe_name}"
    disk_path.write_bytes(content_bytes)

    file_hash = _aw_hash.sha256(content_bytes).hexdigest()
    retention_until = _aw_date.today().replace(year=_aw_date.today().year + retention_years)

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO shiksha_archive_documents
              (id, edition, doc_type, target_id, file_path, file_name, file_mime, file_size, file_hash,
               period_from, period_to, snapshot_for, generated_by, retention_until, legal_basis, metadata)
            VALUES (:id, :ed, :dt, :ti, :p, :n, :m, :sz, :h,
                    :pf, :pt, :sf, :gb, :ru, :lb, CAST(:md AS jsonb))
        """), {
            "id": doc_id, "ed": edition, "dt": doc_type, "ti": target_id,
            "p": str(disk_path), "n": file_name, "m": mime,
            "sz": len(content_bytes), "h": file_hash,
            "pf": period_from, "pt": period_to, "sf": snapshot_for,
            "gb": "system",
            "ru": retention_until, "lb": legal_basis,
            "md": _aw_json.dumps(metadata or {}),
        })

    return {
        "id": doc_id, "file_path": str(disk_path), "file_hash": file_hash,
        "size": len(content_bytes), "retention_until": retention_until.isoformat(),
    }


@kita_router.post("/archive/snapshot/attendance")
async def archive_attendance_today(payload: dict = Body(default_factory=dict)):
    """On-demand: erzeugt PDF der Anwesenheitsliste + speichert im Archiv."""
    target_date_str = payload.get("date") or _aw_date.today().isoformat()
    target_date = _aw_date.fromisoformat(target_date_str)
    snapshot = await _aw_anwesenheit_for_date(target_date)

    # Einfaches HTML→PDF mittels reportlab (oder weasyprint)
    pdf_bytes = _aw_render_attendance_pdf(snapshot)
    result = _aw_archive_save(
        edition="kita", doc_type="attendance_list",
        target_id="all", content_bytes=pdf_bytes,
        file_name=f"attendance_{target_date.isoformat()}.pdf",
        snapshot_for=target_date,
        metadata={"sections": len(snapshot["sections"]),
                  "total_kids": sum(s["counts"]["kids_total"] for s in snapshot["sections"]),
                  "total_staff": sum(s["counts"]["staff_total"] for s in snapshot["sections"])},
        retention_years=7,
        legal_basis="KBBG · 7 Jahre Aufbewahrungspflicht",
    )
    return result


def _aw_render_attendance_pdf(snapshot: dict) -> bytes:
    """Rendert Anwesenheitsliste als simples PDF (reportlab)."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        # Fallback: nur Text als PDF-ähnlicher Bytes-Stream
        return f"SHIKSHA · KITA Anwesenheitsliste {snapshot['date']}\n(reportlab nicht installiert)".encode()

    from io import BytesIO
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm,
                             leftMargin=1*cm, rightMargin=1*cm)
    styles = getSampleStyleSheet()
    story = []
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#ff4d8d"))
    story.append(Paragraph(f"SHIKSHA · KITA Anwesenheitsliste · {snapshot['date']}", title))
    story.append(Spacer(1, 0.3*cm))

    for section in snapshot["sections"]:
        section_title = ParagraphStyle("sec", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#2d7a5f"))
        story.append(Paragraph(f"{section['group_name']} · {section['counts']['kids_present']}/{section['counts']['kids_total']} Kinder · {section['counts']['staff_present']}/{section['counts']['staff_total']} Mitarbeiter", section_title))

        # Mitarbeiter
        if section["staff"]:
            staff_data = [["Mitarbeiter", "Rolle", "Bereiche", "Status"]]
            for s in section["staff"]:
                areas = ", ".join(sl["area"] for sl in s["slices"]) or "—"
                statuses = ", ".join(set(sl["status"] for sl in s["slices"])) or "—"
                staff_data.append([s["name"], s["role"], areas, statuses])
            t = Table(staff_data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2d7a5f")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e6e4de")),
                ("PADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2*cm))

        # Kinder
        if section["children"]:
            kids_data = [["Kind", "Geb.-Jahr", "Bereiche", "Status"]]
            for c in section["children"]:
                areas = ", ".join(sl["area"] for sl in c["slices"]) or "—"
                statuses = ", ".join(set(sl["status"] for sl in c["slices"])) or "—"
                kids_data.append([c["name"], str(c["birth_year"] or "—"), areas, statuses])
            t = Table(kids_data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ffd93d")),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e6e4de")),
                ("PADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.5*cm))

    # Footer mit Hash-Hinweis
    story.append(Spacer(1, 1*cm))
    footer = ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#9a8e9e"))
    story.append(Paragraph(f"Generiert: {_aw_dt.now().isoformat()} · Manipulationsschutz: SHA-256 · SHIKSHA · DSGVO-konform · EU-Hosting", footer))

    doc.build(story)
    return buf.getvalue()


@kita_router.get("/archive/documents")
async def archive_list(edition: str = None, doc_type: str = None, limit: int = 100):
    sql = "SELECT id, edition, doc_type, target_id, file_name, file_size, file_hash, generated_at, retention_until, snapshot_for FROM shiksha_archive_documents WHERE 1=1"
    params = {"lim": limit}
    if edition:
        sql += " AND edition = :ed"; params["ed"] = edition
    if doc_type:
        sql += " AND doc_type = :dt"; params["dt"] = doc_type
    sql += " ORDER BY generated_at DESC LIMIT :lim"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "documents": [
            {
                "id": r[0], "edition": r[1], "doc_type": r[2], "target_id": r[3],
                "file_name": r[4], "file_size": r[5], "file_hash_short": r[6][:16] if r[6] else None,
                "generated_at": r[7].isoformat() if r[7] else None,
                "retention_until": r[8].isoformat() if r[8] else None,
                "snapshot_for": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ],
    }


@kita_router.get("/archive/documents/{doc_id}/file")
async def archive_doc_file(doc_id: str):
    with engine.connect() as conn:
        r = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime, file_hash FROM shiksha_archive_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not r:
            raise HTTPException(404, "Archiv-Dokument nicht gefunden")
        # Audit-Log
        conn.execute(sa.text("""
            INSERT INTO shiksha_archive_audit (id, archive_doc_id, action)
            VALUES (:id, :did, 'download')
        """), {"id": _new_id("audit"), "did": doc_id})
    fp = _aw_Path(r[0])
    if not fp.exists():
        raise HTTPException(404, "Datei auf Disk nicht gefunden")
    # Hash-Verifikation
    actual_hash = _aw_hash.sha256(fp.read_bytes()).hexdigest()
    if actual_hash != r[3]:
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO shiksha_archive_audit (id, archive_doc_id, action, action_status)
                VALUES (:id, :did, 'hash_mismatch', 'tamper_detected')
            """), {"id": _new_id("audit"), "did": doc_id})
        raise HTTPException(500, "⚠ Tamper-Detection: Datei-Hash stimmt nicht mit DB überein!")
    return _aw_FileResponse(path=fp, media_type=r[2] or "application/pdf", filename=r[1])

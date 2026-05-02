"""
SHIKSHA · world Router — shiksha.world Plattform-Site + community Edition-Vorschläge

In Phase 4 aus kita_compliance_router.py extrahiert (Zeilen 5181-5389), um
den /m/shiksha-Routing-Konflikt aufzulösen: der dortige /m/{slug}-Catch-all
hat /m/shiksha geschluckt, weil er zuerst registriert wurde.

Wird in main.py inkludiert mit:
  from world_router import world_router
  app.include_router(world_router)   # MUSS vor kita_router stehen

Wichtig — Reihenfolge:
  app.include_router(world_router)   # 1. spezifische Routes
  app.include_router(kita_router)    # 2. enthält /m/{slug}-Catch-all

Endpoints (alle unter /kita-Prefix wegen nginx-Rewrite /m/ → /kita/m/):

  GET  /m/shiksha                          Plattform-Site (platform_meta.html)
  GET  /api/platform/editions              alle Editionen
  GET  /api/platform/proposals             community Vorschläge (Top by upvotes)
  POST /api/platform/proposals             neuen Vorschlag einreichen
  POST /api/platform/proposals/{id}/upvote upvote
  GET  /api/platform/modules               Modul-Showcase
  GET  /api/platform/live-stats            anonymisierte Live-Daten
  GET  /api/platform/greeting              Tageszeit-Anrede für Hero

Bekannte Schulden: docs/security-todos.md (hardcoded DB-Credentials in
calendar_module.py — verwandter, separater Sprint).
"""
import datetime
import pathlib
from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from database import engine


world_router = APIRouter(prefix="/kita", tags=["world", "platform"])


# ============================================================
# HELPERS
# ============================================================

def _season(today=None):
    today = today or date.today()
    m = today.month
    if m in (3, 4, 5):    return "spring"
    if m in (6, 7, 8):    return "summer"
    if m in (9, 10, 11):  return "autumn"
    return "winter"


# ============================================================
# /m/shiksha — Plattform-Site (specific match, must be registered
#              BEFORE kita_router's /m/{slug} catch-all)
# ============================================================

@world_router.get("/m/shiksha", response_class=HTMLResponse)
async def platform_site():
    """Die Plattform-Site selbst — vollständig durch das Template gerendert."""
    tmpl_path = pathlib.Path("/opt/shiksha/marketing_templates/platform_meta.html")
    if not tmpl_path.exists():
        return HTMLResponse(content="<h1>Plattform-Template fehlt</h1>", status_code=500)
    return HTMLResponse(content=tmpl_path.read_text(encoding="utf-8"))


# ============================================================
# /api/platform/* — Editions-Galerie + Community-Vorschläge
# ============================================================

@world_router.get("/api/platform/editions")
async def platform_editions():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT slug, name, headline, tagline, description,
                   icon, accent_color, status, page_url, position,
                   deployed_at, pilot_count
            FROM editions
            ORDER BY position, slug
        """)).mappings().fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("deployed_at"): d["deployed_at"] = d["deployed_at"].isoformat()
        out.append(d)
    return {"editions": out, "count": len(out)}


@world_router.get("/api/platform/proposals")
async def platform_proposals(limit: int = 20):
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, edition_name, description, use_case,
                   proposer_name, upvotes, status, created_at
            FROM edition_proposals
            WHERE status != 'declined'
            ORDER BY upvotes DESC, created_at DESC
            LIMIT :l
        """), {"l": limit}).mappings().fetchall()
    return {"proposals": [
        {**dict(r), "created_at": r["created_at"].isoformat() if r.get("created_at") else None}
        for r in rows
    ]}


@world_router.post("/api/platform/proposals")
async def platform_proposal_create(payload: dict = Body(...)):
    name = (payload.get("edition_name") or "").strip()
    if not name:
        raise HTTPException(400, "edition_name Pflicht")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO edition_proposals
              (edition_name, description, use_case, proposer_email, proposer_name)
            VALUES (:n, :d, :u, :em, :pn)
            RETURNING id
        """), {
            "n": name,
            "d": payload.get("description"),
            "u": payload.get("use_case"),
            "em": payload.get("proposer_email"),
            "pn": payload.get("proposer_name"),
        })
        new_id = result.scalar()
    return {"id": new_id, "ok": True, "message": "Danke! Wir melden uns, wenn wir's ernst nehmen."}


@world_router.post("/api/platform/proposals/{pid}/upvote")
async def platform_proposal_upvote(pid: int):
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE edition_proposals SET upvotes = upvotes + 1
            WHERE id = :id RETURNING upvotes
        """), {"id": pid})
        row = result.first()
    if not row:
        raise HTTPException(404)
    return {"id": pid, "upvotes": row[0]}


# ============================================================
# /api/platform/modules + /live-stats + /greeting
# ============================================================

@world_router.get("/api/platform/modules")
async def platform_modules():
    """Alle sichtbaren Module für die Plattform-Site."""
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT slug, edition, headline, subline, description,
                   icon, accent_color, status, deployed_at, visual_kind
            FROM shiksha_modules
            WHERE status IN ('live', 'beta', 'planned')
            ORDER BY position, slug
        """)).mappings().fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("deployed_at"):
            d["deployed_at"] = d["deployed_at"].isoformat()
        out.append(d)
    return {"modules": out, "count": len(out)}


@world_router.get("/api/platform/live-stats")
async def platform_live_stats():
    """Anonymisierte Live-Daten von allen Pilot-Kunden zusammen."""
    today = date.today()
    stats = {
        "active_organisations": 0,
        "kids_present_today": 0,
        "events_this_week": 0,
        "messages_sent_week": 0,
        "modules_live": 0,
    }
    try:
        with engine.connect() as conn:
            # Live-Anwesenheit (KITA)
            try:
                stats["kids_present_today"] = int(conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                    WHERE work_date = :d AND status = 'present' AND person_type = 'child'
                """), {"d": today}).scalar() or 0)
            except Exception: pass
            # Events
            try:
                stats["events_this_week"] = int(conn.execute(sa.text("""
                    SELECT COUNT(*) FROM kita_calendar_events
                    WHERE start_date BETWEEN :a AND :b
                """), {"a": today - datetime.timedelta(days=today.weekday()),
                       "b": today + datetime.timedelta(days=6 - today.weekday())}).scalar() or 0)
            except Exception: pass
            # Module live
            stats["modules_live"] = int(conn.execute(sa.text("""
                SELECT COUNT(*) FROM shiksha_modules WHERE status = 'live'
            """)).scalar() or 0)
            # Aktive Marketing-Sites = aktive Organisationen
            try:
                stats["active_organisations"] = int(conn.execute(sa.text("""
                    SELECT COUNT(*) FROM marketing_sites WHERE status = 'live'
                """)).scalar() or 0)
            except Exception: pass
    except Exception as e:
        stats["error"] = str(e)
    stats["timestamp"] = datetime.datetime.now().isoformat()
    return stats


@world_router.get("/api/platform/greeting")
async def platform_greeting():
    """Lebendige Hero-Begrüßung für shiksha.world — datenschutz-freundlich."""
    now = datetime.datetime.now()
    h = now.hour
    if 5 <= h < 11:    line1 = "Guten Morgen"
    elif 11 <= h < 14: line1 = "Schönen Mittag"
    elif 14 <= h < 18: line1 = "Hallo am Nachmittag"
    elif 18 <= h < 22: line1 = "Guten Abend"
    else:              line1 = "Eine ruhige Nacht"

    weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][now.weekday()]
    season = _season()
    season_de = {"spring": "Frühling", "summer": "Sommer", "autumn": "Herbst", "winter": "Winter"}[season]

    return {
        "line1": line1,
        "weekday": weekday,
        "season": season,
        "season_de": season_de,
        "time": now.isoformat(),
    }

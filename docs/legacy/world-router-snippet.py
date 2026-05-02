"""
SHIKSHA · world v2 Plattform-Router — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle für die Plattform-Site-Endpoints (shiksha.world),
am 2.05.2026 via world_v2_deploy.sh an /opt/shiksha/kita_compliance_router.py
ANGEHÄNGT — nicht als separater Router deployed.

Der deployed-Stand lebt heute in:

    server/kita_compliance_router.py  ab Zeile ~5186

mit GET /api/platform/editions, GET/POST /api/platform/proposals,
POST /api/platform/proposals/{id}/upvote.

Diese Datei dient als Ausgangspunkt für Phase 4 — den /m/shiksha-Routing-
Konflikt. Lösung dort: world-Endpoints aus kita_compliance_router.py
herauslösen in einen eigenständigen Router (server/world_router.py),
vor dem Marketing-Catch-all /m/{slug} registriert. Wenn das passiert,
wandert dieser Snippet zurück nach server/.

Original-Quelle: cowork/outputs/world_v2/world_v2_router.py
Original-Datum: 2026-05-02 08:52
Importiert ins Repo: 2026-05-02

Cowork hatte zusätzlich shiksha_world/ (v1) — wird nicht migriert,
v2 ersetzt v1.

— Original-Inhalt unverändert ab hier —
"""

"""
SHIKSHA · world v2 — Editionen + Vorschläge

Endpoints:
  GET  /api/platform/editions          — alle Editionen
  GET  /api/platform/proposals         — Top-Vorschläge (community)
  POST /api/platform/proposals         — neue Edition vorschlagen
  POST /api/platform/proposals/{id}/upvote

Anhängen an /opt/shiksha/kita_compliance_router.py.
"""

@kita_router.get("/api/platform/editions")
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


@kita_router.get("/api/platform/proposals")
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


@kita_router.post("/api/platform/proposals")
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


@kita_router.post("/api/platform/proposals/{pid}/upvote")
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

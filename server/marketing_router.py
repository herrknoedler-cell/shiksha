"""
SHIKSHA · Marketing-Sites Router
Phase 1 — KITA-Pilot Krummelus.

Endpoints:
  Builder/Admin:
    POST   /admin/marketing/sites             — neue Site anlegen
    GET    /admin/marketing/sites/{slug}      — Site laden
    PUT    /admin/marketing/sites/{slug}      — bearbeiten
    POST   /admin/marketing/sites/{slug}/generate  — Claude-AI-Content
    POST   /admin/marketing/sites/{slug}/publish   — live schalten
    POST   /admin/marketing/sites/{slug}/upload    — Asset hochladen
    GET    /admin/marketing/pool/images?edition=kita&season=spring — Pool-Bilder

  Public:
    GET    /m/{slug}                          — Marketing-Site rendern
    GET    /m/asset/{asset_id}                — Asset ausliefern
    POST   /m/{slug}/anmeldung                — Anmelde-Formular submitten

Voraussetzungen (im venv):
  pip install anthropic httpx jinja2

Env (in /opt/shiksha/.env):
  ANTHROPIC_API_KEY=sk-ant-...
  MARKETING_ASSETS_DIR=/opt/shiksha/marketing_assets
  MARKETING_TEMPLATES_DIR=/opt/shiksha/marketing_templates

Anhängen an /opt/shiksha/kita_compliance_router.py.
"""

import os as _mk_os
import json as _mk_json
import hashlib as _mk_hash
import pathlib as _mk_path
import shutil as _mk_shutil
import datetime as _mk_dt
from datetime import date as _mk_date

import httpx as _mk_httpx
from fastapi import UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from jinja2 import Environment as _mk_jinja_env, FileSystemLoader as _mk_fs_loader, select_autoescape

ANTHROPIC_API_KEY = _mk_os.environ.get("ANTHROPIC_API_KEY", "")
ASSETS_DIR = _mk_path.Path(_mk_os.environ.get("MARKETING_ASSETS_DIR", "/opt/shiksha/marketing_assets"))
TEMPLATES_DIR = _mk_path.Path(_mk_os.environ.get("MARKETING_TEMPLATES_DIR", "/opt/shiksha/marketing_templates"))

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

_mk_jinja = _mk_jinja_env(
    loader=_mk_fs_loader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ============================================================
# JAHRESZEITEN-LOGIK
# ============================================================

def _mk_season(today=None):
    today = today or _mk_date.today()
    m = today.month
    if m in (3, 4, 5):    return "spring"
    if m in (6, 7, 8):    return "summer"
    if m in (9, 10, 11):  return "autumn"
    return "winter"


# ============================================================
# GEOCODING + POIs (OpenStreetMap, gratis)
# ============================================================

async def _mk_geocode(address):
    """Adresse → (lat, lng, country, region)."""
    if not address:
        return None
    async with _mk_httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "addressdetails": 1, "limit": 1},
                headers={"User-Agent": "SHIKSHA-Marketing-Builder/1.0"},
            )
            arr = r.json()
            if not arr:
                return None
            x = arr[0]
            ad = x.get("address", {})
            return {
                "lat": float(x["lat"]), "lng": float(x["lon"]),
                "country": ad.get("country", ""),
                "country_code": ad.get("country_code", "").upper(),
                "region": ad.get("state") or ad.get("region") or "",
                "city": ad.get("city") or ad.get("town") or ad.get("village") or "",
                "display": x.get("display_name", ""),
            }
        except Exception as e:
            print(f"[mk_geocode] {e}")
            return None


async def _mk_nearby_pois(lat, lng, radius_m=3000):
    """OpenStreetMap Overpass-API: Bahnhof, Flughafen, Sehenswürdigkeiten."""
    if not lat or not lng:
        return {}
    query = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lng})["railway"="station"];
      node(around:{radius_m * 5},{lat},{lng})["aeroway"="aerodrome"];
      node(around:{radius_m},{lat},{lng})["tourism"~"attraction|museum|viewpoint"];
      node(around:{radius_m},{lat},{lng})["shop"="supermarket"];
    );
    out body 20;
    """
    async with _mk_httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            elements = r.json().get("elements", [])
        except Exception as e:
            print(f"[mk_nearby_pois] {e}")
            return {}
    out = {"trains": [], "airports": [], "attractions": [], "supermarkets": []}
    for e in elements:
        t = e.get("tags", {})
        name = t.get("name") or t.get("name:de")
        if not name: continue
        if t.get("railway") == "station":
            out["trains"].append(name)
        elif t.get("aeroway") == "aerodrome":
            out["airports"].append(name)
        elif t.get("tourism"):
            out["attractions"].append(name)
        elif t.get("shop") == "supermarket":
            out["supermarkets"].append(name)
    # Deduplicate
    for k in out: out[k] = list(dict.fromkeys(out[k]))[:5]
    return out


# ============================================================
# CLAUDE-AI CONTENT-GENERATION
# ============================================================

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"   # aktuelles Standardmodell


async def _mk_claude_call(system_prompt, user_prompt, max_tokens=2000):
    """Direkt-Call zur Claude API (ohne SDK-Abhängigkeit)."""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY nicht gesetzt"}

    async with _mk_httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        if r.status_code != 200:
            return {"error": f"Claude API {r.status_code}: {r.text[:300]}"}
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return {"text": text, "usage": data.get("usage", {})}


def _mk_cache_key(*parts):
    raw = "|".join(str(p) for p in parts)
    return _mk_hash.sha256(raw.encode()).hexdigest()[:32]


async def _mk_generate_kita_content(site_data, geo, pois):
    """KITA-Content über Claude generieren. Cached."""
    cache_key = _mk_cache_key("kita-v1", site_data.get("business_name"),
                              site_data.get("address_line"), site_data.get("city"))
    with engine.connect() as conn:
        cached = conn.execute(sa.text("SELECT response FROM marketing_llm_cache WHERE cache_key = :k"),
                              {"k": cache_key}).first()
    if cached:
        return cached[0]

    system = """Du bist die Stimme von SHIKSHA, einer Plattform für KITAs im DACH-Raum.
Schreibe warm, persönlich, präzise — wie ein erfahrener Kollege, nicht wie eine Werbeagentur.
Sprache: Deutsch, du-Form bei Eltern-Anrede, Sie-Form bei formellen Sektionen.
Vermeide Floskeln wie 'liebevoll', 'ganzheitlich', 'individuell'. Sei konkret.
Antworte ausschließlich als JSON-Objekt mit den genau angeforderten Feldern."""

    user = f"""Generiere die Texte für die Marketing-Webseite einer KITA mit diesen Daten:

Name: {site_data.get('business_name')}
Adresse: {site_data.get('address_line')}, {site_data.get('postal_code')} {site_data.get('city')}
Region: {geo.get('region') if geo else 'unbekannt'}
Land: {geo.get('country') if geo else 'unbekannt'}
Nahegelegene Bahnhöfe: {', '.join((pois or {}).get('trains', [])) or 'nichts gefunden'}
Nahegelegene Flughäfen: {', '.join((pois or {}).get('airports', [])) or 'nichts gefunden'}
Nahegelegene Sehenswürdigkeiten: {', '.join((pois or {}).get('attractions', [])) or 'nichts gefunden'}

Liefere folgende Felder zurück (JSON):
- "tagline": eine prägnante Zeile (max 50 Zeichen), z.B. "Eine KITA, die mitwächst."
- "description": 2-3 Sätze als Hero-Untertitel
- "about_text": 3 Absätze über die KITA, ihre Werte, ihre Atmosphäre. Erzählend, nicht aufzählend.
- "concept_text": 2-3 Absätze zum pädagogischen Ansatz. Konkret und greifbar, keine Buzzwords.
- "arrival_text": 1 Absatz Anfahrt mit den realen Bahnhof/Flughafen-Daten oben — wie man am besten herfindet."""

    res = await _mk_claude_call(system, user, max_tokens=2500)
    if res.get("error"):
        return {"error": res["error"]}

    # JSON aus Antwort extrahieren
    text = res["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = _mk_json.loads(text)
    except Exception:
        return {"error": "Claude-Antwort war kein gültiges JSON", "raw": text[:500]}

    # Cache schreiben
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO marketing_llm_cache (cache_key, response, model, tokens_used)
            VALUES (:k, CAST(:r AS jsonb), :m, :t)
            ON CONFLICT (cache_key) DO NOTHING
        """), {
            "k": cache_key, "r": _mk_json.dumps(parsed),
            "m": CLAUDE_MODEL,
            "t": (res.get("usage") or {}).get("input_tokens", 0) + (res.get("usage") or {}).get("output_tokens", 0),
        })
    return parsed


# ============================================================
# ADMIN-ENDPOINTS
# ============================================================

@kita_router.post("/admin/marketing/sites")
async def mk_site_create(payload: dict = Body(...)):
    slug = (payload.get("slug") or "").strip().lower()
    name = (payload.get("business_name") or "").strip()
    if not slug or not name:
        raise HTTPException(400, "slug und business_name Pflicht")
    edition = payload.get("edition", "kita")
    with engine.begin() as conn:
        try:
            result = conn.execute(sa.text("""
                INSERT INTO marketing_sites
                  (slug, edition, business_name, address_line, postal_code, city, country,
                   contact_email, phone, status)
                VALUES (:s, :e, :n, :a, :pc, :c, :co, :em, :ph, 'draft')
                RETURNING id
            """), {
                "s": slug, "e": edition, "n": name,
                "a": payload.get("address_line"), "pc": payload.get("postal_code"),
                "c": payload.get("city"), "co": payload.get("country", "AT"),
                "em": payload.get("contact_email"), "ph": payload.get("phone"),
            })
            new_id = result.scalar()
        except Exception as e:
            raise HTTPException(400, f"Slug existiert? {e}")
    return {"id": new_id, "slug": slug, "edition": edition}


@kita_router.get("/admin/marketing/sites/{slug}")
async def mk_site_get(slug: str):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                           {"s": slug}).mappings().first()
    if not row:
        raise HTTPException(404, "Site nicht gefunden")
    out = dict(row)
    for k in ("created_at", "updated_at", "last_published_at"):
        if out.get(k): out[k] = out[k].isoformat()
    if out.get("trial_until"): out["trial_until"] = out["trial_until"].isoformat()
    return out


@kita_router.put("/admin/marketing/sites/{slug}")
async def mk_site_update(slug: str, payload: dict = Body(...)):
    allowed = ("business_name", "tagline", "description", "address_line", "postal_code",
               "city", "country", "lat", "lng", "contact_email", "phone", "website_external",
               "opening_hours", "about_text", "concept_text", "arrival_text", "excursions_text",
               "accent_color", "season_override",
               "logo_asset_id", "hero_asset_id", "gallery_asset_ids")
    fields = {k: payload[k] for k in allowed if k in payload}
    if not fields:
        raise HTTPException(400, "keine Felder")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    fields["s"] = slug
    sql = f"UPDATE marketing_sites SET {', '.join(set_parts)} WHERE slug = :s"
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Site nicht gefunden")
    return {"slug": slug, "updated": list(fields.keys())}


@kita_router.post("/admin/marketing/sites/{slug}/generate")
async def mk_site_generate(slug: str):
    """Claude-AI generiert Texte aus Standort-Daten."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        raise HTTPException(404, "Site nicht gefunden")
    site_d = dict(site)

    # Geocoding
    full_address = ", ".join(filter(None, [
        site_d.get("address_line"), site_d.get("postal_code"),
        site_d.get("city"), site_d.get("country")
    ]))
    geo = await _mk_geocode(full_address)
    pois = await _mk_nearby_pois(geo["lat"], geo["lng"]) if geo else {}

    # Claude
    if site_d["edition"] == "kita":
        result = await _mk_generate_kita_content(site_d, geo, pois)
    else:
        result = {"error": f"Edition '{site_d['edition']}' noch nicht unterstützt"}

    if result.get("error"):
        return {"ok": False, "error": result["error"]}

    # Update Site
    with engine.begin() as conn:
        conn.execute(sa.text("""
            UPDATE marketing_sites SET
              tagline = :tl, description = :d, about_text = :a,
              concept_text = :c, arrival_text = :ar,
              lat = :lat, lng = :lng,
              extra = CAST(:x AS jsonb),
              updated_at = NOW()
            WHERE slug = :s
        """), {
            "s": slug,
            "tl": result.get("tagline"), "d": result.get("description"),
            "a": result.get("about_text"), "c": result.get("concept_text"),
            "ar": result.get("arrival_text"),
            "lat": geo["lat"] if geo else None,
            "lng": geo["lng"] if geo else None,
            "x": _mk_json.dumps({"geo": geo, "pois": pois}),
        })
    return {"ok": True, "generated": result, "geo": geo, "pois": pois}


@kita_router.post("/admin/marketing/sites/{slug}/publish")
async def mk_site_publish(slug: str):
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE marketing_sites
              SET status = 'live', last_published_at = NOW()
            WHERE slug = :s
            RETURNING id, status
        """), {"s": slug})
        if result.rowcount == 0:
            raise HTTPException(404, "Site nicht gefunden")
    return {"slug": slug, "status": "live"}


@kita_router.post("/admin/marketing/sites/{slug}/upload")
async def mk_site_upload(slug: str, role: str = Form(...), file: UploadFile = File(...)):
    """Lädt ein Asset hoch und verknüpft es mit der Site (role: logo|hero|gallery)."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT id FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).first()
    if not site:
        raise HTTPException(404, "Site nicht gefunden")
    site_id = site[0]

    site_dir = ASSETS_DIR / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace("/", "_").replace("..", "_")
    timestamp = _mk_dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    final_path = site_dir / f"{role}-{timestamp}-{safe_name}"
    with final_path.open("wb") as f:
        _mk_shutil.copyfileobj(file.file, f)

    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            INSERT INTO marketing_assets (site_id, file_path, mime_type, source)
            VALUES (:sid, :fp, :mt, 'upload')
            RETURNING id
        """), {"sid": site_id, "fp": str(final_path), "mt": file.content_type})
        asset_id = result.scalar()

        if role == "logo":
            conn.execute(sa.text("UPDATE marketing_sites SET logo_asset_id = :a WHERE id = :s"),
                         {"a": asset_id, "s": site_id})
        elif role == "hero":
            conn.execute(sa.text("UPDATE marketing_sites SET hero_asset_id = :a WHERE id = :s"),
                         {"a": asset_id, "s": site_id})
        elif role == "gallery":
            conn.execute(sa.text("""
                UPDATE marketing_sites
                  SET gallery_asset_ids = array_append(gallery_asset_ids, :a)
                WHERE id = :s
            """), {"a": asset_id, "s": site_id})
    return {"asset_id": asset_id, "role": role, "url": f"/m/asset/{asset_id}"}


@kita_router.get("/admin/marketing/pool/images")
async def mk_pool_images(edition: str = "kita", season: str = None):
    season = season or _mk_season()
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT id, file_path, alt_text, pool_tags FROM marketing_assets
            WHERE site_id IS NULL
              AND pool_edition = :e
              AND (pool_season = :ss OR pool_season = 'all')
            ORDER BY id
        """), {"e": edition, "ss": season}).mappings().fetchall()
    return {"season": season, "images": [
        {"id": r["id"], "url": f"/m/asset/{r['id']}", "alt": r["alt_text"], "tags": r.get("pool_tags") or []}
        for r in rows
    ]}


# ============================================================
# PUBLIC-ENDPOINTS
# ============================================================

@kita_router.get("/m/asset/{asset_id}")
async def mk_asset(asset_id: int):
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT file_path, mime_type FROM marketing_assets WHERE id = :i"),
                           {"i": asset_id}).first()
    if not row:
        raise HTTPException(404)
    fp = row[0]
    if not _mk_path.Path(fp).exists():
        raise HTTPException(404, "Datei nicht da")
    return FileResponse(fp, media_type=row[1] or "application/octet-stream")


@kita_router.get("/m/{slug}", response_class=HTMLResponse)
async def mk_public_site(slug: str):
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT * FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        return HTMLResponse(content="<h1>Diese Seite gibt es noch nicht.</h1>", status_code=404)

    site_d = dict(site)
    season = site_d.get("season_override") or _mk_season()
    edition = site_d.get("edition", "kita")

    # Live-Daten holen
    today = _mk_date.today()
    live = {}
    try:
        with engine.connect() as conn:
            kids_total = conn.execute(sa.text("SELECT COUNT(*) FROM kita_legacy_children WHERE active = true")).scalar() or 0
            try:
                kids_present = conn.execute(sa.text("""
                    SELECT COUNT(DISTINCT legacy_child_id) FROM kita_daily_assignments
                    WHERE work_date = :d AND status = 'present' AND person_type = 'child'
                """), {"d": today}).scalar() or 0
            except Exception:
                kids_present = 0
            # Wochen-Theme
            monday = today - _mk_dt.timedelta(days=today.weekday())
            wt = conn.execute(sa.text("SELECT theme FROM weekly_themes WHERE week_start = :w"),
                              {"w": monday}).first()
            # Bevorstehende Eltern-sichtbare Termine
            events = conn.execute(sa.text("""
                SELECT title, event_type, start_date, color FROM kita_calendar_events
                WHERE start_date BETWEEN :a AND :b AND visible_eltern = true
                ORDER BY start_date LIMIT 5
            """), {"a": today, "b": today + _mk_dt.timedelta(days=30)}).mappings().fetchall()
        live = {
            "kids_present": kids_present,
            "kids_total": kids_total,
            "weekly_theme": wt[0] if wt else None,
            "events": [dict(e, start_date=e["start_date"].isoformat()) for e in events],
        }
    except Exception:
        live = {}

    # Wissens-Snippet (Eltern-Audience)
    try:
        bites = _grt_json.loads(_mk_path.Path("/opt/shiksha/data/knowledge_bites.json").read_text())
        eltern_bites = [b for b in bites if "eltern" in b.get("audience", []) or not b.get("audience")]
        import random as _mk_rand
        seed = today.toordinal()
        knowledge = _mk_rand.Random(seed).choice(eltern_bites) if eltern_bites else None
    except Exception:
        knowledge = None

    # Greeting
    hour = _mk_dt.datetime.now().hour
    greeting = ("Guten Morgen" if hour < 11 else
                "Schönen Mittag" if hour < 14 else
                "Hallo" if hour < 18 else "Guten Abend")

    # Gallery-Bilder
    gallery = []
    if site_d.get("gallery_asset_ids"):
        with engine.connect() as conn:
            for gid in site_d["gallery_asset_ids"]:
                row = conn.execute(sa.text("SELECT id, alt_text FROM marketing_assets WHERE id = :i"),
                                   {"i": gid}).first()
                if row:
                    gallery.append({"id": row[0], "url": f"/m/asset/{row[0]}", "alt": row[1] or ""})

    # Logo / Hero URLs
    logo_url = f"/m/asset/{site_d['logo_asset_id']}" if site_d.get("logo_asset_id") else None
    hero_url = f"/m/asset/{site_d['hero_asset_id']}" if site_d.get("hero_asset_id") else None

    # Template rendern
    try:
        tmpl_name = f"{edition}_{season}.html"
        tmpl = _mk_jinja.get_template(tmpl_name)
    except Exception:
        try:
            tmpl = _mk_jinja.get_template(f"{edition}_spring.html")  # fallback auf spring
        except Exception:
            return HTMLResponse(content=f"<h1>Template fehlt: {edition}_{season}.html</h1>", status_code=500)

    html = tmpl.render(
        site=site_d, live=live, knowledge=knowledge,
        greeting=greeting, gallery=gallery,
        logo_url=logo_url, hero_url=hero_url,
        season=season, today=today.isoformat(),
    )
    return HTMLResponse(content=html)


@kita_router.post("/m/{slug}/anmeldung")
async def mk_public_anmeldung(slug: str, payload: dict = Body(...)):
    """Anmelde-Formular submitted — speichert in der existierenden Eltern-Anmeldungs-Tabelle."""
    with engine.connect() as conn:
        site = conn.execute(sa.text("SELECT id, edition, business_name, contact_email FROM marketing_sites WHERE slug = :s"),
                            {"s": slug}).mappings().first()
    if not site:
        raise HTTPException(404)
    # Schreibt in eine "soft-Anmeldung"-Tabelle, die wir (sofern existent) nutzen.
    # Für MVP: einfach in marketing_sites.extra anhängen
    entry = {
        "received_at": _mk_dt.datetime.now().isoformat(),
        "site_slug": slug,
        **{k: payload.get(k) for k in ("name", "email", "phone", "child_name", "child_birth", "message")},
    }
    with engine.begin() as conn:
        conn.execute(sa.text("""
            UPDATE marketing_sites
              SET extra = jsonb_set(extra,
                    '{anmeldungen}',
                    COALESCE(extra->'anmeldungen', '[]'::jsonb) || CAST(:e AS jsonb))
            WHERE slug = :s
        """), {"e": _mk_json.dumps(entry), "s": slug})
    return {"ok": True, "message": "Wir haben Ihre Nachricht erhalten und melden uns bald."}

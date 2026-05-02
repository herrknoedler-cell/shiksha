"""
SHIKSHA · Fixtures Importer V1
Stand: 25.04.2026

Lädt SCHULE- und CAMPING-Fixtures (JSON) idempotent in die SHIKSHA-DB.

Aufruf auf dem Server (nach DB-Migrationen):
    cd /opt/shiksha
    source venv/bin/activate
    python3 fixtures_importer.py --schule fixtures/yogaschule_wien.json
    python3 fixtures_importer.py --schule fixtures/surfschule_sylt.json
    python3 fixtures_importer.py --camping fixtures/camping_allweglehen_bayern.json
    python3 fixtures_importer.py --camping fixtures/camping_inntalblick_tirol.json

    # oder alle auf einmal
    python3 fixtures_importer.py --all-in /opt/shiksha/fixtures/

Verhalten:
- Idempotent: doppelter Import überschreibt bestehende Datensätze (UPSERT)
- Schreibt Pattern-Signale in {schule|camping}_signals (für Dashboard-Demo)
- Loggt jeden Schritt
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Json


# ---------------------------------------------------------------------------
# DB Connection
# ---------------------------------------------------------------------------

def get_db_connection():
    """Liest aus Standard SHIKSHA-Umgebungsvariablen oder Default."""
    return psycopg.connect(
        host=os.getenv("SHIKSHA_DB_HOST", "localhost"),
        dbname=os.getenv("SHIKSHA_DB_NAME", "shiksha"),
        user=os.getenv("SHIKSHA_DB_USER", "postgres"),
        password=os.getenv("SHIKSHA_DB_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def upsert(cur, table, pk, data: dict):
    """Generic UPSERT — pk ist der Spaltenname des Primary Key."""
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(cols)
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c != pk])

    sql = f"""
    INSERT INTO {table} ({cols_sql})
    VALUES ({placeholders})
    ON CONFLICT ({pk}) DO UPDATE SET {update_set};
    """
    values = [Json(v) if isinstance(v, (dict, list)) else v for v in data.values()]
    cur.execute(sql, values)


def log(msg, level="INFO"):
    print(f"[{level}] {datetime.now().strftime('%H:%M:%S')} — {msg}", flush=True)


# ---------------------------------------------------------------------------
# SCHULE.EDITION Importer
# ---------------------------------------------------------------------------

def import_schule(conn, fixture_path: Path):
    log(f"SCHULE Import: {fixture_path.name}")
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()
    school = data["school"]

    # 1. School
    upsert(cur, "schools", "id", {
        "id": school["id"],
        "name": school["name"],
        "edition": school.get("edition", "schule.shiksha"),
        "type": school.get("type"),
        "primary_address": school.get("primary_address"),
        "secondary_locations": school.get("secondary_locations", []),
        "contact": school.get("contact"),
        "uid_number": school.get("uid_number"),
        "reg_number": school.get("reg_number"),
        "tax_number": school.get("tax_number"),
        "bank_account": school.get("bank_account"),
        "business_hours": school.get("business_hours"),
        "weather_dependent": school.get("weather_dependent", False),
        "has_minors": school.get("has_minors", False),
        "insurance_info": school.get("insurance_info"),
        "rooms": school.get("rooms", []),
        "tags": school.get("tags", []),
    })
    log(f"  ✓ school: {school['id']}")

    # 2. Guardians
    for g in data.get("guardians", []):
        upsert(cur, "guardians", "id", {
            "id": g["id"],
            "full_name": g["full_name"],
            "contact": g.get("contact"),
            "related_students": g.get("related_students", []),
        })
    log(f"  ✓ guardians: {len(data.get('guardians', []))}")

    # 3. Students
    for s in data.get("students", []):
        upsert(cur, "students", "id", {
            "id": s["id"],
            "school_id": s["school_id"],
            "full_name": s["full_name"],
            "birthdate": s.get("birthdate"),
            "guardian_ids": s.get("guardian_ids", []),
            "contact": s.get("contact"),
            "language": s.get("language", "de"),
            "level": s.get("level", {}),
            "consent_records": s.get("consent_records", []),
            "medical_notes": s.get("medical_notes"),
            "wetsuit_size": s.get("wetsuit_size"),
            "first_visit": s.get("first_visit"),
        })
    log(f"  ✓ students: {len(data.get('students', []))}")

    # 4. Instructors
    for i in data.get("instructors", []):
        upsert(cur, "instructors", "id", {
            "id": i["id"],
            "school_id": i["school_id"],
            "full_name": i["full_name"],
            "role": i.get("role"),
            "contact": i.get("contact"),
            "languages": i.get("languages", ["de"]),
            "licenses": i.get("licenses", []),
            "background_check": i.get("background_check"),
            "specialties": i.get("specialties", []),
            "availability": i.get("availability"),
            "hourly_rate": i.get("hourly_rate"),
            "since": i.get("since"),
        })
    log(f"  ✓ instructors: {len(data.get('instructors', []))}")

    # 5. Package templates
    for p in data.get("package_templates", []):
        upsert(cur, "package_templates", "id", {
            "id": p["id"],
            "school_id": p["school_id"],
            "name": p["name"],
            "count": p["count"],
            "price": p["price"],
            "validity_days": p["validity_days"],
            "applicable_course_types": p.get("applicable_course_types", ["all"]),
        })
    log(f"  ✓ package_templates: {len(data.get('package_templates', []))}")

    # 6. Package instances
    for pi in data.get("package_instances", []):
        upsert(cur, "package_instances", "id", {
            "id": pi["id"],
            "template_id": pi["template_id"],
            "student_id": pi["student_id"],
            "remaining_count": pi["remaining_count"],
            "purchased_at": pi["purchased_at"],
            "expires_at": pi["expires_at"],
            "status": pi.get("status", "active"),
        })
    log(f"  ✓ package_instances: {len(data.get('package_instances', []))}")

    # 7. Courses
    for c in data.get("courses", []):
        upsert(cur, "courses", "id", {
            "id": c["id"],
            "school_id": c["school_id"],
            "name": c["name"],
            "type": c.get("type"),
            "level": c.get("level"),
            "capacity_min": c.get("capacity_min", 1),
            "capacity_max": c.get("capacity_max", 99),
            "price": c.get("price"),
            "duration_minutes": c.get("duration_minutes"),
            "weather_dependent": c.get("weather_dependent", False),
            "status": c.get("status", "planned"),
            "schedule_pattern": c.get("schedule_pattern"),
            "instructor_id": c.get("instructor_id"),
            "start_date": c.get("start_date"),
            "end_date": c.get("end_date"),
            "metadata": c.get("metadata", {}),
        })
    log(f"  ✓ courses: {len(data.get('courses', []))}")

    # 8. Course sessions (examples)
    for s in data.get("course_sessions_examples", []):
        upsert(cur, "course_sessions", "id", {
            "id": s["id"],
            "course_id": s["course_id"],
            "scheduled_at": s["scheduled_at"],
            "location": s.get("location"),
            "instructor_id": s.get("instructor_id"),
            "status": s.get("status", "scheduled"),
            "expected_attendees": s.get("expected_attendees", []),
        })
    log(f"  ✓ sessions: {len(data.get('course_sessions_examples', []))}")

    # 9. Enrollments (examples)
    for e in data.get("enrollments_active_examples", []):
        upsert(cur, "enrollments", "id", {
            "id": e["id"],
            "student_id": e["student_id"],
            "course_id": e["course_id"],
            "status": e.get("status", "inquiry"),
            "consent_status": e.get("consent_status"),
            "trial_class_session_id": e.get("trial_class_session_id"),
            "enrolled_at": e.get("enrolled_at"),
        })
    log(f"  ✓ enrollments: {len(data.get('enrollments_active_examples', []))}")

    # 10. Pattern Signals (für Dashboard-Demo)
    for sig in data.get("_pattern_signals_to_emit", []):
        cur.execute("""
            INSERT INTO schule_signals
                (school_id, signal_key, severity, params, status)
            VALUES (%s, %s, %s, %s, 'open')
            ON CONFLICT DO NOTHING
        """, (school["id"], sig["signal_key"], sig.get("severity", "info"), Json(sig.get("params", {}))))
    log(f"  ✓ signals geschrieben: {len(data.get('_pattern_signals_to_emit', []))}")

    conn.commit()
    log(f"  ✓ {fixture_path.name} importiert.")


# ---------------------------------------------------------------------------
# CAMPING.EDITION Importer
# ---------------------------------------------------------------------------

def import_camping(conn, fixture_path: Path):
    log(f"CAMPING Import: {fixture_path.name}")
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cur = conn.cursor()
    cs = data["campsite"]

    # 1. Campsite
    upsert(cur, "campsites", "id", {
        "id": cs["id"],
        "name": cs["name"],
        "edition": cs.get("edition", "camping.shiksha"),
        "type": cs.get("type"),
        "primary_address": cs.get("primary_address"),
        "contact": cs.get("contact"),
        "uid_number": cs.get("uid_number"),
        "tax_number": cs.get("tax_number"),
        "reg_number": cs.get("reg_number"),
        "bank_account": cs.get("bank_account"),
        "season": cs.get("season"),
        "capacities": cs.get("capacities"),
        "infrastructure": cs.get("infrastructure", []),
        "weather_dependent": cs.get("weather_dependent", True),
        "has_minors": cs.get("has_minors", False),
        "has_pool": cs.get("has_pool", False),
        "has_playground": cs.get("has_playground", False),
        "dog_friendly": cs.get("dog_friendly", False),
        "languages_supported": cs.get("languages_supported", ["de"]),
        "insurance_info": cs.get("insurance_info"),
        "behoerden_auflagen": cs.get("behoerden_auflagen", []),
        "tags": cs.get("tags", []),
    })
    log(f"  ✓ campsite: {cs['id']}")

    # 2. Pitches
    for p in data.get("pitches", []):
        upsert(cur, "pitches", "id", {
            "id": p["id"],
            "campsite_id": cs["id"],
            "label": p["label"],
            "category": p.get("category", "standard"),
            "size_m2": p.get("size_m2"),
            "electricity_amp": p.get("electricity_amp", 0),
            "water": p.get("water", False),
            "drain": p.get("drain", False),
            "shadow": p.get("shadow"),
            "dog_allowed": p.get("dog_allowed", False),
            "view": p.get("view"),
            "status": "available",
        })
    log(f"  ✓ pitches: {len(data.get('pitches', []))}")

    # 3. Accommodations
    for a in data.get("accommodations", []):
        upsert(cur, "accommodations", "id", {
            "id": a["id"],
            "campsite_id": cs["id"],
            "type": a.get("type", "mobile_home"),
            "name": a.get("name"),
            "size_m2": a.get("size_m2"),
            "beds": a.get("beds"),
            "amenities": a.get("amenities", []),
            "weekly_high": a.get("weekly_high"),
            "weekly_low": a.get("weekly_low"),
            "dog_allowed": a.get("dog_allowed", False),
        })
    log(f"  ✓ accommodations: {len(data.get('accommodations', []))}")

    # 4. Guardians
    for g in data.get("guardians_camping", []):
        upsert(cur, "guardians_camping", "id", {
            "id": g["id"],
            "full_name": g["full_name"],
            "contact": g.get("contact"),
            "related_minors": g.get("related_minors", []),
        })
    log(f"  ✓ guardians: {len(data.get('guardians_camping', []))}")

    # 5. Guests
    for guest in data.get("guests", []):
        upsert(cur, "guests", "id", {
            "id": guest["id"],
            "campsite_id": cs["id"],
            "full_name": guest["full_name"],
            "primary_adult": guest.get("primary_adult"),
            "address": guest.get("address"),
            "contact": guest.get("contact"),
            "language": guest.get("language", "de"),
            "vehicle_plate": guest.get("vehicle_plate"),
            "is_minor": guest.get("is_minor", False),
            "birthdate": guest.get("birthdate"),
            "guardian_ids": guest.get("guardian_ids", []),
            "first_visit": guest.get("first_visit"),
        })
    log(f"  ✓ guests: {len(data.get('guests', []))}")

    # 6. Reservations
    for r in data.get("reservations", []):
        upsert(cur, "reservations", "id", {
            "id": r["id"],
            "campsite_id": cs["id"],
            "guest_id": r["guest_id"],
            "pitch_id": r.get("pitch_id"),
            "accommodation_id": r.get("accommodation_id"),
            "from_date": r["from_date"],
            "to_date": r["to_date"],
            "persons": r.get("persons", 1),
            "minors_count": r.get("minors_count", 0),
            "status": r.get("status", "inquiry"),
            "deposit_paid": r.get("deposit_paid", False),
            "deposit_due": r.get("deposit_due"),
            "total_amount": r.get("total_amount"),
            "type": r.get("type", "standard"),
        })
    log(f"  ✓ reservations: {len(data.get('reservations', []))}")

    # 7. Stays
    for s in data.get("stays_active", []):
        upsert(cur, "stays", "id", {
            "id": s["id"],
            "campsite_id": cs["id"],
            "guest_id": s["guest_id"],
            "pitch_id": s.get("pitch_id"),
            "accommodation_id": s.get("accommodation_id"),
            "check_in": s["check_in"],
            "check_out": s.get("check_out"),
            "persons": s.get("persons", 1),
            "minors_count": s.get("minors_count", 0),
            "dog": s.get("dog"),
            "status": s.get("status", "running"),
        })
    log(f"  ✓ stays: {len(data.get('stays_active', []))}")

    # 8. Pattern Signals
    for sig in data.get("_pattern_signals_to_emit", []):
        cur.execute("""
            INSERT INTO camping_signals
                (campsite_id, signal_key, severity, polarity, params, status)
            VALUES (%s, %s, %s, %s, %s, 'open')
            ON CONFLICT DO NOTHING
        """, (cs["id"], sig["signal_key"], sig.get("severity", "info"), sig.get("polarity", "neutral"), Json(sig.get("params", {}))))
    log(f"  ✓ signals geschrieben: {len(data.get('_pattern_signals_to_emit', []))}")

    conn.commit()
    log(f"  ✓ {fixture_path.name} importiert.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SHIKSHA Fixtures Importer")
    parser.add_argument("--schule", help="Pfad zu einer SCHULE-Fixture-JSON")
    parser.add_argument("--camping", help="Pfad zu einer CAMPING-Fixture-JSON")
    parser.add_argument("--all-in", help="Verzeichnis mit allen Fixtures (importiert sie alle)")
    parser.add_argument("--dry-run", action="store_true", help="Keine DB-Schreibvorgänge, nur Parsing-Test")
    args = parser.parse_args()

    if not (args.schule or args.camping or args.all_in):
        parser.error("Mindestens eine der Optionen --schule, --camping oder --all-in nötig.")

    if args.dry_run:
        log("DRY-RUN — keine DB-Verbindung.")
        if args.schule:
            with open(args.schule) as f:
                data = json.load(f)
            log(f"  ✓ {args.schule}: {len(data.get('students', []))} Schüler, {len(data.get('courses', []))} Kurse")
        if args.camping:
            with open(args.camping) as f:
                data = json.load(f)
            log(f"  ✓ {args.camping}: {len(data.get('pitches', []))} Pitches, {len(data.get('guests', []))} Gäste")
        return 0

    try:
        conn = get_db_connection()
    except Exception as e:
        log(f"DB-Verbindung fehlgeschlagen: {e}", level="ERROR")
        log("Hinweis: Setze SHIKSHA_DB_HOST/NAME/USER/PASSWORD oder läuft das Script auf dem Server?", level="HINT")
        return 1

    try:
        if args.all_in:
            base = Path(args.all_in)
            for path in sorted(base.glob("**/*.json")):
                if "yogaschule" in path.name or "surfschule" in path.name:
                    import_schule(conn, path)
                elif "camping_" in path.name and path.name.endswith(".json"):
                    import_camping(conn, path)

        if args.schule:
            import_schule(conn, Path(args.schule))

        if args.camping:
            import_camping(conn, Path(args.camping))

        log("Alle Imports erfolgreich.")
        return 0
    except Exception as e:
        conn.rollback()
        log(f"Fehler: {e}", level="ERROR")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
import_calendar.py — Migriere kita_legacy_calendar nach events.

Idempotent: Wiederholte Läufe duplizieren nicht (UPSERT auf legacy_id+legacy_source).
Person-ID-Lookup: Legacy-Events referenzieren alte Kinder/Staff-IDs; wir mappen
auf neue persons.id via persons.legacy_id-Brücke.

Pattern aus import_persons.py + Drop-Bug-Lessons (T-002):
- `from shiksha_engine.db import SessionLocal` (nicht .database)
- Kein `id=uuid4()` — events.id ist autoincrement Integer
- first()-Helper für tolerante Spaltennamen
- Unbekannte Felder landen in metadata_.legacy_raw als Backup

Run vom Server:
    cd /opt/shiksha-engine
    source .venv/bin/activate

    # Phase 0 — Inspect
    python scripts/import_calendar.py --inspect

    # Phase 1 — Dry-Run
    python scripts/import_calendar.py --tenant krummelus --dry-run

    # Phase 2 — Real
    python scripts/import_calendar.py --tenant krummelus

Optionen:
    --schema kita_legacy --table calendar   überschreibt Default public.kita_legacy_calendar
    --operator <id>                          default: thomas
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from shiksha_engine.db import SessionLocal      # type: ignore
from shiksha_engine.models.event import Event   # type: ignore
from shiksha_engine.models.person import Person # type: ignore


# --------------------------------------------------------------------- Config

DEFAULT_SCHEMA = "public"
DEFAULT_TABLE = "kita_legacy_calendar"
LEGACY_SOURCE = "kita_legacy_calendar"

# Legacy-Type → neuer event_type. Unbekannt → "termin"
TYPE_NORMALISATION = {
    "termin": "termin",
    "event": "termin",
    "appointment": "termin",
    "urlaub": "urlaub",
    "vacation": "urlaub",
    "ferien": "urlaub",
    "abwesenheit": "abwesenheit",
    "absence": "abwesenheit",
    "krankheit": "abwesenheit",
    "kurs": "kurs",
    "course": "kurs",
    "musikkreis": "kurs",
    "bewegung": "kurs",
}


# ------------------------------------------------------------------- Helpers

def first(row: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return default


def parse_dt(value: Any) -> Optional[datetime]:
    """Tolerantes Datetime-Parsing — ISO, deutsch, mit/ohne TZ."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        # Falls naive → als UTC interpretieren
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None


def _serializable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, (str, int, float, bool, type(None))):
            out[k] = v
        elif isinstance(v, (list, dict)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def normalize_event_type(raw_type: Any) -> str:
    if not raw_type:
        return "termin"
    key = str(raw_type).strip().lower()
    return TYPE_NORMALISATION.get(key, "termin")


# ------------------------------------------------------------------- Person-Lookup

class PersonResolver:
    """Cached Lookup: alter Legacy-ID → neue persons.id."""

    def __init__(self, db: Session, tenant_org_id: str):
        self.db = db
        self.tenant = tenant_org_id
        self._cache: dict[str, int] = {}
        self._unresolved: set[str] = set()

    def resolve(self, legacy_person_id: Any) -> Optional[int]:
        if legacy_person_id is None or legacy_person_id == "":
            return None
        key = str(legacy_person_id)
        if key in self._cache:
            return self._cache[key]
        if key in self._unresolved:
            return None
        person = (
            self.db.query(Person)
            .filter(
                Person.tenant_org_id == self.tenant,
                Person.legacy_id == key,
                Person.legacy_source.in_(("kita_legacy_children", "kita_legacy_staff")),
            )
            .first()
        )
        if person:
            self._cache[key] = person.id
            return person.id
        self._unresolved.add(key)
        return None

    def stats(self) -> dict:
        return {
            "resolved": len(self._cache),
            "unresolved_legacy_ids": sorted(self._unresolved),
        }


def extract_legacy_participants(row: dict) -> list[Any]:
    """Holt die Legacy-Participant-IDs aus diversen denkbaren Spalten."""
    for key in ("teilnehmer_ids", "participants", "participant_ids", "teilnehmer", "children_ids", "child_ids"):
        v = row.get(key)
        if v is None:
            continue
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Komma-separiert?
                return [x.strip() for x in v.split(",") if x.strip()]
    return []


# ------------------------------------------------------------------- Mapper

def map_calendar_row(row: dict, resolver: PersonResolver) -> dict:
    """Legacy-Calendar-Row → events-Payload."""
    raw_type = first(row, "typ", "type", "event_type", "kategorie")
    event_type = normalize_event_type(raw_type)

    start_at = parse_dt(first(row, "start", "start_at", "datum", "begin", "von"))
    end_at = parse_dt(first(row, "ende", "end_at", "end", "bis"))

    legacy_parts = extract_legacy_participants(row)
    resolved_parts: list[int] = []
    unresolved: list[Any] = []
    for lp in legacy_parts:
        new_id = resolver.resolve(lp)
        if new_id is not None:
            resolved_parts.append(new_id)
        else:
            unresolved.append(lp)

    metadata: dict[str, Any] = {
        "subtype": first(row, "subtyp", "subtype"),
        "legacy_raw": _serializable(row),
    }

    # Original-Type bewahren, falls die Normalisierung Information frisst
    if raw_type and str(raw_type).lower() != event_type:
        metadata["original_type"] = str(raw_type)

    if unresolved:
        metadata["unresolved_legacy_participants"] = unresolved

    # Urlaub-Default-Status: aus alter Welt war alles approved
    if event_type == "urlaub":
        metadata["status"] = "approved"

    # Subtype-Felder dezent rausschmeißen wenn None
    metadata = {k: v for k, v in metadata.items() if v is not None}

    return {
        "legacy_id": str(first(row, "id", "event_id", "uuid")),
        "legacy_source": LEGACY_SOURCE,
        "event_type": event_type,
        "title": (first(row, "titel", "title", "name", "label") or "Termin")[:255],
        "description": first(row, "beschreibung", "description", "notes", "notizen"),
        "location": first(row, "ort", "location", "place"),
        "start_at": start_at,
        "end_at": end_at,
        "all_day": bool(first(row, "ganztags", "all_day", "allday", default=False)),
        "participants": resolved_parts,
        "metadata_": metadata,
    }


# ------------------------------------------------------------------- Inspect

def inspect(session: Session, schema: str, table: str) -> None:
    print(f"\n=== {schema}.{table} ===\n")

    cols = session.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = :s AND table_name = :t
        ORDER BY ordinal_position
    """), {"s": schema, "t": table}).fetchall()

    if not cols:
        print(f"⚠  Keine Tabelle {schema}.{table} gefunden.\n")
        candidates = session.execute(text("""
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE (table_name LIKE 'kita%'
                OR table_name LIKE '%calendar%'
                OR table_name LIKE '%termin%'
                OR table_name LIKE '%event%')
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
        """)).fetchall()
        if candidates:
            print("Kandidaten:")
            for c in candidates:
                print(f"  {c.table_schema}.{c.table_name}")
        return

    print("Spalten:")
    for c in cols:
        nul = "NULL" if c.is_nullable == "YES" else "NOT NULL"
        print(f"  {c.column_name:<28} {c.data_type:<22} {nul}")

    count = session.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar()
    print(f"\nGesamt-Rows: {count}")

    print(f"\nBeispiel (3 Zeilen):\n")
    rows = session.execute(text(f'SELECT * FROM "{schema}"."{table}" LIMIT 3')).mappings().all()
    for r in rows:
        print(json.dumps(dict(r), indent=2, default=str, ensure_ascii=False))
        print()


# -------------------------------------------------------------------- Import

def import_calendar(
    session: Session,
    tenant: str,
    operator_id: str,
    schema: str,
    table: str,
    dry_run: bool,
) -> None:
    print(f"\n→ {schema}.{table}  ⇒  events (tenant={tenant})")
    if dry_run:
        print("  [TROCKENLAUF — nichts wird geschrieben]")

    rows = session.execute(text(f'SELECT * FROM "{schema}"."{table}"')).mappings().all()
    print(f"  {len(rows)} Quell-Rows gefunden\n")

    resolver = PersonResolver(session, tenant)
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped_no_start": 0,
        "errors": [],
    }

    now = datetime.now(tz=timezone.utc)

    for raw in rows:
        try:
            data = map_calendar_row(dict(raw), resolver)
        except Exception as e:  # pragma: no cover
            stats["errors"].append((dict(raw).get("id"), str(e)))
            continue

        if not data["start_at"]:
            stats["skipped_no_start"] += 1
            continue

        existing = (
            session.query(Event)
            .filter_by(legacy_id=data["legacy_id"], legacy_source=data["legacy_source"])
            .first()
        )

        if existing:
            stats["updated"] += 1
            label = "UPDATE"
            if not dry_run:
                for k, v in data.items():
                    if k in ("legacy_id", "legacy_source"):
                        continue
                    setattr(existing, k, v)
                existing.tenant_org_id = tenant
                existing.operator_id = operator_id
                existing.updated_at = now
        else:
            stats["inserted"] += 1
            label = "INSERT"
            if not dry_run:
                e = Event(
                    tenant_org_id=tenant,
                    operator_id=operator_id,
                    active=True,
                    created_at=now,
                    updated_at=now,
                    **data,
                )
                session.add(e)

        parts_repr = f"[{len(data['participants'])}]"
        print(f"  {label}: {data['event_type']:<13} {data['title'][:35]:<35} "
              f"{data['start_at'].isoformat()[:16]}  parts={parts_repr}  legacy={data['legacy_id']}")

    if not dry_run:
        session.commit()
        print("\n  ✓ committed\n")
    else:
        session.rollback()
        print()

    person_stats = resolver.stats()
    print(f"  Stats:")
    print(f"    inserted={stats['inserted']}")
    print(f"    updated={stats['updated']}")
    print(f"    skipped(no start_at)={stats['skipped_no_start']}")
    print(f"    errors={len(stats['errors'])}")
    print(f"    Persons resolved={person_stats['resolved']}")
    if person_stats["unresolved_legacy_ids"]:
        print(f"    Persons UNRESOLVED legacy IDs:")
        for lid in person_stats["unresolved_legacy_ids"][:10]:
            print(f"      - {lid}")
        if len(person_stats["unresolved_legacy_ids"]) > 10:
            print(f"      … +{len(person_stats['unresolved_legacy_ids']) - 10} weitere")
    if stats["errors"]:
        print("  Fehler:")
        for id_, err in stats["errors"][:5]:
            print(f"    - id={id_}: {err}")


# ----------------------------------------------------------------------- CLI

def main() -> None:
    p = argparse.ArgumentParser(description="Import legacy KITA calendar into shiksha events.")
    p.add_argument("--tenant", default="krummelus", help="Tenant org_id (default: krummelus)")
    p.add_argument("--operator", default="thomas", help="Audit operator id (default: thomas)")
    p.add_argument("--schema", default=DEFAULT_SCHEMA)
    p.add_argument("--table", default=DEFAULT_TABLE)
    p.add_argument("--inspect", action="store_true", help="Nur Struktur + Beispiel zeigen")
    p.add_argument("--dry-run", action="store_true", help="Zeigen was passieren würde, ohne zu schreiben")
    args = p.parse_args()

    with SessionLocal() as session:
        if args.inspect:
            inspect(session, args.schema, args.table)
            return
        import_calendar(
            session, args.tenant, args.operator,
            args.schema, args.table, args.dry_run,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        sys.exit(130)

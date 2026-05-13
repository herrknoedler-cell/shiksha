#!/usr/bin/env python3
"""
import_persons.py — Migriere kita_legacy_children + kita_legacy_staff in persons.

Idempotent: Wiederholte Läufe duplizieren nicht. UPSERT auf (legacy_id, legacy_source).
Tolerant gegen unbekannte Spaltennamen via first(row, "vorname", "first_name", ...).

Run vom Server aus (DB ist dort lokal erreichbar):

    cd /opt/shiksha-engine
    source .venv/bin/activate

    # Phase 0 — Strukturen ansehen (welche Spalten existieren wirklich?)
    python scripts/import_persons.py --inspect --source kita_legacy_children
    python scripts/import_persons.py --inspect --source kita_legacy_staff

    # Phase 1 — Trockenlauf (zeigt, was passieren würde, schreibt nichts)
    python scripts/import_persons.py --source kita_legacy_children --tenant krummelus --dry-run
    python scripts/import_persons.py --source kita_legacy_staff    --tenant krummelus --dry-run

    # Phase 2 — Echter Lauf
    python scripts/import_persons.py --source kita_legacy_children --tenant krummelus
    python scripts/import_persons.py --source kita_legacy_staff    --tenant krummelus

Falls die Tabellen anders heißen / in anderem Schema liegen:
    --schema kita_legacy --table children
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# Imports relativ zur shiksha-engine: das Skript erwartet, dass es aus dem
# Projektverzeichnis (mit aktivem venv) gestartet wird.
from shiksha_engine.db import SessionLocal  # type: ignore
from shiksha_engine.models.person import Person   # type: ignore


# --------------------------------------------------------------------- Config

SOURCE_CONFIG = {
    "kita_legacy_children": {
        "kind": "kind",
        "schema": "public",
        "table": "kita_legacy_children",
    },
    "kita_legacy_staff": {
        "kind": "staff",
        "schema": "public",
        "table": "kita_legacy_staff",
    },
}


# ------------------------------------------------------------------- Helpers

def first(row: dict, *keys: str, default: Any = None) -> Any:
    """Erstes nicht-leeres Feld aus row für eine der gegebenen Spalten."""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return default


def parse_date(value: Any) -> Optional[date]:
    """Tolerante Datums-Parsing — ISO, deutsch, US-Format."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _serializable(row: dict) -> dict:
    """Macht eine Row JSON-serialisierbar für jsonb."""
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, (str, int, float, bool, type(None))):
            out[k] = v
        elif isinstance(v, (list, dict)):
            # JSONB-Spalten kommen schon als list/dict zurück
            out[k] = v
        else:
            out[k] = str(v)
    return out


def split_name(name: Any) -> tuple[str, str]:
    """
    Single-Field 'name' aus Legacy → (given_name, family_name).
      'Mira Fiel'                     → ('Mira', 'Fiel')
      'Nicole Kerschbaumer-Bachmann'  → ('Nicole', 'Kerschbaumer-Bachmann')
      'Anna Maria Müller'             → ('Anna Maria', 'Müller')   # rsplit von rechts
      'Lio'                           → ('Lio', '')
      None / ''                       → ('', '')
    Edge-Cases wie 'Jan von der Heyde' → ('Jan von der', 'Heyde'); manuelle Korrektur im Modal.
    """
    if name is None:
        return ("", "")
    s = str(name).strip()
    if not s:
        return ("", "")
    if " " not in s:
        return (s, "")
    given, family = s.rsplit(" ", 1)
    return (given.strip(), family.strip())


def _pick(row: dict, *keys: str) -> dict:
    """Sammelt nicht-leere Felder aus row für die gegebenen keys (für metadata-Sub-Objekte)."""
    out = {}
    for k in keys:
        v = row.get(k)
        if v not in (None, "", [], {}):
            if isinstance(v, (date, datetime)):
                out[k] = v.isoformat()
            else:
                out[k] = v
    return out


# ------------------------------------------------------------------- Mappers

def map_child_row(row: dict) -> dict:
    """
    Kita-Legacy-Children → persons. 'name' ist Single-Field, wird via rsplit(" ", 1) gesplittet.
    Strukturierte Metadata mit medical/compliance/profile/safeguarding/parents-Sektionen.
    """
    name_raw = first(row, "name", "vorname", "first_name", "given_name") or ""
    given, family = split_name(name_raw)

    birth_date = parse_date(first(row, "birth_date", "birthdate", "geburtsdatum", "dob"))
    birth_year = first(row, "birth_year", "geburtsjahr")

    metadata: dict[str, Any] = {}

    # Medical-Cluster — Allergien/Medikamente sind beim Tagesbetrieb relevant
    medical = _pick(row, "allergies", "medications", "medical_notes", "dietary_notes")
    if medical:
        metadata["medical"] = medical

    # Compliance — Foto-Einverständnis ist DSGVO-relevant
    compliance = _pick(row, "photo_consent")
    if compliance:
        metadata["compliance"] = compliance

    # Profil — Nationalität, Muttersprache
    profile = _pick(row, "nationality", "native_language")
    if profile:
        metadata["profile"] = profile

    # Safeguarding — sensitiv, separat von normalen notes
    safeguarding = _pick(row, "notes_safeguarding")
    if safeguarding:
        metadata["safeguarding"] = safeguarding

    # Eltern + Abholberechtigte (JSONB-Arrays, oft leer in Phase 1)
    relations = _pick(row, "parents", "pickup_authorized")
    if relations:
        metadata["relations"] = relations

    # Birth-Year-only Marker, falls Datenschutz-Modus
    if not birth_date and birth_year:
        metadata["birth_year_only"] = birth_year

    # Komplette Quell-Zeile als Backup
    metadata["legacy_raw"] = _serializable(row)

    return {
        "kind": "kind",
        "legacy_id": str(first(row, "id", "child_id", "uuid")),
        "legacy_source": "kita_legacy_children",
        "given_name": given,
        "family_name": family,
        "birth_date": birth_date,
        "gender": first(row, "gender", "geschlecht", "sex"),
        "group_id": first(row, "group_name", "gruppe", "group_id", "group"),
        "entry_date": parse_date(first(row, "entry_date", "eintritt", "entry", "start_date")),
        "exit_date": parse_date(first(row, "exit_date", "austritt", "exit", "end_date")),
        "notes": first(row, "notes", "notizen", "comment", "bemerkung"),
        "address": first(row, "address", "adresse"),
        "phone": first(row, "phone", "telefon"),
        "email": first(row, "email"),
        "metadata_": metadata,
    }


def map_staff_row(row: dict) -> dict:
    """
    Kita-Legacy-Staff → persons. 'name' ist Single-Field. Anstellungs-Cluster (role,
    employment_type, weekly_hours, contract_type, qualification) landet in metadata_.employment.
    """
    name_raw = first(row, "name", "vorname", "first_name", "given_name") or ""
    given, family = split_name(name_raw)

    metadata: dict[str, Any] = {}

    # Anstellungs-Cluster
    employment = _pick(
        row,
        "role", "employment_type", "weekly_hours", "contract_type", "qualification",
    )
    if employment:
        metadata["employment"] = employment

    # Falls Staff später als Operator verknüpfbar — email als Match-Key vormerken
    if row.get("email"):
        metadata["operator_link_hint"] = {"email": row["email"]}

    metadata["legacy_raw"] = _serializable(row)

    return {
        "kind": "staff",
        "legacy_id": str(first(row, "id", "staff_id", "uuid")),
        "legacy_source": "kita_legacy_staff",
        "given_name": given,
        "family_name": family,
        "email": first(row, "email"),
        "phone": first(row, "phone", "telefon"),
        "address": first(row, "address", "adresse"),
        "entry_date": parse_date(first(row, "entry_date", "eintritt", "entry", "start_date")),
        "exit_date": parse_date(first(row, "exit_date", "austritt", "exit", "end_date")),
        "notes": first(row, "notes", "notizen", "comment", "bemerkung"),
        "metadata_": metadata,
    }


MAPPERS = {
    "kita_legacy_children": map_child_row,
    "kita_legacy_staff": map_staff_row,
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
                OR table_name LIKE '%kind%'
                OR table_name LIKE '%child%'
                OR table_name LIKE '%staff%'
                OR table_name LIKE '%mitarbeiter%')
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

def import_source(
    session: Session,
    source: str,
    tenant: str,
    operator_id: str,
    schema: str,
    table: str,
    dry_run: bool,
) -> None:
    mapper = MAPPERS[source]
    print(f"\n→ {schema}.{table}  ⇒  persons (kind={SOURCE_CONFIG[source]['kind']})")
    if dry_run:
        print("  [TROCKENLAUF — nichts wird geschrieben]")

    rows = session.execute(text(f'SELECT * FROM "{schema}"."{table}"')).mappings().all()
    print(f"  {len(rows)} Quell-Rows gefunden\n")

    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}

    for raw in rows:
        try:
            data = mapper(dict(raw))
        except Exception as e:  # pragma: no cover
            stats["errors"].append((dict(raw).get("id"), str(e)))
            continue

        if not data["given_name"] and not data["family_name"]:
            stats["skipped"] += 1
            continue

        existing = (
            session.query(Person)
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
        else:
            stats["inserted"] += 1
            label = "INSERT"
            if not dry_run:
                person = Person(
                    id=uuid4(),
                    tenant_org_id=tenant,
                    operator_id=operator_id,
                    active=True,
                    **data,
                )
                session.add(person)

        name = f"{data['given_name']} {data['family_name']}".strip()
        print(f"  {label}: {name:<35} legacy_id={data['legacy_id']}")

    if not dry_run:
        session.commit()
        print("\n  ✓ committed\n")
    else:
        session.rollback()
        print()

    print(f"  Stats: inserted={stats['inserted']}, "
          f"updated={stats['updated']}, "
          f"skipped(no-name)={stats['skipped']}, "
          f"errors={len(stats['errors'])}")
    if stats["errors"]:
        print("  Fehler:")
        for id_, err in stats["errors"][:10]:
            print(f"    - id={id_}: {err}")


# ----------------------------------------------------------------------- CLI

def main() -> None:
    p = argparse.ArgumentParser(description="Import legacy KITA persons into shiksha persons.")
    p.add_argument("--source", choices=list(SOURCE_CONFIG.keys()), required=True)
    p.add_argument("--tenant", default="krummelus", help="Tenant org_id (default: krummelus)")
    p.add_argument("--operator", default="thomas", help="Audit operator id (default: thomas)")
    p.add_argument("--schema", help="DB-Schema überschreiben (default: aus SOURCE_CONFIG)")
    p.add_argument("--table", help="Legacy-Tabelle überschreiben (default: aus SOURCE_CONFIG)")
    p.add_argument("--inspect", action="store_true", help="Nur Struktur + Beispiel zeigen")
    p.add_argument("--dry-run", action="store_true", help="Zeigen was passieren würde, ohne zu schreiben")
    args = p.parse_args()

    cfg = SOURCE_CONFIG[args.source]
    schema = args.schema or cfg["schema"]
    table = args.table or cfg["table"]

    with SessionLocal() as session:
        if args.inspect:
            inspect(session, schema, table)
            return
        import_source(session, args.source, args.tenant, args.operator, schema, table, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        sys.exit(130)

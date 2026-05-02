"""
SHIKSHA · KITA · SQLite → PostgreSQL Migration (V3)
Verlustfrei. Filter: nur letzte 5 staff (echte Mitarbeiter).
Mit autocommit + temp deaktivierten FK-Triggers.

Asymmetrische ENV-Konvention:
  DATABASE_URL         — Ziel (PostgreSQL), gleiche Konvention wie Hauptstrang
  LEGACY_SQLITE_PATH   — Quelle (Pfad zur SQLite-Datei der alten KITA-App)

Aufruf:
  /opt/shiksha/venv/bin/python /tmp/migrate_sqlite_to_pg.py
"""
import os
import sqlite3
import psycopg2

SQLITE_PATH = os.environ.get("LEGACY_SQLITE_PATH", "/opt/shiksha-kita/shiksha_kita.db")
PG_DSN = os.environ.get("DATABASE_URL")
if not PG_DSN:
    raise RuntimeError(
        "DATABASE_URL ist nicht gesetzt.\n"
        "Setup: docs/DEPLOY.md → systemd-Drop-In oder Shell-Export."
    )

TABLES_ORDER = [
    "areas", "rooms", "groups", "staff", "children",
    "daily_sessions", "child_attendance", "child_absence",
    "time_entries", "observations", "incidents",
    "requests", "request_responses",
]

BOOL_COLS = {"active", "reportable_disease", "informed_parents", "resolved"}


def convert_value(col_name, val):
    if val is None:
        return None
    if col_name in BOOL_COLS:
        return bool(val)
    return val


def main():
    print("=" * 60)
    print(" SHIKSHA · KITA · SQLite → PostgreSQL (V3)")
    print("=" * 60)

    sl = sqlite3.connect(SQLITE_PATH)
    sl.row_factory = sqlite3.Row

    pg = psycopg2.connect(PG_DSN)
    pg.autocommit = True   # ← Jeder Insert sofort persistent

    # Filter staff
    excluded_staff_ids = []
    staff_rows = sl.execute("SELECT id FROM staff ORDER BY id DESC").fetchall()
    if len(staff_rows) > 5:
        excluded_staff_ids = [r[0] for r in staff_rows[5:]]
        print(f"⚠ Filter: {len(excluded_staff_ids)} Test-Mitarbeiter ausgelassen "
              f"(IDs: {excluded_staff_ids}). 5 echte werden migriert.")
    print()

    # FK-Triggers temporär deaktivieren (nur für diese Session)
    cur_pg = pg.cursor()
    try:
        cur_pg.execute("SET session_replication_role = 'replica'")
        print("✓ FK-Triggers temporär deaktiviert für Migration.\n")
    except Exception as e:
        print(f"⚠ Kann FK-Triggers nicht deaktivieren ({e}). Migration läuft trotzdem mit Risiko.\n")
    cur_pg.close()

    total_migrated = {}

    for table in TABLES_ORDER:
        cur_pg = pg.cursor()
        try:
            rows = sl.execute(f"SELECT * FROM {table}").fetchall()

            if table == "staff":
                rows = [r for r in rows if r["id"] not in excluded_staff_ids]

            if table in ("time_entries", "observations", "incidents", "child_absence"):
                filtered = []
                for r in rows:
                    keys = r.keys()
                    skip = False
                    if "staff_id" in keys and r["staff_id"] in excluded_staff_ids:
                        skip = True
                    if "reported_by_staff_id" in keys and r["reported_by_staff_id"] in excluded_staff_ids:
                        skip = True
                    if not skip:
                        filtered.append(r)
                rows = filtered

            if not rows:
                print(f"  {table}: 0 Zeilen (übersprungen)")
                cur_pg.close()
                continue

            cols = list(rows[0].keys())
            placeholders = ", ".join(["%s"] * len(cols))
            col_list = ", ".join(cols)
            target = f"kita_legacy_{table}"
            sql = f"INSERT INTO {target} ({col_list}) VALUES ({placeholders})"

            count = 0
            errors = 0
            for r in rows:
                try:
                    values = [convert_value(c, r[c]) for c in cols]
                    cur_pg.execute(sql, values)
                    count += 1
                except Exception as e:
                    errors += 1
                    row_id = r["id"] if "id" in r.keys() else "?"
                    print(f"    ⚠ Fehler bei {table} id={row_id}: {str(e)[:120]}")

            # Sequence resetten
            try:
                cur_pg.execute(
                    f"SELECT setval(pg_get_serial_sequence('{target}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {target}), 1))"
                )
            except Exception:
                pass

            cur_pg.close()
            print(f"  {table}: {count} Zeilen → {target}" +
                  (f" ({errors} Fehler)" if errors else ""))
            total_migrated[table] = count

        except Exception as e:
            print(f"  ✗ {table}: SCHWERER FEHLER {str(e)[:120]}")
            cur_pg.close()

    # FK-Triggers reaktivieren
    cur_pg = pg.cursor()
    try:
        cur_pg.execute("SET session_replication_role = 'origin'")
    except Exception:
        pass
    cur_pg.close()

    print()
    print("=" * 60)
    print(" Migration abgeschlossen")
    print("=" * 60)
    print(f"  Tabellen migriert: {len(total_migrated)}")
    print(f"  Datensätze gesamt: {sum(total_migrated.values())}")
    print()

    # Verifikation
    cur_pg = pg.cursor()
    print("Verifikation in PostgreSQL:")
    for table in TABLES_ORDER:
        target = f"kita_legacy_{table}"
        try:
            cur_pg.execute(f"SELECT COUNT(*) FROM {target}")
            cnt = cur_pg.fetchone()[0]
            if cnt > 0:
                print(f"  {target}: {cnt} Zeilen")
        except Exception as e:
            print(f"  {target}: ERROR {e}")
    cur_pg.close()

    sl.close()
    pg.close()
    print()
    print("✓ Fertig.")


if __name__ == "__main__":
    main()

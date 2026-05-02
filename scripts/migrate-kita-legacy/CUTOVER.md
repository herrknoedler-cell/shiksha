# SHIKSHA · KITA · Cut-Over Plan
**SQLite-only → Geteilte PostgreSQL-DB**

Stand: 29.04.2026

---

## Phase 1: Migration (SQLite → PostgreSQL)

### Schritt 1: Schema anlegen

```bash
sudo -u postgres psql -d shiksha -f /tmp/legacy_schema.sql
```

### Schritt 2: SQLite-Backup

```bash
cp /opt/shiksha-kita/shiksha_kita.db /opt/shiksha-kita/shiksha_kita.db.backup_$(date +%Y%m%d_%H%M)
ls -la /opt/shiksha-kita/*.backup_*
```

### Schritt 3: Daten migrieren

```bash
/opt/shiksha/venv/bin/python /tmp/migrate_sqlite_to_pg.py
```

Erwartung:
```
groups: 3
staff: 5      (gefilter, 3 Test-IDs ausgeschlossen)
children: 18
rooms: 8
areas: 3
```

### Schritt 4: Alte App-Konfig auf PostgreSQL umstellen

Die alte App nutzt eine `.env`-Datei + SQLAlchemy. Es gibt **zwei Optionen**:

**Option A — Alte App liest aus PostgreSQL (`kita_legacy_*` Tabellen):**

Diese Variante erfordert ein `__tablename__`-Mapping in `models.py` der alten App. Das ist eine ~10-zeilige Änderung pro Modell.

**Option B (einfacher) — Alte App neben PostgreSQL behalten, READ-only:**

Alte App bleibt auf SQLite (read/write), aber ein Cron-Job synct alle 5 Minuten in PostgreSQL. Die NEUE App liest dann nur aus PostgreSQL.

### Empfehlung: Option B als Übergang

**Cron-Sync alle 5 Min:**
```bash
# /etc/systemd/system/shiksha-kita-sync.service
[Service]
Type=oneshot
ExecStart=/opt/shiksha/venv/bin/python /opt/shiksha-kita/sync_to_pg.py

# /etc/systemd/system/shiksha-kita-sync.timer
[Timer]
OnCalendar=*:0/5
```

So bleibt die alte App komplett unangetastet und Du kannst in Ruhe umsteigen.

---

## Phase 2: Neue App liest die Legacy-Daten

In `kita_compliance_router.py` die neuen Endpoints ergänzen:

```python
@kita_router.get("/legacy/children")
async def list_legacy_children():
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
          SELECT c.id, c.name, c.birth_year, c.group_id, g.name AS group_name
          FROM kita_legacy_children c
          LEFT JOIN kita_legacy_groups g ON g.id = c.group_id
          WHERE c.active = true
          ORDER BY c.name
        """)).fetchall()
    return {"children": [{"id": r[0], "name": r[1], "birth_year": r[2], "group_id": r[3], "group": r[4]} for r in rows]}
```

Im Trägerin-Dashboard neuer Tab **👶 Kinder** der die 18 echten zeigt.

---

## Phase 3: Subdomain-Konfig

**Aktueller Zustand:**
- `kita.shiksha.tun.zone` → 127.0.0.1:8001 (alte App)

**Empfehlung — sanfter Übergang:**
Subdomain bleibt erstmal auf alte App. Im neuen Trägerin-Dashboard wird ein Link zur alten gesetzt:

```
https://shiksha.tun.zone/accounting/ui/kita/dashboard
  └── Tab "Operativer Tag" → Link zu kita.shiksha.tun.zone/app/manage.html
```

**Später (wenn neue App alle Features hat):**

```nginx
server {
    server_name kita.shiksha.tun.zone;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        # Path-Rewrite für saubere URLs
        rewrite ^/$ /accounting/ui/kita/anmeldung last;
        rewrite ^/admin /accounting/ui/kita/dashboard last;
        rewrite ^/eltern /accounting/ui/kita/eltern last;
    }
}
```

---

## Phase 4: Stilllegung der alten App (frühestens in 4 Wochen)

```bash
systemctl stop shiksha-kita
systemctl disable shiksha-kita
mv /opt/shiksha-kita /opt/_archive/shiksha-kita-$(date +%Y%m%d)
```

SQLite-Backup behalten für 6 Monate.

---

## Roll-Back-Plan (falls etwas schiefgeht)

```bash
# 1. Legacy-Tabellen in PostgreSQL droppen
sudo -u postgres psql -d shiksha -c "
  DROP TABLE IF EXISTS
    kita_legacy_request_responses, kita_legacy_requests,
    kita_legacy_observations, kita_legacy_incidents,
    kita_legacy_time_entries, kita_legacy_child_absence,
    kita_legacy_child_attendance, kita_legacy_daily_sessions,
    kita_legacy_children, kita_legacy_staff, kita_legacy_groups,
    kita_legacy_rooms, kita_legacy_areas
  CASCADE;
"

# 2. SQLite-Backup wiederherstellen
cp /opt/shiksha-kita/shiksha_kita.db.backup_LATEST /opt/shiksha-kita/shiksha_kita.db

# 3. Service restart
systemctl restart shiksha-kita
```

— Stand 29.04.2026 · Verlustfrei · Beide Apps können parallel laufen

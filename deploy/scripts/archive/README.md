# Archived Deploy Scripts

Skripte hier sind **obsolet** — ihr Effekt ist mittlerweile permanent
in den Server-Code eingebaut. Sie liegen archiviert statt gelöscht,
weil sie als Referenz lesbar machen, wie ein bestimmter Fix damals
angewandt wurde (Logbuch-Funktion).

Daumenregel für Aufnahme hier: nur archivieren, wenn der Effekt
nachweislich schon im Server-Code drin ist. Sonst bleibt das Skript
in `deploy/scripts/` als history-of-changes.

## Inventar

| Skript | Was es tat | Warum obsolet |
|---|---|---|
| `fix_greeting.sh` | Knowledge-Bites world-readable, DATABASE_URL in Cron-Job, Insights-Cron-Test | Permissions + Cron-Wiring sind seit dem ersten produktiven Lauf gesetzt |
| `fix_header_import.sh` | `Header` in den FastAPI-Imports von `kita_compliance_router.py` ergänzt (Dashboard-Router brauchte Header für `X-User-Id`) | Der Import ist permanent in `server/kita_compliance_router.py` |
| `fix_knowledge_bites.sh` | Lokale `knowledge_bites.json` validieren, hochladen | JSON ist live; künftige Änderungen gehen über sync.sh |
| `fix_marketing.sh` | Korrigierte `knowledge_bites.json` + Pool-Importer-Aufruf | Marketing-Fixes sind in `server/marketing_router.py` und data-Stand ist live |
| `mount_fix.sh` | Restored Backup von `accounting_router.py`, detektiert Router-Variable, patched Mounts | Mounts sind permanent korrekt im aktuellen `accounting_router.py` |
| `mount_fix2.sh` | Final-Fix: alte auto-Mount-Blöcke weg, neue Mounts mit FUNCTION-LOCAL `FileResponse`-Import, neuer Service-Worker auch nach `kita_ui/` | Mount-Block ist im Code permanent eingebaut |
| `mount_uis.sh` | Idempotente UI-Mounts in `accounting_router.py` ergänzen | Mounts sind im Live-Code |

## Wann zurück in `deploy/scripts/`?

Wenn ein Fix *zurück gerollt* werden müsste oder ein neuer Server-Deploy
ohne den jeweiligen Patch hochkommt, lebt das Skript hier als Re-Apply-
Vorlage. Das passiert nur in echten Notfällen — die Standard-Deploy-Pfad
ist `deploy/scripts/sync.sh` (Phase 3).

## Wann ganz löschen?

Vorerst nicht. Beim Übergang auf eine vollständig env-getriebene Konfig +
sync.sh + Database-Migrations-Runner werden diese Skripte irrelevant.
Dann — frühestens — Löschung als Aufräum-Commit.

# SHIKSHA — Tech-Debt-Liste

**Zweck:** Bekannte Schwächen, die wir absichtlich offen lassen, weil sie nicht den aktuellen Pfad blockieren. Jeder Eintrag mit: **Was, Warum bisher offen, Wann fällig, Konkrete Lösung.**

Die Liste wird beim Onboarding eines neuen Build-Schritts kurz quergelesen — wenn ein Punkt akut wird, kommt er in den Build-Plan.

---

## T-001 — Pytest leakt in `shiksha_core` (Test-Isolation kaputt)

**Was:** `conftest.py` setzt `DB_SCHEMA=shiksha_core_test`, aber bei Test-Läufen können trotzdem Rows in `shiksha_core` landen (Production-Schema). Konkret entdeckt nach `pytest`-Lauf vor dem Daten-Import: zwei Persons (Tobias, Angelina) mit `kind=kind`, `tenant_org_id=krummelus`, IDs 1+2 in `shiksha_core.persons` — also in Production. Manuelles Cleanup + Sequence-Reset nötig.

**Warum bisher offen:** Cleanup ist trivial, die Test-Suite läuft trotzdem grün (159 passed). Echte Auswirkung nur, wenn jemand vor produktivem Import vergisst zu cleanen.

**Wann fällig:** Vor dem ersten produktiven Mehr-Tenant-Deploy. Solange nur Krummelus pilot ist, ist das Risiko visuell sichtbar (Mira sieht 2 unbekannte Kinder) und korrigierbar.

**Konkrete Lösung:**
1. `conftest.py`: Schema-Switch verbindlicher via `with switch_schema():`-Context-Manager, der Session-Engine neu bindet
2. Fixtures-Cleanup-Hook: `yield` + `delete from persons where legacy_source is null and tenant_org_id='krummelus'` als Pre-Check beim Start jedes pytest-Laufs
3. Optional: Separater Datenbank-User mit `SET search_path` nur auf Test-Schema

---

## T-002 — Wiederholte Cowork-Drop-Bugs (mehrere Klassen, jetzt vier)

**Was — bisherige Klasse:**
- `from shiksha_engine.database` (richtig: `shiksha_engine.db`)
- `id=uuid4()` für Integer-Autoincrement-PK

**Was — Klasse aus Drop 5.5.4.1:**
- **Migration-vs-Model-Drift:** Migration 0008 fügte `organizations.timezone` hinzu, aber das Python-Organization-Model wurde nicht parallel aktualisiert. Resultat: SQLAlchemy weiß nicht von der Spalte, beim Read nichts da, beim Insert SQL-Error. Claude Code fixte mit `timezone: Mapped[str]` und `server_default="Europe/Berlin"`.
- **Schema-Hardcoding im FK:** Mein `event.py` hatte `ForeignKey("shiksha_core.organizations.id")` hartkodiert. Bricht im Test-Schema `shiksha_core_test` mit `NoReferencedTableError`. Das `person.py`-Modell nutzt schon ein dynamisches Pattern (`f"{schema_name()}.organizations.id"` plus `schema_args()` im `__table_args__`); das hätte ich übernehmen müssen, habe ich nicht.

**Was — Klasse aus Drop 5.5.4.4:**
- **Master-Code-Veralten:** Mein `outputs/`-Drop für `shiksha-client.js` war **älter** als der bereits im Repo liegende Stand. Claude Code hat das beim Vergleich gemerkt (17328 vs 17962 bytes) und statt `cp` einen **Inline-Patch** gemacht — die 7 neuen Methoden in den lokalen Stand eingefügt, nicht überschrieben. Das hat funktioniert, weil Claude Code clever war. Gefahr beim nächsten Mal: stilles Überschreiben von Bug-Fixes, die schon im Repo sind.

  Konkrete Konvention für die Zukunft: **Drops, die bestehende Files patchen, müssen entweder (a) als Edit-Anweisungen formuliert sein (nicht als komplette neue Files), oder (b) explizit als 'überschreibt' markieren und Claude Code prüft per `git diff` vor dem cp.**

**Was — Klasse aus Drop 5.5.4.2:**
- **Pydantic-v2 `alias` ist bidirektional:** Ich nutzte `Field(default_factory=dict, alias="metadata_")` für den `EventOut.metadata`-Field. Das ist Pydantic-v2-falsch — `alias` wird sowohl beim Input ALS AUCH beim JSON-Output verwendet, wodurch der API-Response-Key `metadata_` (mit Underscore) wird statt `metadata`. Korrekt: `validation_alias="metadata_"` (nur Input) plus `model_config = ConfigDict(populate_by_name=True)`. **`persons.py` hat das schon richtig** — ich habe die Lesson nicht übernommen.
- **URL-Param-Encoding bei `datetime.isoformat()`:** Default-Format ist `2026-05-13T10:00:00+00:00`. Das `+` wird im URL-Query-String zu Space dekodiert, → 422. Lösung in Tests: explizit `Z`-Suffix erzwingen (`.isoformat().replace("+00:00", "Z")`) oder `urllib.parse.quote()` benutzen. Konvention: in allen künftigen URL-Datetime-Tests Z-Suffix als Default.
- **Router-Prefix-Pattern:** Ich setzte `APIRouter(prefix="/api/v1/calendar")` direkt im Router-File. Andere Router im Repo (`persons`, `heim`, `bridge`) lassen `main.py` den Prefix beim `app.include_router()` setzen. Konsistenz-Fix: Prefix gehört in `main.py`, nicht in den Router-File.
- **Conftest-Fixture mit `legacy_id=string` in Integer-Spalte:** Mein `krummelus_with_birthdays`-Fixture setzte `legacy_id="bday-test"`. `persons.legacy_id` ist im aktuellen DB-Stand offenbar Integer (nicht Text). Fix: `legacy_id` weglassen (nullable). Lesson: Fixtures NIE mit hardkodierten Type-Annahmen — nullable Felder weglassen.

**Warum bisher offen:** Cowork-Author hat keinen Zugriff auf den Live-Repo-Stand. Pattern wie der Schema-Helper sind nirgends als "must use"-Konvention dokumentiert — sie leben nur im Code von person.py und werden nicht automatisch übernommen.

**Wann fällig:** Jetzt — vier Drop-Bugs in zwei Modulen ist Pattern, nicht Zufall.

**Konkrete Lösung:**

1. **`SHIKSHA_REPO_MAP.md` als Cowork-Memory anlegen** — Modul-Namen, PK-Typen pro Tabelle, Schema-Helper-Pattern, FK-Konventionen, Import-Pfade. Drop-Author liest erst diese Datei, bevor Skripte fließen.

2. **Pre-Drop-Linter ergänzen:**
   ```bash
   # outputs/_smoke_test.sh — wird mit jedem Drop ausgeliefert
   python -c "from shiksha_engine.db import SessionLocal, Base"
   python -c "from shiksha_engine.models.event import Event"
   python -c "import shiksha_engine.alembic.versions.20260513_0008_events"
   ```

3. **Migration + Model-Pair Convention:** Jede Migration, die eine Tabelle ändert, MUSS im selben Drop das entsprechende Python-Model anpassen. Linter-Check: `grep "ALTER TABLE" migration.py → finde betroffenes Model → check column count`.

4. **Schema-aware FK-Helper überall:** In `models/__init__.py` ein Helper `def fk(table: str) -> str: return f"{schema_name()}.{table}"` exportieren. Alle FKs nutzen `fk("organizations.id")` statt String-Hardcoding.

---

## T-003 — Mira-Person ↔ Operator-Auth-Link aktivieren

**Was:** `persons.id=19` (Mira Fiel als Stammdaten-Person) und `operators.krummelus_mira` (Mira als Auth-Identity) sind aktuell zwei separate Records. Verknüpfung als Hint im Metadata: `metadata.operator_link_hint = {"email": "fiel.mira@gmail.com"}`. Aber: Keine echte FK-Beziehung, keine Frontend-Logik, die "Mein Profil" auf Mira's Person-Eintrag verlinkt.

**Warum bisher offen:** Mira braucht ihre eigene Person-Karte erst, wenn das Heim "Mein Profil"-Akzent oder Eltern-Onboarding via "Pädagoge X kennt Familie Y"-Verknüpfung kommt. Aktuell sieht sie ihre Kollegen in `/personen.html?tab=staff` und das reicht.

**Wann fällig:** Vor Eltern-Onboarding (Schritt 6) — dann braucht jede Eltern-Person eine Verknüpfung zu Kindern, und dasselbe Pattern wird für Staff ↔ Operator wichtig.

**Konkrete Lösung:**
1. Migration: `persons.operator_id_link` als optionale FK auf `operators.id` (NULLABLE, ON DELETE SET NULL)
2. Backfill-Skript: `UPDATE persons SET operator_id_link = o.id FROM operators o WHERE persons.metadata->'operator_link_hint'->>'email' = o.email AND persons.tenant_org_id = o.org_id`
3. `GET /api/v1/persons/me` für Operator → liefert die verknüpfte Person-Row
4. Heim-Karte "Mein Profil" → Link zu `/personen.html?person=me`

---

## T-004 — PersonCreate.tenant_org_id für Multi-Tenant

**Was:** Aktuell hartkodiertes `tenant_org_id=krummelus` im Import-Skript + `target_tenant`-Resolution im Endpoint nutzt nur `current_operator.org_id`. Wenn Developer ohne `org_id` (System-Kind) Personen anlegen will, kommt `400 "Developer must call from a tenant context"`. Workaround: SQL-Update auf `operators.thomas.org_id`.

**Warum bisher offen:** Nur ein Tenant existiert (Krummelus), Workaround kostet 1 SQL-Befehl.

**Wann fällig:** Sobald ein zweiter Tenant pilotiert wird (Yoga? Surf?).

**Konkrete Lösung:**
1. `PersonCreate.tenant_org_id: Optional[str] = None` als Schema-Erweiterung
2. Endpoint-Logik: `tenant = payload.tenant_org_id or current_operator.org_id`; bei Developer mit `kind=system` und gesetztem `tenant_org_id` aus Payload akzeptieren
3. Frontend-Tenant-Picker für Developer-Rolle (Dropdown im personen.html-Header, der die Liste aus `organizations` zieht)

---

## T-005 — Asset-Versioning bei Patches

**Was:** `shiksha-ui.v1.0.0.js` / `.css` und `shiksha-client.js` haben fixen Pfad. Bei Patch (z.B. v1.0.1) liefert Browser den gecachten Stand → Hard-Refresh (Cmd+Shift+R) nötig.

**Warum bisher offen:** Dev-Phase, alle Tester wissen Bescheid. Mira hat den Browser-Cache neulich auch geleert.

**Wann fällig:** Vor erstem produktivem Pilot-Onboarding mit Eltern (Phase 2).

**Konkrete Lösung:**
1. Asset-Pfade mit Version-Suffix: `shiksha-ui.v1.0.1.js` (semver bei jedem Patch)
2. Oder: Build-Hash als Query-Param: `<script src="shiksha-ui.v1.0.0.js?v=${BUILD_HASH}">`, Hash kommt aus `git rev-parse --short HEAD` zum Build-Zeitpunkt
3. Pragmatisch in der Übergangszeit: nginx `add_header Cache-Control "no-cache, must-revalidate"` für die Frontend-Assets

---

## T-006 — `metadata_`-Convention am DB-Layer ausrollen (positive Verbesserung)

**Was:** In Migration 0008 wurde der DB-Spaltenname `metadata_` (mit Underscore) direkt verwendet, anstatt wie bei `persons` über einen Schema-Alias zu gehen (`validation_alias="metadata_"`). Das umgeht die SQLAlchemy-`Base.metadata`-Namespace-Kollision direkt am Datentyp-Layer, ohne Aliasing in jedem Schema. Claude Code's Beobachtung: "Sauberer Pattern, könnte für künftige Modelle ausgerollt werden."

**Warum bisher offen:** Alte Tabellen (`persons`, `memories`, …) nutzen das alte Pattern und funktionieren. Migration wäre invasiv (ALTER COLUMN RENAME).

**Wann fällig:** Bei der nächsten Phase, wo wir ohnehin größere Schema-Refactorings haben. Nicht im laufenden Modul-Sprint.

**Konkrete Lösung:**
1. Konvention dokumentieren in `SHIKSHA_REPO_MAP.md` (kommt aus T-002): "Neue Tabellen verwenden `metadata_` als Spaltenname direkt."
2. Migration für Bestand: einmaliger Sweep, der für `persons`, `memories`, etc. die Spalten umbenennt und das Alias entfernt — gepaart mit Model-Updates.

---

## T-008 — Attendance Read-Side-Merge-Cache (Performance)

**Was:** `GET /api/v1/attendance/day` macht einen Read-Side-Merge zwischen `attendance_records` (manuell/Import) und Calendar-Events (Urlaub/Abwesenheit). Für Krummelus-Maßstab (23 Persons, wenige Events) ist das unkritisch. Bei N>100 Persons + viele Events wird's O(events × avg_participants_pro_event) — überschaubar, aber pro Day-View ein DB-Roundtrip mit Calendar-Query.

**Warum bisher offen:** Krummelus-Pilot reicht aktuell. Premature optimization sonst.

**Wann fällig:** Beim zweiten Tenant mit > 80 Persons (oder wenn `GET /day` > 500ms im p95 läuft).

**Konkrete Lösung:**
1. Tag-Cache mit TTL=60s in `services/attendance_cache.py` — Key: `(tenant_org_id, date, role-Signatur)`
2. Cache-Invalidate bei POST/PATCH/DELETE auf `/records` oder `/events` (Calendar-Brücke)
3. Optional Redis statt In-Memory wenn Multi-Worker (siehe auch WebAuthn-Challenge-Store-Notiz aus Schritt 5.5.1)

---

## T-009 — Tenant-TZ-Drift in time-of-day-Logik

**Status:** partially resolved. **Eröffnet:** 5.5.5.6.a (Live-Smoke). **Schwere:** mittel — silent-fail, kein User-sichtbarer Crash, aber falsche Daten in der 2-Stunden-Mitternachts-Lücke.

**Was:** Provider- und Query-Funktionen, die "today" mit `datetime.now(tz=timezone.utc).date()` berechnen, liefern in der 2-Stunden-Lücke nach Mitternacht (00:00–02:00 Vienna im Sommer / 00:00–01:00 im Winter) das Vortags-Datum, obwohl Tenants außerhalb von UTC liegen. Konsequenz: Anwesenheits-Cards zeigen morgens den Vortag, Calendar-Summary zeigt gestern statt heute.

**Stand pro Stelle:**

| Stelle | Status | Commit |
|---|---|---|
| `heim_providers.attendance_summary` | resolved | `eb9c851` |
| `heim_providers.attendance_week` | resolved | `eb9c851` |
| `calendar_query.py` Lines 232/233 | pending | siehe `bundle_calendar_tz_fix.md` |
| `calendar_query.py` Lines 281/282 | pending | siehe `bundle_calendar_tz_fix.md` |

**Konkrete Lösung:** Pattern-Migration auf Tenant-Timezone-Lookup via `operator.organization.timezone`:

```python
# vorher
now = datetime.now(tz=timezone.utc)
today_start = datetime.combine(now.date(), time(0, 0), tzinfo=timezone.utc)

# nachher
tz = ZoneInfo(operator.organization.timezone or "UTC")
now = datetime.now(tz=tz)
today_start = datetime.combine(now.date(), time(0, 0), tzinfo=tz)
```

**Pattern-Pflicht:** Vor jedem neuen Service, der "today" für Tenant-bezogene Zeitfenster berechnet (Identity-Authorization-Validity-Check, Push-Scheduling, Compliance-Reporting): Pattern aus `heim_providers.attendance_summary` übernehmen oder gemeinsamen Helper `shiksha_engine/lib/timezones.py::today_in_tenant_tz(operator)` extrahieren wenn ≥4 Aufrufer.

**Wann fällig:** `bundle_calendar_tz_fix.md` deployed + Identity-Modul (5.5.6.2) nutzt das Pattern von Anfang an.

---

## T-010 — Legacy Identity-Code archivieren

**Status:** open, wartet auf 5.5.6.6.b. **Eröffnet:** 5.5.6.0-Spec-Lieferung. **Schwere:** niedrig — Legacy lebt parallel, blockiert nichts, aber Konfusion bei zukünftigen Lesern und doppelte Code-Pfade in Suchen.

**Was:** Nach Abschluss von 5.5.6 (Identity-Modul portiert, Bridge-Trim live) bleibt der legacy Identity-Code unbenutzt im Repo liegen:

```
server/identity_router.py            ~600 LOC
server/identity_migration.sql        ~111 LOC
server/identity_ui/wizard.html       ~672 LOC
server/identity_ui/manifest.json      ~16 LOC
server/paedagogen_ui/shiksha-avatar.js   ~157 LOC (wird in 5.5.6.5 nach frontend/ verschoben)
```

Grep nach `identity_persons`, `identity_router` etc. findet doppelte Treffer (alt-Welt + neue Welt). `shiksha-avatar.js` wird sowieso refactor-moved in 5.5.6.5, betrifft den Punkt also nur teilweise.

**Konkrete Lösung:** Drei Optionen, in der Reihenfolge der Empfehlung:

1. **Move nach `legacy/identity/` mit `README.md`-Verweis auf Spec.** 6-Monats-Übergangszeit nach 5.5.6.6.b, danach Re-Evaluation. Maximale Reversibilität wenn beim Live-Betrieb Lücken auffallen.
2. **Branch-Archiv:** Code in einen `archive/identity-pre-1.5`-Branch verschieben, im main delete. Schwerer aufzufinden für Devs, aber sauberer trunk.
3. **Hard-Delete + Reference-Note** im Tech-Debt-Eintrag. Aggressivster Pfad, nur sinnvoll wenn die neue Implementation 2+ Monate problemlos läuft.

Empfehlung: Option 1 (Move nach `legacy/`).

**Wann fällig:** 5.5.6.6.b (Bridge-Trim) deployed + 2 Wochen ohne Identity-bezogene Rollbacks.

---

## T-011 — Three-Tier-Cleanup-Job für Identity-Auto-Löschung

**Status:** open, wartet auf 5.5.6.2. **Eröffnet:** DSFA-Erstellung 5.5.6.0. **Schwere:** hoch — DSGVO-Pflicht. Ohne funktionierenden Cleanup-Job verletzt das System Art. 5(1)(e) DSGVO (Speicherbegrenzung) und Art. 17 DSGVO.

**Was:** Drei verschiedene Aufbewahrungs-Tiers (siehe `docs/dsfa/identity-modul-at.md` §1.5) brauchen automatisierte Cleanup-Logik:

- **Tier 1 — Scan-Dateien:** max. `tenant.retention.scan_files_days` (Default 30 Tage AT) nach Verifikation, dann Hard-Delete inkl. File-System
- **Tier 2 — Strukturierte Daten + Authorizations:** Betreuungsende-Datum des verlinkten Kindes + `tenant.retention.structured_data_after_end_years` (Default 3 AT)
- **Tier 3 — Audit-Log:** `created_at` + `tenant.retention.audit_log_years` (Default 7 AT)

Zusätzlich: Legal-Hold-Flag pausiert alle drei Tiers für betroffene Records.

**Konkrete Lösung:** Nightly-Job `services/identity_cleanup.py` mit drei Tier-Methoden plus Pre-Check:

```python
def run_nightly_cleanup():
    for tenant in active_tenants():
        cfg = tenant.jurisdiction_yaml()["identity"]["retention"]
        cleanup_tier_1_files(tenant, cfg["scan_files_days"])
        cleanup_tier_2_structured(tenant, cfg["structured_data_after_end_years"])
        cleanup_tier_3_audit_log(tenant, cfg["audit_log_years"])

def cleanup_tier_1_files(tenant, days):
    cutoff = today_in_tenant_tz(tenant) - timedelta(days=days)
    for doc in pending_file_delete(tenant, cutoff):
        if doc.identity_person.legal_hold:
            continue
        delete_filesystem_file(doc.file_ref)
        doc.file_ref = None
        doc.file_deleted_at = now_tenant_tz(tenant)
        log_audit("identity_document.file_auto_deleted", doc)
```

Tier 2 und Tier 3 analog. Wichtig:

1. **Legal-Hold-Check vor jeder Lösch-Operation**, nicht nur am Tier-Eintritt
2. **Monitoring-Counter pro Tier** (`deleted_count_per_day` als Prometheus-Metric oder DB-Tabelle) für Audit-Verifikation
3. **Alarm wenn 24h ohne Cleanup-Lauf** (Cron- oder Job-Queue-Health-Check)
4. **Trockenlauf-Modus** (`--dry-run` Flag) für Erst-Deploy-Verifikation

**Pflicht-Tests (mindestens fünf):**

1. Tier-1: File älter als 30d → gelöscht
2. Tier-1: File mit `legal_hold=true` → NICHT gelöscht
3. Tier-2: Strukturierte Daten mit Betreuungsende +3J → gelöscht, Audit-Log bleibt
4. Tier-3: Audit-Log älter als 7J → gelöscht
5. Cross-Tier: Jurisdiction-Override (`at-8.yaml` setzt anderen Wert) → wird respektiert

**Wann fällig:** Vor Live-Schaltung des Identity-Moduls für AT-Tenants (5.5.6.6.b für AT-Tenants ist hard-blocked auf T-011, weil die DSB-Anfrage diesen Punkt vermutlich abfragt). 5.5.6.2 (Endpoints + OCR) deployed + Cleanup-Job läuft eine Woche mit Dry-Run-Flag + ein vollständiger Tier-1-Cleanup mit Real-Delete (kontrolliert) + Monitoring zeigt erwartete Counter.

---

## T-012 — Vier-Augen-Bestätigung bei Identity-Verifikation

**Status:** open, deferred aus 5.5.6.4. **Eröffnet:** 5.5.6.4-Pre-Flight. **Schwere:** mittel — DSFA §4.2 nennt Vier-Augen-Prinzip als organisatorische Maßnahme; aktuell verifiziert in der Implementation eine Person allein, was traceable via Audit-Log ist aber nicht das in der DSFA dokumentierte Pattern.

**Was:** Spec §5.1 (3-Step-Wizard) und DSFA §4.2 sehen vor, dass eine zweite leitende oder pädagogische Person die Verifikation gegenzeichnet. 5.5.6.4-Bundle schlug einen PIN-basierten Ansatz vor (`/api/v1/operators/verify-pin`), aber im Repo existiert kein PIN-System — Operator-Auth läuft ausschließlich über WebAuthn/Passkey. Ein PIN-Sub-Feature wäre kein Mini-Add, sondern ein eigenständiger Sprint (DB-Spalte + Migration + Mint-UI + Verify-Endpoint + Operator-Schulung). Für 5.5.6.4 wurde die Vier-Augen-Pflicht daher zurückgestellt; die Verifikation läuft mit single-operator-Klick, der Audit-Log dokumentiert Operator-ID und Zeitstempel.

**Praktischer Kontext:** Krummelus hat aktuell genau eine Leitung (Mira). Ein hartes Vier-Augen-Constraint würde den Workflow blockieren, wenn keine zweite leitende Person vor Ort ist — was im Pilot der Normalfall ist. Bei Multi-Leitungs-Tenants wird der Need real.

**Konkrete Lösung:** Drei Optionen, in der Reihenfolge der Empfehlung:

1. **Zweiter Passkey-Inline-Login.** Im Step-3-UI ein Button "Zweite Mitarbeiterin bestätigt jetzt" — startet WebAuthn-Flow mit `operator_id` der zweiten Person; bei Erfolg wird ein zweiter JWT im `X-Second-Operator-Token`-Header an `/persons/{id}/verify` mitgeschickt. Backend prüft: beide Tokens valide, gleicher Tenant, beide Rolle `leitung`/`padagoge`, beide Operator-IDs ≠. Saubere Auth-Wiederverwendung, kein PIN-System nötig. Aufwand: ~2-3h.
2. **PIN-System bauen.** Komplettes Sub-Feature wie oben beschrieben. Bessere UX am Tablet, aber deutlich mehr Code. Aufwand: ~4-6h.
3. **Bei single-operator bleiben, DSFA §4.2 anpassen.** Audit-Log-Pflicht ist DSGVO-konform; Vier-Augen war eine empfohlene aber nicht zwingende Maßnahme. Begründung im DSFA-Text: "Bei Single-Leitungs-Tenants ist Vier-Augen-Constraint impraktikabel; Audit-Log mit Operator-ID + Zeitstempel + Konsens-Text deckt Rechenschaftspflicht ab."

**Empfehlung:** Option 1 nach Krummelus-Live-Go, sobald ein zweiter Tenant mit mehreren Leitungen onboardet wird. Bis dahin Option 3 (DSFA-Text anpassen). Optionen 2 ist über-engineered.

**Wann fällig:** Vor Onboarding des zweiten AT-Tenants ODER vor 5.5.6.6.b-Live-Schaltung, falls die DSB-Antwort Vier-Augen explizit fordert.

---

## Schließe-Kriterien

Ein Tech-Debt-Eintrag wird gelöscht (nicht "✅ erledigt" gestrichen), wenn:
1. Die konkrete Lösung implementiert UND
2. Im Build-Plan als eigener Schritt protokolliert UND
3. Im Smoke-Test der nachfolgenden Module verifiziert ist.

Vermerk im Commit-Message: `closes T-XYZ`.

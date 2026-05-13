# SHIKSHA — Tech-Debt-Liste

**Zweck:** Bekannte Schwächen, die wir absichtlich offen lassen, weil sie nicht den aktuellen Pfad blockieren. Jeder Eintrag mit: **Was, Warum bisher offen, Wann fällig, Konkrete Lösung.**

Die Liste wird beim Onboarding eines neuen Build-Schritts kurz quergelesen — wenn ein Punkt akut wird, kommt er in den Build-Plan.

Historisches Audit-Trail (RESOLVED-Einträge mit Commit-Hash) lebt weiter in [`tech-debt.md`](tech-debt.md). Diese Datei hier ist die lebendige Open-Items-Liste mit T-IDs.

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

## Schließe-Kriterien

Ein Tech-Debt-Eintrag wird gelöscht (nicht "✅ erledigt" gestrichen), wenn:
1. Die konkrete Lösung implementiert UND
2. Im Build-Plan als eigener Schritt protokolliert UND
3. Im Smoke-Test der nachfolgenden Module verifiziert ist.

Vermerk im Commit-Message: `closes T-XYZ`.

# SHIKSHA Identity Spec

**Modul:** 5.5.6 Identity-Modul (inkl. Avatar-Engine-Refactor)
**Version:** v0.3-DRAFT
**Status:** Draft — Hash-Strategie + Edition-Config-Layer explizit modelliert; wartet auf Schema-Verifikation aus `cowork_identity_schema_dump.md`
**Vorgänger-Specs:** `SHIKSHA_CALENDAR_SPEC.md`, `SHIKSHA_ATTENDANCE_SPEC.md`
**Ausgangs-Commit:** `eb9c851` (Stand Phase 1.5, nach Calendar/Attendance, vor T-009-Fix)
**Repo-Layout:** `docs/SHIKSHA_REPO_MAP.md` (Provider-/Heim-/Bridge-Patterns)

Stellen mit `[TODO-VERIFY]` werden nach Eintreffen des Schema-Dumps zu konkreten Werten getightet.

---

## 1. Zweck & Scope

### 1.1 Was Identity ist

Identity ist die **Verifikations- und Berechtigungs-Schicht** für Personen, die nicht direkt operativ in der Kita arbeiten — primär Abhol-berechtigte (Eltern, Großeltern, Tageseltern, Babysitter), sekundär andere DSGVO-relevante Personen-Records (z. B. Lehrer-Externe bei Phase-2-Editionen).

Das Modul beantwortet drei Fragen:

1. **Wer ist diese Person?** — Stammdaten + Ausweis-Verifikation (OCR/MRZ-Pipeline aus Original-Identity portiert).
2. **Was darf diese Person tun?** — Authorization-Records (Kind X abholen, Buchung Y starten, Kurs Z besuchen).
3. **Wer hat wann was getan?** — DSGVO-Audit-Log über jeden Zugriff auf Identity-Daten.

### 1.2 Was Identity NICHT ist

- **Kein Mitarbeiter-Login.** Pädagoginnen/Leitung werden weiter über `operators`-Tabelle authentifiziert. Identity ist die Schicht *darunter* für Personen, die selbst nicht im Kita-System eingeloggt sind.
- **Kein Passkey-System.** Phase-2-Ziel (siehe §13), aber außerhalb 5.5.6.
- **Keine Avatar-Logik.** Avatar-Engine ist ein verwandtes Sub-Drop (5.5.6.5), aber konzeptuell separat — siehe §10.

### 1.3 Edition-Agnostik

Das Original `identity_migration.sql` ist edition-agnostisch konzipiert (Spalte `edition` wird beim Port weggelassen, weil `shiksha_core.persons.tenant_org_id` → `organizations.edition` denselben Zweck erfüllt). Identity-Tabellen leben im `shiksha_core`-Schema.

Konkret: ein einziges `identity_persons.id` kann sowohl in einer Kita-Edition (Abhol-Berechtigung) als auch in einer Phase-2-Edition (Vereinslehrer-Verifikation) referenziert werden — die Edition entsteht erst über die `target_type`+`target_id`-Kombination in `identity_authorizations`.

---

## 2. Architektur-Entscheidungen

### ADR-1: OCR/MRZ-Pipeline behalten (Hybrid-Ziel)

**Status:** accepted

**Kontext:** Das Identity-Original implementiert OCR (tesseract) + MRZ-Parsing (TD1/TD3) für Ausweis-Scan. Vor Port stand die Frage: portieren wie es ist, oder gleich auf Passkey-basierte Abholer-Authentifizierung wechseln, sobald die Bridge Eltern-Logins erlaubt.

**Entscheidung:** OCR/MRZ-Pipeline **portieren wie sie ist**. Passkey-Authorization wird als eigene Phase 2.1 nach Phase-1.5-Abschluss umgesetzt.

**Begründung:**

1. **Realität in Kitas:** Großeltern, Tageseltern und gelegentliche Abholer (Babysitter, Onkel) sind oft ohne Smartphone unterwegs. Ein Passkey-only-System würde sie ausschließen oder zur manuellen Mitarbeiter-Verifikation zwingen — das ist der heutige Workflow ohne System.
2. **Original-Code ist substantiell:** ~600 LOC funktionierende Pipeline mit OCR-Confidence, MRZ-Parsing für TD1+TD3, manuelle Bestätigung durch Mitarbeiter. Das wegzuwerfen wäre Verlust ohne Ersatz.
3. **Passkey hat Voraussetzungen:** setzt Eltern-Login via Bridge voraus (Phase-2-Material), plus Mint/Storage/Rotation/Recovery-Flows. Das ist nicht zwei Stunden Arbeit, sondern ein eigenes Modul.
4. **Risiko-Profil:** Port = mechanisch, kleine Surface. Passkey = neue Crypto-Surface, größere Surface.

**Konsequenzen:**

- `identity_documents` mit OCR-Output und MRZ-JSON bleibt Teil des Schemas.
- `tesseract` bleibt System-Dependency (siehe §3.5).
- `identity_authorizations.auth_method` wird eingeführt mit Default `"ausweis_scan"`, um Phase-2-Erweiterung um `"passkey_signed"` ohne Schema-Migration zu erlauben.

### ADR-2: Verknüpfung mit `persons`, nicht Parallel-Tabelle

**Status:** accepted

**Kontext:** Das Original hat `identity_persons` als eigenständige Tabelle mit eigenen Stammdaten. In Phase 1.5 existiert bereits `shiksha_core.persons` (Migration 0001-ff) mit `kind`-Diskriminator (`staff`/`klient`/`system`, erweitert in `0004` um Identity-relevante Werte). Frage: gleicht-namige Personen verknüpfen oder duplizieren?

**Entscheidung:** `identity_persons` bleibt **eigene Tabelle**, hat aber **optionale FK** `linked_person_id → persons.id`. Bei Erstellung versucht der Service einen Auto-Link gegen `persons` (gleicher Tenant, deckungsgleicher `full_name + birth_date`); Mitarbeiter kann Link manuell setzen/lösen.

**Begründung:**

1. **Trennung der Lifecycles:** ein Klient (`persons.kind='klient'`) kann seine Identity-Verifikation behalten, auch wenn der Klient-Record archiviert wird. DSGVO-Audit braucht den Identity-Record unabhängig.
2. **Nicht-Klienten:** ein Abholer ist oft kein eigener `persons`-Record (das wäre Phase 2 mit `persons.kind='eltern'`). `identity_persons` muss eigenständig existieren können.
3. **Soft-Link statt Hart-Merge:** wenn `linked_person_id` `NULL` ist, ist die Identity stand-alone; wenn gesetzt, wird in Queries nach Person automatisch der `persons`-Record mit gezogen.

**Konsequenzen:**

- `identity_persons.linked_person_id`: `UUID NULL REFERENCES persons(id) ON DELETE SET NULL`
- Service-Layer: `identity_query.try_auto_link(identity_person_id)` als Helper, der Match-Logik kapselt.
- Berechtigungs-Logik: `identity_authorizations.subject_identity_person_id` (statt direkt `persons.id`), weil ein Abholer eben *kein* `persons`-Record sein muss.

### ADR-3: Schema `shiksha_core`, nicht `public`

**Status:** accepted

**Kontext:** Das Original liegt in PG-Schema `public`. Phase 1.5 hat alle neuen Tabellen ins `shiksha_core`-Schema migriert (Migrations `0001`–`0009`).

**Entscheidung:** Alle Identity-Tabellen in `shiksha_core`. Migration wird **Greenfield** angelegt (kein Daten-Migrations-Pfad aus `public.identity_*`), weil Krummelus laut Phase-1.5-Plan keine identity-Daten aus der alten Welt mitbringt.

**Begründung:** konsistenter Pattern mit 5.5.3/4/5; vermeidet Cross-Schema-Joins.

**Konsequenzen:**

- Alembic-Migration `20260516_0010_identity.py` (Datum [TODO-VERIFY] beim Anlegen).
- Falls eine Edition später identity-Daten aus alter Welt mitbringt: separates Import-Skript analog `scripts/import_persons.py`, eigene 5.5.6.3-Lieferung. Aktuell deaktiviert.

### ADR-4: Wizard 5-Step → 3-Step verschmolzen

**Status:** accepted

**Kontext:** Original-Wizard hat 5 Schritte: (1) Person & Einwilligung, (2) Vorderseite scannen, (3) Rückseite scannen, (4) Selfie, (5) Bestätigen & Speichern.

**Entscheidung:** **3-Step**:

1. **Person & Consent** — Stammdaten + DSGVO-Einwilligung.
2. **Ausweis-Scan** — Vorder- und Rückseite als zwei Captures innerhalb eines UI-Steps (separate `POST /upload`-Calls bleiben backend-seitig, nur das UI verschmilzt).
3. **Selfie + Bestätigung** — Selfie-Capture und Mitarbeiter-Bestätigung in einem Step.

**Begründung:**

1. **Wahrgenommene Länge:** 5 Schritte fühlen sich lang an für eine Erfassung, die selten >3 Min dauert. 3 Schritte mit Sub-Captures sind kognitiv leichter.
2. **Backend bleibt:** drei Upload-Calls (`id_front`, `id_back`, `selfie`) bleiben separat — das ist eine UI-Verschmelzung, kein Schema-Bruch.
3. **Mitarbeiter-Bestätigung:** muss DSGVO-rechtlich explizit erfolgen, kann aber als Tap unter dem Selfie passieren statt eigener Bildschirm.

**Konsequenzen:**

- Frontend `identity.html` rendert 3-Step-Progress, sendet weiterhin 3 Upload-Calls (oder optional als FormData mit drei Files in einem Call, falls Backend das stützt — [TODO-VERIFY] nach Schema-Dump).
- Wizard-CSS-Tokens (`--holi-pink` etc.) bleiben — Look identisch.

### ADR-5: Avatar als separates Sub-Drop (5.5.6.5)

**Status:** accepted

**Kontext:** `shiksha-avatar.js` (157 LOC, voll funktionsfähig) liegt aktuell unter `server/paedagogen_ui/`. Phase-1.5-Frontends (`anwesenheit.html`, `personen.html`) nutzen ihn nicht; `anwesenheit.html` macht Avatar-Saturation inline mit CSS-`filter`.

**Entscheidung:** Avatar-Refactor als **eigenes Sub-Drop 5.5.6.5** innerhalb 5.5.6, unabhängig von Identity-Verifikation. Refactor-only, **keine Logik-Änderung** an der Engine.

**Begründung:**

1. **Konzeptuelle Trennung:** Avatar ist Render-Schicht für Personen-UI, Identity ist Verifikations-Layer. Sie kreuzen sich nur in `identity.html` (Avatar als visueller Hint), nicht im Datenmodell.
2. **Logik-Risiko klein:** die Engine ist getestet via existierende Heim-Cards (legacy). Refactor = File-Move + Import-Anpassung, ~1-2h.
3. **Quick Win nach Identity-Backend:** kann am Ende von 5.5.6 stehen, wenn der Backend-Aufwand fertig ist.

**Konsequenzen:** siehe §10 und Sub-Drop 5.5.6.5 in §12.

### ADR-6: `persons.metadata.avatar_*` statt typed Spalten

**Status:** accepted (provisorisch — revidierbar wenn Avatar-Features wachsen)

**Kontext:** Avatar braucht ggf. `color_seed`, `ring_color`, evtl. weitere Felder. Frage: als typed Spalten in `persons` (`avatar_color_seed VARCHAR`, `avatar_ring_color VARCHAR`) oder im freien JSON-Bag `persons.metadata_`?

**Entscheidung:** **`metadata_.avatar_*`** für 5.5.6. Migration nur, wenn ≥3 Avatar-Felder mit Indexierungs-Bedarf entstehen.

**Begründung:**

1. **Edition-Agnostik:** typed Spalten bedeuten Schema-Migration für jede neue Edition, die Avatar nicht braucht. JSON-Bag ist flexibel.
2. **Aktuell zwei Felder:** `color_seed` (deterministisch aus `persons.id` ableitbar via Hash) und `ring_color` (gruppen-basiert). Nicht-indexiert, lese-only beim Rendern. JSON reicht.
3. **Reversibel:** wenn Avatar in Phase 2 zu mehr Feldern wächst (animierte Statuses, Custom-Photos), Migration `persons` → typed Spalten als eigenständiger Sprint.

**Konsequenzen:**

- `services/identity_avatar.py`: Helper `compute_avatar_metadata(person) → dict` mit deterministischem Color-Seed (z. B. `sha256(person.id)[:6]` als Hex-Hue).
- Beim Person-Erstellen / -Update: `persons.metadata_.avatar = {color_seed: ..., ring_color: ...}` setzen.
- Frontend liest `person.metadata.avatar.color_seed` (über Pydantic-Out-Schema oder direkten JSON-Pass-Through).

### ADR-7: Jurisdictions-Layer mit Deep-Merge

**Status:** accepted

**Kontext:** DSGVO-Retention-Fristen, MRZ-Feld-Whitelist und Aufsichtsbehörden-Kontakt variieren je Land (AT/DE/CH) und teils je Bundesland/Kanton. Edition-Configs (`kita.yaml`/`camping.yaml`/…) bleiben jurisdiktions-frei, weil ein Kita-Vokabular in Wien und München identisch ist; was sich unterscheidet, ist die rechtliche Auslegung der Datenhaltung. Spec v0.1 modellierte einen globalen `auto_delete_at = 365 Tage`-Default — das ist falsch.

**Entscheidung:** Eigene Config-Achse `editions/jurisdictions/<code>.yaml` parallel zu Editions. Resolution per Deep-Merge: Country-Default (z.B. `at.yaml`) wird von Bundesland/Kanton-Override (z.B. `at-8.yaml` für Vorarlberg) ergänzt; übrige Keys erben.

**Begründung:**

1. **Recht ≠ Vokabular.** DSGVO-Auslegung gehört nicht in `kita.yaml`. Edition × Jurisdiktion ist 2D — jede Edition kann in jeder Jurisdiktion laufen.
2. **Country-Default deckt 90 %.** Innerhalb eines Landes sind Retention-Fristen meist landesweit. Override nur für Bundesland/Kanton-spezifische Punkte (z.B. Bildungsdirektion-Kontakt).
3. **Deep-Merge ist sparsam.** `at-8.yaml` mit drei Zeilen reicht, wenn Vorarlberg nur eine zusätzliche Behörde nennen will.

**Konsequenzen:**

- Neues Verzeichnis `server/shiksha_engine/editions/jurisdictions/`:
  - `at.yaml` — Country-Default (Retention 30d/3a/7a, Hash-Algorithmus, DSB als Behörde, DSFA-Pflicht).
  - `at-8.yaml` — Vorarlberg, ergänzt `regional_oversight: Bildungsdirektion Vorarlberg`.
  - `at-9.yaml` — Wien (TODO bei erstem Wien-Tenant).
  - `de.yaml` / `de-bw.yaml` / `ch.yaml` — analog wenn andere Länder hinzukommen.
- Neue `organizations`-Spalten:
  - `jurisdiction VARCHAR(5) NOT NULL` (ISO 3166-2, z.B. `"at-8"`). Nicht aus `region` ableiten — explizit ist sauberer (parsing-frei, validierbar).
  - `identity_salt VARCHAR(64) NOT NULL` (per-Tenant-Salt für Hash-Strategie — siehe §7.1).
- Loader im Service-Layer: `services/jurisdiction.py:load_jurisdiction(code) → dict` mit Deep-Merge country+region, LRU-gecached. Convenience-Method auf Organization-Model: `organization.jurisdiction_yaml()` ruft den Loader. Aufruf-Site liest `org.jurisdiction_yaml()["identity"]`. Voll dokumentiert in §3.6.
- Migration `20260516_0010_identity` setzt für Krummelus `jurisdiction='at-8'` und generiert `identity_salt` via `secrets.token_hex(32)`. Default-Werte für andere bestehende Tenants müssen vor Migration-Run vergeben werden (Pre-Migration-Sanity-Check oder Migration-Failure).

---

## 3. Datenmodell

### 3.1 Schema-Übersicht

```
shiksha_core.identity_persons          ← Stammdaten + Verifikations-Status
                                         (KEIN doc_number raw — siehe §3.2)
shiksha_core.identity_documents        ← Datei-Refs + OCR/MRZ-Output
                                         (mrz_parsed whitelist-gefiltert)
shiksha_core.identity_authorizations   ← Wer darf was (target_type/id, valid_from/to)
shiksha_core.identity_audit_log        ← DSGVO-Pflicht, jeder Zugriff,
                                         Retention 7 Jahre (Art. 5(2) DSGVO)
```

Plus Erweiterung an `shiksha_core.organizations`:

```
organizations.jurisdiction VARCHAR(5) NOT NULL   ← ISO 3166-2 (z.B. "at-8" für
                                                   Vorarlberg, "de" als
                                                   reiner Country-Code möglich).
                                                   NOT NULL — jeder Tenant
                                                   muss zugeordnet sein.
                                                   Backfill für bestehende
                                                   Tenants in Migration 0010
                                                   (Krummelus → "at-8").
organizations.identity_salt VARCHAR(64) NOT NULL ← Per-Tenant-Salt für
                                                   doc_number_hash (siehe §7.1).
                                                   Beim Tenant-Anlegen via
                                                   secrets.token_hex(32)
                                                   generiert, niemals an
                                                   Frontend/API exportiert.
```

Plus Erweiterung an `shiksha_core.persons`:

```
persons.metadata_.avatar = {           ← JSON-Sub-Objekt (kein Migrations-Schema)
    color_seed: "a3f2c8",              ← deterministisch aus persons.id
    ring_color: "#7b4cff",             ← optional, gruppen-basiert
}
```

### 3.2 `identity_persons`

[TODO-VERIFY] — exakte Spalten nach Schema-Dump tightenen. Konzept-Skelett:

```sql
CREATE TABLE shiksha_core.identity_persons (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_org_id   UUID NOT NULL REFERENCES organizations(id),
    full_name       VARCHAR NOT NULL,
    birth_date      DATE,
    nationality     VARCHAR,                       -- aus MRZ wenn vorhanden
    doc_kind        VARCHAR,                       -- aus MRZ: "personalausweis"/"reisepass"
    doc_number_hash VARCHAR(24),                   -- sha256(doc_number_normalized
                                                   --        + tenant_salt)[:24]
                                                   -- KEIN raw doc_number gespeichert.
                                                   -- Datensparsamkeit per DSB-Praxis
                                                   -- (Bescheid DSB-D123.901/0002-DSB/2019).
                                                   -- Re-Verifikation am Eingangs-Tablet
                                                   -- via re-hash + lookup: Ausweis
                                                   -- erneut scannen → selbes Hash →
                                                   -- Match in DB.
                                                   -- VARCHAR statt CHAR damit
                                                   -- jurisdictions andere
                                                   -- hash_length_hex wählen können.
    doc_expiry      DATE,                          -- aus MRZ

    consent_given       BOOLEAN NOT NULL DEFAULT FALSE,
    consent_text        TEXT,                      -- verbatim Consent-Wortlaut
    consent_given_at    TIMESTAMP WITH TIME ZONE,
    structured_delete_at TIMESTAMP WITH TIME ZONE, -- Service-side aus jurisdiction
                                                   -- berechnet (nicht DB-Default),
                                                   -- z.B. AT = linked_person.exit_date
                                                   -- + 3 Jahre, oder verified_at + 3a
                                                   -- wenn nicht-linked.
                                                   -- Vor Verifikation: created_at + 30d.

    verification_status VARCHAR NOT NULL DEFAULT 'pending'
                        CHECK (verification_status IN ('pending', 'verified', 'rejected')),
    verified_by_operator_id  UUID REFERENCES operators(id),
    verified_at         TIMESTAMP WITH TIME ZONE,

    linked_person_id    UUID REFERENCES persons(id) ON DELETE SET NULL,  -- ADR-2

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_identity_persons_tenant ON shiksha_core.identity_persons(tenant_org_id);
CREATE INDEX idx_identity_persons_status ON shiksha_core.identity_persons(verification_status)
    WHERE verification_status = 'pending';
CREATE INDEX idx_identity_persons_linked ON shiksha_core.identity_persons(linked_person_id)
    WHERE linked_person_id IS NOT NULL;
```

Felder, die [TODO-VERIFY] gegen Schema-Dump brauchen: ob `nationality` Free-Text oder ISO-3166 ist; ob `doc_number` Eindeutigkeits-Constraint hat; ob `auto_delete_at` einen DB-Default oder Service-side gesetzt wird.

### 3.3 `identity_documents`

[TODO-VERIFY] Konzept-Skelett:

```sql
CREATE TABLE shiksha_core.identity_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_person_id  UUID NOT NULL REFERENCES identity_persons(id) ON DELETE CASCADE,
    doc_kind        VARCHAR NOT NULL
                    CHECK (doc_kind IN ('id_front', 'id_back', 'selfie', 'passport', 'other')),

    file_ref        VARCHAR NOT NULL,              -- Pfad oder S3-Key (siehe §3.5)
    mime_type       VARCHAR NOT NULL,
    file_size_bytes BIGINT NOT NULL,

    ocr_output      TEXT,                          -- raw tesseract-stdout
    ocr_confidence  NUMERIC(5, 2),                 -- 0.00–100.00
    mrz_parsed      JSONB,                         -- TD1/TD3-Parser-Output,
                                                   -- WHITELIST-gefiltert auf
                                                   -- jurisdiction.mrz_fields_to_store.
                                                   -- Implementierung:
                                                   --   services/identity_ocr.py
                                                   --   :_filter_mrz_to_whitelist(parsed,
                                                   --                             allowed)
                                                   -- wird VOR jedem Insert aufgerufen.
                                                   -- Raw-doc_number darf NIE in
                                                   -- mrz_parsed landen — nur als
                                                   -- doc_number_hash in
                                                   -- identity_persons (siehe §3.2).
    mrz_check_ok    BOOLEAN,                       -- Check-Digit-Verifikation

    uploaded_by_operator_id  UUID NOT NULL REFERENCES operators(id),
    uploaded_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    file_delete_at  TIMESTAMP WITH TIME ZONE NOT NULL  -- Service-side aus
                                                       -- jurisdiction.retention
                                                       -- .scan_files_days
                                                       -- (AT: 30d nach upload).
                                                       -- Files weg, JSONB-Metadata
                                                       -- bleibt im Record.
);

CREATE INDEX idx_identity_documents_person ON shiksha_core.identity_documents(identity_person_id);
CREATE INDEX idx_identity_documents_file_expiry ON shiksha_core.identity_documents(file_delete_at)
    WHERE file_ref IS NOT NULL;
CREATE UNIQUE INDEX uq_identity_documents_person_kind
    ON shiksha_core.identity_documents(identity_person_id, doc_kind)
    WHERE doc_kind IN ('id_front', 'id_back', 'selfie');
```

Der UNIQUE-Index sichert, dass pro Identity nur jeweils ein `id_front`, `id_back`, `selfie` existiert (Re-Upload überschreibt — siehe §4.2 Upload-Flow).

Two-Tier-Retention: nach `file_delete_at` wird `file_ref` `NULL` gesetzt + Datei vom Disk gelöscht, **aber der Record bleibt** mit `mrz_parsed`/`ocr_confidence`/`uploaded_at` als Audit-Nachweis. Erst wenn `identity_persons.structured_delete_at` durch ist, wird der Document-Record per Cascade entfernt.

### 3.4 `identity_authorizations`

[TODO-VERIFY] Konzept-Skelett:

```sql
CREATE TABLE shiksha_core.identity_authorizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_org_id   UUID NOT NULL REFERENCES organizations(id),

    subject_identity_person_id  UUID NOT NULL REFERENCES identity_persons(id) ON DELETE CASCADE,

    target_type     VARCHAR NOT NULL
                    CHECK (target_type IN ('child', 'booking', 'lesson', 'global')),
    target_id       UUID,                          -- NULL für target_type='global'

    auth_method     VARCHAR NOT NULL DEFAULT 'ausweis_scan'
                    CHECK (auth_method IN ('ausweis_scan', 'passkey_signed', 'manual_override')),
                    -- 'passkey_signed' reserviert für Phase 2.1 (ADR-1)

    valid_from      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    valid_to        TIMESTAMP WITH TIME ZONE,
    revoked_at      TIMESTAMP WITH TIME ZONE,
    revoked_by_operator_id  UUID REFERENCES operators(id),
    revoke_reason   TEXT,

    granted_by_operator_id  UUID NOT NULL REFERENCES operators(id),
    granted_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    notes           TEXT
);

CREATE INDEX idx_authz_subject ON shiksha_core.identity_authorizations(subject_identity_person_id)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_authz_target ON shiksha_core.identity_authorizations(target_type, target_id)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_authz_tenant_active ON shiksha_core.identity_authorizations(tenant_org_id)
    WHERE revoked_at IS NULL AND (valid_to IS NULL OR valid_to > NOW());
```

`target_type='global'` mit `target_id=NULL` bedeutet "darf alle Kinder/Buchungen/Lessons innerhalb des Tenants" — z. B. ein Co-Elter mit voller Sorgeberechtigung. [TODO-VERIFY] ob das Original den globalen Pfad nutzt.

### 3.5 `identity_audit_log`

[TODO-VERIFY] Konzept-Skelett:

```sql
CREATE TABLE shiksha_core.identity_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_org_id   UUID NOT NULL REFERENCES organizations(id),

    actor_operator_id   UUID REFERENCES operators(id),   -- NULL für system-Actions
    actor_kind          VARCHAR NOT NULL DEFAULT 'operator'
                        CHECK (actor_kind IN ('operator', 'system', 'subject_self')),

    action          VARCHAR NOT NULL,              -- siehe Action-Liste unten
    target_kind     VARCHAR NOT NULL,              -- 'identity_person' / 'identity_document' / 'identity_authorization'
    target_id       UUID NOT NULL,

    details         JSONB,                         -- action-spezifisch (z. B. {old_status, new_status})

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_target ON shiksha_core.identity_audit_log(target_kind, target_id);
CREATE INDEX idx_audit_actor ON shiksha_core.identity_audit_log(actor_operator_id, created_at DESC);
CREATE INDEX idx_audit_tenant_time ON shiksha_core.identity_audit_log(tenant_org_id, created_at DESC);
```

**Action-Liste (DSGVO-Mindestumfang):**

- `identity_person.create` / `update` / `delete` / `read`
- `identity_document.upload` / `read` / `delete`
- `identity_authorization.grant` / `revoke` / `read`
- `identity_verification.approve` / `reject`

Jeder `GET`-Endpoint, der Identity-Daten zurückgibt, schreibt einen `.read`-Eintrag mit dem aufrufenden Operator als Actor. [TODO-VERIFY] ob das Original schon `.read` loggt oder nur Write-Actions.

### 3.6 Edition-Config-Layer (Jurisdictions)

ADR-7 (§2) etabliert die Achse Edition × Jurisdiktion. Datentechnisch:

**Speicher-Form:**

```
server/shiksha_engine/editions/jurisdictions/
├── at.yaml                          ← Country-Default AT
├── at-8.yaml                        ← Vorarlberg-Override (Krummelus)
├── at-9.yaml                        ← Wien-Override (TODO bei erstem Tenant)
├── at/
│   └── consent_de_AT.md             ← Master-Consent-Text, jurisdiction-Referenz
├── de.yaml                          ← TODO bei erstem DE-Tenant
└── de-bw.yaml                       ← TODO bei erstem BW-Tenant
```

**Lookup-Code:** `organizations.jurisdiction` ist `VARCHAR(5) NOT NULL` (ISO 3166-2 — `"at-8"`, `"de-bw"`; ein Country-only `"de"` ist erlaubt, wenn keine regionale Differenzierung nötig).

**Loader-Pattern (Service-Layer):**

```python
# services/jurisdiction.py
from functools import lru_cache
import yaml
from pathlib import Path

JURISDICTIONS_ROOT = Path("editions/jurisdictions")

@lru_cache(maxsize=64)
def load_jurisdiction(code: str) -> dict:
    """
    Lädt jurisdiction-Config mit Deep-Merge.

    code: ISO 3166-2 wie "at-8". Wenn region-Variante existiert:
          country-Default + region-Override.
          Wenn nur country existiert: country zurück.
    """
    parts = code.split("-")
    country = parts[0]
    region  = code if len(parts) > 1 else None

    country_path = JURISDICTIONS_ROOT / f"{country}.yaml"
    if not country_path.exists():
        raise ValueError(f"Unknown jurisdiction country: {country}")
    config = yaml.safe_load(country_path.read_text())

    if region:
        region_path = JURISDICTIONS_ROOT / f"{region}.yaml"
        if region_path.exists():
            override = yaml.safe_load(region_path.read_text())
            _deep_merge(config, override)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Override gewinnt, dict-Werte werden rekursiv gemerged."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
```

**Model-Helper auf Organization:**

```python
# models/organization.py
class Organization(Base):
    # … bestehende Spalten …
    jurisdiction = Column(String(5), nullable=False)
    identity_salt = Column(String(64), nullable=False)

    def jurisdiction_yaml(self) -> dict:
        """Liefert die geloadete jurisdiction-Config (LRU-gecached)."""
        from shiksha_engine.services.jurisdiction import load_jurisdiction
        return load_jurisdiction(self.jurisdiction)
```

**Aufruf-Pattern aus Providern und Services:**

```python
policy = operator.organization.jurisdiction_yaml()["identity"]
retention_days = policy["retention"]["scan_files_days"]
hash_len = policy["hash_length_hex"]
allowed_mrz = policy["mrz_fields_to_store"]
```

**LRU-Cache-Invalidierung:** Bei Code-Deploy wird der Process neu gestartet (systemd restart), der Cache leert sich automatisch. Bei Live-YAML-Editing (selten) muss `load_jurisdiction.cache_clear()` aufgerufen werden — eigener Admin-Endpoint optional, alternativ Service-Restart.

**Fallback-Verhalten:** Wenn `<country>.yaml` nicht existiert → `ValueError` beim Lookup → 500 beim API-Call. Kein silent default — eine neue Edition ohne Jurisdiction-Config ist ein Konfigurationsfehler, kein Laufzeitthema.

### 3.7 File-Storage für Dokumente

Empfehlung: gleiches Pattern wie für andere Uploads in Shiksha (vermutlich `server/uploads/identity/<uuid>/<doc_kind>.<ext>`, [TODO-VERIFY] gegen bestehende Konvention). DSGVO-Pflicht: Files müssen mit `identity_documents.file_delete_at` verknüpft sein und vom Tier-1-Cleanup-Job mit-entfernt werden (siehe §7.4).

`identity_documents.file_ref` enthält den relativen Pfad ab Storage-Root. Direkter Filesystem-Zugriff vermieden — Service-Schicht (`identity_query.get_document_file(doc_id) → bytes`) kapselt I/O.

---

## 4. Endpoints

Basis-Pfad: `/api/v1/identity/`. Auth via JWT (Operator-Token), `role_scope`-geprüft.

### 4.1 Person-CRUD

| Method | Pfad | Auth-Scope | Zweck |
|---|---|---|---|
| `POST`  | `/persons` | `leitung`, `paedagogin` | Identity-Person anlegen (Step 1 des Wizards) |
| `GET`   | `/persons` | `leitung`, `paedagogin` | Liste mit Filtern (`?status=pending`, `?linked=false`) |
| `GET`   | `/persons/{id}` | `leitung`, `paedagogin` | Detail mit Documents + Authorizations |
| `PATCH` | `/persons/{id}` | `leitung`, `paedagogin` | Stammdaten ändern (vor Verifikation) |
| `DELETE` | `/persons/{id}` | `leitung` | Hard-Delete inkl. Documents (DSGVO) |
| `POST`  | `/persons/{id}/verify` | `leitung`, `paedagogin` | Mitarbeiter-Bestätigung (Step 3 des Wizards) |
| `POST`  | `/persons/{id}/reject` | `leitung`, `paedagogin` | Verifikation ablehnen mit Begründung |

### 4.2 Document-Upload

| Method | Pfad | Auth-Scope | Zweck |
|---|---|---|---|
| `POST` | `/persons/{id}/upload?doc_kind=id_front\|id_back\|selfie` | `leitung`, `paedagogin` | Datei-Upload + OCR/MRZ-Trigger (sync oder async — siehe §5.2) |
| `GET`  | `/persons/{id}/documents` | `leitung`, `paedagogin` | Liste der Documents (Metadata) |
| `GET`  | `/documents/{id}/file` | `leitung`, `paedagogin` | Datei-Inhalt (gestreamt) — schreibt `read`-Audit-Eintrag |
| `DELETE` | `/documents/{id}` | `leitung` | Document hard-löschen (DSGVO-Korrekturpfad) |

### 4.3 Authorizations

| Method | Pfad | Auth-Scope | Zweck |
|---|---|---|---|
| `POST` | `/authorizations` | `leitung` | Berechtigung erteilen (`subject_identity_person_id`, `target_type`, `target_id`, optional `valid_to`) |
| `GET`  | `/authorizations` | `leitung`, `paedagogin` | Liste mit Filtern (`?target_type=child&target_id=...`, `?subject=...`) |
| `GET`  | `/authorizations/{id}` | `leitung`, `paedagogin` | Detail |
| `DELETE` | `/authorizations/{id}` | `leitung` | Widerruf (setzt `revoked_at`, schreibt Audit-Eintrag) |

### 4.4 Audit-Log

| Method | Pfad | Auth-Scope | Zweck |
|---|---|---|---|
| `GET` | `/audit-log` | `leitung` only | Filterbar nach `?target_kind`, `?target_id`, `?actor_operator_id`, `?from`, `?to`. Pagination via Cursor. |

### 4.5 Heim-Provider-Endpoint (5.5.6.6.a)

`provider("identity.summary")` registriert sich im bestehenden Provider-Registry. Datenform:

```json
{
  "pending_count": 3,
  "expiring_soon_count": 1,
  "subtitle": "3 zu prüfen · 1 läuft ab"
}
```

`expiring_soon_count` = Identities mit `doc_expiry` in den nächsten 30 Tagen. [TODO-VERIFY] ob 30 Tage ein sinnvoller Default ist (kann via `editions/kita.yaml` parametrisiert werden).

---

## 5. Flows

### 5.1 Abholer-Erfassung (3-Step-Wizard)

```
Step 1: Person & Consent (UI)
  └─ POST /identity/persons
     body: {full_name, birth_date, consent_text, consent_given: true}
     ← {id, verification_status: 'pending', auto_delete_at: ...}

Step 2: Ausweis-Scan (UI, zwei Captures in einem UI-Step)
  ├─ POST /identity/persons/{id}/upload?doc_kind=id_front
  │  body: multipart/form-data, file=<png|jpg>
  │  ← {document_id, ocr_confidence, mrz_parsed: null}
  └─ POST /identity/persons/{id}/upload?doc_kind=id_back
     body: multipart/form-data, file=<png|jpg>
     ← {document_id, ocr_confidence, mrz_parsed: {birth_date, nationality, doc_number, doc_expiry, ...}, mrz_check_ok: true}
     Side-Effect: auto-fill identity_persons.{birth_date, nationality, doc_number, doc_expiry}
                  wenn diese im POST /persons nicht gesetzt waren oder leer.
                  Nie überschreiben falls bereits manuell gesetzt.

Step 3: Selfie + Bestätigung (UI)
  ├─ POST /identity/persons/{id}/upload?doc_kind=selfie
  │  ← {document_id, ocr_confidence: null, mrz_parsed: null}
  └─ POST /identity/persons/{id}/verify
     body: {} (Tap durch Mitarbeiter)
     ← {verification_status: 'verified', verified_at, verified_by_operator_id, auto_delete_at: <verlängert>}
```

[TODO-VERIFY] welcher Audit-Eintrag pro Schritt geschrieben wird (Original-Verhalten als Referenz).

### 5.2 OCR/MRZ — sync oder async?

**Empfehlung:** **sync** für 5.5.6, **async** als Optimierung in Phase 2.

**Begründung:** OCR auf einem Tablet-foto eines Ausweises dauert ~1-2 s mit `tesseract --psm 6`. Das ist akzeptabel als blocking Call innerhalb des Wizards (UI zeigt Spinner). Async + Polling = Komplexität ohne UX-Mehrwert.

Wenn das Original bereits async-Pfad mit Job-Queue hat: behalten. [TODO-VERIFY] gegen Schema-Dump.

### 5.3 Authorization erstellen

```
POST /identity/authorizations
body: {
    subject_identity_person_id: <uuid>,
    target_type: 'child',
    target_id: <uuid_des_kindes>,
    valid_to: '2026-12-31T23:59:59+02:00',   # optional, NULL = unbefristet
    notes: 'Großmutter, holt Mo+Mi ab'
}
← {id, granted_at, granted_by_operator_id}
```

**Pre-Condition:** `identity_persons.verification_status = 'verified'`. Service-Layer wirft 422 wenn nicht erfüllt.

### 5.4 Authorization widerrufen

```
DELETE /identity/authorizations/{id}
body: {revoke_reason: 'Sorgerechtsänderung 2026-06-01'}
← 204 No Content
```

Setzt `revoked_at` und `revoked_by_operator_id`, **löscht nicht**. Audit-Spur bleibt.

### 5.5 Verifikations-Check am Eingang (Zukunft)

Out of scope für 5.5.6 (das ist `/api/v1/identity/check`, kommt mit dem späteren Eingangs-Tablet-Flow). Endpoint-Skelett für Forward-Compat reserviert, Implementierung nicht in 5.5.6.

---

## 6. Berechtigungs-Modell

### 6.1 role_scope für Identity-Endpoints

Drei Identity-relevante Rollen-Werte (analog zu bestehender role_scope-Konvention):

- **`leitung`** — voller Schreibzugriff inkl. Person-Löschung, Authorization-Erteilen/Widerrufen, Audit-Log-Lesen.
- **`paedagogin`** — Lesen + Verifikations-Tap + Document-Upload. **Kein** Authorization-Erteilen, **keine** Hard-Deletes.
- **`developer`** — wie `leitung`.

Mappung in `editions/kita.yaml` analog zu bestehenden Heim-Karten-Definitionen. [TODO-VERIFY] welche role_scope-Werte das System aktuell kennt.

### 6.2 target_type-Wertebereich

Aus dem Original (ADR-1) übernommen:

- `child` — Berechtigung für einen Klienten (`persons.kind='klient'`)
- `booking` — Berechtigung für eine spezifische Buchung (Zeit-begrenzt)
- `lesson` — Berechtigung für einen Kurs/Lesson (wiederkehrend)
- `global` — Berechtigung für alle Kinder im Tenant (Voll-Sorge-Eltern)

[TODO-VERIFY] ob Original noch andere Werte hat.

### 6.3 Phase-2-Erweiterung (Forward-Compat)

`auth_method` als Diskriminator (ADR-1) — Passkey-signierte Authorizations werden in Phase 2.1 als `'passkey_signed'` eingeführt. Das Schema hält die Spalte schon jetzt vor.

---

## 7. DSGVO

### 7.1 Pflicht-Felder

- `consent_text`: verbatim Wortlaut des Einwilligungs-Texts, der dem User angezeigt wurde, gespeichert auf Person-Level (nicht referenziert, damit spätere Text-Änderungen rückwirkende Einwilligungen nicht verfälschen). Master-Text liegt jurisdiction-spezifisch unter `jurisdiction.consent_text_path` (AT-Default: `editions/jurisdictions/at/consent_de_AT.md`).
- `consent_given_at`: Zeitstempel der Einwilligung.
- `structured_delete_at`: Service-side berechnet beim Verify/Update. AT-Default: `linked_person.exit_date + 3 Jahre` (§ 1489 ABGB), oder bei nicht-verknüpften Abholern `verified_at + 3 Jahre`. Vor Verifikation: `created_at + 30 Tage` (verwaiste Drafts).
- `identity_documents.file_delete_at`: Service-side `uploaded_at + jurisdiction.retention.scan_files_days`. AT-Default: 30 Tage (DSB-Bescheid DSB-D123.901/0002-DSB/2019).
- DSFA-Pflicht (`jurisdiction.dsfa_required`): Datenschutz-Folgenabschätzung muss vor Live-Schaltung für die Tenant-Jurisdiktion existieren. Wird nicht im Code modelliert, sondern als Process-Gate vor 5.5.6.6.b geprüft (siehe §14.2.6).

**Hash-Strategie für `doc_number_hash`:**

```
doc_number_hash = sha256(doc_number_normalized + tenant_salt)[:hash_length_hex]
```

- `doc_number_normalized`: kanonische Form via `normalize_doc_number()` (siehe unten). Verhindert Hash-Drift durch OCR-Artefakte wie eingestreute Leerzeichen oder Case-Wechsel zwischen Re-Scans.
- `tenant_salt`: in `organizations.identity_salt` (siehe §3.1), beim Tenant-Anlegen via `secrets.token_hex(32)` generiert.
- `hash_length_hex`: aus `jurisdiction.hash_length_hex` (AT-Default: 24 → 96-bit).
- `hash_algorithm`: aus `jurisdiction.hash_algorithm` (AT-Default: sha256).
- **Tenant-Salt ist niemals exportierbar** — kein API-Endpoint liest oder schreibt ihn, keine Logs, kein Audit-Log-Detail-Feld. Nur die DB-Spalte. Bei Tenant-Delete bleibt das Salt mit dem Org-Record gelöscht; alle bisherigen Hashes werden damit irreversibel anonym.
- Pro-Tenant-Salt verhindert Cross-Tenant-Identity-Lookup: dieselbe Person mit demselben Ausweis bekommt in zwei Tenants unterschiedliche Hashes. **Feature, nicht Bug** — DSGVO-Datentrennung.

**Normalisierungs-Funktion (kanonisch, lebt in `services/identity_ocr.py`):**

```python
import re

def normalize_doc_number(raw: str) -> str:
    s = raw.strip()                 # äußerer Whitespace
    s = re.sub(r"\s+", "", s)       # innerer Whitespace (OCR-Artefakte)
    s = s.upper()                   # case-folding
    return s
```

Drei Transforms, in dieser Reihenfolge:

1. **Äußerer Whitespace** — `strip()`: führende/trailing Spaces aus OCR-Padding.
2. **Innerer Whitespace** — `re.sub(r"\s+", "", s)`: OCR streut bei niedrig-Auflösung Spaces in MRZ-Strings ein (z.B. `"L01 X00 T47"` statt `"L01X00T47"`); ohne diesen Schritt würde dasselbe Dokument bei Re-Scan einen anderen Hash erzeugen.
3. **Case-Folding** — `upper()`: deutscher Personalausweis und Reisepass nutzen Großbuchstaben, aber OCR-Tessearct gibt teils Kleinbuchstaben zurück bei schwachem Kontrast.

**Bewusst NICHT in der Normalisierung:**

- Keine Sonderzeichen-Filterung (`-`, `/`) — bleiben Teil der Doc-Number, falls vorhanden.
- Keine führende-Nullen-Reduktion — der deutsche Personalausweis hat führende Buchstaben (`L01X00T47`), nicht Zahlen; bei Reisepässen würde Nullen-Strip die Eindeutigkeit brechen.
- Keine Unicode-Normalisierung (NFC/NFD) — MRZ ist ASCII-only per ICAO 9303.

### 7.2 Audit-Pflicht

Jeder Lese-Zugriff auf Person-Stammdaten, Documents oder Authorizations schreibt einen `*.read`-Eintrag (siehe §3.5 Action-Liste). Jede Schreib-Aktion ebenso.

### 7.3 Recht auf Löschung

`DELETE /identity/persons/{id}` (nur `leitung`):

1. Löscht alle Document-Files vom Filesystem.
2. `DELETE` auf `identity_persons` cascadet zu `identity_documents` und `identity_authorizations`.
3. **Audit-Log bleibt** — DSGVO erlaubt Audit-Retention auch nach Subject-Löschung (legitimes Interesse + gesetzliche Pflicht).
4. **Hash-Verweis bleibt im Audit-Log.** `identity_audit_log.details.doc_number_hash` darf den (jetzt verwaisten) Hash behalten. Begründung: ohne Tenant-Salt + Original-Dokument ist der Hash irreversibel — kein Personenbezug mehr im DSGVO-Sinne (Art. 4 Nr. 1, "identifizierte/identifizierbare Person"). Das ist konsistent mit Erwägungsgrund 26 zu anonymisierten Daten. Der Hash bleibt nutzbar als Audit-Marker (z.B. "selbiger Ausweis tauchte später wieder auf"), ohne die ursprüngliche Person wiederherstellbar zu machen.
5. Audit-Eintrag `identity_person.delete` mit Operator und Begründung.

### 7.4 Cleanup-Job — Three-Tier (Phase 1.5 noch nicht in Scope)

Three-Tier nach jurisdiction-spezifischen Fristen:

| Stufe | Was wird gelöscht | Trigger | AT-Default |
|---|---|---|---|
| **Tier 1** | `identity_documents.file_ref` + Disk-Datei | `file_delete_at < NOW()` | 30 Tage nach Upload |
| **Tier 2** | `identity_persons` + cascade (`documents`, `authorizations`) | `structured_delete_at < NOW()` | 3 Jahre nach Betreuungs-Ende / Verify |
| **Tier 3** | `identity_audit_log` | `created_at + jurisdiction.retention.audit_log_years < NOW()` | 7 Jahre (gesetzlich Art. 5(2) DSGVO) |

**Tier-Reihenfolge wichtig:** Tier 1 läuft selbständig (Files weg, Metadata bleibt). Tier 2 wartet auf Tier 1 (kein File mehr da, jetzt darf Record sterben). Tier 3 ist eigener Lauf, unabhängig — Audit-Log überlebt seinen Subject um Jahre.

Implementierung **nicht in 5.5.6.x** — als Tech-Debt `T-011` in `SHIKSHA_TECH_DEBT.md` mit drei Sub-Tasks (`T-011-tier1`/`-tier2`/`-tier3`). Vor Tier-1-Live ist Krummelus formal in Auto-Delete-30d-Modus, aber kein Job läuft → ein Nicht-Löschen kann DSB-relevant werden. Workaround bis Cron-Job existiert: manueller Lauf via Admin-Endpoint oder einmaliges Skript.

---

## 8. Heim-Karten (5.5.6.6.a)

Eine neue Karte in `editions/kita.yaml`:

```yaml
identitaeten_pruefen:
  card_id: identitaeten_pruefen
  title: "Identitäten prüfen"
  subtitle: "{pending_count} zu prüfen · {expiring_soon_count} läuft ab"
  icon: shield-check
  url: /identity.html?filter=pending
  role_scope: [leitung, paedagogin, developer]
  time_priority: 60                       # niedriger als wer_ist_da (100), höher als compliance
  provider: identity.summary
```

Falls bereits eine `abholer_pruefen`-Karte ohne Provider existiert (Handoff §5 erwähnt): die wird an `identity.summary` angeschlossen und `identitaeten_pruefen` weggelassen. [TODO-VERIFY] welcher Name passt.

Provider-Logik in `services/heim_providers.py`:

```python
@register_provider("identity.summary")
def identity_summary(operator: Operator) -> dict:
    tenant = operator.organization
    tz = ZoneInfo(tenant.timezone or "UTC")
    today = datetime.now(tz=tz).date()
    cutoff = today + timedelta(days=30)

    pending = session.query(IdentityPerson).filter(
        IdentityPerson.tenant_org_id == tenant.id,
        IdentityPerson.verification_status == 'pending',
    ).count()

    expiring = session.query(IdentityPerson).filter(
        IdentityPerson.tenant_org_id == tenant.id,
        IdentityPerson.verification_status == 'verified',
        IdentityPerson.doc_expiry.between(today, cutoff),
    ).count()

    return {
        "pending_count": pending,
        "expiring_soon_count": expiring,
        "subtitle": f"{pending} zu prüfen · {expiring} läuft ab",
    }
```

Pattern-Authority: `attendance_summary` in `heim_providers.py` Stand `eb9c851` (Tenant-TZ-Lookup). **Nach T-009-Fix** denselben Helper nutzen.

---

## 9. Bridge-Trim (5.5.6.6.b)

Schritt-für-Schritt analog 5.5.5.6.b:

1. `routers/bridge.py` öffnen, `ALLOWED_PREFIXES` finden.
2. `'kita/identity'` entfernen.
3. Tests in `tests/test_bridge.py` durchgehen, Vorkommen von `kita/identity` durch `kita/push` oder `kita/compliance` ersetzen (per `sed -i`).
4. Reject-Regression-Test ergänzen: `GET /bridge/kita/identity → 404`.
5. Smoke nach Deploy: `bridge/kita/push` weiter durchgereicht, `bridge/kita/identity` reject.

**Voraussetzung:** alle anderen 5.5.6-Sub-Drops sind deployed und `/api/v1/identity/*` läuft live. Vorher Trim = 404 für Frontend.

---

## 10. Avatar-Engine (5.5.6.5)

### 10.1 Refactor-Scope

**Move:**
```
server/paedagogen_ui/shiksha-avatar.js
  → server/shiksha_engine/frontend/shiksha-avatar.js
```

**Edit:**
- Import-Pfade in HTML-Files die das Script ziehen.
- `shiksha-client.js` ergänzen um Avatar-Helper-Methoden (`renderAvatar(person)`, `setRingColor(personId, color)`).

### 10.2 Integration in bestehende Surfaces

- `anwesenheit.html`: CSS-`filter`-basierte Saturation durch `ShikshaAvatar.render(el, {isAbsent: !present})` ersetzen.
- `personen.html`: alle `<img>`-Person-Icons durch `<div data-shiksha-avatar data-name="…">` ersetzen.
- `identity.html` (5.5.6.4): nach Verifikation Avatar mit deterministischem Color-Seed rendern.

### 10.3 Logik-Änderungen

**Keine.** Engine-Verhalten bleibt identisch. Wenn beim Refactor Bugs auffallen: separater Mini-Sprint, nicht in 5.5.6.5 verschnüren.

### 10.4 Server-Side Avatar-Vorbereitung

Optional in 5.5.6.5: `services/identity_avatar.py` mit:

```python
def compute_avatar_metadata(person: Person) -> dict:
    """Deterministische Avatar-Felder aus Person ableiten."""
    color_seed = hashlib.sha256(str(person.id).encode()).hexdigest()[:6]
    ring_color = person.group.color if person.group else None
    return {"color_seed": color_seed, "ring_color": ring_color}
```

Beim `Person.create()` und `Person.update()` automatisch `metadata_.avatar` setzen (ADR-6).

---

## 11. Akzeptanzkriterien

### Modul-Schluss (5.5.6 komplett)

1. ✅ `SHIKSHA_IDENTITY_SPEC.md` v1.0 in `docs/specs/` (5.5.6.0)
2. ✅ Alembic-Migration `0010_identity` mit allen 4 Tabellen + Indices + Constraints
3. ✅ Models, Schemas, Services, Router in der bekannten Layout-Struktur
4. ✅ 14 Endpoints implementiert + dokumentiert (siehe §4)
5. ✅ ~20 Tests grün (CRUD, Berechtigungs-Pflicht, OCR-Confidence-Mock, MRZ-Parse, Auth-Revoke, Audit-Pflicht, role_scope-Reject, Lifecycle-Verify) plus ≥5 Hash-Pflicht-Tests:
   - `normalize_doc_number("  L01X00T47  ")` → `"L01X00T47"`
   - `normalize_doc_number("L01 X00 T47")` → `"L01X00T47"` (innerer Whitespace)
   - `normalize_doc_number("l01x00t47")` → `"L01X00T47"` (case-fold)
   - `normalize_doc_number("L01\tX00\nT47")` → `"L01X00T47"` (Tabs/Newlines via `\s+`)
   - Cross-Tenant-Reject: gleicher `doc_number` in zwei Tenants → unterschiedliche Hashes (Salt-Trennung)
6. ✅ Wizard-Frontend `identity.html` mit 3-Step-UI funktioniert end-to-end gegen Live-API
7. ✅ Avatar-Engine in `frontend/`, in `anwesenheit.html` + `personen.html` integriert
8. ✅ Heim-Karte „Identitäten prüfen" in `kita.yaml`, Provider live
9. ✅ Bridge `kita/identity` aus Whitelist entfernt
10. ✅ Test-Suite gesamt grün (Basis 207 + T-009 +1-2 + ≥20 Identity-Tests ≈ ≥228)
11. ✅ Legacy `server/identity_*` als `T-010` in `SHIKSHA_TECH_DEBT.md` archiviert
12. ✅ `jurisdictions/at.yaml` + `jurisdictions/at-8.yaml` im Repo, `organizations.jurisdiction='at-8'` für Krummelus gesetzt (Migration `0010` Backfill)
13. ✅ DSB-Pre-Rollout-Query gestellt + Antwort dokumentiert (BLOCKER für 5.5.6.6.b, AT-Tenants only)
14. ✅ DSFA für AT-Identity-Modul in `docs/dsfa/` abgelegt

---

## 12. Sub-Drop-Aufteilung

Vorgeschlagene Reihenfolge (nach T-009 Mini-Sprint):

```
5.5.6.0  Spec-Lieferung                  Diese Datei nach docs/specs/.
                                          Lese-Runde mit Thomas vor Code.
                                          Aufwand: lese + diskutiere, 0 LOC.

5.5.6.1  DB + Models + Schemas           Alembic 0010_identity.
                                          IdentityPerson/Document/Authorization/AuditLog Models.
                                          Pydantic-Schemas (Create/Out/Patch/AuthOut).
                                          ~6 Smoke-Tests (Migration up/down, FK-Cascade,
                                          Index-Existence). Kein Endpoint.
                                          Aufwand: ~3-4h.

5.5.6.2  Endpoints + OCR + Tests         Router identity.py mit allen 14 Endpoints.
                                          Service identity_query.py (linker, summary, list).
                                          Service identity_ocr.py (tesseract + MRZ-Parser).
                                          ~20 Tests (siehe §11).
                                          Aufwand: ~6-8h.

5.5.6.3  Greenfield-Import               SKIP — keine Legacy-Daten zu importieren.
                                          (Reserviert falls eine Edition später Identity-
                                           Daten mitbringt.)

5.5.6.4  Frontend Surface                identity.html (3-Step-Wizard).
                                          shiksha-client.js-Methoden.
                                          End-to-end gegen Live-API.
                                          Aufwand: ~4-5h.

5.5.6.5  Avatar-Engine-Refactor          File-Move + Import-Anpassung.
                                          Integration in anwesenheit.html + personen.html.
                                          Optional: services/identity_avatar.py.
                                          Aufwand: ~1-2h.

5.5.6.6.a Heim-Karten + Provider         Karte + identity.summary-Provider.
                                          Aufwand: ~1h.

5.5.6.6.b Bridge-Trim                    kita/identity raus, Tests anpassen.
                                          Modul-Schluss.
                                          Aufwand: ~30 Min.
                                          ⚠️ BLOCKER für AT-Tenants:
                                          DSB-Antwort + DSFA müssen
                                          vorliegen (siehe §14.2.6).
```

**Gesamt-Aufwand:** ~15-20 Arbeitsstunden Code, verteilt auf 6 Bundle-Runs an Claude Code.
**Plus Process-Aufwand parallel:** DSB-Anfrage (4-12 Wochen Antwortzeit), DSFA schreiben (~4-8h Mira-Arbeit + ggf. juristische Review). Beides startet mit 5.5.6.0-Spec-Closure, blockiert nur 5.5.6.6.b.

**Reihenfolge-Begründung:** Backend-Stack (.1 → .2) zuerst, dann UI (.4) gegen lebendes Backend, Avatar (.5) als Frontend-Polish, Heim-Karte (.6.a) zeigt das Modul nach außen, Bridge-Trim (.6.b) erst wenn alles steht.

---

## 13. Forward-Compat — Phase 2

### 13.1 Passkey-Authorization

Wenn Phase 2.1 startet (Eltern-Login via Bridge), wird `auth_method='passkey_signed'` aktiviert:

```python
POST /identity/authorizations
body: {
    subject_identity_person_id: <abholer_id>,
    target_type: 'child',
    target_id: <kind_id>,
    auth_method: 'passkey_signed',
    passkey_signature: '<base64-signature>',     # neue Spalte oder JSONB-Detail
    parent_passkey_pubkey: '<base64-pubkey>',
}
```

Schema-Erweiterung:

```sql
ALTER TABLE shiksha_core.identity_authorizations
ADD COLUMN passkey_signature TEXT,
ADD COLUMN passkey_signer_id UUID;  -- FK auf passkey-Tabelle (Phase 2.1)
```

Keine Schema-Migration in `identity_persons` nötig.

### 13.2 Hybrid-Modus (Phase 2.x)

Eltern: Passkey-signiert. Großeltern/Tageseltern ohne Smartphone: weiter Ausweis-Scan (`auth_method='ausweis_scan'`). Mitarbeiter sehen in der Card-View beide Pfade unter „aktive Berechtigungen".

### 13.3 Identity als Login-Mechanismus?

**Out of scope für 5.5.6 + Phase 2.1.** Wenn perspektivisch Abholer-Tablets am Eingang sich gegen `identity_persons` authentifizieren (Passkey-Tap statt Mitarbeiter-Bestätigung), wird das ein eigenständiges Tablet-Modul mit eigenen Auth-Surfaces. Nicht hier spezifizieren.

---

## 14. Open Items (vor 5.5.6.0-Lese-Runde mit Thomas zu klären)

### 14.1 Schema-Verifikation

Alle mit `[TODO-VERIFY]` markierten Stellen werden gegen `cowork_identity_schema_dump.md` (Output von `bundle_identity_schema_verify.md`) getightet. Voraussichtlich:

- Genaue Spaltennamen + Typen (nationality, doc_number, doc_expiry)
- Existenz von Triggern/Stored Procedures
- DSGVO-Default-Fristen (`auto_delete_at`)
- Storage-Pfad-Konvention für Document-Files
- role_scope-Werte und target_type-Werte aus Original

### 14.2 Inhaltliche Fragen für Thomas

1. **`auto_delete_at`-Default:** 365 Tage nach Verifikation sinnvoll? Rechtliche Vorgabe für KiBeG (kinderbetreuungs-relevante Dokumente)? Mein Vorschlag ist konservativ — Bundesländer-spezifische Fristen sind oft kürzer (3-12 Monate nach Beendigung des Betreuungs-Verhältnisses).

2. **Selfie-Speicherung:** das Original speichert ein Selfie. Für die DSGVO-Begründung müsste der Zweck dokumentiert sein („Wiederkennung am Eingang"). Wenn am Eingang faktisch nicht abgeglichen wird, fällt der Zweck weg und das Feld sollte raus.

3. **`target_type='global'`:** Original nutzt das? Wenn nein, vereinfachen wir den ENUM auf `child / booking / lesson` und sparen die Sonder-Logik.

4. **Heim-Karten-Name:** „Identitäten prüfen" vs. „Abholer prüfen" — der zweite Name passt besser zur Kita-Realität, der erste ist generischer für edition-Übergänge (Vereins-Lehrer-Verifikation in Phase 2). Tendiere zu zweitem.

5. **role_scope `paedagogin`:** darf eine Pädagogin Document-Files lesen (also Ausweis-Fotos anschauen)? Oder nur Metadata + Verifikations-Status sehen? DSGVO-konservativ: nur Metadata für `paedagogin`, Files nur für `leitung`.

6. **DSB-Pre-Rollout-Query + DSFA für AT-8 (Krummelus):** `jurisdictions/at.yaml` hat `pre_rollout_authority_query_required: true` und `dsfa_required: true`. Das sind Process-Gates, kein Code:

   - **DSB-Query** an `dsb@dsb.gv.at` vor Live-Schaltung (4-12 Wochen Antwortzeit) — beschreibt das geplante Verarbeitungs-Setup und holt Klarheit über Retention-Auslegung pro Anwendungs-Kontext.
   - **DSFA** (Datenschutz-Folgenabschätzung) muss schriftlich dokumentiert vorliegen. Skelett-Template existiert unter `docs/dsfa/identity-modul-at.md` (v1.0-DRAFT, Stand 2026-05-16); produktiv-fertige Fassung erfordert juristische Begutachtung und Träger-spezifische Ausfüllung der `<<…>>`-Platzhalter.

   Beide blockieren **5.5.6.6.b** (Live-Schaltung) für AT-Tenants, **nicht** 5.5.6.1–.6.6.a (Backend + UI bauen). Mira muss parallel zum Cowork-Lauf die DSB-Anfrage starten.

### 14.3 Reihenfolge-Frage

Sub-Drop 5.5.6.3 (Greenfield-Import) als Skip — bestätigen, dass Krummelus wirklich keine identity-Daten aus alter Welt mitbringt. Wenn doch (`identity_persons.csv` o.ä.), wird das eine reguläre Sub-Drop-Lieferung.

### 14.4 Spec-Status

Diese Datei ist **v0.3-DRAFT**. Tightening-Pfad:

```
v0.1-DRAFT (2026-05-15)    Initial-Draft von Cowork.

v0.2-DRAFT (2026-05-16)    Jurisdictions-Layer eingearbeitet (ADR-7),
                           Three-Tier-Retention, MRZ-Whitelist + Hash,
                           DSB-Anfrage + DSFA als Process-Gates,
                           organizations.jurisdiction-Spalte modelliert.
                           File-Anlagen:
                             editions/jurisdictions/at.yaml
                             editions/jurisdictions/at-8.yaml
                             editions/jurisdictions/at/ (Subdir für
                                                         consent_de_AT.md)

v0.3-DRAFT (2026-05-16)    Hash-Strategie + Edition-Config-Layer explizit:
                             - doc_number_hash VARCHAR(24) (statt CHAR)
                               mit Re-Verifikations-Begründung am Eingangs-
                               Tablet.
                             - sha256(doc_number_normalized + tenant_salt)
                               [:hash_length_hex] dokumentiert; tenant_salt
                               in organizations.identity_salt VARCHAR(64)
                               NOT NULL.
                             - mrz_parsed-Whitelist verweist auf
                               _filter_mrz_to_whitelist() im OCR-Service.
                             - §3.6 NEU: Edition-Config-Layer mit Loader-
                               Code, LRU-Cache, Organization.jurisdiction_
                               yaml()-Method, Deep-Merge-Implementierung.
                             - organizations.jurisdiction von NULL auf
                               NOT NULL verschärft (kein globaler Fallback
                               mehr).
                             - §7.3 Recht-auf-Löschung: Hash bleibt im
                               Audit-Log als irreversibler Marker (kein
                               Personenbezug nach DSGVO Art. 4 + EW 26).
                             - normalize_doc_number() formal definiert
                               (trim + inner-whitespace + upper),
                               5 Hash-Pflicht-Tests in §11 aufgenommen.
                             - Begleit-Dokumente angelegt:
                               docs/dsfa/identity-modul-at.md (v1.0-DRAFT,
                                                               211 Z).
                               docs/dsfa/dsb-anschreiben-at.md (v1.0-DRAFT,
                                                               formales
                                                               Konsultations-
                                                               Schreiben
                                                               Art. 36 DSGVO).
                               editions/jurisdictions/at/consent_de_AT.md
                                                              (v1.0-DRAFT,
                                                               Master-Consent).
                               Alle drei mit <<...>>-Platzhaltern für träger-
                               spezifisches Ausfüllen, juristische Prüfung
                               vor Produktiv-Verwendung erforderlich.

v0.4-DRAFT                 Nach Schema-Dump-Eintreffen, [TODO-VERIFY]
                           aufgelöst, Pattern-Konflikte gegen Repo
                           aufgelöst (siehe Cowork-Handoff §1 für die
                           sieben offenen Punkte: UUID vs Integer-PKs,
                           padagoge vs paedagogin, Underscore- vs Dot-
                           Provider-Names, frontend-Pfad).

v1.0                       Nach Thomas-Review, committed, 5.5.6.0 closed.
                           DSB-Anfrage parallel gestartet (BLOCKER für
                           5.5.6.6.b).
```

---

## 15. Pattern-Quellen + Pre-Drop-Reading

Beim Implementieren der Sub-Drops ist **Code-Pattern aus dem Repo immer autoritativ über diesem Dokument** (Lerneffekt aus 5.5.5.6.a — siehe Handoff §1 „Beobachtungen aus der Implementierung"). Konkret:

- **Decorator-Namen** (`@register_provider` vs `@provider`) → aus `heim_providers.py` Stand `eb9c851`
- **Service-Layer-Pattern** → analog `calendar_query.py` und `attendance_query.py`
- **Router-Pattern** → analog `routers/calendar.py` und `routers/attendance.py`
- **Test-Pattern** → analog `tests/test_calendar.py` und `tests/test_attendance.py`
- **Migration-Pattern** → analog `alembic/versions/2026*_000{5,6,7,8,9}_*.py`

Wenn die Spec im Detail vom existierenden Pattern abweicht: Pattern gewinnt, Spec wird gefixt.

---

**Ende SHIKSHA_IDENTITY_SPEC.md v0.1-DRAFT**

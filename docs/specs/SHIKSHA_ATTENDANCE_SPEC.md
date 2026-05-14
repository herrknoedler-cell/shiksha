# SHIKSHA Attendance — Modul-Spec (Schritt 5.5.5.0)

**Status:** v2 final · 2026-05-14
**Ziel:** Drittes Modul der Phase 1.5. Mira's wichtigste tägliche Surface — wer ist da, wer wann gekommen, wer wann gegangen. Avatar-Engine als visueller Anker. Personalschlüssel-Compliance als Live-Berechnung. Brücke zu Kalender (Urlaub/Abwesenheit) und Personen.

---

## 1. Ziel & Scope

**Was Anwesenheit ist:** Die Frage, die Mira jeden Morgen stellt: "Wer ist heute da?". Ein Tag-zentrisches Modul, das pro Person + pro Tag einen Anwesenheits-Status führt (anwesend, krank, beurlaubt, abwesend, …) plus optionaler Check-In/Check-Out-Zeitstempel. Die UI ist die zweite Surface, die Mira den ganzen Tag offen hat (neben Kalender).

**Cross-Edition-Anspruch:** Datenmodell ist neutral. KITA hat Kinder + Pädagogen. YOGA hat Schüler + Trainer. CAMPING hat Gäste + Personal. Die Status-Werte und der Personalschlüssel sind Edition-konfigurierbar.

**Phase 1 Scope (was JETZT gebaut wird):**

1. Backend mit voller CRUD (`attendance_records`-Tabelle, REST)
2. **Avatar-View** auf Tag-Basis (Mira sieht "Wer ist im Haus?")
3. Sechs Status-Werte für KITA: **anwesend · abwesend · krank · urlaub · fortbildung · gast**
4. Check-In/Check-Out-Buttons (optional, kein Muss)
5. **Live-Personalschlüssel** mit Vorarlberg-KGG-Defaults (für Krummelus-Pilot)
6. **Auto-Sync mit Kalender** — Urlaub/Abwesenheit aus `events` werden als Attendance-Defaults übernommen
7. Daten-Import aus `kita_legacy_anwesenheit` falls vorhanden (Inspect zuerst)
8. Drei Heim-Karten: **Wer ist da · Personalschlüssel · Anwesenheit**

**Explizit NICHT in Phase 1:**

- **Eltern-Self-Check-In** (Eltern kommen, scannen QR-Code) — Phase 2
- **Foto-Anwesenheit** (Mira scannt Kinder-Avatare) — Phase 2 mit Bilddatenbank
- **Historische Analysen** (Anwesenheits-Quote pro Monat, etc.) — Phase 3
- **Predictive: "wer kommt heute wahrscheinlich nicht"** — Phase 3 mit Memory
- **Automatischer Förder-Stundensatz-Berechner** — wird in einem späteren Compliance-Modul angedockt
- **Anwesenheit für mehrere Standorte** — Multi-Standort generell in Phase 2

---

## 2. Datenmodell

### 2.1 `attendance_records`-Tabelle

```sql
CREATE TABLE shiksha_core.attendance_records (
  id              SERIAL PRIMARY KEY,
  tenant_org_id   TEXT NOT NULL REFERENCES organizations(id),

  -- Person + Tag — UNIQUE wird als partial INDEX angelegt (Postgres unterstützt
  -- kein UNIQUE … WHERE im CREATE TABLE). Siehe nach CREATE TABLE.
  person_id       INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  date            DATE NOT NULL,

  -- Status — Pflicht
  status          TEXT NOT NULL,  -- 'anwesend' | 'abwesend' | 'krank' | …

  -- Optionale Zeitstempel (Check-In/Check-Out)
  check_in_at     TIMESTAMPTZ,
  check_out_at    TIMESTAMPTZ,

  -- Soll-Zeiten (vereinbart, z.B. KGG-Stundenplan), optional
  expected_in_at  TIMESTAMPTZ,
  expected_out_at TIMESTAMPTZ,

  -- Gruppen-Zuordnung für DEN Tag (kann von persons.group_id abweichen)
  group_id        INTEGER,

  -- Auto-Sync-Marker (kommt aus Kalender)
  source          TEXT,           -- 'manual' (default) | 'calendar_sync' | 'legacy_import'
  source_event_id INTEGER,        -- FK auf events.id wenn source='calendar_sync'

  -- Notizen
  notes           TEXT,

  -- Edition-spezifisches
  metadata_       JSONB NOT NULL DEFAULT '{}',

  -- Audit
  operator_id     TEXT REFERENCES operators(id) ON DELETE SET NULL,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

-- Performance-Indizes
CREATE INDEX idx_attendance_tenant_date
  ON shiksha_core.attendance_records (tenant_org_id, date)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_attendance_person_date
  ON shiksha_core.attendance_records (person_id, date DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_attendance_status
  ON shiksha_core.attendance_records (tenant_org_id, status, date)
  WHERE deleted_at IS NULL;

-- Partial UNIQUE: nur aktive Records (deleted_at IS NULL) sind eindeutig pro (person, day).
-- Soft-Delete + Neuanlage am selben Tag bleibt damit möglich.
CREATE UNIQUE INDEX uq_attendance_person_date_active
  ON shiksha_core.attendance_records (person_id, date)
  WHERE deleted_at IS NULL;
```

**SQLAlchemy-Pendant** (im Model):

```python
__table_args__ = (
    Index(
        "uq_attendance_person_date_active",
        "person_id", "date",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
    schema_args(),
)
```

### 2.2 Warum partial unique

Ein Soft-Delete soll möglich machen, am gleichen Tag eine neue Anwesenheits-Zeile für dieselbe Person anzulegen (z.B. nach Korrektur). Reguläres UNIQUE würde das verhindern.

### 2.3 `metadata_`-Konvention

Reserved keys (analog Calendar):

| Key | Werte | Bedeutung | Wer schreibt |
|---|---|---|---|
| `subtype` | edition-specific | Feinere Klassifikation (z.B. "fortbildung_pflicht" vs "fortbildung_freiwillig") | Frontend |
| `compliance` | object | KGG-Anrechnung, Förder-Marker, etc. | Frontend |
| `legacy_raw` | object | Quell-Zeile aus Legacy-Import | Import-Skript |
| `late_arrival_minutes` | int | `max(0, check_in_at - expected_in_at)` in Minuten | **Backend, beim POST/PATCH** |
| `early_pickup_minutes` | int | `max(0, expected_out_at - check_out_at)` in Minuten | **Backend, beim POST/PATCH** |

**Backend-Berechnungs-Regel** (siehe Pflicht-Test §6.4 L7): bei jedem POST/PATCH mit gesetztem `check_in_at` und vorhandenem `expected_in_at`, berechnet das Backend `late_arrival_minutes` und schreibt es in `metadata_`. Analog für Check-Out. Frontend muss diese Felder NICHT mitgeben — wenn doch, werden sie überschrieben.

### 2.4 `attendance_settings`-Tabelle (Tenant-Config)

Pro Tenant ein Eintrag mit Defaults — Öffnungszeiten, Personalschlüssel, etc.

```sql
CREATE TABLE shiksha_core.attendance_settings (
  tenant_org_id           TEXT PRIMARY KEY REFERENCES organizations(id),

  -- Öffnungszeiten (Display-Zeitfenster im UI)
  opens_at                TIME NOT NULL DEFAULT '07:00',
  closes_at               TIME NOT NULL DEFAULT '17:00',

  -- Personalschlüssel: <child_age_max>: <kinder_pro_paedagoge>
  -- z.B. {"3": 6, "6": 12} → bis 3 Jahre: 6 Kinder/Päd, ab 3 bis 6: 12/Päd
  staff_ratio             JSONB NOT NULL DEFAULT '{}',

  -- Andere Compliance-Settings
  metadata_               JSONB NOT NULL DEFAULT '{}',

  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Krummelus-Seed nach Migration:
```sql
INSERT INTO shiksha_core.attendance_settings (
  tenant_org_id, opens_at, closes_at, staff_ratio
) VALUES (
  'krummelus', '07:30', '15:30',
  '{"3": 6, "6": 12}'::jsonb  -- Vorarlberg-KGG-Defaults
);
```

---

## 3. Status-Werte — KITA-Definition

| Status | Default-Color | Default-Icon | Bedeutung | Zählt in Personalschlüssel? |
|---|---|---|---|---|
| `anwesend` | accent-mint | check-circle | Person ist im Haus | ja (Päd. nur, Kinder ja) |
| `abwesend` | cool-grey | minus-circle | Bekannt nicht da, ohne Grund | nein |
| `krank` | rose | medical-bag | Mit Krankenstand | nein |
| `urlaub` | sand-warm | umbrella | Geplante Abwesenheit | nein |
| `fortbildung` | accent-blue | book-open | Päd. in Schulung | nein (Päd. zählt nicht im Haus) |
| `gast` | violet | sparkle | Schnupperkind, Hospitant, etc. | optional (Tenant-Config) |
| `unbekannt` | grey | question | Default, wenn nichts gesetzt | nein |

**Cross-Edition-Erweiterungen:**

```python
KITA_STATUS = ("anwesend", "abwesend", "krank", "urlaub", "fortbildung", "gast", "unbekannt")
YOGA_STATUS = ("anwesend", "abgesagt", "verspätet", "unbekannt")
CAMPING_STATUS = ("eingecheckt", "ausgecheckt", "noshow", "verlängert", "unbekannt")
```

---

## 4. Auto-Sync mit Kalender (Brücke!)

Ein Kalender-Event `event_type=urlaub` oder `abwesenheit` für `participants=[mira.id]` soll automatisch in der Anwesenheit erscheinen als entsprechender Status. Mira muss nicht doppelt pflegen.

### 4.1 Beim Lesen (Read-Side Merge)

`GET /api/v1/attendance/day?date=2026-05-14&tenant_org_id=krummelus` liefert:

1. Alle `attendance_records` für diesen Tag aus DB (manuell angelegt oder Legacy-Import)
2. Plus: virtuelle Records aus `events`-Tabelle, die für diesen Tag relevant sind und für die keine manuelle Anwesenheit existiert
3. Merge-Reihenfolge: manuelle DB-Records > virtuelle Calendar-Records

```python
def get_day(db, tenant_org_id, date) -> list[AttendanceOut]:
    # 1. Manuelle Records
    manual = db.query(AttendanceRecord).filter(
        AttendanceRecord.tenant_org_id == tenant_org_id,
        AttendanceRecord.date == date,
        AttendanceRecord.deleted_at.is_(None),
    ).all()
    seen_person_ids = {r.person_id for r in manual}

    # 2. Virtuelle aus Calendar
    virtual_events = db.query(Event).filter(
        Event.tenant_org_id == tenant_org_id,
        Event.event_type.in_(("urlaub", "abwesenheit")),
        Event.deleted_at.is_(None),
        Event.start_at <= date_end,
        or_(Event.end_at.is_(None), Event.end_at >= date_start),
    ).all()

    virtual_records = []
    for ev in virtual_events:
        for person_id in ev.participants:
            if person_id in seen_person_ids:
                continue
            virtual_records.append(make_virtual_record(person_id, date, ev))

    return manual + virtual_records
```

**Wichtig:** Mira's "Mark as anwesend" auf einem virtuellen Record erzeugt einen **echten** DB-Record, der den virtuellen für diesen Tag überschreibt. Source ist dann `manual` (Mira hat überstimmt).

### 4.2 Virtual-Record → echter Record (API-Pattern)

Virtuelle Records aus Calendar haben **`id = null`**. PATCH funktioniert nicht (keine ID), also:

**Frontend-Logik:**
```javascript
async function setStatus(record, newStatus) {
  if (record.virtual) {
    // Virtual → POST mit allen Werten aus dem virtuellen Record
    await client.createAttendance({
      person_id: record.person_id,
      date: record.date,
      status: newStatus,
      source_event_id: record.source_event_id,  // Audit-Spur zurück zum Calendar-Event
      // check_in_at/out_at/notes etc. übernehmen oder neu
    });
  } else {
    // Echt → PATCH
    await client.patchAttendance(record.id, { status: newStatus });
  }
  reload();
}
```

POST mit `source_event_id` gesetzt + neuer `status` = der virtuelle Record wird durch den echten ersetzt. Beim nächsten `GET /day` taucht der virtuelle nicht mehr auf, weil die UNIQUE-Index-Logic den echten Record als den maßgeblichen erkennt.

### 4.3 Performance-Notiz für Read-Side-Merge

Beim aktuellen Krummelus-Maßstab (23 Persons, wenige Events) ist die Merge-Performance unkritisch. Für größere KITAs (50+ Persons) gilt:

- Calendar-Query nutzt **GIN-Index** auf `events.participants` (`@> '[person_id]'::jsonb`), NICHT App-Side-Iteration über Persons-Liste
- Eine SQL-Query lädt alle relevanten Urlaub/Abwesenheit-Events im Tag-Range, danach Python entpackt die `participants`-Arrays
- O(events_im_zeitraum × avg_participants_pro_event) statt O(persons × events)

Tracking als **T-008 Read-Side-Merge-Cache** in T-Debt: wenn N>100 Persons, dann Day-Cache pro Tenant mit TTL=60s.

---

## 5. UI-Ansichten

### 5.1 Drei Modi: Heute · Übersicht · Korrekturen

**Heute** (default, Hauptansicht):

```
┌──────────────────────────────┐
│ Heim · Anwesenheit           │
│                              │
│ Anwesend                     │
│ 13 Kinder · 3 Pädagog. · Frei│
│ Personalschlüssel: grün ✓   │
│                              │
│ [Heute] [Übersicht] [Korr.]  │
│                              │
│ ← Mittwoch · 14. Mai →       │
│                              │
│ KINDER                       │
│ ─────────                    │
│  ○ Lio        anwesend  08:10│
│  ○ Nikita     krank          │
│  ○ Amrei      anwesend  07:55│
│  ○ Faye       urlaub         │
│  ○ Amelie     ?              │
│  …                           │
│                              │
│ MITARBEITER                  │
│ ─────────                    │
│  ◆ Mira F.    anwesend  07:30│
│  ◆ Kerstin H. fortbildung    │
│  …                           │
│                              │
│ [+ Gast eintragen]           │
└──────────────────────────────┘
```

Pro Zeile:
- Avatar (Foto später, Initialen jetzt)
- Name (Vorname + Nachname)
- Status (mit Color-Code)
- Check-In-Zeit (wenn vorhanden)
- Tap auf Zeile → Status-Modal (status-wahl, optional Check-In/Out-Zeit, Notiz)

**Übersicht** (Heute + nächste Tage):

```
┌──────────────────────────────┐
│ ÜBERSICHT                    │
│ Mai 14–20, 2026              │
│                              │
│ Mi 14:  13 anwesend  ✓       │
│ Do 15:  14 erwartet  ?       │
│ Fr 16:  12 erwartet  ?       │
│ Sa 17:  geschlossen          │
│ So 18:  geschlossen          │
│ Mo 19:  Schließtag (Pfingst.)│
│ Di 20:  14 erwartet  ?       │
└──────────────────────────────┘
```

Tap auf Tag → Tag-View dieses Datums.

**Korrekturen** (Mira ändert vergangene Tage):

Liste der letzten N Tage mit Anwesenheits-Counts. Tap auf Tag → editiert bearbeitbarer Tag-View.

### 5.2 Avatar-Engine

Im "Heute"-View ist der Avatar pro Person eine **kleine, lebendige** Anzeige:

- Anwesend → Avatar in voller Farbe (Saturation 100%)
- Abwesend/krank/urlaub → Avatar in Pastell, ausgegraut
- Unbekannt → Avatar mit Fragezeichen-Overlay

Beim Status-Wechsel: kurze CSS-Transition (300ms ease-in-out fade-in der Sättigung).

**Phase-1-Implementierung:** Initialen-Avatar wie in `personen.html`, mit `filter: saturate(0.3)` für nicht-anwesende Personen.

**Phase 2:** Echte Fotos aus Bilddatenbank (Pre-Investment: `persons.metadata.compliance.photo_consent` ist schon da).

### 5.3 Live-Personalschlüssel

Oben in der Stats-Zeile:

```
Personalschlüssel: grün ✓
```

oder

```
Personalschlüssel: ROT ⚠
Du brauchst 2 weitere Pädagoginnen ab 13:00 (Spitzenzeit).
```

Berechnungs-Logik:

1. Hole `attendance_settings.staff_ratio` für den Tenant
2. Für jeden 15-min-Slot zwischen `opens_at` und `closes_at`:
   - Zähle Kinder, die zu dieser Zeit anwesend (check_in_at ≤ slot < check_out_at oder kein Check-Out)
   - Zähle Pädagogen analog
   - Berechne erforderliche Päd. = ceil(kinder / ratio_for_age_band)
   - Wenn ist_count < erforderlich: ROT, sonst GRÜN
3. Aggregiere: wenn irgendwo ROT, gesamter Tag ROT mit erstem ROT-Slot als Hinweis

**Phase 1 Simplifizierung — Sweepline-Algorithmus:**

```python
# services/attendance_ratio.py (~30 LOC)
def max_concurrent_present(records: list[AttendanceRecord]) -> tuple[int, datetime | None]:
    """
    Sweepline über alle check_in_at/check_out_at-Events des Tages.
    Returns (max_count, time_of_max).

    Sonderfall: record.status='anwesend' aber check_in_at=NULL
      → zählt als ganztags anwesend (opens_at bis closes_at).
    """
    events = []  # [(time, +1 oder -1)]
    for r in records:
        if r.status != "anwesend":
            continue
        if r.check_in_at:
            events.append((r.check_in_at, +1))
            events.append((r.check_out_at or end_of_day(r.date), -1))
        else:
            # status=anwesend ohne Zeitstempel → ganztags
            events.append((start_of_day(r.date), +1))
            events.append((end_of_day(r.date), -1))

    events.sort()  # Stable sort, +1 vor -1 bei gleicher Zeit
    cur = 0
    peak = 0
    peak_time = None
    for time, delta in events:
        cur += delta
        if cur > peak:
            peak = cur
            peak_time = time
    return peak, peak_time
```

Vergleich gegen erforderlich = `ceil(peak_kinder / ratio_for_age_band)`. Wenn ist_paed_peak < erforderlich → ROT. Sonst grün.

Reicht für 99% der Compliance-Realität. Erst wenn Vorarlberg-Behörde feinere Slot-Granular sehen will → Phase 3 mit echtem Slot-Aggregat.

### 5.4 Status-Modal

Tap auf eine Zeile öffnet ein kompaktes Modal:

```
┌─ Lio · Mittwoch, 14. Mai ──┐
│                              │
│ Status:                      │
│ [anwesend] abwesend krank    │
│ urlaub  fortbildung  gast    │
│                              │
│ Check-In:   [08:10]          │
│ Check-Out:  [____]           │
│                              │
│ Gruppe:     1                │
│                              │
│ Notiz: ___________________   │
│                              │
│           [Abbrechen]  [OK]  │
└──────────────────────────────┘
```

Segmented Control für Status (gut auf Mobile). Time-Inputs für Check-In/Out. Optional Gruppe + Notiz.

---

## 6. Berechtigung

### 6.1 Read/Write-Matrix

| Rolle | Lesen | Schreiben | Löschen |
|---|---|---|---|
| `developer` | alles | alles | alles (mit Audit-Log) |
| `leitung` | alles im Tenant | alles | alles |
| `padagogin` | alles im Tenant (auch Kollegen-Anwesenheit) | Kinder (alles) + eigener Status + Kollegen-Check-In | nur eigene Records |
| `eltern` | **nichts in Phase 1** | nichts | nichts |
| `teilnehmer` | **nichts in Phase 1** | nichts | nichts |

**Eltern-Sicht in Phase 2** — abhängig von T-003 (Mira-Person ↔ Operator-Auth-Link). Solange Eltern-Operator nicht auf seine Kind-Persons verlinkt sind, gibt's kein sauberes "eigene Kinder"-Filter. Deshalb Phase 1: Eltern bekommen `403 Forbidden` auf alle Attendance-Endpoints. Im Heim sehen sie die "Wer ist da"-Karte nicht (role_scope schließt sie aus).

**Begründung Pädagogin schreibt Kollegen-Check-In:** im KITA-Alltag tippt oft EINE Person für alle. Mira morgens: "Kerstin ist da, ich tippe sie ein." Das geht nicht ohne diese Erlaubnis.

### 6.2 Pflicht-Tests (analog Calendar §6.4)

In `tests/test_attendance.py` müssen mindestens fünf Berechtigungs-Tests existieren:

1. **`test_eltern_read_filter`** — Eltern bekommt 403 auf `/api/v1/attendance/day` (Phase 1)
2. **`test_padagogin_can_check_in_kollegen`** — Pädagogin darf Kollegen-Check-In setzen
3. **`test_cross_tenant_reject`** — Operator von Tenant A bekommt 404 bei Records von Tenant B
4. **`test_eltern_cannot_write`** — POST/PATCH/DELETE als `eltern` liefert 403
5. **`test_virtual_records_via_calendar_urlaub`** — Wenn Calendar-Event `urlaub` für Mira existiert, erscheint sie in `/day` mit `status=urlaub, virtual=true`

Plus zwei Berechnungs-Pflicht-Tests:

6. **`test_late_arrival_minutes_calculated`** — POST mit `expected_in_at=08:00`, `check_in_at=08:15` → Backend setzt `metadata.late_arrival_minutes=15` automatisch
7. **`test_sweepline_peak_concurrent`** — Drei Kinder eingecheckt mit überlappenden Zeiten → `max_concurrent_present` liefert korrekten Peak und Zeitpunkt

---

## 7. Heim-Karten

Drei neue Karten in `editions/kita.yaml`:

```yaml
- card_id: wer_ist_da
  title: "Wer ist da"
  subtitle: "{kids_present_count} Kinder · {staff_present_count} Päd."
  icon: people
  url: /anwesenheit.html
  role_scope: [leitung, padagogin, developer]
  time_priority: 100   # höchste, weil meistgenutzt
  provider: attendance.live_counts

- card_id: personalschluessel
  title: "Personalschlüssel"
  subtitle: "{ratio_status_label}"
  icon: shield-check
  url: /anwesenheit.html?view=ratio
  role_scope: [leitung, developer]
  time_priority: 90
  provider: attendance.live_counts

- card_id: anwesenheit_woche
  title: "Anwesenheit Woche"
  subtitle: "Ø {avg_present_count} Kinder/Tag"
  icon: chart
  url: /anwesenheit.html?view=overview
  role_scope: [leitung, padagogin, developer]
  time_priority: 60
  provider: attendance.week_summary
```

Provider liefert:
- `kids_present_count` (Kinder mit status=anwesend gerade jetzt)
- `staff_present_count` (Päd. mit status=anwesend gerade jetzt)
- `ratio_status_label` ("grün ✓" / "ROT ⚠" / "knapp ⚠")
- `avg_present_count` (gleitender Durchschnitt letzte 7 Tage)

---

## 8. Daten-Migration

`scripts/import_attendance.py` analog zu `import_calendar.py`:

1. **Phase 0 — Inspect** zeigt Struktur von `kita_legacy_anwesenheit` (Tabellen-Name vermutlich)
2. **Phase 1 — Dry-Run**
3. **Phase 2 — Real** mit Person-ID-Lookup analog Calendar

Falls Krummelus keine Legacy-Anwesenheit hat (Greenfield wie Calendar) → Skript-Sanity reicht, ab dem 5.5.5.4 (UI-Drop) startet Mira mit leerer Tabelle und pflegt ihren ersten Tag selbst.

---

## 9. Bridge-Übergang

- `kita/anwesenheit` bleibt in Whitelist, bis Frontend komplett auf `/api/v1/attendance/*` umgestellt ist
- Nach grünem Smoke-Test (5.5.5.6): Whitelist-Eintrag `kita/anwesenheit` entfernen

---

## 10. API-Übersicht

```
/api/v1/attendance/
  GET    /day?date=YYYY-MM-DD              Tag-Liste mit Merge von Calendar
  GET    /overview?from=YYYY-MM-DD&to=...  Mehrtages-Übersicht (counts)
  GET    /person/{person_id}?from=&to=     Person-Verlauf
  POST   /records                          Status setzen
  PATCH  /records/{id}                     Status ändern
  DELETE /records/{id}                     Soft-Delete (Korrektur)
  GET    /settings                         attendance_settings auslesen
  PATCH  /settings                         Settings ändern (nur leitung)
  GET    /live_counts                      Provider für Heim-Karten
  GET    /week_summary                     7-Tage-Aggregat
```

### 10.1 `AttendanceOut`- und `AttendanceCreate`-Schemas

**Wichtig zum Datentyp:** `check_in_at`/`check_out_at`/`expected_in_at`/`expected_out_at` sind **`datetime` (TIMESTAMPTZ)**, NICHT `time`. Wenn Mira im UI "08:10" tippt, muss das Frontend mit dem aktuellen Datum und der Tenant-TZ zu einem vollen ISO-Datetime kombinieren:

```javascript
// Frontend (kalender.html-Pattern wiederverwenden)
function combineDateTime(dateStr, timeStr, tz) {
  // dateStr = "2026-05-14", timeStr = "08:10", tz = "Europe/Vienna"
  // → "2026-05-14T08:10:00+02:00" (oder Z falls UTC)
  const local = new Date(`${dateStr}T${timeStr}:00`);
  return local.toISOString();  // ergibt UTC-ISO mit Z-Suffix
}
```

In URL-Query-Strings (Test- und Listen-Endpoints) **immer Z-Suffix erzwingen**:

```python
# Test-Pattern (siehe Repo-Map §6)
now_z = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
```

```python
class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: Optional[int] = None       # None für virtuelle Records aus Calendar
    person_id: int
    person_brief: Optional[ParticipantBrief] = None  # Lazy-Resolved
    date: date
    status: str
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None
    group_id: Optional[int] = None
    notes: Optional[str] = None
    source: str = "manual"
    source_event_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    virtual: bool = False           # True wenn aus Calendar gemerged


class AttendanceCreate(BaseModel):
    """Payload für POST /records. Inkl. Promotion eines virtuellen Records via source_event_id."""
    person_id: int
    date: date
    status: str
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None
    group_id: Optional[int] = None
    notes: Optional[str] = None
    source: str = "manual"
    source_event_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # late_arrival_minutes wird NICHT vom Client gesetzt — Backend rechnet das
    tenant_org_id: Optional[str] = None  # Developer-Override


class AttendancePatch(BaseModel):
    status: Optional[str] = None
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None
    group_id: Optional[int] = None
    notes: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    active: Optional[bool] = None
```

### 10.2 `LiveCounts`-Schema

```python
class LiveCounts(BaseModel):
    kids_present_count: int
    staff_present_count: int
    ratio_status: Literal["green", "yellow", "red"]
    ratio_status_label: str         # "grün ✓" oder "ROT ⚠ — 1 Päd. fehlt"
    next_check_at: Optional[datetime] = None  # nächste Spitzenzeit
```

---

## 11. Sub-Schritt-Aufteilung

```
5.5.5.0     Diese Spec                                  ← Du bist hier
5.5.5.1     DB-Migration + Models + Schemas             (~200 LOC)
              • attendance_records + attendance_settings
              • Partial-Unique-Index (deleted_at IS NULL)
              • Krummelus-Seed mit Vorarlberg-KGG-Ratio
5.5.5.2     Endpoints + 22 Tests + Sweepline-Service    (~650 LOC + 22 Tests)
              • 5 Berechtigungs-Pflicht-Tests (§6.2)
              • 2 Berechnungs-Pflicht-Tests (late_arrival, sweepline)
              • Calendar-Merge mit Read-Side-Logik
              • services/attendance_ratio.py mit Sweepline (~30 LOC)
5.5.5.3     Daten-Import-Skript                         (~180 LOC)
              • Person-ID-Lookup wiederverwenden
              • Wenn Greenfield (wie Calendar) → nur Sanity-Run
5.5.5.4     anwesenheit.html — Heute-View               (~500 LOC)
              • Avatar-Engine mit Saturation-Toggle
              • Status-Modal als Segmented Control
              • Live-Counts + Personalschlüssel-Anzeige
              • Virtual-Record-Promotion via POST /records
5.5.5.5     anwesenheit.html — Übersicht + Korrekturen  (~280 LOC)
5.5.5.6.a   Heim-Karten + Provider                      (~140 LOC + 4 Tests)
              • attendance.live_counts + week_summary
              • 3 Karten (wer_ist_da, personalschluessel, anwesenheit_woche)
5.5.5.6.b   Bridge-Trim + Final-Smoke                   (~40 LOC)
```

Sieben Drops, vermutlich über 5-6 Iterationen. Größter Brocken 5.5.5.2 (Endpoints + Tests, ~650 LOC mit Calendar-Merge-Code).

Sieben Drops, vermutlich über 5-6 Iterationen — Anwesenheit ist näher an Calendar als an Personen (komplexer als Stammdaten).

---

## 12. Akzeptanzkriterien (Modul gesamt)

1. ✅ Mira öffnet `/anwesenheit.html` am Morgen, sieht 18 Kinder + 5 Päd., tippt jeweils einmal — fertig
2. ✅ Status-Wechsel ist 2-Tap (Zeile → Modal → Status-Button → OK)
3. ✅ Avatar-Saturation ändert sich live bei Status-Wechsel
4. ✅ Live-Personalschlüssel zeigt grün/rot mit Begründung
5. ✅ Calendar-Brücke: Mira's Urlaub aus dem Kalender erscheint automatisch als `status=urlaub`, virtual
6. ✅ Drei Heim-Karten zeigen echte Counts ("Wer ist da: 13 Kinder · 3 Päd.")
7. ✅ Mobile-First (399px Viewport): alle Listen sauber, Avatar-Spalten lesbar
8. ✅ Berechtigung getestet (Eltern sieht nur eigene Kinder etc.)
9. ✅ Pytest grün (~25 neue Tests)
10. ✅ Bridge-Whitelist `kita/anwesenheit` entfernt nach 5.5.5.6.b

---

## 13. Designfragen (alle in v2 beantwortet)

**F1 — Eltern-Sicht in Phase 1:** ✅ **Nein.** Verschoben auf Phase 2, sauberer als T-003-Pre-Req. Solange Operator-↔-Person-Link nicht implementiert ist, gibt's kein zuverlässiges "eigene Kinder"-Filter. Phase 1: Eltern bekommen `403` auf Attendance-Endpoints; Heim-Karten sind nicht im `role_scope: eltern`.

**F2 — `expected_in_at` als Pflicht:** ✅ Optional Phase 1, Pflicht Phase 2 bei Förderstunden-Berechnung. Wenn vorhanden: `late_arrival_minutes` wird automatisch berechnet (siehe §2.3).

**F3 — Auto-Check-Out um closes_at:** ✅ Ja, als kleiner Cron-Helper in 5.5.5.6.a. **Cron-Env-Pattern explizit dokumentieren** im Drop-Doc (systemd-Timer auf dem Server, läuft jede Nacht 23:00 lokaler Tenant-TZ, setzt `check_out_at = closes_at` für alle offenen Records des Tages mit `source != 'cron'`).

**F4 — Personalschlüssel pro Gruppe vs. Standort:** ✅ Pro Standort/Tenant in Phase 1. Pro Gruppe als optional Tenant-Setting Phase 2.

**F5 — Gast-Status im Personalschlüssel:** ✅ `gast` zählt mit, Tenant-Override via `attendance_settings.metadata.gast_counts: false` für Träger, die das anders wollen.

---

## 14. Was als nächstes

Nach Deiner Bestätigung der Spec (oder Anpassungen an F1-F5):

→ **5.5.5.1** — DB-Migration + Models + Schemas als erstes Drop-Paket.

---

**Bindend für alle folgenden Drops dieses Moduls.** Änderungen werden hier protokolliert.

### Änderungen
- v1 · 2026-05-14 · Initial draft (Claude)
- v2 · 2026-05-14 · F1 zurück auf Phase 2, F3 Cron-Env-Pattern dokumentiert, L1 Partial-Unique als Index (SQL + SQLAlchemy), L2 Performance-Note + T-008-Vermerk, L3 TZ-Suffix-Doc in §10.1, L4 Sweepline-Algorithmus skizziert, L5 Virtual-Record-Promotion via POST, L6 fünf Pflicht-Tests + zwei Berechnungs-Tests in §6.2, L7 late_arrival_minutes als Backend-Auto-Calc in §2.3 (Claude Code review feedback)

# SHIKSHA Calendar — Modul-Spec (Schritt 5.5.4.0)

**Status:** v2 final · 2026-05-13
**Ziel:** Zweites Modul der gradual migration (Phase 1.5). Folgt dem Pattern von Personen. Wird zur Belastungsprobe Nr. 3 für das Design-System v1.0.0.

---

## 1. Ziel & Scope

**Was Calendar ist:** Der zeitliche Backbone von SHIKSHA. Mira pflegt hier ihre Tage: wer ist da, was ist los, was kommt. Es ist nicht "noch eine App", sondern die zweite Surface, auf die fast jede Heim-Karte zeigt — neben Personen.

**Cross-Edition-Anspruch:** Das Datenmodell ist neutral. KITA bekommt KITA-Event-Types (Eingewöhnung, Elternabend), YOGA bekommt YOGA-Types (Workshop, Kurseinheit), CAMPING Reservierung etc. Die Engine ist eine.

**Phase 1 Scope (was JETZT gebaut wird):**

1. Backend mit voller CRUD (events-Tabelle, REST)
2. Drei UI-Modi: **Tag · Woche · Monat** (Mobile-First)
3. Vier Event-Types für KITA: **Termin · Urlaub · Abwesenheit · Kurs**
4. Verknüpfung zu `persons` über `participants` (jsonb array von person_ids)
5. Daten-Import von `kita_legacy_calendar`
6. Drei Heim-Karten: **Heute · Diese Woche · Kalender**

**Explizit NICHT in Phase 1:**

- **Recurrence (RRULE)** — wiederkehrende Termine werden über "Beim Anlegen N Wiederholungen erzeugen" gelöst. Echte RRULE-Expansion ist Phase 2.
- **Externe Kalender-Sync** (iCal, Google) — Phase 3.
- **Einladungen mit Zusage-Workflow** — Phase 2.
- **Geburtstage automatisch aus `persons.birth_date`** — wird als virtuelles Event vom Backend bei Read gemerged, kommt in 5.5.4.4 wenn Zeit, sonst Phase 2.
- **Jahres-Übersicht** — auf Mobile wertlos, später als Desktop-Feature.

---

## 2. Datenmodell

### 2.1 `events`-Tabelle

```sql
CREATE TABLE shiksha_core.events (
  id              SERIAL PRIMARY KEY,
  tenant_org_id   TEXT NOT NULL REFERENCES organizations(id),

  -- Idempotenz-Key für Legacy-Import
  legacy_id       TEXT,
  legacy_source   TEXT,
  UNIQUE (legacy_id, legacy_source),

  -- Typ + Inhalt
  event_type      TEXT NOT NULL,  -- 'termin' | 'urlaub' | 'abwesenheit' | 'kurs'
  title           TEXT NOT NULL,
  description     TEXT,
  location        TEXT,

  -- Zeit
  start_at        TIMESTAMPTZ NOT NULL,
  end_at          TIMESTAMPTZ,
  all_day         BOOLEAN NOT NULL DEFAULT FALSE,

  -- Verknüpfung zu Personen (jsonb array von person_ids als integer)
  participants    JSONB NOT NULL DEFAULT '[]',

  -- Edition-spezifisches (Subtype, Urgency, Recurrence-Group, Status, etc.)
  -- Konvention für metadata_-Keys siehe §2.4
  metadata_       JSONB NOT NULL DEFAULT '{}',

  -- Audit
  operator_id     TEXT REFERENCES operators(id),
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

-- Performance-Indizes
CREATE INDEX idx_events_tenant_start
  ON shiksha_core.events (tenant_org_id, start_at)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_events_type
  ON shiksha_core.events (tenant_org_id, event_type, start_at)
  WHERE deleted_at IS NULL;

-- Für "Events von Person X" — GIN-Index auf participants
CREATE INDEX idx_events_participants
  ON shiksha_core.events USING GIN (participants);
```

### 2.2 Entscheidung: `participants` als jsonb statt M2M-Tabelle

**Pro jsonb:**
- Einfacher zu pflegen (kein eigener Endpoint, ein Update reicht)
- GIN-Index macht "Events von Person X" trotzdem schnell
- Phase 1 hat keine Zusatz-Felder pro (event, person) wie "responded_at"

**Pro M2M:**
- Erweiterbar (Zusage-Status, Role-im-Event)
- DB-FK-Integrity

**Entscheidung:** **jsonb für Phase 1**, M2M wenn Phase 2 Einladungs-Workflow kommt. Migration dann: `INSERT INTO event_participants SELECT event_id, p FROM events, jsonb_array_elements_text(participants) p`.

### 2.3 `event_type` als Enum-String

Frei-String mit Application-Level-Validation (statt CHECK-CONSTRAINT) — das macht Edition-Erweiterungen ohne Migration möglich:

```python
KITA_EVENT_TYPES = ("termin", "urlaub", "abwesenheit", "kurs")
YOGA_EVENT_TYPES = ("termin", "urlaub", "workshop", "kurseinheit")
CAMPING_EVENT_TYPES = ("reservierung", "checkin", "checkout", "event")
```

Validation lebt in `services/event_types.py` mit `is_valid_type(edition, t)`.

### 2.4 `metadata_`-Konvention

Strukturierte Sektionen analog zu `persons.metadata_`. Reserved keys:

| Key | Werte | Bedeutung |
|---|---|---|
| `subtype` | edition-specific (siehe §3) | Feinere Klassifikation eines `termin` (Eingewöhnung, Elternabend …) |
| `urgency` | `normal` (default) \| `important` \| `urgent` | Visuelle Hervorhebung — siehe §4.5 |
| `recurrence_group` | UUID-String | Anker für später-Reihen-Operations (alle Events derselben Reihe) |
| `recurrence_index` | Integer `1..N` | Position innerhalb der Reihe |
| `status` | `approved` (default) \| `pending` \| `rejected` | Workflow-State; nur relevant bei `event_type=urlaub` in Phase 1 |
| `color` | reserved | Eine direkte Color-Override ist **nicht** vorgesehen — Color kommt aus `event_type` + `urgency`. Siehe §4.5. |
| `legacy_raw` | object | Komplette Quell-Zeile aus Legacy-Import, identisches Pattern zu `persons` |

### 2.5 Time-Zone-Handling (L1)

`start_at` und `end_at` sind `TIMESTAMPTZ` (UTC im Storage). Display-Zeitzone kommt aus der Tenant-Config:

```sql
ALTER TABLE shiksha_core.organizations
  ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Europe/Berlin';
```

- Krummelus (Vorarlberg) → `Europe/Vienna`
- Berliner KITA → `Europe/Berlin`
- Wien-Yoga → `Europe/Vienna`
- Zürich → `Europe/Zurich`

Frontend liest `org.timezone` aus dem JWT (oder lazy via `client.getOrganization()`) und rendert alle Zeitstempel via `Intl.DateTimeFormat(..., { timeZone })`. Backend macht NIE TZ-Konversion — nur UTC rein / UTC raus.

Die `organizations.timezone`-Spalte kommt mit der gleichen Migration wie die `events`-Tabelle (Drop 5.5.4.1), damit der Punkt nicht später nachgezogen werden muss.

---

## 3. Event-Types — KITA-Definition

| Type | Default-Color | Default-Icon | Typische Inhalte |
|---|---|---|---|
| `termin` | Edition-Primary | calendar-event | Elternabend, Ausflug, Eingewöhnungs-Gespräch |
| `urlaub` | sand-warm | umbrella | Urlaubstage Mitarbeiter |
| `abwesenheit` | cool-grey | absence | Krankheit, Fortbildung, sonstige Ausfälle |
| `kurs` | accent-mint | sparkle | Wöchentlicher Musikkreis, Bewegungsrunde |

**Color/Icon-Mapping** in `editions-css/kita.v1.0.0.css` als Custom Properties:

```css
[data-event-type="termin"]      { --evt-color: var(--shk-edition-primary); }
[data-event-type="urlaub"]      { --evt-color: var(--shk-edition-warm); }
[data-event-type="abwesenheit"] { --evt-color: var(--shk-color-text-faint); }
[data-event-type="kurs"]        { --evt-color: var(--shk-edition-accent); }
```

So sind die Event-Farben Theming-bewusst (Hell/Dunkel) und Edition-spezifisch.

### 3.1 `event_subtypes` — UI-Hilfe pro Edition

Subtypes leben in `editions/<edition>.yaml` als reine UI-Vorschläge. **Kein DB-Constraint**, freie Eingabe bleibt möglich — der Dropdown im Modal-Editor schlägt nur vor, sodass Mira nicht jedes Mal "Eingewöhnung" abtippt:

```yaml
# editions/kita.yaml
event_subtypes:
  termin:
    - eingewöhnung
    - elternabend
    - ausflug
    - schließtag
    - gespräch
  kurs:
    - musikkreis
    - bewegungsrunde
    - waldgang
```

Andere Editions ziehen analog nach:

```yaml
# editions/yoga.yaml
event_subtypes:
  workshop:
    - faszien
    - meditation
    - retreat
  termin:
    - probestunde
    - lehrer-meeting

# editions/camping.yaml
event_subtypes:
  reservierung:
    - kurzurlauber
    - dauergast
    - gruppe
  event:
    - lagerfeuer
    - sportabend
```

Frontend lädt diese Liste beim Modal-Open via `client.getEditionConfig().event_subtypes[currentType]` und füllt einen Datalist-Input. Gespeichert wird in `metadata.subtype` — Phase 1 sucht/gruppiert noch nicht danach.

---

## 4. UI-Ansichten

### 4.1 Drei Modi: Tag · Woche · Monat

**Tag** (default auf Mobile):
- Vertikale Timeline 6:00 – 20:00 (konfigurierbar pro Edition)
- All-Day-Bereich oben (max 3 Zeilen sichtbar, scrollbar)
- Events als Glas-Karten in Spalten (Type-color als Linke-Kante)
- Tap → Modal

**Woche** (default auf Tablet/Desktop, optional auf Mobile):
- 7 Tage × 24h-Grid auf Desktop
- Auf Mobile: 7 Tag-Karten horizontal scrollbar (jede Tag-Karte zeigt Events des Tages als Mini-Liste)

**Monat**:
- Klassischer 6×7-Grid mit Tagen
- Pro Tag bis zu 3 Event-Indikatoren (Punkt + Title-Trunc)
- "+5 mehr" Indicator wenn mehr
- Tap auf Tag → wechselt in Tag-Modus

### 4.2 Navigation

Header der Surface:
```
[< heute >]    Mai 2026    [Tag | Woche | Monat]    [+ Termin]
```

- "heute" zentriert die Ansicht auf heute
- Pfeile: ein Tag/Woche/Monat zurück/vor
- View-Switcher als shk-tabs
- "+ Termin"-Button öffnet Create-Modal mit `start_at = jetzt`

### 4.3 URL-Schema

```
/kalender.html                        — heute, Tag-View
/kalender.html?view=woche             — heute, Woche
/kalender.html?view=monat             — heute, Monat
/kalender.html?view=tag&d=2026-05-15  — bestimmter Tag
/kalender.html?view=monat&m=2026-06   — bestimmter Monat
/kalender.html?event=42               — Modal direkt offen
```

So sind alle Ansichten bookmark-bar und teilbar.

### 4.4 Modal-Editor (Create/Edit)

Felder:
- **Titel** (Pflicht)
- **Typ** (Dropdown: Termin/Urlaub/Abwesenheit/Kurs)
- **Subtype** (Datalist mit Vorschlägen aus `editions/kita.yaml > event_subtypes[type]`, free-form — speichert in `metadata.subtype`)
- **Datum + Zeit** (Date+Time-Picker, "Ganztags"-Toggle, Bis-Datum optional)
- **Ort** (frei, optional)
- **Beteiligte** (Multi-Select aus persons; rendert Avatare im Form)
- **Beschreibung** (Textarea)
- **Dringlichkeit** (Segmented Control: normal / wichtig / dringend — speichert in `metadata.urgency`)
- **Wiederholung** (Dropdown: einmalig / täglich für N / wöchentlich für N / monatlich für N — generiert N Events bei Save, alle mit derselben `metadata.recurrence_group=<uuid>` und `metadata.recurrence_index=1..N`)

Wiederholung ist **client-side multi-insert**, nicht Server-side RRULE. Der `recurrence_group`-Anker ist gratis-Bonus (4 Zeilen Code), damit Phase 2 später eine "Reihe ab Datum X verschieben/löschen"-Operation als Server-Endpoint anbieten kann, ohne dass Mira jedes Event einzeln anfassen muss.

### 4.5 Urgency-Stufen statt Color-Override (F4)

Statt freier Color-Wahl (Outlook-Bunter-Teppich-Falle) drei Stufen:

| `metadata.urgency` | Visuell |
|---|---|
| `normal` (default) | Type-Default-Color greift |
| `important` | Linke-Kante 4px statt 2px |
| `urgent` | Rote Outline (`var(--shk-color-danger)`), sanft pulsierend (`@keyframes shk-pulse`) |

CSS-Mapping in `editions-css/kita.v1.0.0.css`:

```css
.shk-event[data-urgency="important"] { border-left-width: 4px; }
.shk-event[data-urgency="urgent"] {
  outline: 2px solid var(--shk-color-danger);
  animation: shk-pulse 2.4s ease-in-out infinite;
}
@keyframes shk-pulse {
  0%, 100% { outline-color: var(--shk-color-danger); }
  50%      { outline-color: transparent; }
}
```

### 4.6 Geburtstage als virtuelle Events (F2)

Backend mergt beim Read von `GET /events?from=A&to=B` die Geburtstage von Personen in den Zeitraum:

- ID = `null` oder `"birthday:<person_id>:<yyyy>"`
- `event_type` = `"geburtstag"` (Sondertyp, nur read-only)
- `start_at` = der Geburtstag im Jahr A oder B
- `all_day = true`
- `participants = [person_id]`
- `metadata = {synthetic: true, person_age: <int>}`

**Berechtigung (Klärung zu F2):**

- `leitung`, `padagogin`, `developer` sehen alle Tenant-Geburtstage
- `eltern`, `teilnehmer` sehen nur Geburtstage von Personen, mit denen sie eine bestehende `participants`-Verknüpfung haben (eigenes Kind, etc.). Sonst leakt das.
- `?person_id=42`-Filter liefert auch den Geburtstag von Person 42 mit.

Geburtstage sind nicht editierbar (Frontend hide Modal-Save bei `synthetic=true`). Korrektur via `personen.html` → Modal → Geburtsdatum ändern.

---

## 5. Person-Verknüpfung

### 5.1 Datenfluss

- Modal-Editor lädt beim Öffnen `client.listPersons({ kind: 'kind' })` und `{ kind: 'staff' })`
- Person-Picker zeigt Initialen-Avatar + Name
- Bei Save: `event.participants = [person_id_1, person_id_2, ...]`
- Read-Side: Backend liefert `participants_resolved` als optionales Feld, das Names+Avatars-Info hinzufügt für UI

### 5.2 "Events von einer Person"

`GET /api/v1/calendar/events?person_id=42` filtert via `participants @> '[42]'::jsonb`. Performance dank GIN-Index. Brauchen wir für:
- "Mira's Urlaubsplan" (filter `participants @> [mira.id] AND event_type='urlaub'`)
- Person-Detail-View später (Tech-Debt T-006, neuer Eintrag)

---

## 6. Berechtigung

### 6.1 Read/Write-Matrix

| Rolle | Lesen | Schreiben | Löschen |
|---|---|---|---|
| `developer` | alle Events aller Tenants (bei expliziter org_id-Wahl) | dito | dito |
| `leitung` | alle Events des Tenants | alle | alle |
| `padagogin` | alle Events des Tenants¹ | (`operator_id == self.id` OR `self.person_id IN participants`) UND `event_type IN (termin, kurs, abwesenheit)` | dito |
| `eltern` | "betreffend" (siehe 6.2) | keine | keine |
| `teilnehmer` | analog `eltern` | keine | keine |

¹ Mit Ausnahme der Urlaub-Privacy-Regel (6.3).

### 6.2 "Betreffend" für Eltern/Teilnehmer

Ein Event ist "betreffend" für `eltern` X, wenn eines gilt:

- `participants @> [<eigenes_kind_id>]` (eines der eigenen Kinder ist beteiligt) ODER
- Event ist **global**: `participants = '[]'` UND `event_type = 'termin'` (z.B. KITA-Schließtage, allgemeine Elternabende)

Privater Termin von Mira (mit Mira als participant) oder Urlaub von Kerstin sind explizit **nicht** betreffend.

### 6.3 Urlaub-Privacy (F5)

`event_type=urlaub` UND `metadata.status != 'approved'` ist nur sichtbar für:

- `operator_id` (Antragsteller) PLUS
- Rollen `leitung`, `developer`

Genehmigter Urlaub (`status=approved`, der **Default** für Phase 1 und für Migration aus alter Welt) ist für alle Tenant-Mitglieder sichtbar — Pädagoginnen müssen wissen, wann Kollegen weg sind.

`pending`-Status kommt erst in Phase 2 mit dem Antrags-Workflow. In Phase 1 ist jeder neu angelegte Urlaub direkt `approved`.

### 6.4 Test-Anforderungen (L3)

In `tests/test_calendar.py` müssen mindestens vier Berechtigungs-Tests existieren:

1. **`test_eltern_read_filter`** — Eltern sehen nur betreffende Events
2. **`test_padagogin_urlaub_other_pending`** — Pädagogin sieht nicht den `pending`-Urlaub eines Kollegen
3. **`test_cross_tenant_reject`** — Operator von Tenant A bekommt 404 bei Event von Tenant B
4. **`test_eltern_cannot_write`** — POST/PATCH/DELETE als `eltern` liefert 403

---

## 7. Heim-Karten

Drei neue Karten in `editions/kita.yaml`:

```yaml
- card_id: heute
  title: "Heute"
  subtitle: "{event_count_today} Termine, {staff_count_today} im Haus"
  icon: sun
  url: /kalender.html?view=tag
  role_scope: [leitung, padagoge, developer]
  time_priority: 95
  provider: calendar.today_summary

- card_id: diese_woche
  title: "Diese Woche"
  subtitle: "{event_count_week} Termine"
  icon: calendar-week
  url: /kalender.html?view=woche
  role_scope: [leitung, padagoge, developer]
  time_priority: 80

- card_id: kalender
  title: "Kalender"
  subtitle: ""
  icon: calendar
  url: /kalender.html?view=monat
  role_scope: [leitung, padagoge, eltern, developer]
  time_priority: 50
```

Provider `calendar.today_summary` lebt in `services/heim_providers.py` und liefert `event_count_today`, `staff_count_today` (= Anzahl Staff ohne Urlaub/Abwesenheit heute).

---

## 8. Daten-Migration

`scripts/import_calendar.py` analog zu `import_persons.py`:

1. **Phase 0 — Inspect** zeigt Struktur von `kita_legacy_calendar`
2. **Phase 1 — Dry-Run** mappt alte Spalten auf neue
3. **Phase 2 — Real**

Erwartetes Mapping (zu verifizieren in Inspect-Phase):

| Legacy-Spalte | events-Feld |
|---|---|
| `id` | `legacy_id` |
| `titel` / `title` | `title` |
| `typ` / `type` | `event_type` (mit Normalisierung) |
| `start` / `start_at` / `datum` | `start_at` |
| `ende` / `end_at` | `end_at` |
| `ganztags` / `all_day` | `all_day` |
| `ort` / `location` | `location` |
| `beschreibung` / `description` | `description` |
| `teilnehmer_ids` / `participants` (json) | `participants` (nach Legacy-ID→Person-ID-Lookup) |

**Person-ID-Lookup:** Legacy-Events referenzieren Kinder/Staff mit alten IDs (z.B. `kita_legacy_children.id=1` für Lio). Importer muss jeden Legacy-Person-ID nach neuer `persons.id` übersetzen via `metadata.legacy_raw.id` oder `legacy_id`-Spalte.

---

## 9. Bridge-Übergang

- `kita/calendar` bleibt in Whitelist, bis Frontend komplett auf `/api/v1/calendar/events` umgestellt ist
- Nach grünem Smoke-Test (5.5.4.5): Whitelist-Eintrag `kita/calendar` entfernen

---

## 10. Architektur-Übersicht

```
/api/v1/calendar/
  GET    /events                    Liste mit ?from=&to=&type=&person_id=&include_birthdays=true
  GET    /events/{id}               Detail (mit participants_resolved)
  POST   /events                    Create (mit optional repeat: {kind, count})
  PATCH  /events/{id}               Partial Update
  DELETE /events/{id}               Soft-Delete (eigene Events oder leitung)
  GET    /stats                     EventStats (siehe 10.1)
  GET    /today_summary             TodaySummary (siehe 10.2)
```

### 10.1 EventStats-Schema (L5)

```python
class EventStats(BaseModel):
    total: int                              # Anzahl aktive Events des Tenants (deleted_at IS NULL)
    today: int                              # Anzahl Events deren Tag (Tenant-TZ) = heute
    this_week: int                          # Anzahl Events im aktuellen Mo–So-Fenster
    by_type: dict[str, int]                 # {"termin": 12, "urlaub": 3, "abwesenheit": 1, "kurs": 4}
    by_status: dict[str, int]               # {"approved": 18, "pending": 1, "rejected": 0}
```

### 10.2 TodaySummary-Schema

```python
class TodaySummary(BaseModel):
    event_count_today: int                  # für Heim-Karte "Heute"
    staff_count_today: int                  # Anzahl Staff ohne (Urlaub|Abwesenheit) heute,
                                            # = persons(kind=staff, active=True) − Events(type∈{urlaub,abwesenheit}, today)
    next_event: EventListItem | None        # nächstes anstehende Event ab JETZT
```

Code-Layout:

```
shiksha_engine/
  models/
    event.py                — Event-Model
  schemas/
    event.py                — EventOut, EventListItem, EventCreate, EventPatch, EventStats
  routers/
    calendar.py             — REST-Endpoints
  services/
    event_types.py          — Validation, color-mapping, edition-aware types
    calendar_query.py       — Filter-Builder für ?from=&to=&type=...
  alembic/versions/
    20260513_0008_events.py — Migration
```

---

## 11. Sub-Schritt-Aufteilung

```
5.5.4.0     Diese Spec                                                ← Du bist hier
5.5.4.1     DB-Migration + Models + Schemas                           (~140 LOC)
              • events-Tabelle, organizations.timezone-Spalte
              • Event-Model, EventStats, TodaySummary
5.5.4.2     Endpoints + Berechtigungs-Enforcement + Tests             (~450 LOC + ~18 Tests)
              • 4 Berechtigungs-Tests laut §6.4
              • Urlaub-Status-Visibility, virtuelle Geburtstage
5.5.4.3     Daten-Import-Skript + Person-ID-Lookup                    (~200 LOC)
5.5.4.4     kalender.html — Tag-View                                  (~350 LOC)
5.5.4.5     kalender.html — Woche- + Monat-View                       (~400 LOC)
5.5.4.6.a   Heim-Provider + Karten                                    (~150 LOC + 3-5 Tests)
              • calendar.today_summary Provider mit eigenen Queries
              • Drei neue Karten in editions/kita.yaml
              • Frisch deployed → Voraussetzung für 6.b
5.5.4.6.b   Bridge-Trim + Final-Smoke                                 (~30 LOC)
              • kita/calendar aus Whitelist
              • Modul gesamtgrün
```

Brutto sieben Drops, über 4-5 Iterationen kompakt durchspielbar — analog Personen. Der 5.5.4.6-Split trennt das Provider-Build (das Calendar-Backend nutzt) vom Whitelist-Trim (der das Calendar-Backend voraussetzt) und macht den Smoke-Test sauberer.

---

## 12. Akzeptanzkriterien (Modul gesamt)

1. ✅ Mira kann auf `/kalender.html` ihre Woche überblicken, Termin/Urlaub/Abwesenheit anlegen, Personen zuordnen
2. ✅ Event-Types sind farbig/visuell unterscheidbar in allen drei Ansichten
3. ✅ Mobile-First: alle Ansichten funktionieren auf 399px Viewport
4. ✅ Drei Heim-Karten (Heute/Diese Woche/Kalender) verlinken in passende Ansicht
5. ✅ Legacy-Daten importiert mit Person-Verknüpfung
6. ✅ Tests grün (mind. 15 neue: CRUD, Tenant-Iso, Person-Filter, Stats, Person-ID-Lookup im Importer)
7. ✅ Bridge-Whitelist für `kita/calendar` entfernt
8. ✅ Design-System v1.0.0 weiter belastungsgetestet — kein neues CSS außer Event-Type-Color-Mapping

---

## 13. Designfragen (alle in v2 beantwortet)

**F1 — Wiederholung:** ✅ Client-side Multi-Insert MIT `metadata.recurrence_group=<uuid>` und `metadata.recurrence_index=1..N` als Anker. Phase 1 nutzt den Anker nicht aktiv, Phase 2 kann mit Server-Endpoint "Reihe ab Datum X verschieben/löschen" nachziehen ohne Schema-Change.

**F2 — Geburtstage virtuell:** ✅ Ja, mit expliziter Berechtigungs-Logik (§4.6 + §6). Eltern/Teilnehmer sehen nur Geburtstage von Personen mit `participants`-Verknüpfung. Leitung/Pädagogin sehen alle. Synthetic Events sind read-only.

**F3 — Eingewöhnung als Subtype:** ✅ Ja über `metadata.subtype`. PLUS: `editions/<edition>.yaml > event_subtypes` als UI-Hilfe (siehe §3.1). Mira tippt nicht selber, sondern wählt aus Datalist-Vorschlägen.

**F4 — Color-Override:** ✅ Keine freie Color-Wahl, sondern drei Urgency-Stufen `normal | important | urgent` mit CSS-Mapping in `kita.v1.0.0.css` (siehe §4.5). Verhindert Outlook-Bunter-Teppich.

**F5 — Pädagogin-Privacy:** ✅ Urlaub mit `metadata.status != 'approved'` ist nur für Antragsteller + leitung/developer sichtbar. Genehmigter Urlaub (Default) ist für alle Tenant-Mitglieder sichtbar. `pending` ist Phase-2-Konzept (§6.3).

---

## 14. Was als nächstes

→ **5.5.4.1** — DB-Migration + Models + Schemas als erstes Drop-Paket. Dann sind wir auf den Schienen.

---

**Bindend für alle folgenden Drops dieses Moduls.** Änderungen an dieser Spec werden hier protokolliert.

### Änderungen
- v1 · 2026-05-13 · Initial draft (Claude)
- v2 · 2026-05-13 · F1-F5 beantwortet, L1 Time-Zone-Handling ergänzt, §3.1 `event_subtypes`-Pattern, §4.5 Urgency-Stufen, §4.6 Geburtstage-Logik, §6 Berechtigung präzisiert + L3 Test-Anforderungen, §10.1/10.2 EventStats + TodaySummary definiert, §11 5.5.4.6 in 6.a + 6.b gesplittet (Claude Code review feedback)

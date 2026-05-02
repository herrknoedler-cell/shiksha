# SHIKSHA — SCHULE.EDITION BUILD PACK V1

**Stand:** 25. April 2026
**Aufbaut auf:** SHIKSHA V4 (19.04.2026), CLUB.EDITION Architektur, Marktanalyse SCHULE/CAMPING V1 (25.04.2026)
**Zweck:** SCHULE.EDITION soweit deployen-bereit machen, dass mit Leuchtturm-Partnern reale Daten in das System fließen können.

---

## 1. STATUS IN EINEM SATZ

SCHULE.EDITION ist die fünfte SHIKSHA-Edition (nach business, restaurant, camp, stitch), spezialisiert auf inhaber-geführte Bildungsbetriebe — Yogaschulen, Surfschulen, Tanz-, Reit-, Skischulen — mit zwei voll spezifizierten Fiktiv-Beispielen (Yogaschule Wien, Surfschule Sylt) und Drop-in-Inhalten zur Validierung des document.module-Foto-Flows ohne Drittdaten.

---

## 2. EDITION-PROFIL (DEPLOY-FERTIG)

```json
{
  "edition": "schule.shiksha",
  "version": "1.0.0",
  "lead_domain": "education",
  "supporting_domains": [
    "scheduling",
    "weather",
    "communications",
    "payments",
    "safeguarding"
  ],
  "modules_reused": [
    "people",
    "activity",
    "resource",
    "participation",
    "safeguarding",
    "competency",
    "assessment",
    "knowledge",
    "partnership",
    "funding",
    "document",
    "accounting",
    "calendar"
  ],
  "modules_new": [
    "course",
    "enrollment",
    "package",
    "instructor_qualification",
    "weather_dependency"
  ],
  "entities": [
    "School",
    "Student",
    "Guardian",
    "Instructor",
    "Course",
    "CourseSession",
    "Enrollment",
    "Package",
    "Equipment",
    "InstructorLicense",
    "Assessment",
    "WeatherWindow"
  ],
  "policies": [
    {
      "key": "schule.no_auto_certification",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Prüfungs-Ergebnisse (Surf-Level, Yoga-Stufe, Reit-Abzeichen) brauchen explizite Lehrer-Bestätigung. Kein automatisches Bestehen."
    },
    {
      "key": "schule.no_auto_minor_communication",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Bei Schülern unter 16 geht jede Kommunikation an den Guardian. SHIKSHA versendet nichts ohne explizite Operator-Freigabe."
    },
    {
      "key": "schule.consent_required_for_minors",
      "level": "block",
      "scope": "Gate 1 — Intake",
      "rationale": "Anmeldung minderjähriger Schüler ohne dokumentierten Guardian-Consent ist gesperrt."
    },
    {
      "key": "schule.weather_advisory_only",
      "level": "warn",
      "scope": "Gate 2 — Routing",
      "rationale": "Wetter-basierte Verschiebungen werden vorgeschlagen, nie automatisch ausgeführt."
    },
    {
      "key": "schule.instructor_license_check",
      "level": "warn",
      "scope": "Gate 2 — Routing",
      "rationale": "Vor Kurs-Zuweisung prüft der Orchestrator die Lizenz-Gültigkeit. Abgelaufene Lizenz blockiert Zuweisung."
    }
  ],
  "language_modes": ["flow", "action", "alert"],
  "reference_cases": [
    "SCHULE_001 (Yogaschule, Indoor, ganzjährig, Multi-Lehrer)",
    "SCHULE_002 (Surfschule, Outdoor, saisonal, wetter-dependent)"
  ],
  "fixtures_path": "/fixtures/schule_edition/",
  "review_required_default": true
}
```

---

## 3. MODUL-KOMPOSITION

### 3.1 Wiederverwendete Module aus dem generischen Vokabular

Diese Module kommen 1:1 aus der CLUB.EDITION-Architektur und werden in SCHULE genutzt:

| Modul | SCHULE-spezifische Verwendung |
|---|---|
| `people` | Schüler, Lehrer, Eltern (Guardian-Link kritisch bei Minderjährigen) |
| `activity` | Wird zu `CourseSession` konkretisiert — eine konkrete Stunde, ein konkreter Termin |
| `resource` | Räume (Yoga-Studios, Surf-Spots, Skipisten), Equipment (Boards, Matten, Skier) |
| `participation` | Anwesenheit, Streak-Detection für Retention |
| `safeguarding` | **Pflichtmodul** bei Minderjährigen-Betrieb: Schutzkonzept, Background-Checks, Einverständnisse, Incident-Reports |
| `competency` | Surf-Level (Anfänger/Fortgeschritten), Yoga-Stufe, Reit-Abzeichen |
| `assessment` | Prüfungen mit Evidence (Foto/Video), Beobachtungs-Notizen |
| `knowledge` | Sicherheitshinweise, Lehrinhalte, Theorie |
| `partnership` | Hersteller (Boards, Matten), Versicherung, lokale Kooperationen |
| `funding` | Bildungsschecks, Sportförderung, Vereinsförderung |
| `document` | Anmeldung-PDF, Rechnung, Mahnung, Versicherungs-Polizze (heute schon produktiv!) |
| `accounting` | Offene Posten pro Schüler, Paket-Verbrauch, Lehrer-Honorare |
| `calendar` | Kursplan, Saisonkalender, Schulferien |

### 3.2 SCHULE-spezifische Module (neu)

#### `course`
Eine zeitlich strukturierte Lehr-Einheit aus mehreren Sessions.

**Objekte:**
- `course` — Surf-Anfängerkurs Juli, Yoga-Block 6-Wochen, Skischule Klasse 3 Woche 7
- `course_template` — wiederverwendbare Vorlage (Curriculum, Anzahl Sessions, Equipment-Bedarf)
- `course_session` — eine konkrete Stunde (Montag 18 Uhr, Surf-Spot Westerland, Lehrer Pia)
- `course_status` — `planned`, `enrollment_open`, `running`, `completed`, `cancelled`, `weather_postponed`

**Signale:**
- `course.enrollment_threshold_reached` — genug Schüler für Durchführung
- `course.understaffed` — kein Lehrer zugewiesen oder Lehrer fällt aus
- `course.weather_critical` — Wetter macht Outdoor-Durchführung unsicher
- `course.completion_rate_low` — viele Schüler erscheinen nicht zu späteren Sessions

**Abhängigkeiten:** `people`, `resource`, `instructor_qualification`, `weather_dependency`

#### `enrollment`
Anmeldung eines Schülers zu einem konkreten Kurs.

**Objekte:**
- `enrollment` — Schüler X meldet sich für Kurs Y an
- `enrollment_status` — `inquiry`, `pending_consent` (bei Minderjährigen), `confirmed`, `cancelled`, `waitlist`
- `consent_record` — wer hat wann was bestätigt
- `trial_class_record` — Probestunde besucht? Ergebnis?

**Signale:**
- `enrollment.consent_overdue` — Anmeldung wartet seit 5 Tagen auf Guardian-Consent
- `enrollment.waitlist_promotion_available` — Platz frei, nächste Person auf Warteliste
- `enrollment.trial_followup_due` — Probestunde war vor 3 Tagen, kein Anschluss

**Abhängigkeiten:** `people`, `course`, `safeguarding`, `package`

#### `package`
Mengenrabatt-Logik: 10er-Karte, Monatskarte, Jahresabo, Kursblock.

**Objekte:**
- `package_template` — "10er-Karte Yoga 6 Monate gültig 180€"
- `package_instance` — Schüler X hat diese 10er-Karte gekauft, 6 verbraucht, läuft ab am DD.MM.YYYY
- `package_consumption_record` — eine Einlösung
- `package_status` — `active`, `paused`, `consumed`, `expired`, `refunded`

**Signale:**
- `package.expiring_soon` — Karte läuft in 14 Tagen ab, 4 Sessions ungenutzt
- `package.consumption_anomaly` — 10er-Karte in 3 Tagen aufgebraucht (Cluster-Verhalten erkennen)
- `package.refund_request_pending` — Schüler hat Rückerstattung beantragt

**Abhängigkeiten:** `people`, `accounting`, `enrollment`

#### `instructor_qualification`
Lehrer-Lizenz, Weiterbildung, Verfügbarkeit.

**Objekte:**
- `instructor_license` — DSV-Skilehrer Anwärter, Yoga Alliance RYT-200, ISA Surf Instructor Level 1
- `license_validity` — Ausstellungsdatum, Ablaufdatum, Erneuerungs-Frist
- `availability_window` — Lehrer Pia ist montags und mittwochs verfügbar, im Juli komplett
- `qualification_match` — Welcher Lehrer kann welchen Kurs unterrichten?

**Signale:**
- `instructor.license_expiring` — Lizenz läuft in 60 Tagen ab
- `instructor.under_qualified_for_assignment` — Versuch, Lehrer ohne passende Lizenz zuzuweisen
- `instructor.overload_detected` — Trainer trägt 60% der Stunden in dieser Woche
- `instructor.background_check_due` — Führungszeugnis-Erneuerung fällig

**Abhängigkeiten:** `people`, `safeguarding`, `assessment`

#### `weather_dependency`
Wetter-Abhängigkeit für Outdoor-Sport-Kurse (Surf, Ski, SUP, Klettern).

**Objekte:**
- `weather_window` — geplantes Zeitfenster für eine Session
- `weather_signal` — Open-Meteo-Daten + Schwellwert-Logik
- `decision_record` — Operator hat um 16:00 entschieden: Verschiebung um 24h
- `alternative_plan` — Indoor-Theorie, Equipment-Wartung, Verschiebungs-Slot

**Signale:**
- `weather.go_no_go_decision_due` — 18 Stunden vor Session, Wetter unsicher, Entscheidung fällig
- `weather.threshold_breach` — Wind > 35 kn = Surf-Stopp
- `weather.window_recovery` — nach Verschiebung wieder geeignete Bedingungen
- `weather.communication_pending` — Verschiebung beschlossen, Schüler noch nicht informiert

**Abhängigkeiten:** `course`, `course_session`, `communications`

### 3.3 Modul-Abhängigkeitsgraph

```
            ┌──────────────────────────────────┐
            │  SCHULE_ORCHESTRATOR             │
            │  Sprache · Patterns · Focus      │
            └──────────────────────────────────┘
                    ▲ alle Signale, gewichtet
                    │
    ┌───────────────┼─────────────────────────────┐
    │               │                             │
course   ←→   enrollment   ←→   package   ←→   accounting
    │               │                             ↑
    │               ▼                             │
    │         safeguarding ────► consent_record   │
    │               │
    ├──► instructor_qualification ←─ people ──────┘
    │
    └──► weather_dependency ←─ Open-Meteo
            │
            ▼
        course_session ←→ resource (Spot, Equipment)
```

---

## 4. POLICY GATES (DETAILLIERT)

### Gate 1 — Intake

| Trigger | Policy | Verhalten |
|---|---|---|
| Anmeldung Minderjähriger ohne Consent | `schule.consent_required_for_minors` | block — `pending_consent` Status, Operator wird informiert |
| Anmeldung mit unklarem Geburtsdatum | `schule.age_verification_required` | warn — Operator muss bestätigen |
| Foto-Upload ohne erkennbare Felder | `document.unreadable` | warn — Confidence < 0.3, "Ich kann das gerade nicht lesen — neues Foto?" |

### Gate 2 — Routing

| Trigger | Policy | Verhalten |
|---|---|---|
| Kurs ohne Lehrer-Zuweisung 24h vor Start | `schule.understaffed_alert` | alert — eskaliert zur Operator-Sicht |
| Outdoor-Kurs, Wetter unsicher 18h vor Start | `schule.weather_advisory_only` | warn — Vorschlag generieren, nicht ausführen |
| Lehrer-Zuweisung ohne passende Lizenz | `schule.instructor_license_check` | block — Zuweisung scheitert mit Sprache "Pia hat (noch) keinen ISA Level 1 — soll Tom übernehmen?" |

### Gate 3 — Action

| Trigger | Policy | Verhalten |
|---|---|---|
| Kommunikation an Schüler unter 16 | `schule.no_auto_minor_communication` | block — geht immer an Guardian |
| Prüfungs-Ergebnis automatisch eintragen | `schule.no_auto_certification` | block — braucht Lehrer-Signatur |
| Refund-Auszahlung ohne Operator-Freigabe | `schule.no_auto_refund` | block — Vorschlag, nie Ausführung |
| Wetter-Verschiebung an alle Schüler | `schule.weather_advisory_only` | block — Vorschlag, Operator wählt Empfänger |

### Gate 4 — Learning

| Trigger | Policy | Verhalten |
|---|---|---|
| Schüler-Verhaltens-Pattern (z.B. Streak) | `schule.pattern_promotion_with_consent` | warn — Pattern wird gespeichert, Promotion erst nach Operator-Bestätigung |
| Lehrer-Bewertungs-Aggregat | `schule.no_auto_instructor_rating` | block — nie vom System aggregiert |

---

## 5. LANGUAGE LAYER — SCHULE-SPEZIFISCH

Sprache entsteht im Orchestrator (V4-Prinzip 3). SCHULE-Texte werden im `text_key`-Vokabular wie folgt benannt:

```yaml
schule.enrollment.consent_pending:
  flow:    "Lukas wartet auf Mama"
  action:  "Erinnern an Lukas Mutter?"
  alert:   "Lukas Anmeldung läuft ab"

schule.course.weather_unsicher:
  flow:    "Donnerstag noch offen"
  action:  "Plan B vorschlagen?"
  alert:   "Sturm Donnerstag — entscheiden"

schule.instructor.license_expiring:
  flow:    "Toms Lizenz läuft"
  action:  "Tom an Erneuerung erinnern?"
  alert:   "Toms Lizenz endet morgen"

schule.package.expiring_soon:
  flow:    "Annas Karte fast aus"
  action:  "Anna Erinnerung schicken?"
  alert:   "Annas Karte verfällt heute"

schule.participation.streak_broken:
  flow:    "Sarah seit 14 Tagen weg"
  action:  "Kurz bei Sarah nachfragen?"
  alert:   "—"

schule.course.understaffed:
  flow:    "Surfkurs braucht Lehrer"
  action:  "Tom oder Pia anbieten?"
  alert:   "Kurs morgen ohne Lehrer"

schule.instructor.overload:
  flow:    "Tom trägt diese Woche 60%"
  action:  "Sarah bitten einzuspringen?"
  alert:   "—"

schule.assessment.evidence_missing:
  flow:    "Lukas Surf-Level offen"
  action:  "Foto/Video ergänzen?"
  alert:   "—"
```

**Confidence in Sprache, nicht Prozent:**
- hoch (>0.85) → "Soll ich Anna anschreiben?"
- mittel (0.6–0.85) → "Vermutlich Anna Fischer. Stimmt das?"
- niedrig (<0.6) → "Für wen ist das?"

---

## 6. REFERENZFÄLLE

### SCHULE_001 — Yogaschule Wien (Indoor, ganzjährig)

**Schule:** "Lichtquelle Wien" (fiktiv) — 2 Räume, 5 Lehrer, ~120 aktive Schüler
**Standort:** Wien 7. Bezirk, Burggasse
**Geschäftsmodell:** Drop-in (25€), 10er-Karte (180€), Monatskarte (110€), Workshops
**Kursangebot:** Hatha, Vinyasa, Yin, Pre-Natal, Kinder-Yoga (Safeguarding!)

**Komplexität, die SHIKSHA validiert:**
- Multi-Lehrer-Plan mit Vertretungs-Logik
- Paket-Logik mit Verfall
- Pre-Natal-Kurse mit medizinischen Auflagen (Hebammen-Bescheinigung)
- Kinder-Yoga mit Guardian-Consent
- Workshops als Sonderfall (Einmal-Buchung, kein Paket)
- Equipment-Verleih (Yogamatte zum Mitnehmen)

**Foto-Test-Dokumente (siehe Fixtures):**
- Anmeldung Probestunde
- Rechnung 10er-Karte
- Mahnung Monatskarte
- Hebammen-Bescheinigung Pre-Natal
- Lieferschein Yogamatten-Großhändler
- Versicherungs-Erstrechnung

### SCHULE_002 — Surfschule Sylt (Outdoor, saisonal, wetter-dependent)

**Schule:** "Inselwellen Sylt" (fiktiv) — Westerland, 2 Spots (Brandenburger Strand + Buhne 16)
**Standort:** Westerland, Sylt
**Geschäftsmodell:** Tageskurs (95€), 5-Tage-Camp (480€), Privat-Stunde (110€/h), Equipment-Verleih
**Lehrer:** 1 ganzjähriger Inhaber, 4 Saison-Lehrer (Mai–Oktober), ISA-zertifiziert

**Komplexität, die SHIKSHA validiert:**
- Saison-Lehrer-Onboarding (Lizenz-Check, Verträge, Einverständnisse)
- Wetter-Abhängigkeit (Wind, Wellen, Tide) als Erstklass-Signal
- Verschiebungs-Logik (Plan B: Theorie, Plan C: ganz absagen)
- Multi-Sprache (Deutsch, Englisch, Niederländisch)
- Equipment-Logistik (Boards, Wetsuits — Größen, Schäden)
- Kombi mit Unterkunft (Surfcamp inkl. Pension)
- Versicherungs-Reibung (Verletzungs-Risiko Outdoor)

**Foto-Test-Dokumente (siehe Fixtures):**
- Anmeldung 5-Tage-Camp (englisch)
- Wetter-Verschiebungs-Email
- Rechnung Privat-Stunde
- Lieferschein Wetsuit-Großhändler
- Versicherungs-Mahnung
- Behördenpost Strandzonen-Genehmigung

---

## 7. DATENBANK-ERWEITERUNGEN

Vollständige SQL-Migration: siehe `server/schule_db_migration.sql` (separate Datei).

**Kerntabellen, die ergänzt werden:**

```sql
-- schools (Schule selbst als Entity-Erweiterung)
CREATE TABLE schools (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  edition TEXT DEFAULT 'schule.shiksha',
  type TEXT,                          -- 'yoga', 'surf', 'ski', 'dance', 'riding'
  primary_address JSONB,
  secondary_locations JSONB,
  business_hours JSONB,
  weather_dependent BOOLEAN DEFAULT FALSE,
  has_minors BOOLEAN DEFAULT FALSE,   -- triggert safeguarding-Modul
  insurance_info JSONB,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- students
CREATE TABLE students (
  id TEXT PRIMARY KEY,
  school_id TEXT REFERENCES schools(id),
  full_name TEXT NOT NULL,
  birthdate DATE,
  is_minor BOOLEAN GENERATED ALWAYS AS (
    birthdate > CURRENT_DATE - INTERVAL '18 years'
  ) STORED,
  guardian_ids TEXT[],
  contact JSONB,
  level JSONB,                        -- per Disziplin
  consent_records JSONB,
  medical_notes TEXT,
  enrolled_courses TEXT[],
  active_packages TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- instructors
CREATE TABLE instructors (
  id TEXT PRIMARY KEY,
  school_id TEXT REFERENCES schools(id),
  full_name TEXT NOT NULL,
  contact JSONB,
  licenses JSONB,                     -- [{type, level, valid_until, issued_by}]
  background_check JSONB,             -- {valid_until, file_id}
  availability JSONB,
  hourly_rate NUMERIC,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- courses
CREATE TABLE courses (
  id TEXT PRIMARY KEY,
  school_id TEXT REFERENCES schools(id),
  name TEXT NOT NULL,
  type TEXT,
  level TEXT,
  capacity_min INTEGER,
  capacity_max INTEGER,
  price NUMERIC,
  currency TEXT DEFAULT 'EUR',
  duration_minutes INTEGER,
  weather_dependent BOOLEAN DEFAULT FALSE,
  status TEXT DEFAULT 'planned',
  start_date DATE,
  end_date DATE,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- course_sessions
CREATE TABLE course_sessions (
  id TEXT PRIMARY KEY,
  course_id TEXT REFERENCES courses(id),
  scheduled_at TIMESTAMPTZ,
  location JSONB,
  instructor_id TEXT REFERENCES instructors(id),
  status TEXT DEFAULT 'scheduled',    -- 'scheduled', 'running', 'completed', 'weather_postponed', 'cancelled'
  postponement_reason TEXT,
  rescheduled_to TIMESTAMPTZ,
  attendance JSONB,
  notes TEXT
);

-- enrollments
CREATE TABLE enrollments (
  id TEXT PRIMARY KEY,
  student_id TEXT REFERENCES students(id),
  course_id TEXT REFERENCES courses(id),
  status TEXT DEFAULT 'inquiry',
  consent_status TEXT,
  trial_class_session_id TEXT,
  enrolled_at TIMESTAMPTZ DEFAULT NOW(),
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT
);

-- packages
CREATE TABLE package_templates (
  id TEXT PRIMARY KEY,
  school_id TEXT REFERENCES schools(id),
  name TEXT NOT NULL,
  count INTEGER,                      -- Anzahl Sessions
  price NUMERIC,
  validity_days INTEGER,
  applicable_course_types TEXT[]
);

CREATE TABLE package_instances (
  id TEXT PRIMARY KEY,
  template_id TEXT REFERENCES package_templates(id),
  student_id TEXT REFERENCES students(id),
  remaining_count INTEGER,
  purchased_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  status TEXT DEFAULT 'active'
);

CREATE TABLE package_consumptions (
  id TEXT PRIMARY KEY,
  package_instance_id TEXT REFERENCES package_instances(id),
  course_session_id TEXT REFERENCES course_sessions(id),
  consumed_at TIMESTAMPTZ DEFAULT NOW()
);

-- weather_windows
CREATE TABLE weather_windows (
  id TEXT PRIMARY KEY,
  course_session_id TEXT REFERENCES course_sessions(id),
  forecast_data JSONB,
  decision_required_at TIMESTAMPTZ,
  decision TEXT,                      -- 'go', 'no_go', 'postpone'
  decided_by TEXT,
  decided_at TIMESTAMPTZ
);

-- guardians (Vormünder/Eltern)
CREATE TABLE guardians (
  id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  contact JSONB,
  related_students TEXT[],
  consent_history JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. API-ENDPOINTS (NEU)

```
SCHULE EDITION
==============
GET    /schule/state                          — SchoolState (Sprachfähig, analog ClubState)
GET    /schule/state/summary                  — Kompakte Sprache, ein Satz

POST   /schule/courses                        — Kurs anlegen
GET    /schule/courses                        — Liste mit Filter
GET    /schule/courses/{id}                   — Detail
POST   /schule/courses/{id}/sessions          — Sessions hinzufügen

POST   /schule/enrollments                    — Anmeldung anlegen
GET    /schule/enrollments                    — Filter (offen, wartend, bestätigt)
POST   /schule/enrollments/{id}/consent       — Consent dokumentieren

POST   /schule/students                       — Schüler anlegen (mit Guardian-Logik)
GET    /schule/students/{id}                  — Stammdaten + Pakete + Kurse

POST   /schule/instructors                    — Lehrer anlegen
GET    /schule/instructors/{id}/availability  — Verfügbarkeit + Lizenz-Check

POST   /schule/packages                       — Paket-Template
POST   /schule/packages/instances             — Paket kaufen
POST   /schule/packages/consume               — Paket-Einlösung

POST   /schule/weather/check                  — Wetter-Entscheidung anstoßen
POST   /schule/weather/decide                 — Operator-Entscheidung speichern

POST   /schule/orchestrate                    — Volle Orchestrierung (Patterns, Focus, Actions)
POST   /schule/orchestrate/summary            — Kompakt
```

---

## 9. EINGABEMASKEN (OPERATOR-UI)

Drei Kern-Eingabemasken im SHIKSHA-Sprachstil. Vollständige HTML-Mockups:
- `ui/operator_kurs_anlegen.html`
- `ui/operator_anmeldung.html` (Anmeldung mit Consent-Logik)
- `ui/operator_wetter_entscheiden.html` (Surf-spezifisch)

**Sprachregeln im UI** (aus V4):
- Max 3–6 Wörter pro Zeile
- Keine Erklärungen
- Keine Prozentzahlen
- Confidence in Sprache, nicht Zahl
- Statt Feldliste → ein formulierter Satz nach Speichern

---

## 10. MOBILE-APPS (TEILNEHMER-SICHT)

Eine PWA-fähige HTML-Anwendung mit drei Hauptscreens:

**Datei:** `ui/teilnehmer_app.html`

**Screens:**
1. **Heute** — was heute ansteht (oder das nächste was passiert)
2. **Stundenplan** — kommende Sessions mit Status (geplant, verschoben, abgesagt)
3. **Mein Kram** — Pakete, Anwesenheit, Fortschritt, Equipment-Reservierungen

**Sprachregeln** wie Operator-UI: max 3–6 Wörter, sprachorientiert.

---

## 11. AUSWERTUNGEN (DASHBOARD)

Datei: `ui/operator_dashboard.html`

**Aufbau analog ClubState:**
- Eine sprachliche Zusammenfassung oben (1–2 Sätze)
- Recent Signals mit Severity
- Patterns (z.B. "Mittwochs-Yoga 18 Uhr seit 4 Wochen ausgebucht")
- Recommended Focus (3 Aktionen mit höchster Wirkung)
- Drilldowns: Engagement, Trainer-Last, Retention, Finanzen

---

## 12. FIKTIVE INHALTE (KI-GENERIERT)

**Pfad:** `fixtures/schule_edition/ai_documents/`

12 vorbereitete Dokumente, geeignet für Foto-Tests, OCR-Validierung, Edition-Härtung:

**Yogaschule Wien:**
1. `yoga_anmeldung_lukas_minor.md` — Anmeldung Kinderkurs mit Guardian-Consent
2. `yoga_rechnung_10er_karte.md` — Rechnung Lichtquelle Wien
3. `yoga_mahnung_monatskarte.md` — Mahnung wegen offener Monatskarte
4. `yoga_hebammen_bescheinigung.md` — Medizinische Freigabe Pre-Natal
5. `yoga_lieferschein_matten.md` — Großhändler-Lieferschein
6. `yoga_versicherung_erstrechnung.md` — Wiener Städtische Versicherung

**Surfschule Sylt:**
7. `surf_anmeldung_5tage_english.md` — Niederländischer Gast, englisch
8. `surf_wetter_verschiebung.md` — Verschiebungs-Email an Gruppe
9. `surf_rechnung_privat_stunde.md` — Rechnung
10. `surf_lieferschein_wetsuits.md` — Großhändler ION
11. `surf_versicherung_mahnung.md` — Sportversicherung
12. `surf_behoerde_strandzonen.md` — Genehmigung Gemeinde Sylt

Jedes Dokument ist:
- realistisch formuliert (deutsch oder englisch je nach Kontext)
- mit korrekten österreichischen / deutschen Adressformaten
- mit plausiblen UID/Steuernummern (klar als fiktiv markiert)
- für SHIKSHA-Foto-Flow als Klartext-Vorlage geeignet

---

## 13. DEPLOY-ANLEITUNG (SCHRITT FÜR SCHRITT)

### 13.1 Workspace-Teil (lokal, schon fertig)
Alle UI-Mockups, Fixtures, Dokumente sind im Workspace bereit. Können sofort lokal angeschaut, kopiert oder weiter iteriert werden.

### 13.2 Server-Teil (auf shiksha.tun.zone deployen)

**Schritt 1 — Code auf Server kopieren:**
```bash
# Vom lokalen Workspace
scp -i ~/.ssh/shiksha_key \
    server/schule_models.py \
    server/schule_orchestrator.py \
    server/schule_db_migration.sql \
    root@88.99.174.186:/opt/shiksha/
```

**Schritt 2 — DB-Migration ausführen:**
```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186
sudo -u postgres psql -d shiksha -f /opt/shiksha/schule_db_migration.sql
```

**Schritt 3 — main.py erweitern:**
Importe und Router-Inklusion hinzufügen (siehe `server/MAIN_PY_PATCH.md`).

**Schritt 4 — Service neu starten:**
```bash
systemctl restart shiksha
systemctl status shiksha
journalctl -u shiksha -f
```

**Schritt 5 — Smoke-Test:**
```bash
curl http://shiksha.tun.zone/health
curl http://shiksha.tun.zone/schule/state
```

**Schritt 6 — Fixtures laden (Yogaschule Wien):**
```bash
curl -X POST http://shiksha.tun.zone/schule/import \
     -H "Content-Type: application/json" \
     -d @fixtures/yogaschule_wien.json
```

---

## 14. WAS NACH DIESER SESSION FEHLT

| Fehlt | Wer | Wann |
|---|---|---|
| Realer Foto-Test mit fiktiven Dokumenten | Du, mit dem Handy | 1–2 h |
| Anpassung document.module-Felder für Anmeldung-Bögen | Build | nächste Session |
| safeguarding-Modul (V1) implementieren | Build | nächste Session |
| Pre-Pilot-Test mit komplettem Flow | Du + ein Helfer | Halbtag |
| CAMPING.EDITION-Build-Pack (analog) | Build | nächste Session |
| 90-Sekunden-Foto-Demo aufnehmen | Du | 1 h |
| Outreach an erste Yoga-Studios | Du | sobald Demo fertig |

---

## 15. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL FÜR SCHULE)

1. SCHULE.EDITION ist eine Komposition aus 13 generischen + 5 spezifischen Modulen — kein Neubau.
2. `safeguarding` ist Pflicht-Modul, sobald `school.has_minors = true`.
3. Wetter-Verschiebung ist immer Vorschlag, nie Ausführung.
4. Prüfungs-/Level-Bestätigung braucht immer einen Menschen (`schule.no_auto_certification`).
5. Kommunikation an Minderjährige geht **immer** an Guardians (`schule.no_auto_minor_communication`).
6. SchoolState (Sprache) entsteht im Orchestrator, nie in Modulen.
7. Foto-Flow ist die primäre Eingabemethode — Eingabemasken sind Backup, nicht Hauptpfad.
8. Mobile-App für Schüler ist read-only-first: Anmelden ja, aber alle Aktionen brauchen Operator-Bestätigung.
9. `package`-Logik ist immer transparent: Schüler sieht jederzeit Stand, Verfall, Rückerstattungs-Optionen.
10. Lehrer-Lizenz-Check ist Block-Policy, nicht nur Warnung — ein Skilehrer-Anwärter darf keinen Aufbaukurs übernehmen.

---

## 16. WIEDEREINSTIEG NACH CHAT-VERLUST

```
1. SCHULE.EDITION Build-Pack V1 ist fertig (25.04.2026)
2. Status:
   - Master-Doc: dieses File
   - Edition-Profile: section 2 (deploy-ready JSON)
   - DB-Schema: server/schule_db_migration.sql
   - Pydantic-Models: server/schule_models.py
   - Orchestrator: server/schule_orchestrator.py
   - Fixtures: fixtures/yogaschule_wien.json + surfschule_sylt.json
   - AI-Dokumente: fixtures/schule_edition/ai_documents/ (12 Stück)
   - Operator-UI: ui/operator_kurs_anlegen.html
   - Teilnehmer-App: ui/teilnehmer_app.html
   - Dashboard: ui/operator_dashboard.html
3. Nächster Schritt: Deploy auf shiksha.tun.zone (siehe section 13)
4. Danach: CAMPING.EDITION als Build-Pack analog dieser Vorlage
```

---

## 17. LETZTER SATZ

SCHULE.EDITION ist nicht erst dann real, wenn der erste Yoga-Lehrer in Wien das Foto seiner Hebammen-Bescheinigung macht — sondern jetzt schon, weil das System weiß, was passieren wird, bevor es passiert ist.

Stand: 25. April 2026 · Build-Pack V1 · Bereit zum Deploy

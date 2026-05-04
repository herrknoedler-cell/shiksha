# SHIKSHA — TAGESAUSKLANG-Modul · Build Pack V0.1

**Stand:** 4. Mai 2026
**Status:** Konzept-Skizze · Umsetzung nach Krummelus-Pilot-Stabilisierung
**Cross-Reference:**
- `master_vision.md` — strategische DNA
- `docs/build-packs/SHIKSHA_DIALOG_BUILD_PACK_V2.md` — Conversational-Engine
- `docs/WORDING_AND_LANGUAGE.md` — Persona + Vokabular
- `docs/pilot/krummelus-lessons-v1.md` — Ursprung der Idee

---

## 1. Die Idee in einem Satz

> *Ein 5-10-Minuten-Ritual am Tagesende, in dem SHIKSHA mit der Trägerin den Tag durchgeht — fragend, hörend, mitschreibend.*

Aus Mira-Pilot, 4. Mai 2026:

> *"Sie kann sich auch gut vorstellen, kurz vor Feierabend ein Ritual von 5-10 Minuten einzuführen, an dem sie an SHIKSHA die Beobachtungen des Tages mitteilt und auf Fragen von SHIKSHA antwortet."*

Diese Aussage hat die Architektur-Strategie verändert: **Onboarding ist einmalig — Tagesausklang ist das Beziehung-bauende Modul.**

---

## 2. Warum das Modul wichtig ist

### Onboarding bringt Daten. Tagesausklang baut Beziehung.

Vergleich:

| Onboarding | Tagesausklang |
|---|---|
| 15-30 Min, einmalig | 5-10 Min, täglich |
| Stammdaten erfassen | Beobachtungen sammeln |
| Setup-Charakter | Ritual-Charakter |
| Frage: *"Wer bist Du?"* | Frage: *"Wie war heute?"* |
| User lernt Software | User trifft eine Person |

### Was das Modul für Mira (und vergleichbare Trägerinnen) löst

```
Pain                                  → Tagesausklang löst
─────────────────────────────────────────────────────────
"Beobachtungen verschriftlichen"      → automatisch beim Erzählen
"Zettel verlieren"                    → existiert als Eintrag, nicht als Zettel
"Den Überblick verlieren"             → tägliche Strukturierung im Dialog
"An alles denken müssen"              → SHIKSHA fragt gezielt nach
"Unsicherheit"                        → ritualisierter Sicherheits-Anker
```

### Marken-Versprechen real machen

Die Marken-DNA *"Lebendig, Lernend, Lieb"* bleibt abstrakt, solange Mira SHIKSHA nur **manchmal** nutzt. Ein tägliches 5-Min-Ritual macht aus Software eine Mit-Arbeiterin.

> *"Das ist die operationalisierte Form der Marke: Mit-Arbeiterin, die jeden Abend kurz vorbeischaut."*

---

## 3. User-Flow

### Trigger

Push-Notification um konfigurierte Uhrzeit (Default: 17:30, individuell anpassbar pro Trägerin):

> *"Tagesausklang. 5 Minuten?"*

Mira antwortet via Tap auf die Notification → SHIKSHA-PWA öffnet sich direkt im Tagesausklang-Modus.

### Konversation

```
SHIKSHA:    Schönen Feierabend, Mira.
            Wie war heute?

Mira:       (tippt frei) War ein guter Tag. Drei Anmeldungen
            für die Sommerzeit, sonst nichts Besonderes.

SHIKSHA:    [Tool-Call: save_day_summary(date=heute, mood='gut',
                                         keywords=['anmeldungen'])]
            
            Drei Anmeldungen — magst Du mir die Namen sagen?
            Dann hab ich sie morgen schon im Blick.

Mira:       Lara, Tobias, Mia. Alle für Sommer 2027.

SHIKSHA:    [Tool-Call: pre_register_children(names=[...], 
                                              start='2027-summer')]
            
            Hab ich. Drei Kinder, Sommer 2027. Eltern bekommen
            heute Abend noch eine Bestätigungs-Mail von mir, ja?

Mira:       Ja, gerne.

SHIKSHA:    [Tool-Call: send_confirmation_emails(...)]
            
            Eine Frage noch: Hast Du heute irgendwo gestockt?
            Etwas, das einfacher hätte gehen sollen?

Mira:       Die Anmeldung. Ich musste dreimal nachfragen,
            ob die Geschwister-Daten dabei sind.

SHIKSHA:    Verstanden. Das schreib ich Dir auf — wir machen
            das Anmelde-Formular am Ende der Woche schlauer.
            
            [Tool-Call: log_friction_point(area='anmeldung',
                                            description='...')]

            Sonst noch was, das ich wissen sollte?

Mira:       Nein, war ruhig. Bis morgen.

SHIKSHA:    Schönen Abend, Mira.
            
            (Modul schließt nach 30 Sekunden Inaktivität.)
```

**Beobachtungen:**

- Drei Tool-Calls passieren still im Hintergrund — Mira sieht das Gespräch, nicht die Mechanik.
- Beobachtungen werden zu DB-Einträgen, ohne dass Mira "ein Formular ausfüllen" muss.
- Anmeldungen-Daten + Friction-Point-Logging entstehen aus normalem Gespräch.
- SHIKSHA hat eine konkrete Aktion versprochen ("Anmelde-Formular schlauer machen") und einen Audit-Trail dafür.

---

## 4. Frage-Architektur

### Kern-Fragen (immer mindestens eine davon)

```
1. Wie war heute?                          → Stimmungs-Anker
2. Welches Kind hat Dich heute überrascht? → Beobachtungs-Trigger
3. Was musst Du Dir merken für morgen?     → Aufgaben-Anker
4. Hast Du heute irgendwo gestockt?        → Friction-Logging
5. Hast Du etwas dem Land zu melden?       → Audit-Trigger
```

### Kontextuelle Anpassung

SHIKSHA wählt Fragen basierend auf:

```python
def select_questions(context):
    questions = []

    # Stimmungs-Anker — immer
    questions.append("wie_war_heute")

    # Bei viel Aktivität: konkretere Folgefragen
    if context.activity_level == 'high':
        questions.append("was_war_heute_anders")
        questions.append("hast_du_gestockt")

    # Bei ruhigem Tag: kürzer
    elif context.activity_level == 'low':
        return questions[:1]  # nur Stimmungs-Anker

    # Wenn Eltern-Push reinkam und unbeantwortet:
    if context.unread_parent_messages > 0:
        questions.append("eltern_push_uebersicht")

    # Wenn ST% unter Soll:
    if context.st_percent_below_threshold:
        questions.append("personal_situation")

    # Wenn Audit fällig:
    if context.audit_due_within_7_days:
        questions.append("audit_vorbereitung")

    # Wenn Geburtstag morgen:
    if context.birthday_tomorrow:
        questions.append("geburtstag_vorbereitung")

    return questions
```

### Frage-Templates pro Kontext

```yaml
wie_war_heute:
  default: "Wie war heute?"
  high_activity: "Volltag heute. Wie ist's gelaufen?"
  monday: "Wie war der Wochenstart?"
  friday: "Wie war die Woche zum Schluss?"

was_war_heute_anders:
  default: "Was war heute anders als sonst?"
  with_birthday: "Mit Lenas Geburtstag heute — wie war die Stimmung?"

hast_du_gestockt:
  default: "Hast Du heute irgendwo gestockt?"
  alternativ: "Wo hat's heute gehakt?"
  alternativ_2: "Was hätte einfacher gehen sollen?"

eltern_push_uebersicht:
  default: "Drei Eltern haben heute geschrieben — magst Du sie kurz durchsehen?"
  with_count: "{count} Eltern-Nachrichten warten — willst Du sie jetzt oder morgen?"

audit_vorbereitung:
  default: "Audit ist in {days} Tagen. Was fehlt Dir noch?"
  urgent: "Audit ist morgen. Lass uns die letzten Punkte durchgehen."

geburtstag_vorbereitung:
  default: "Morgen hat {kind} Geburtstag. Habt Ihr was vorbereitet?"
```

### Tonalitäts-Regeln (aus Wording-Codex)

- Kurze Sätze (8-14 Wörter)
- Mira-Vokabular wo möglich (*"speisen"*, *"verschriftlichen"*)
- Niemals technisch (*"Daten erfassen"*, *"Eintrag speichern"*)
- Sätze fühlen sich an wie sie entstehen, nicht wie vorbereitet

---

## 5. Tech-Architektur

### Modul-Struktur

```
shiksha/tagesausklang_module/
├── __init__.py
├── tagesausklang_engine.py       # Trigger-Logik, Frage-Auswahl,
│                                  #  Conversation-Steuerung
├── tagesausklang_router.py       # FastAPI-Endpoints
├── question_planner.py            # Kontext-basierte Frage-Selektion
├── question_templates.py          # YAML-basierte Templates
├── observation_writer.py          # Beobachtungs-Tagebuch-Persistenz
├── friction_logger.py             # Friction-Point-Logging
└── notification_scheduler.py     # Cron für Push-Notifications
```

### Datenbank-Schema

```sql
-- Konfiguration pro Trägerin
CREATE TABLE tagesausklang_config (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id),
    org_slug        TEXT NOT NULL,
    enabled         BOOLEAN DEFAULT true,
    trigger_time    TIME DEFAULT '17:30',
    timezone        TEXT DEFAULT 'Europe/Vienna',
    days_active     INT[] DEFAULT '{1,2,3,4,5}',  -- Mo-Fr
    UNIQUE (user_id, org_slug)
);

-- Tages-Sessions (eine pro Tag pro Operator)
CREATE TABLE tagesausklang_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id),
    org_slug        TEXT NOT NULL,
    date            DATE NOT NULL,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    duration_seconds INT,
    mood            TEXT,                         -- 'ruhig'|'normal'|'stressig'|'gut'
    keywords        TEXT[],                       -- aus Conversation extrahiert
    summary         TEXT,                         -- LLM-erzeugte Tages-Zusammenfassung
    UNIQUE (user_id, org_slug, date)
);

-- Beobachtungen, die im Tagesausklang entstehen
CREATE TABLE observations (
    id              SERIAL PRIMARY KEY,
    session_id      INT REFERENCES tagesausklang_sessions(id),
    org_slug        TEXT NOT NULL,
    child_id        INT REFERENCES children(id) NULL,
    employee_id     INT REFERENCES employees(id) NULL,
    text            TEXT NOT NULL,
    raw_dialog      TEXT,                         -- Ursprung im Dialog
    tags            TEXT[],
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Friction-Points (Reibungsmomente, die Mira erwähnt hat)
CREATE TABLE friction_points (
    id              SERIAL PRIMARY KEY,
    session_id      INT REFERENCES tagesausklang_sessions(id),
    org_slug        TEXT NOT NULL,
    area            TEXT NOT NULL,                -- 'anmeldung'|'kalender'|'eltern_kommunikation'|...
    description     TEXT NOT NULL,
    severity        INT DEFAULT 1,                -- 1-5, vom LLM eingeschätzt
    status          TEXT DEFAULT 'open',          -- 'open'|'acknowledged'|'resolved'
    promised_action TEXT,                         -- was SHIKSHA versprochen hat
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Konversations-Persistenz (analog Dialog-Modul)
CREATE TABLE tagesausklang_messages (
    id              SERIAL PRIMARY KEY,
    session_id      INT REFERENCES tagesausklang_sessions(id),
    role            TEXT NOT NULL,                -- 'user'|'assistant'|'tool_call'|'tool_result'
    content         TEXT,
    tool_name       TEXT,
    tool_input      JSONB,
    tool_output     JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### Cron-Trigger

```cron
# /etc/cron.d/shiksha-tagesausklang
*/5 * * * * www-data /opt/shiksha/venv/bin/python \
    /opt/shiksha/tagesausklang_module/notification_scheduler.py \
    >> /var/log/shiksha-tagesausklang.log 2>&1
```

Cron alle 5 Min. Script prüft pro `tagesausklang_config`-Eintrag, ob die `trigger_time` (in der konfigurierten Timezone) gerade eintritt — wenn ja, Push-Notification senden.

### Tools (Function-Calling im LLM-Provider)

```python
TAGESAUSKLANG_TOOLS = [
    "save_day_summary",          # Tages-Stimmung + Keywords speichern
    "log_observation",            # Beobachtung zum Kind/Mitarbeiter
    "log_friction_point",         # Reibungspunkt mit Promised-Action
    "pre_register_children",      # Kinder voranmelden
    "send_confirmation_emails",   # Eltern-Bestätigungen
    "schedule_followup",          # Aufgabe für morgen merken
    "get_today_context",          # SHIKSHA holt sich den Tages-Kontext
                                  #  (Eltern-Pushs, ST%, Audit-Stand, etc.)
    "close_session",              # Tages-Session abschließen + Zusammenfassung
]
```

### Persona-Prompt-Erweiterung

System-Prompt ergänzt das Dialog-Build-Pack v2.0 um Tagesausklang-Spezifika:

```
Du bist im Tagesausklang-Modus. Das ist anders als der reguläre Dialog:

- Mira hat gerade Feierabend. Sei kurz und präzise.
- Stell maximal 3-5 Fragen pro Session, nicht mehr.
- Wenn Mira nichts erzählen will, akzeptier das. Sag "Schönen Abend"
  und schließe still.
- Halte das Tempo niedrig. Pausen sind okay.
- Frag nicht nach offiziellen Daten (ZVR, Steuernummer). 
  Tagesausklang ist nicht für Verwaltungs-Eingabe.
- Frag nach Mensch-zu-Mensch-Themen: Stimmung, Beobachtungen,
  Wünsche, Reibungen.

Tools, die Du nutzen darfst (alle still im Hintergrund):
{tagesausklang_tools_documentation}

Tools, die Du im Tagesausklang NICHT nutzt:
- save_user_identity, save_traeger, save_kita_basics 
  (das ist Onboarding-Material)
- create_marketing_site (das ist gezielte Aktion, nicht Tagesausklang)
- Action-Tools mit Bestätigungs-Gates (außer Mira fordert es explizit)
```

---

## 6. UI

### Eintritt

Mira tappt auf die Push-Notification. PWA öffnet sich auf:

```
https://krummelus.shiksha.world/tagesausklang
```

### Layout (Phone)

```
┌──────────────────────────────────────┐
│                                      │
│       Schönen Feierabend, Mira.      │  ← H1, hell, ruhig
│                                      │
│       Wie war heute?                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ Tippe ...                       │  │ ← Eingabe-Feld, fokussiert
│  └────────────────────────────────┘  │
│                                      │
│                                      │
│                                      │
│              5 Min ─ ●                │ ← Tages-Indikator,
│                                      │   sehr dezent
└──────────────────────────────────────┘
```

### Dialog-Verlauf

Konversations-Bubbles, sehr ruhig. SHIKSHA links, Mira rechts. Maximal 2-3 Bubbles sichtbar (alte scrollen weg). Tool-Calls werden NICHT angezeigt — sie passieren im Hintergrund.

### Abschluss

Wenn Session vorbei (Mira schreibt *"bis morgen"* oder schweigt 30 Sek):

```
┌──────────────────────────────────────┐
│                                      │
│       Schönen Abend, Mira.           │
│                                      │
│       Bis morgen.                    │
│                                      │
│                                      │
│                                      │
│  ─── ✓ Tagesausklang vom 4. Mai ──── │
│                                      │
└──────────────────────────────────────┘
```

Tab schließt von selbst nach 5 Sekunden (oder Mira schließt manuell).

### Desktop

Identisches Layout, in der Mitte zentriert, max-width 600px. Apple-style Großformat-Eleganz.

---

## 7. Phasen

### v0.1 — Konzept (heute fertig)

Diese Datei.

### v0.2 — Krummelus-Pilot Manuelle Variante (kommende 2 Wochen)

Bevor Code: Mira testet das Ritual **mündlich** mit Founder. Jeden Abend 5 Min Voice-Call oder Chat-Nachricht via beliebigem Medium. Lessons sammeln. Bevor Code-Sprint startet: 5-10 Tagesausklang-Sessions als Datenbasis.

### v1.0 — MVP-Code (nach Pilot-Lessons, ~5-7 Tage Sprint)

```
□ tagesausklang_engine.py + question_planner.py
□ DB-Migration (alle Tabellen aus Sektion 5)
□ Cron-Trigger-Setup mit timezone-aware Logik
□ 8 Tools verfügbar (siehe Liste oben)
□ PWA-Frontend (Mobile-First)
□ Persona-Prompt-Erweiterung im LLM-Provider
□ Test mit Mira als ersten echten User
```

### v1.1 — Multi-Operator (1 Tag Sprint)

Mira + Mama haben jeweils eigene Tagesausklang-Sessions. SHIKSHA kann an beide unterschiedliche Push-Notifications senden, mit unterschiedlichen Trigger-Zeiten. Optional: Mama bekommt eine Wochen-Übersicht aus Miras Tagesausklängen.

### v1.2 — Voice-Eingabe (optional, später)

Mira tippt aktuell. Wenn sie unterwegs ist (Heimweg, Auto), wäre Voice-Eingabe schneller. Browser-API + Whisper-Cloud.

### v1.3 — Insight-Generierung (langfristig)

Aus 30+ Tagesausklang-Sessions kann SHIKSHA Muster erkennen:

- Welcher Wochentag ist immer stressig?
- Welche Reibungspunkte tauchen wiederkehrend auf?
- Welche Kinder werden überdurchschnittlich oft erwähnt?

Diese Insights als monatlicher "Tagesausklang-Bericht" für die Trägerin.

---

## 8. Krummelus-Pilot — der erste Tagesausklang

### Wann?

Nach Onboarding-Phase 2 abgeschlossen ist (Daten in der DB, PWA installiert, Folge-Termin durchgelaufen). Realistisch: **Mitte/Ende Mai 2026.**

### Konkretes Setup

```
Mira's Konfiguration:
  trigger_time:    17:30
  timezone:        Europe/Vienna
  days_active:     Mo-Fr
  notification:    "Tagesausklang. 5 Minuten?"
```

### Erfolgs-Kriterien für die ersten 14 Tage

```
✓ Mira startet Tagesausklang an mindestens 8 von 10 Werktagen
✓ Durchschnittliche Session-Dauer: 4-7 Minuten (nicht zu kurz, nicht zu lang)
✓ Mindestens 1 Beobachtung pro Session entsteht
✓ Mira schließt Sessions positiv (nicht "egal, bis morgen")
✓ Nach 14 Tagen: Mira sagt "ja, ich mag das" — oder ehrlich "nicht mehr"
```

Wenn nach 14 Tagen Mira sagt *"das hat mir was gegeben"*: **Tagesausklang ist Marken-DNA.**
Wenn sie sagt *"ich vergesse es jeden Tag"*: Trigger-Zeit anpassen, Frage-Formate ändern.
Wenn sie sagt *"das war zu viel"*: Format auf 3 Min straffen oder weniger Tage.

### Mira-Lessons-Loop

Jede Woche der ersten 4 Wochen: Founder reviewed Tagesausklang-Sessions (anonymisiert oder gemeinsam mit Mira). Was funktioniert, was nicht? **Frage-Templates wachsen mit den ersten 100 Sessions.**

---

## 9. Risiken + Mitigationen

### Risiko 1: Mira vergisst es

**Symptom:** Sessions werden ignoriert.

**Mitigationen:**
- Trigger-Zeit anpassen (vielleicht ist 17:30 zu spät, vielleicht zu früh)
- Notification-Wording anpassen (*"Tagesausklang"* vs. *"5 Minuten?"* vs. *"Schon Feierabend?"*)
- Streak-Anzeige: *"3 Tage am Stück — schöne Routine."*

### Risiko 2: Sessions werden zu lang

**Symptom:** 20+ Min, Mira erschöpft.

**Mitigationen:**
- LLM-Prompt: harter Cut bei 5 Fragen
- UI-Indikator *"5 Min ─ ●"* unten zeigt die Norm
- Bei Überlauf: SHIKSHA sagt *"Genug für heute. Den Rest morgen, ja?"*

### Risiko 3: Mira nutzt es als Beschwerde-Kanal

**Symptom:** Jeder Tagesausklang ist Frust-Auslass über andere.

**Mitigationen:**
- Zuhören ohne Bewerten (Marken-DNA)
- ABER: nach 5 Minuten Frust freundlich umlenken: *"Lass uns morgen früh schauen, was Du davon abgeben kannst."*
- Friction-Point-Logging als Ventil mit konkreter Aktion → Mira merkt: SHIKSHA macht was draus.

### Risiko 4: Datenschutz bei Beobachtungen

**Symptom:** Mira erwähnt sehr private Familien-Details über Kinder.

**Mitigationen:**
- Beobachtungen sind nur für Mira + Mama sichtbar (org_slug-gebunden)
- Niemals an externen LLM-Provider gesendet ohne Anonymisierung
- DSGVO-Hinweis im ersten Tagesausklang: *"Was Du mir sagst, bleibt zwischen uns."*
- Beobachtungen können von Mira jederzeit gelöscht werden

### Risiko 5: LLM-Halluzinationen

**Symptom:** SHIKSHA "erinnert sich" an Dinge, die Mira nie gesagt hat.

**Mitigationen:**
- Kontext-Compression mit `known_facts` (Single-Source-of-Truth)
- Bei jeder neuen Tagesausklang-Session: erst aktuellen `known_facts` laden, dann reden
- Bei Widerspruch zwischen LLM-Erinnerung und Datenbank: DB gewinnt

---

## 10. Marken-Stimme im Tagesausklang

Beispiele, wie SHIKSHA *im* Tagesausklang spricht:

✅ Erlaubt:

> *"Schönen Feierabend, Mira."*
> *"Wie war heute?"*
> *"Hab ich gemerkt."*
> *"Sag's mir morgen, wenn Du sie hast."*
> *"Schönen Abend. Bis morgen."*

❌ Nicht erlaubt:

> *"Ihr Tagesausklang-Datensatz wurde gespeichert."*
> *"Vielen Dank für Ihre Eingabe."*
> *"Möchten Sie weitere Daten erfassen?"*

(Verstöße gegen Wording-Codex Liste B + C.)

---

## 11. Zielbild

> *Tagesausklang ist nicht ein Feature. Es ist die operationalisierte Form von Marken-DNA: Mit-Arbeiterin, die jeden Abend kurz vorbeischaut.*
>
> *Wenn Mira nach drei Wochen sagt: "Das gehört jetzt zu meinem Feierabend" — dann ist SHIKSHA mehr als Software.*

---

**Build Pack v0.1 · Stand 4. Mai 2026 · TAGESAUSKLANG als Beziehungs-Modul · Erste Pilot-Tests Mitte Mai 2026 mit Mira Fiel · Code-Sprint nach Pilot-Lessons**

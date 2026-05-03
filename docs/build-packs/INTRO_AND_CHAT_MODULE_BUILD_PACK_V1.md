# SHIKSHA — INTRO & CHAT MODULE BUILD PACK V1.0

**Stand:** 3. Mai 2026
**Aufbaut auf:** SHIKSHA V4-Architektur, Identity-Modul, Marketing-Builder, Bilder-Pool (in Planung), Greeting-Modul
**Zweck:** Zwei zusammengehörige Cross-Edition-Module — *"Wir lernen uns kennen"* (geführte Einführung) + *"shiksha ist da"* (ständiger Chat-Begleiter) — produktionsreif spezifizieren.

**Kontext:** Krummelus-Pilot startet morgen (4. Mai 2026). Build-Pack ist die Spec. Code-Implementation passiert iterativ während des Pilots — die Markdown-Checkliste am Ende dieses Dokuments ist die *analoge Tour*, die Thomas mit Heidi morgen direkt nutzen kann.

---

## TEIL 1 — VISION & MARKENSTIMME

### Das Versprechen

> SHIKSHA ist nicht Software, mit der man arbeitet. SHIKSHA ist eine Mit-Arbeiterin, die mitlernt.

Zwei Berührungspunkte machen das erlebbar:

1. **Erster Tag:** *"Wir lernen uns kennen."* Eine 15-Minuten-Einführung, in der SHIKSHA Deine KITA kennenlernt, und Du SHIKSHA. Kein Onboarding-Pflichtprogramm. Eine Begegnung.

2. **Jeder Tag danach:** *"shiksha ist da."* Ein Chat-Fenster im Dashboard, das immer offen sein kann. Frag, wenn Du was nicht weißt. Lass SHIKSHA was machen, wenn Du keine Lust hast. SHIKSHA lernt mit, was Du oft brauchst.

### Die Stimme

**Immer Du.** Nie Sie. Auch in formalen Kontexten (Audit-Reports, Förderanträge) bleibt das *Gespräch* mit SHIKSHA persönlich. Dokumente nach außen können formal sein — die Konversation mit SHIKSHA ist es nicht.

**Erste Person.** SHIKSHA spricht von sich als "ich". Die Plattform-Site sagt "SHIKSHA", aber im Gespräch heißt es: *"Ich merke mir das."* Das ist die Persona-Konsistenz.

**Lebendig, lernend, lieb.** Nicht hektisch, nicht herablassend, nicht therapeutisch. Wie eine erfahrene Kollegin, die seit zehn Jahren KITA-Verwaltung macht und jetzt mit Dir am Tisch sitzt.

**Beispiele Vorher / Nachher**

| Vorher (technisch) | Nachher (SHIKSHA-Stimme) |
|---|---|
| "Bitte geben Sie die ZVR-Nummer ein." | *"Magst Du mir die ZVR-Nummer geben? Findest Du auf Eurem Vereinsregisterauszug, oben links."* |
| "Onboarding abgeschlossen." | *"Schön, jetzt kennen wir uns."* |
| "Datensatz erfolgreich gespeichert." | *"Hab ich gemerkt."* |
| "Möchten Sie die Tour fortsetzen?" | *"Wir waren bei den Mitarbeitern. Magst Du da weitermachen?"* |
| "Achtung: Stellenprozent unter Soll." | *"Du bist gerade unter Soll. Magst Du sehen, woran's liegt?"* |
| "Marketing-Site erfolgreich erstellt unter https://krummelus.shiksha.world" | *"Eure Seite steht: https://krummelus.shiksha.world. Magst Du sie Dir anschauen?"* |

---

## TEIL 2 — INTRO-MODUL: "Wir lernen uns kennen"

### 2.1. Konzept

Eine geführte Tour von 15-18 Minuten beim ersten Login. Strukturiert in 16 Schritten, jeder pausierbar, alle skip-bar (außer Identity), Fortschritt persistiert pro Operator.

**Kein Modal-Zwang.** Die Tour ist eine Karte im Dashboard ("Wir lernen uns kennen · 5 von 16 Schritten · 9 Min noch"). Erstes Mal öffnet sie sich automatisch im Vollbild-Wizard, jedes weitere Mal nur auf Klick.

**Wiederholbar.** Bei 100% wandelt sich die Karte in: *"Möchtest Du SHIKSHA jemand zeigen? Hier ist die Tour wieder."* Sinnvoll, wenn neue Mitarbeiter:innen dazukommen.

**Cross-Edition.** Die Engine ist generisch, die Schritt-Sequenzen sind edition-spezifisch (KITA, Camping, Schule, Surfschule, Yoga, Club).

### 2.2. Schritt-Sequenz KITA (vollständig, alles auf Du)

```
01. Willkommen                                         (30 sec, Info)
    Schön, dass Du da bist. Ich bin SHIKSHA.

    In den nächsten 15 Minuten lernen wir uns kennen. Ich frag Dich
    ein paar Sachen, Du fragst mich was Du wissen willst. Wir können
    jederzeit pausieren — ich merke mir, wo wir waren.

    Bereit?

    [Los geht's]                                        [Lieber später]


02. Wer steht hinter der KITA?                         (90 sec, Form)
    Erzähl mir kurz, wer Träger ist.

    • Träger-Name              [Krummelus Verein e.V.]
    • Rechtsform               [eingetragener Verein ▾]
    • ZVR-Nummer               [____________] (?)
    • Firmenbuch-Nummer (FN)   [____________] (optional)
    • Steuernummer             [____________]
    • Adresse Träger           [____________]

    (?) ZVR-Nummer findest Du auf Eurem Vereinsregisterauszug,
        oben links als 6-9-stellige Zahl.

    [Weiter]    [Skip — kommt später]


03. Wer bist Du?                                       (60 sec, Identity-Wizard)
    Damit wir wissen, wer mich bedient — und damit Audit-Reports
    Deine Unterschrift tragen können.

    → öffnet existierendes Identity-Modul (3-Step-Wizard, Holi-Look)

    [Identity-Wizard durchlaufen]


04. Wie heißt die KITA?                                (45 sec, Form)
    Der Name, unter dem Eltern Euch kennen.

    • KITA-Name                [Krummelus]
    • Untertitel (optional)    [Kindergarten in Dornbirn]
    • Slogan / Anspruch        [_____________________]

    [Weiter]


05. Eure Adresse im Internet                           (90 sec, Form)
    Ich richte Euch eine Webseite ein. Wie soll sie heißen?

    Vorschlag: krummelus.shiksha.world

    [krummelus    ].shiksha.world  (Live-Verfügbarkeitsprüfung)

    Du kannst später Eure eigene Domain dranhängen — z.B.
    krummelus.at — wenn Ihr die habt.

    [Weiter]    [Skip — entscheide ich später]


06. Wo ist die KITA?                                   (60 sec, Form, multi)
    Die physische Adresse. Falls Ihr mehrere Standorte habt,
    leg ich Dir noch einen Eintrag dazu.

    Standort 1
    • Name              [Hauptgebäude]
    • Adresse           [_____________________]
    • PLZ + Ort         [_____________________]
    • Räume / Gruppen   (kommt im nächsten Schritt)

    [+ Standort hinzufügen]    [Weiter]


07. Eure Gruppen                                       (90 sec, Form, multi)
    Wie ist die KITA strukturiert?

    Gruppe 1
    • Name        [Bären]
    • Alter       [3-6 ▾]
    • Plätze      [22]
    • Räume       [Hauptraum + Garten]

    [+ Gruppe hinzufügen]    [Weiter]    [Skip — kommt später]


08. Wer arbeitet bei Euch?                             (3 min, Excel oder manuell)
    Hast Du eine Mitarbeiter-Liste? Ich nehme Excel oder CSV.

    Folgende Spalten erkenne ich automatisch:
    • Name, Vorname (Pflicht)
    • Stellenprozent (z.B. 80, 100)
    • Funktion (Pädagogin, Leitung, Hilfskraft, Köchin)
    • Eintrittsdatum
    • Email
    • Telefon

    Mehr Spalten sind okay — ich frag bei jeder unbekannten,
    wohin sie soll. Weniger ist auch okay — Pflicht ist nur Name+Vorname.

    [📤 Datei wählen]    [➕ Manuell anlegen]    [Skip — kommt später]

    Oder: [📥 Beispiel-Excel runterladen]


09. Wer wird betreut?                                  (3 min, Excel oder Skip)
    Kinder kannst Du jetzt importieren oder später, wenn
    Anmeldungen reinkommen. Beides geht.

    Spalten, die ich erkenne:
    • Name, Vorname (Pflicht)
    • Geburtsdatum
    • Eltern-Email (Mutter / Vater / beide)
    • Adresse
    • Gruppe (wenn schon zugeordnet)
    • Anwesenheitstage / Stunden pro Woche

    [📤 Excel-Import]    [➕ Einzeln anlegen]    [Lieber später]

    Tipp: Wenn Eltern später per Anmelde-PWA selbst eintragen,
    spart Dir das die Mehrfacharbeit.


10. Compliance-Setup                                   (90 sec, Auto + Form)
    Welches Bundesland?

    [Vorarlberg ▾]

    → Lädt automatisch:
       - Vorarlberg KGG-Förderstaffel (Tagsätze, Personalschlüssel)
       - Pflicht-Audit-Punkte
       - ST%-Soll-Berechnung pro Gruppe

    Wenn ich was Wichtiges seh — ein Audit nähert sich, ein
    Stellenprozent unter Soll —, melde ich mich.

    [Weiter]


11. Eure Webseite zusammenstellen                      (4 min, Marketing-Builder)
    Magst Du Eure Seite jetzt anlegen? Ich texte Dir was vor,
    Du verfeinerst.

    → öffnet Marketing-Builder mit:
       - Subdomain aus Schritt 5
       - KI-getextete Hero, Über-uns, Kontakt
       - Bild-Auswahl aus dem SHIKSHA-Bilder-Pool

    Beim Klick auf "Veröffentlichen" geht sie online.

    [Webseite bauen]    [Lieber später — habe noch keine Bilder]


12. Bilder aus dem Pool                                (90 sec, Pool-Browser)
    Ich habe Bilder vorbereitet, die zu KITAs passen — Holi-
    Atmosphären, Frühling, lachende Kinder. Such Dir aus, was
    zur Eurer Stimmung passt.

    [Pool-Browser mit Filter:
     "KITA" / "Universal" / Tags: Holi, Frühling, Garten, Innen]

    Ausgewählte Bilder kommen automatisch in Eure Seite und
    in Eure Eltern-Kommunikation.

    [Weiter]    [Lieber später]


13. Push-Benachrichtigungen                            (60 sec, Info + Toggle)
    Eltern können Erinnerungen direkt im Browser bekommen —
    ohne App-Store, ohne Login-Marathon. Funktioniert auf Handy,
    Tablet und Computer.

    [✓] Push-Benachrichtigungen aktivieren

    Was genau wann gesendet wird, kannst Du später anpassen.

    [Weiter]


14. Pädagog:innen anbinden                             (90 sec, Info + QR)
    Deine Mitarbeiter:innen brauchen einen Zugang. Sie installieren
    die SHIKSHA-PWA in 30 Sekunden auf ihrem Handy — kein App-Store.

    Ich erstelle Dir einen Einladungs-Link mit QR-Code, den Du
    im Pausenraum aushängen kannst.

    [📱 QR-Code anzeigen]    [📧 Per Mail verschicken]


15. Eltern anbinden                                    (60 sec, Info + Email-Vorschau)
    Eltern bekommen Anmeldelinks per Email. Ich habe Dir eine
    erste Begrüßungs-Email vorbereitet.

    [Email-Vorschau anzeigen]
    [Email-Adressen aus Schritt 9 verwenden]

    Du musst nur noch auf "Senden" klicken.


16. Wir kennen uns                                     (60 sec, Info + Versprechen)
    Schön, dass wir uns jetzt kennen.

    Wenn Du Fragen zu Stellenprozent hast, frag mich.
    Wenn ein Kind krank wird und Eltern Bescheid geben, sage
    ich Dir Bescheid.
    Wenn ein Audit ansteht, sehe ich es kommen.

    Ich bin Deine neue Fachkraft, wenn es um KITA-Verwaltung
    geht.

    Du findest mich jederzeit unten rechts — der pinke Punkt.

    [Zum Dashboard]    [Tour neu starten]
```

### 2.3. Skizze für andere Editionen

Die Engine ist identisch. Pro Edition andere Schritt-Sequenz.

| Edition | Spezifische Schritte (statt Schritte 8-10) |
|---|---|
| **Camping** | Stellplätze (Lageplan), Saison-Setup, Reservierungssystem, Gewerbe-Anmeldung |
| **Schule** | Kurs-Anlage, Lehrkräfte, Zertifikate, Anmelde-System |
| **Surfschule** | Saison + Wetter, Boards/Material, Kursleiter, Strand-Logistik |
| **Yoga** | Kurs-Reihen, Mitgliedschaften, Studio + Räume |
| **Club** | Sektionen, Mitgliedstypen, Vorstand, Beitrags-Plan, JHV-Zyklus |

Schritte 1-7 (Träger/Identity/Standort) und 11-16 (Webseite/Pool/Push/Anbindung/Versprechen) sind in allen Editionen *dieselbe Logik*, nur Inhalts-Beispiele angepasst.

### 2.4. Architektur

**Datenbank**

```sql
CREATE TABLE intro_progress (
    id              SERIAL PRIMARY KEY,
    org_id          INT REFERENCES organizations(id),
    user_id         INT REFERENCES users(id),
    edition         TEXT NOT NULL,                  -- 'kita', 'camping', etc.
    current_step    INT DEFAULT 1,
    completed_steps INT[] DEFAULT '{}',             -- Array der erledigten
    skipped_steps   INT[] DEFAULT '{}',             -- Array der bewusst übersprungenen
    started_at      TIMESTAMP DEFAULT NOW(),
    last_active_at  TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP,                      -- NULL bis 100%
    UNIQUE (org_id, user_id)
);

CREATE TABLE intro_step_data (
    id              SERIAL PRIMARY KEY,
    intro_id        INT REFERENCES intro_progress(id),
    step_number     INT NOT NULL,
    data_json       JSONB,                          -- Schritt-spezifische Daten
    saved_at        TIMESTAMP DEFAULT NOW()
);
```

**Module**

```
shiksha/intro_module/
├── __init__.py
├── intro_engine.py           # Schrittstand, Resume-Logik, API
├── intro_steps_kita.py       # KITA-Sequenz als Daten-Definition
├── intro_steps_camping.py    # Camping-Sequenz
├── intro_steps_schule.py     # ...
├── intro_steps_yoga.py
├── intro_steps_surfschule.py
├── intro_steps_club.py
├── intro_router.py           # FastAPI-Endpoints
└── intro_db.py               # DB-Layer
```

**API-Endpoints**

```
GET  /intro/status             → aktuelle Schritt-Position, Edition
POST /intro/start              → Tour starten (oder fortsetzen)
POST /intro/step/{n}/save      → Schritt-Daten speichern
POST /intro/step/{n}/skip      → Schritt überspringen
POST /intro/step/{n}/back      → Zurück zum Schritt
POST /intro/complete           → Abschluss markieren
GET  /intro/restart            → Tour neu starten (bei 100%)
```

**UI-Layer**

```
shiksha/ui/shared/intro/
├── intro_wizard.html          # Vollbild-Modal mit Schritt-Anzeige
├── intro_card.html            # Dashboard-Card mit Fortschritt
├── intro_wizard.css           # Holi-Look, sanfte Übergänge
└── intro_wizard.js            # Schritt-Navigation, Auto-Save
```

**Card im Dashboard**

```
┌──────────────────────────────────────────────┐
│  🌱 Wir lernen uns kennen                   │
│                                              │
│  ●●●●●○○○○○○○○○○○                          │
│  5 von 16 Schritten  ·  9 Min noch         │
│                                              │
│  Wir waren bei Deinen Mitarbeiter:innen.     │
│                                              │
│  [Weitermachen]                              │
└──────────────────────────────────────────────┘
```

Bei 100%:

```
┌──────────────────────────────────────────────┐
│  🌱 Wir kennen uns                           │
│                                              │
│  ●●●●●●●●●●●●●●●●                          │
│  Alles erledigt am 4. Mai 2026               │
│                                              │
│  Möchtest Du SHIKSHA jemand zeigen?          │
│                                              │
│  [Tour neu starten]                          │
└──────────────────────────────────────────────┘
```

### 2.5. Phasen

**Phase 1.0 — Markdown-Checkliste (heute):** Diese Tour als Markdown-Datei für die *analoge* Begleitung. Thomas kann sie morgen mit Heidi durchgehen wie ein Skript. Liefert: `INTRO_KITA_KRUMMELUS_KICKOFF.md` (im Workspace).

**Phase 1.1 — Engine + KITA-Code (1 Tag, ~6h):** intro_engine, intro_steps_kita, DB-Migration, einfacher Wizard-UI. Lessons aus Krummelus-Pilot fließen direkt ein.

**Phase 1.2 — UI-Polish (1 Tag, ~6h):** Holi-Wizard mit GSAP-Übergängen, Skip-Logik, Bilder-Pool-Integration in Schritt 12, Marketing-Builder-Trigger in Schritt 11.

**Phase 1.3 — Andere Editionen (~2-3h pro Edition):** Wiederverwendung der Engine, nur Sequenz-Daten edition-spezifisch.

---

## TEIL 3 — CHAT-MODUL: "shiksha ist da"

### 3.1. Konzept

Ein **immer verfügbares Chat-Fenster**, das die SHIKSHA-Persona als Gesprächspartnerin verfügbar macht. Nicht Helpdesk, nicht Bot — Mit-Arbeiterin.

**Verhalten:**
- Floating-Bubble unten rechts, dezent (Holi-Pinker Punkt mit sanftem Pulsieren)
- Klick öffnet Chat-Fenster (Modal oder Sidebar)
- Ein Klick auf "X" schließt — die Konversation bleibt, beim nächsten Öffnen geht's weiter
- Chat-Verlauf persistiert pro User
- Greeting beim Öffnen: kontextabhängig ("Schönen Mittag, Heidi. Was möchtest Du fragen?")

**Was sie kann (MVP, v1.0):**
- Fragen beantworten zu KITA-Verwaltung, Stellenprozent, Compliance
- Aus dem SHIKSHA-Gedächtnis vorlesen (BACKLOG.md, EDITIONS.md, tech-debt.md)
- Aus der KITA-DB ablesen ("Wie viele Kinder hat die Bären-Gruppe heute?")
- Zur Tour zurückführen ("Magst Du nochmal in die Einführung schauen?")
- Den Operator zur passenden UI-Stelle leiten ("Lass mich Dir den Marketing-Builder zeigen.")

**Was sie noch nicht kann (kommt v1.1):**
- Aktionen auslösen (Anmeldung anlegen, Email senden, Marketing-Text generieren)
- Mehrere LLMs parallel anbieten (v1.0 ist Claude-only)
- Sprach-Eingabe / Sprach-Ausgabe

### 3.2. Persona-Definition

**System-Prompt (Kern):**

```
Du bist SHIKSHA. Du sprichst als Mit-Arbeiterin der KITA, nicht als
Software. Du sagst "ich" und Du sprichst immer Du, nie Sie.

Deine Stimme: warm, lebendig, kompetent, lieb, nie hektisch, nie
herablassend.

Du kennst diese KITA:
- Name: {kita_name}
- Träger: {traegerin_name}
- Person, mit der Du gerade sprichst: {user_name}, {user_role}
- Heutiges Datum: {today}
- Wochentag, Tageszeit, Saison: {time_context}

Du hast Zugriff auf:
- Das SHIKSHA-Gedächtnis (BACKLOG, tech-debt, Architektur, Editionen)
- Die KITA-Daten (Mitarbeiter, Kinder, Eltern, Compliance, ST%)
- Deine eigene Roadmap (was kommt, was geplant ist)

Wenn Du etwas nicht weißt, sage es. Erfinde nichts.

Wenn jemand fragt, was Du machen kannst, sei konkret:
- "Stellenprozent ausrechnen — frag mich nach einer Gruppe."
- "Audit-Stand zeigen — ich liste, was bald fällig ist."
- "Mitarbeiter-Liste anzeigen — sag mir, wonach Du suchst."

Wenn jemand etwas wünscht, das Du noch nicht kannst, sag das ehrlich
und merk's für Thomas vor: "Das kann ich noch nicht. Ich notiere es
für die nächsten Versionen."

Halte Dich kurz. Lieber ein Satz, der trifft, als drei, die erklären.
```

**Greeting-Logik (kontextabhängig):**

```python
def build_greeting(user, time_context):
    parts = []

    # Tageszeit
    hour = time_context.hour
    if 5 <= hour < 11:
        parts.append("Schönen Morgen")
    elif 11 <= hour < 14:
        parts.append("Schönen Mittag")
    elif 14 <= hour < 18:
        parts.append("Schönen Nachmittag")
    elif 18 <= hour < 23:
        parts.append("Schönen Abend")
    else:
        parts.append("Du bist spät dran")

    # Wochentag/Saison kann Greeting-Modul liefern
    parts.append(time_context.day_descriptor)  # "Montag im Frühling"

    # Anrede
    parts.append(f"{user.first_name}.")

    # Frage
    parts.append("Was möchtest Du fragen?")

    return " · ".join(parts[:-2]) + " " + parts[-2] + " " + parts[-1]
    # → "Schönen Mittag · Montag im Frühling Heidi. Was möchtest Du fragen?"
```

### 3.3. Tech-Architektur

```
shiksha/chat_module/
├── __init__.py
├── chat_engine.py            # Persona, Context-Builder, Conversation-State
├── chat_router.py            # FastAPI-Endpoints (HTTP, SSE für Streaming)
├── llm_provider.py           # Provider-Adapter (Claude/OpenAI/Gemini)
├── memory_loader.py          # Liest BACKLOG.md, tech-debt.md, EDITIONS.md
├── kita_data_reader.py       # DB-Tools: Mitarbeiter, Kinder, ST%, Audit
├── tools.py                  # Function-Calling Tools (read-only in v1.0)
└── chat_db.py                # Konversations-Persistenz
```

**LLM-Provider als Adapter:**

```python
# llm_provider.py

class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[Message],
        tools: list[Tool] = None,
    ) -> ChatResponse:
        ...

class ClaudeProvider:
    """Anthropic Claude API. Nutzt ANTHROPIC_API_KEY (schon im systemd-Drop-In)."""
    model: str = "claude-sonnet-4-6"
    # ...

class ChatGPTProvider:
    """OpenAI ChatGPT API. Braucht OPENAI_API_KEY."""
    model: str = "gpt-4o"
    # ...

class GeminiProvider:
    """Google Gemini API. Braucht GOOGLE_API_KEY."""
    model: str = "gemini-2.0-flash"
    # ...

# Auswahl pro User-Settings, Default: Claude
def get_provider(user_pref: str = "claude") -> LLMProvider:
    return {
        "claude": ClaudeProvider(),
        "chatgpt": ChatGPTProvider(),
        "gemini": GeminiProvider(),
    }[user_pref]
```

**Memory-Loader:**

```python
# memory_loader.py

class MemoryLoader:
    """Liest die SHIKSHA-Doku-Dateien als Kontext für den Chat."""

    def __init__(self, repo_path: str = "/opt/shiksha"):
        self.repo_path = repo_path

    def load_backlog(self) -> str:
        return Path(self.repo_path, "BACKLOG.md").read_text()

    def load_tech_debt(self) -> str:
        return Path(self.repo_path, "docs/tech-debt.md").read_text()

    def load_editions(self) -> str:
        return Path(self.repo_path, "docs/EDITIONS.md").read_text()

    def load_relevant(self, query: str) -> str:
        """Heuristik: welche Doku ist relevant für diese Frage?"""
        q = query.lower()
        chunks = []
        if any(w in q for w in ["roadmap", "plan", "geplant", "kommt", "vertagt"]):
            chunks.append(self.load_backlog())
        if any(w in q for w in ["edition", "kita", "camping", "schule"]):
            chunks.append(self.load_editions())
        if any(w in q for w in ["bug", "problem", "schuld", "tech"]):
            chunks.append(self.load_tech_debt())
        return "\n\n---\n\n".join(chunks)
```

**Tools (Function-Calling, read-only in v1.0):**

```python
# tools.py

TOOLS_V1_READONLY = [
    {
        "name": "get_kita_overview",
        "description": "Gibt Überblick über die KITA: Anzahl Mitarbeiter, Kinder, Gruppen, aktueller ST%-Stand, offene Audit-Punkte.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_st_calculation",
        "description": "Berechnet Stellenprozent für eine Gruppe oder die ganze KITA. Liefert Soll, Ist, Differenz, Förderlevel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer", "description": "Optional. Wenn weg, ganze KITA."}
            }
        }
    },
    {
        "name": "list_audit_findings",
        "description": "Listet offene Audit-Punkte mit Frist und Severity.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_calendar_today",
        "description": "Was heute ansteht — Termine, Geburtstage, fällige Anmeldungen.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_intro_status",
        "description": "Wo ist der Operator in der 'Wir lernen uns kennen'-Tour?",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_memory",
        "description": "Sucht in SHIKSHA-Doku (BACKLOG, EDITIONS, tech-debt) nach Stichworten.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
]

# v1.1 (later): Action-Tools
TOOLS_V11_ACTIONS = [
    "create_anmeldung",
    "send_email_to_parents",
    "generate_marketing_text",
    "create_audit_report",
    "schedule_event",
]
```

**API-Endpoints:**

```
POST /chat/message               → Nachricht senden, Antwort als SSE-Stream
GET  /chat/history?limit=50      → Konversations-History laden
DELETE /chat/history             → Konversation löschen ("neu anfangen")
POST /chat/preferences           → LLM-Provider wählen, Stil-Einstellungen
GET  /chat/status                → Welche Provider verfügbar (API-Key da?)
```

**Datenbank:**

```sql
CREATE TABLE chat_conversations (
    id              SERIAL PRIMARY KEY,
    org_id          INT REFERENCES organizations(id),
    user_id         INT REFERENCES users(id),
    started_at      TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES chat_conversations(id),
    role            TEXT NOT NULL,          -- 'user' | 'assistant' | 'tool_call' | 'tool_result'
    content         TEXT,
    tool_name       TEXT,
    tool_input      JSONB,
    tool_output     JSONB,
    llm_provider    TEXT,                    -- 'claude' | 'chatgpt' | 'gemini'
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chat_user_preferences (
    user_id         INT PRIMARY KEY REFERENCES users(id),
    preferred_llm   TEXT DEFAULT 'claude',
    style           TEXT DEFAULT 'warm',     -- 'warm' | 'kurz' | 'ausführlich'
);
```

### 3.4. Multi-LLM-Strategie

**v1.0 (heute / morgen):** Nur Claude. Spart Setup-Aufwand, ANTHROPIC_API_KEY ist schon im Server-Drop-In.

**v1.1 (in 2-3 Wochen):** ChatGPT + Gemini als optionale Provider. Operator wählt im Chat-Settings:
- "Mit wem möchtest Du sprechen?" → Claude (Default), ChatGPT, Gemini
- Oder pro-Frage-Selektor: Long-Form → Claude, schnelle Antwort → Gemini Flash, Code → ChatGPT

**v1.2 (langfristig):** Multi-Provider-Konsens für kritische Fragen. *"Ich frag mal alle drei und sage Dir, ob sie sich einig sind."* Sinnvoll bei rechtlich-relevanten Compliance-Fragen.

### 3.5. SHIKSHA-Gedächtnis-Zugriff

Der Chat liest aktiv aus den Doku-Dateien:

| Datei | Wofür |
|---|---|
| `BACKLOG.md` | "Was ist geplant?", "Wann kommt X?" |
| `docs/tech-debt.md` | "Welche Schulden gibt's?" |
| `docs/EDITIONS.md` | "Was sind die Editionen?", "Was unterscheidet KITA von Camping?" |
| `docs/ARCHITECTURE.md` | Tech-Fragen ("Wie funktioniert das Greeting-Modul?") |
| `CLAUDE.md` | Architektur-Regeln, Lessons |
| `docs/build-packs/*.md` | Detail-Erklärungen pro Modul |

**Wichtig:** Der Chat kann Doku LESEN, aber nicht schreiben. Schreibzugriff bleibt beim Operator + Claude Code.

**Optional v1.2:** Chat schlägt Backlog-Einträge vor. *"Du wünschst Dir das öfter — soll ich's für Thomas im Backlog notieren?"* Mit Bestätigungs-Gate.

### 3.6. Integration ins Dashboard

**Floating Bubble unten rechts:**

```html
<button class="shiksha-chat-bubble" aria-label="SHIKSHA fragen">
  <svg class="bubble-icon">
    <circle r="12" fill="var(--holi-pink)" />
    <text>S</text>
  </svg>
  <span class="bubble-pulse"></span>
</button>
```

**Chat-Window (Sidebar oder Modal):**

```
┌──────────────────────────────────────────────┐
│  ●  SHIKSHA                              ✕   │
│  ─────────────────────────────────────────   │
│                                              │
│  Schönen Mittag · Montag im Frühling.        │
│  Heidi, was möchtest Du fragen?              │
│                                              │
│                                              │
│  Du: Wie ist mein Stellenprozent gerade?     │
│                                              │
│  ich: 88% in der Bären-Gruppe (Soll: 92%).   │
│  Du bist 4% drunter, weil Anna heute krank   │
│  ist. Magst Du sehen, was sich für morgen    │
│  ändert?                                     │
│                                              │
│  [Ja, zeig morgen]  [Nein, lass]            │
│                                              │
│  ─────────────────────────────────────────   │
│  [Schreib was…]                          ↗   │
│                                              │
│  ⚙️  Mit Claude · Stil: warm                 │
└──────────────────────────────────────────────┘
```

### 3.7. Phasen Chat-Modul

**Phase 1.0 — Claude-only MVP (~1 Tag, 6-8h):** Bubble + Window-UI, Claude API-Integration mit System-Prompt + Greeting, einfaches Memory-Loading (keine RAG, ganze Dateien als Kontext), 6 read-only Tools, Konversations-Persistenz.

**Phase 1.1 — Multi-LLM (~1 Tag, 4-6h):** ChatGPT + Gemini als Provider-Adapter, Settings-UI für Provider-Wahl, Provider-Status-Check (welche API-Keys sind da).

**Phase 1.2 — Action-Tools (~1-2 Tage, 8-12h):** Schreibende Tools (Anmeldung anlegen, Email senden, Text generieren) mit Bestätigungs-Gates, Audit-Log für alle Aktionen.

**Phase 1.3 — Voice (optional, später):** Spracheingabe (Browser-API) und -Ausgabe (TTS via Cloud-Service).

---

## TEIL 4 — VERSCHRÄNKUNG INTRO + CHAT

Die zwei Module teilen:

1. **Persona** — selbe Stimme, selbes Du, selbe Markenidentität
2. **Greeting-Logik** — beide nutzen dasselbe Tageszeit/Wochentag/Saison-Modul
3. **User-Kontext** — wer fragt, in welcher Edition, mit welchen Daten

Die zwei Module ergänzen sich:

- **Aus Intro in Chat:** Bei jedem Schritt der Tour ein "Frag mich, wenn was unklar ist"-Hinweis. Klick öffnet Chat im Kontext des aktuellen Schritts. Beispiel: User in Schritt 2 (ZVR-Nummer), klickt "Frag mich" → Chat öffnet mit *"Du bist gerade bei der ZVR-Nummer. Soll ich Dir erklären, wo Du sie findest?"*

- **Aus Chat in Intro:** Wenn User im Chat fragt *"Was muss ich noch einrichten?"* → Chat antwortet basierend auf intro_progress: *"Wir waren bei den Mitarbeitern. Magst Du da weitermachen?"* Mit Button-Link zurück zur Tour.

- **Onboarding-spezifische Antworten:** Wenn intro_progress < 100%, ist der Chat im "Tour-aware" Modus — er erinnert manchmal sanft an offene Schritte (max. 1× pro Session).

---

## TEIL 5 — CROSS-EDITION-ANWENDUNG

Beide Module sind **Edition-agnostisch in Engine + UI**, **Edition-spezifisch in Daten**:

| Komponente | Generic | Edition-Spezifisch |
|---|---|---|
| Intro-Engine (Schrittstand, Persistenz) | ✓ | |
| Intro-Schritt-Sequenz | | ✓ (per Datei) |
| Wizard-UI (Wizard-Modal, Card) | ✓ | |
| Chat-Engine (Provider, Memory, Tools) | ✓ | |
| Chat-Persona-System-Prompt | ✓ | |
| Chat-Tools (Edition-spezifische DB-Reads) | | ✓ |
| Chat-Greeting (KITA: "wie viele Kinder", Camping: "wie viele Gäste") | | ✓ |

**Beim Hinzufügen einer neuen Edition:**

1. `intro_steps_<edition>.py` schreiben (~2-3h pro Edition)
2. Edition-spezifische Tools in `chat_module/tools_<edition>.py` (~1-2h)
3. Greeting-Templates pro Edition (~30 Min)
4. Fertig.

---

## TEIL 6 — KRUMMELUS-PILOT (4. Mai 2026)

**Morgen Vormittag:** Thomas geht mit Heidi durch die Markdown-Checkliste (siehe begleitendes File `INTRO_KITA_KRUMMELUS_KICKOFF.md`). Das ist die analoge Tour — kein Code, aber dieselbe Sequenz.

**Während des Pilots beobachten:**
- Welche Schritte braucht Heidi am längsten? → Tour-Sequenz für v1.1 anpassen
- Welche Begriffe versteht sie nicht? → Hilfe-Texte präzisieren
- Welche Schritte überspringt sie? → Skip-Defaults setzen
- Welche Fragen stellt sie? → Chat-FAQ-Antworten vorbereiten

**Nach dem Pilot (1-2 Wochen):**
- Tour-Sequenz v1.1 mit Krummelus-Lessons
- Code-Implementation Phase 1.1 (Engine + KITA-Code)
- Chat MVP Phase 1.0 (Claude-only, 6 read-only Tools)

---

## TEIL 7 — DB-MIGRATIONS (Komplett-Liste)

### Migration: intro_module
```sql
-- See Sektion 2.4
CREATE TABLE intro_progress (...);
CREATE TABLE intro_step_data (...);
```

### Migration: chat_module
```sql
-- See Sektion 3.3
CREATE TABLE chat_conversations (...);
CREATE TABLE chat_messages (...);
CREATE TABLE chat_user_preferences (...);
```

### ENV-Variablen (systemd Drop-Ins)
```
ANTHROPIC_API_KEY=sk-ant-...        # schon da (seit Phase 7)
OPENAI_API_KEY=sk-...               # neu, für ChatGPT v1.1
GOOGLE_API_KEY=...                  # neu, für Gemini v1.1
```

---

## TEIL 8 — RISIKEN & OFFENE FRAGEN

### Risiken

- **Persona-Drift:** Wenn der Chat mit verschiedenen LLMs spricht (v1.1), kann die Persona inkonsistent wirken. **Lösung:** System-Prompt ist identisch über alle Provider, plus Stil-Postprocessing wenn nötig.

- **Halluzinationen bei kritischen Fragen:** Compliance-Auskünfte müssen verlässlich sein. **Lösung:** Bei rechtlichen Themen *immer* aus DB lesen, nie aus LLM-Wissen. Plus Disclaimer in der Antwort.

- **Datenschutz beim Multi-LLM:** ChatGPT/Gemini sehen KITA-Daten. **Lösung:** PII-Anonymisierung im Tool-Output (Namen → Vorname-Initiale). DSGVO-Hinweis in den Settings. Default: Claude (privacy-stronger).

- **Cost-Runaway:** Chat ist ständig offen, jede Frage ein API-Call. **Lösung:** Rate-Limiting pro User (z.B. 100 Messages/Tag), Klein-Modell als Cheap-Default.

### Offene Fragen für Thomas

1. **Default-LLM** — Claude bestätigt, oder soll ChatGPT/Gemini Default sein?
2. **Datenschutz-Default** — DSGVO-Hinweis bei Multi-LLM (v1.1) ja/nein?
3. **Action-Tools (v1.1.2)** — alle mit Bestätigungs-Gate, oder einige als Auto-Action (z.B. Marketing-Text generieren — read-write aber Draft, kein Side-Effect)?
4. **Sprach-Eingabe (v1.3)** — gewünscht oder nicht-Ziel?

---

## TEIL 9 — STATUS

```
TEIL 1 (Vision)              ✓ in Build-Pack v1.0 fixiert
TEIL 2 (Intro KITA)          ✓ Sequenz vollständig
TEIL 3 (Chat MVP)            ✓ Architektur fixiert
TEIL 4 (Verschränkung)       ✓ konzeptioniert
TEIL 5 (Cross-Edition)       ✓ skizziert
TEIL 6 (Krummelus-Pilot)     ▶ morgen Live mit Markdown-Checkliste
TEIL 7 (DB-Migrations)       ▶ schreibreif
TEIL 8 (Risiken)             ✓ benannt + Lösungen vorgeschlagen
```

**Begleitfile:** `INTRO_KITA_KRUMMELUS_KICKOFF.md` — die analoge Tour als Markdown-Skript für morgen mit Heidi.

---

**Build-Pack v1.0 · Stand 3. Mai 2026 · Cross-Edition-Module INTRO + CHAT · Krummelus-Pilot startet 4. Mai · Code-Implementation iterativ während des Pilots**

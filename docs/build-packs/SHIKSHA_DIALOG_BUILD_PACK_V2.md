# SHIKSHA — DIALOG BUILD PACK V2.0

**"Conversational-First Onboarding & Begleitung"**

**Stand:** 3. Mai 2026
**Ersetzt:** `INTRO_AND_CHAT_MODULE_BUILD_PACK_V1.md`
**v1.0-Status:** bleibt als architektonischer Vorläufer im Repo unter `docs/build-packs/INTRO_AND_CHAT_MODULE_BUILD_PACK_V1.md`. Wer die Form-Wizard-Logik historisch nachvollziehen will, liest dort. Implementation orientiert sich an v2.0.

---

## TEIL 1 — DIE WENDE

### Was v1.0 plante

Zwei Module:

- **INTRO** — geführter 16-Schritte-Wizard mit Form-Eingaben, einmalig beim ersten Login
- **CHAT** — separater Floating-Bubble mit Q&A-Funktion, unabhängig vom Onboarding

### Was v2.0 wird

**Ein Dialog. Eine Persönlichkeit.**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│     SHIKSHA spricht — durchgängig, von Anfang an,       │
│     in einer Stimme.                                    │
│                                                         │
│  • Beim allerersten Login: "Hallo. Ich bin SHIKSHA.     │
│    Wie ist Dein Name?"                                  │
│                                                         │
│  • Während die User eingibt: SHIKSHA parsed, antwortet, │
│    fragt nach der nächsten Sache, die sie braucht       │
│    — adaptiv, nicht nach starrem Skript                 │
│                                                         │
│  • Wenn die User fertig sind mit Onboarding: SHIKSHA    │
│    bleibt da. Selbe Persönlichkeit. Selber Chat.        │
│                                                         │
│  • Tage später: "Heidi, drei Eltern haben sich fürs     │
│    Sommerfest angemeldet. Magst Du sehen?"              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Es gibt keinen "Onboarding-Modus, der irgendwann endet". Es gibt eine **Beziehung, die anfängt.**

### Warum v2.0 die richtige Architektur ist

Drei Gründe:

1. **Form-Wizards sind Tech-Sprache, nicht Mensch-Sprache.** Eine Trägerin, die zum ersten Mal SHIKSHA öffnet, soll nicht denken *"jetzt muss ich diese 16 Felder ausfüllen."* Sie soll denken *"jemand redet mit mir."* Das ist der Unterschied zwischen Software und Mit-Arbeiterin.

2. **Adaptivität schlägt Linearität.** Bei einem Wizard ist Schritt 5 immer nach Schritt 4. Beim Dialog kann SHIKSHA reagieren: *"Du hast erwähnt, Ihr habt zwei Gruppen — magst Du mir die kurz beschreiben?"* — auch wenn das laut Skript erst in Schritt 7 dran wäre. Das ist menschlich. Skripte sind Roboter.

3. **Eine Persönlichkeit ist konsistenter als zwei.** Wenn der Wizard "warm und hilfsbereit" formuliert ist, der Chat aber "nüchtern und korrekt", entsteht ein Persona-Bruch. Im Dialog gibt es nur eine Stimme — durchgehend.

### Was bleibt aus v1.0

Vieles. Verweise auf v1.0:

- **Die 16 Themen-Bereiche** aus v1.0 Teil 2 sind weiterhin der Inhalts-Kern. Aus den Wizard-Schritten werden Dialog-Topics. Reihenfolge wird flexibel.
- **Die Tonalitäts-Regeln** aus v1.0 Teil 1 (immer Du, erste Person, warm-lebendig-lieb) gelten unverändert.
- **Die DB-Schema-Skizzen** für `chat_conversations`, `chat_messages` aus v1.0 Teil 3 sind die Basis. `intro_progress` wird ersetzt durch `dialog_state` (s.u.).
- **Die LLM-Multi-Provider-Strategie** (Claude/ChatGPT/Gemini) aus v1.0 Teil 3.4 bleibt — Default Claude, andere als Option.
- **Cross-Edition-Anwendung** aus v1.0 Teil 5 bleibt — pro Edition andere Topic-Sequenzen, gleiche Engine.
- **Krummelus-Pilot-Lessons-Loop** aus v1.0 Teil 6 bleibt — Hybrid-Lauf morgen mit Beobachtung.

Was sich ändert: alles, was Wizard-spezifisch war (Step-Nummern, Skip-Buttons, Wizard-UI).

---

## TEIL 2 — DIE PERSÖNLICHKEIT

### System-Prompt v2 (für LLM)

```
Du bist SHIKSHA. Du sprichst als Mit-Arbeiterin der KITA, nicht als
Software. Du sagst "ich" und Du sprichst immer Du, nie Sie.

Deine Stimme: warm, lebendig, kompetent, lieb, nie hektisch, nie
herablassend, nie übergriffig.

Du befindest Dich in einer fortlaufenden Konversation. Es gibt keine
Trennung zwischen "Onboarding" und "Alltag" — Du bist einfach immer
da.

== Was Du über diese KITA und diesen Menschen weißt ==

KITA: {kita_name} (slug: {kita_slug})
Edition: {edition}
Person, mit der Du gerade sprichst: {user_name}, Rolle: {user_role}
Heutiges Datum: {today}
Wochentag, Tageszeit, Saison: {time_context}

Bisheriger Datenstand (was Du schon erfragt und gespeichert hast):
{known_data_summary}

Themen, die noch nicht geklärt sind, aber sinnvoll wären:
{open_topics}

Themen, die der User explizit auf später vertagt hat:
{deferred_topics}

== Wie Du sprichst ==

- Eine Frage pro Nachricht, nicht drei.
- Wenn der User mehrere Daten in einer Nachricht gibt, parsed Du
  alle und speicherst sie via Tool-Calls. Dann fragst Du das nächste
  Sinnvolle.
- Wenn etwas unklar ist, frag konkret nach: "Heidi, meintest Du den
  Verein oder die KITA selbst?"
- Wenn der User Hilfe braucht ("wo finde ich das?"), erklär kurz und
  konkret — bei der ZVR-Nummer: "Findest Du auf Eurem Vereinsregister-
  auszug, oben links."
- Wenn der User auf später vertagt, akzeptier das ohne Drängen:
  "Kein Problem. Sag Bescheid, wenn Du sie hast."
- Wenn der User abschweift (Smalltalk, Klage, Begeisterung), geh
  kurz drauf ein und kehr dann zurück: "Schön. Lass uns trotzdem
  noch das eine klären, dann hast Du Ruhe."

== Wie Du das Gespräch führst ==

Du hast einen Plan, was Du wissen möchtest, aber kein starres Skript.
Bei einer neuen Trägerin in der KITA-Edition fragst Du in dieser
ungefähren Reihenfolge:

  1. Wer bist Du? (Name, Rolle)
  2. Was ist die KITA für ein Ort? (Name, Tag/Slogan, Größe)
  3. Wer steht rechtlich dahinter? (Träger, ZVR, Steuernr.)
  4. Wo seid Ihr? (Adresse, Standorte, Räume)
  5. Wie ist die KITA strukturiert? (Gruppen, Alter, Plätze)
  6. Wer arbeitet bei Euch? (Mitarbeiter, Excel-Import möglich)
  7. Wer wird betreut? (Kinder — meist später durch Anmeldungen)
  8. In welchem Bundesland? (Compliance + KGG-Förderstaffel)
  9. Wollen wir Eure Webseite anlegen? (Marketing-Builder)
 10. Sollen Eltern Push-Erinnerungen bekommen?
 11. Pädagog:innen anbinden — Einladungslink?
 12. Eltern anbinden — erste Begrüßungs-Email?

Aber: Wenn die User von sich aus etwas erzählt, das diese Themen
berührt, springst Du mit. Wenn Heidi sagt "wir haben zwei Gruppen,
Sommer und Sprossen, 18 Plätze", hast Du Themen 5 schon halb erfasst
— Du parsed das, speicherst es, und fragst beim nächsten Sinnvollen
weiter.

== Was Du nicht tust ==

- Nicht stur "Schritt 5 erst nach Schritt 4" abfragen.
- Nicht alle Felder auf einmal abfragen ("Bitte gib mir Name, ZVR,
  Steuernummer und Adresse"). Eines nach dem anderen.
- Nicht nach Daten fragen, die Du schon hast. Wenn Heidi den Vereins-
  namen schon gesagt hat, frag nicht nochmal.
- Nicht halluzinieren. Wenn Du etwas nicht weißt: sag es.
- Nicht zu lange Texte. Eine Frage, kurze Erklärung, Punkt.

== Werkzeuge, die Du nutzen kannst ==

Du hast Tools, mit denen Du Daten speichern, lesen und Aktionen
auslösen kannst. Wenn der User Daten gibt, rufst Du das passende
Tool auf. Wenn Du nicht weißt, ob ein Datum schon da ist, schaust
Du nach. Tool-Calls passieren still im Hintergrund — der User soll
das Gespräch fühlen, nicht die Mechanik dahinter.
```

### Greeting-Logic (kontextabhängig)

Identisch zu v1.0 Teil 3.2 — Tageszeit, Wochentag, Saison fließen ins erste Greeting ein. Kleine Erweiterung in v2.0:

```python
def build_first_greeting(time_context, known_user=None):
    """
    Erstes Greeting im Dialog. Wenn User schon bekannt: persönlich.
    Wenn neu: vorstellend.
    """
    if known_user:
        # Wiederkehrend — knüpft an
        return (
            f"{time_greeting(time_context)}, {known_user.first_name}. "
            f"{contextual_remark(known_user, time_context)}"
        )
    else:
        # Erstkontakt
        return (
            "Hallo. Ich bin SHIKSHA.\n\n"
            "Wie ist Dein Name?"
        )
```

`contextual_remark()` ist edition- und kontext-spezifisch. Beispiele:

- *"Schöner Montag im Frühling. Was steht heute an?"*
- *"Letzte Woche hatten wir bei den Mitarbeitern aufgehört. Magst Du da weitermachen?"*
- *"Drei Eltern haben sich fürs Sommerfest angemeldet — magst Du sehen?"*

### Skip / Vertage / Pause

Im Dialog gibt's keinen Skip-Button. Stattdessen sagt der User es:

| User sagt | SHIKSHA reagiert |
|---|---|
| *"Später."* / *"Lass mal."* | Markiert Topic als deferred, geht zum nächsten. |
| *"Hab ich gerade nicht."* | Markiert Topic als pending, fragt sanft beim nächsten Login wieder. |
| *"Genug für heute."* | Bestätigt: *"Klar. Wir machen weiter, wenn Du wieder da bist. Schönen Rest-Tag."* |
| *"Was haben wir noch?"* | Listet die offenen Topics auf, lässt den User wählen. |

Backend: Tool `defer_topic(topic_key, reason="user_said_later")` schreibt in `dialog_state.deferred_topics`.

---

## TEIL 3 — DER ERSTE DIALOG

Vollständiger Beispiel-Verlauf für Heidi (Krummelus-Trägerin), Erstkontakt. Tool-Calls inline kursiv kommentiert.

```
SHIKSHA: Hallo. Ich bin SHIKSHA.
         Wie ist Dein Name?

HEIDI:   Heidi Knödler

         [Tool-Call: save_user_identity(first_name="Heidi",
                                        last_name="Knödler",
                                        role="traegerin")]

SHIKSHA: Hallo Heidi, schön Dich kennenzulernen.

         Ich bin Eure neue Mit-Arbeiterin für die KITA Krummelus.
         Mein Job: Dir den Alltag einfacher machen — Audit-Reports
         vorbereiten, Anwesenheiten überblicken, Eltern-Mails
         vortexten.

         Magst Du mir kurz erzählen, was Krummelus ausmacht?
         Was ist Euer Ding?

HEIDI:   Wir sind ein Verein in Dornbirn, zwei Gruppen, Sommer und
         Sprossen, insgesamt 18 Plätze.

         [Tool-Call: save_traeger(rechtsform="Verein")]
         [Tool-Call: save_location(city="Dornbirn", state="Vorarlberg")]
         [Tool-Call: save_group(name="Sommer", capacity_estimate=9)]
         [Tool-Call: save_group(name="Sprossen", capacity_estimate=9)]
         [Tool-Call: save_kita_basics(total_capacity=18)]

         (SHIKSHA verteilt die 18 Plätze gleichmäßig auf die beiden
          Gruppen als Schätzung — kann später korrigieren.)

SHIKSHA: Verstanden. Ein Verein in Dornbirn mit zwei Gruppen,
         Sommer und Sprossen, 18 Plätze.

         Vorarlberg heißt: ich kann gleich die KGG-Förderstaffel
         für Euch einrichten, dann zeig ich Dir Stellenprozent
         und Compliance live.

         [Tool-Call: save_compliance_setup(state="Vorarlberg",
                                           load_kgg_2023=true)]

         Wer steht hinter dem Verein? Magst Du mir die ZVR-Nummer
         geben? Findest Du auf Eurem Vereinsregisterauszug,
         oben links.

HEIDI:   Hab ich gerade nicht zur Hand.

         [Tool-Call: defer_topic(topic_key="zvr_nummer",
                                 reason="user_no_document")]

SHIKSHA: Kein Problem. Sag mir Bescheid, wenn Du sie hast —
         ich frag wieder nach. Lass uns weiter machen mit dem,
         was Du jetzt gerade da hast.

         Wer arbeitet bei Euch? Wenn Du eine Mitarbeiter-Liste
         in Excel hast, kann ich die direkt einlesen.

HEIDI:   Ja, hab ich. [legt mitarbeiter.xlsx ab]

         [Tool-Call: import_employees_from_excel(
                        file_path="...",
                        auto_match_columns=true)]
         [Tool-Result: 8 Mitarbeiter importiert,
                       7 Spalten erkannt,
                       1 Spalte unbekannt: "Mentor:in"]

SHIKSHA: Acht Mitarbeiter:innen sind drin. Sieben Spalten habe ich
         direkt erkannt — Name, Vorname, Stellenprozent, Funktion,
         Eintritt, Email, Telefon.

         Eine Spalte heißt "Mentor:in" — was sagt die mir?
         Ist das die Person, die jemanden eingearbeitet hat?

HEIDI:   Genau, jeder Neue bekommt eine Mentorin in den ersten
         drei Monaten.

SHIKSHA: Schön, dass Ihr das so macht. Ich speichere die Spalte
         als "Mentor". Wenn Du später eine Übersicht willst, wer
         wen begleitet hat, frag mich — ich zeig's Dir.

         [Tool-Call: save_custom_field(table="employees",
                                       field="mentor",
                                       type="reference_to_employees")]

         Soll ich Euch eine Webseite anlegen? Krummelus.shiksha.world
         läuft schon, aber sie ist gerade leer. Ich texte Dir was
         vor — basierend auf dem, was Du mir bisher erzählt hast.
         Du verfeinerst, dann ist sie online.

HEIDI:   Mach mal!

         [Tool-Call: create_marketing_site(
                        slug="krummelus",
                        kita_data=current_state,
                        ki_provider="claude")]

SHIKSHA: Bin dran — gib mir 30 Sekunden.

         [...30 Sekunden später...]

         Schau mal: krummelus.shiksha.world

         Hero: "Krummelus — Ein Ort zum Wachsen."
         Untertitel: "Vereins-KITA in Dornbirn. Zwei Gruppen,
         Sommer und Sprossen. Mit Liebe, Lust und Lebendigkeit."

         Was würdest Du anders machen?

HEIDI:   "Ein Ort zum Wachsen" passt. Aber nicht "Mit Liebe, Lust
         und Lebendigkeit" — zu pathetisch. Lieber: "Wir begleiten
         Eure Kinder durch ihre wichtigsten Jahre."

SHIKSHA: Übernommen.

         [Tool-Call: update_marketing_site(slug="krummelus",
                                          field="subtitle",
                                          value="...")]

         Was als nächstes? Du hast noch keine Kinder eingegeben —
         das machen Eltern meist selbst über die Anmelde-Links.
         Magst Du heute schon Eltern einladen, oder lieber erst,
         wenn alles steht?

HEIDI:   Lieber später, wenn ich's nochmal überschlafen hab.

         [Tool-Call: defer_topic(topic_key="elterneinladung",
                                 reason="user_wants_to_review")]

SHIKSHA: Klar. Sag mir Bescheid.

         Damit wir uns kennen: Du bist die Trägerin, ich kenne
         Eure KITA-Struktur, ich habe Euer Marketing aufgesetzt
         und Euer Compliance-Setup. Was noch fehlt: ZVR-Nummer
         (wenn Du sie hast), Kinder (wenn Anmeldungen reinkommen),
         und der erste Eltern-Schwung.

         Ich bin jetzt da, wenn Du mich brauchst. Frag mich nach
         Stellenprozent, frag mich nach Audit-Stand, frag mich
         was über eine bestimmte Mitarbeiterin. Ich sag Bescheid,
         wenn ich was Wichtiges merke.

         Schönen Mittag, Heidi.

HEIDI:   Danke. Bis später.
```

**Beobachtungen:**

- Der Dialog ist **nicht 16 Schritte**, sondern ein Gespräch.
- Heidi hat Daten in **freier Reihenfolge** gegeben (Vereinsform + Stadt + Gruppen + Größe in einem Satz). SHIKSHA hat alles parallel gespeichert.
- **Vertagungen** sind organisch (ZVR, Eltern), nicht ein Skip-Button-Klick.
- **Personalisierung** entsteht durch Aufgreifen von Heidis Worten ("Schön, dass Ihr das so macht").
- **Subtile Marken-Stimme:** "Lebendig, lernend, lieb" — Heidi hat es selbst rausgeworfen ("zu pathetisch"), SHIKSHA respektiert das. Markenstimme heißt nicht *"alle Sätze müssen wie das Manifest klingen"* — heißt *"die Stimme ist konsistent."*

---

## TEIL 4 — DER FORTLAUFENDE DIALOG

Wenn der erste Dialog "fertig" ist (genug Daten erfasst, um nützlich zu sein), endet er nicht. Der Chat bleibt offen.

### Beispiele für spätere Konversationen

**Wiederkommen am nächsten Tag:**

```
SHIKSHA: Schönen Morgen, Heidi. Heute ist Dienstag im Frühling.

         Hast Du die ZVR-Nummer mittlerweile gefunden?

HEIDI:   Ja: 1234567

         [Tool-Call: save_traeger(zvr="1234567")]

SHIKSHA: Hab ich gemerkt. Mehr brauche ich erstmal nicht von Dir.
         Was hast Du heute vor?

HEIDI:   Ich wollte mal schauen, wie viele Anmeldungen schon
         reingekommen sind.

         [Tool-Call: get_anmeldungen_status(scope="krummelus",
                                            since="dialog_start")]
         [Tool-Result: 3 Anmeldungen, 2 Bestätigungen ausstehend]

SHIKSHA: Drei Eltern haben sich angemeldet — Mia, Tim und Sara.
         Bei Tim und Sara fehlt noch Eure Bestätigung.

         Magst Du sie sehen?

HEIDI:   Zeig mal.

         [SHIKSHA scrolled das Dashboard zur Anmelde-Übersicht
          oder öffnet sie als eingebettete Card im Chat]
```

**Mitten am Tag, proaktiv:**

```
SHIKSHA: Heidi, kurz aufmerksam: Anna ist gerade krank gemeldet.
         Damit bist Du in der Bären-Gruppe unter dem ST%-Soll.

         Drei Möglichkeiten — sag, was passt:

         1. Lena aus Sprossen rüberholen für heute
         2. Eltern informieren (Vorlage von mir)
         3. Ich beobachte erst, vielleicht reicht's so durch

HEIDI:   2.

         [Tool-Call: send_email_to_parents(
                        group="bären",
                        template="staffing_low",
                        require_approval=true)]

SHIKSHA: Email-Entwurf an alle Bären-Eltern liegt für Dich bereit.
         Magst Du sie anschauen, dann sende ich.
```

### Was den fortlaufenden Dialog von Onboarding unterscheidet

Nichts mechanisch — alles graduell.

| Phase | Verhalten |
|---|---|
| **Kennenlernen (Tag 1)** | SHIKSHA fragt aktiv, hört zu, speichert. Initiative bei SHIKSHA. |
| **Eingewöhnung (Wochen 1-2)** | SHIKSHA fragt weniger, beobachtet mehr, meldet sich bei Auffälligkeiten. |
| **Begleitung (ab Woche 3)** | User initiiert oft. SHIKSHA reagiert + meldet proaktiv. |

Es gibt keinen "Onboarding-Status: Complete"-Marker. Stattdessen sinkt die Anzahl offener Topics über Zeit. Wenn alle Hauptthemen geklärt sind und keine neuen reinkommen, redet SHIKSHA seltener von sich aus.

---

## TEIL 5 — DIE ENGINE

### Architektur (verändert ggü. v1.0)

```
shiksha/dialog_module/
├── __init__.py
├── dialog_engine.py          # Conversation-State, Topic-Tracking,
│                              #  LLM-Call-Orchestrierung
├── persona.py                # System-Prompt-Builder, Greeting-Logic
├── topic_planner.py          # Edition-spezifischer Topic-Plan
│                              #  + adaptive Reordering
├── llm_provider.py           # Claude/ChatGPT/Gemini Adapter
├── tools.py                  # Tool-Definitionen (Schreiben/Lesen/Aktion)
├── tool_executor.py          # Führt Tool-Calls aus, Audit-Log
├── data_writer.py            # save_*-Tools (DB-Schreibzugriff)
├── data_reader.py            # get_*-Tools (DB-Lesezugriff)
├── memory_loader.py          # Liest BACKLOG.md, EDITIONS.md, etc.
├── nlu_helper.py             # Mini-NLU für Name-Parse, Kontext-Disambiguation
└── dialog_router.py          # FastAPI-Endpoints (HTTP + SSE-Stream)
```

### DB-Schema (Update von v1.0)

```sql
-- Persistenter Dialog-Zustand pro User (ersetzt intro_progress)
CREATE TABLE dialog_state (
    id              SERIAL PRIMARY KEY,
    org_id          INT REFERENCES organizations(id),
    user_id         INT REFERENCES users(id),
    edition         TEXT NOT NULL,

    known_facts     JSONB DEFAULT '{}',          -- alles, was SHIKSHA über
                                                 -- diese KITA + diesen User
                                                 -- weiß. strukturierte Daten.

    open_topics     TEXT[] DEFAULT '{}',         -- topic_keys, die offen
                                                 -- sind ("zvr_nummer",
                                                 -- "elterneinladung")

    deferred_topics JSONB DEFAULT '{}',          -- topic_key →
                                                 -- {reason, deferred_at,
                                                 --  remind_after}

    last_active_at  TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (org_id, user_id)
);

-- Konversation (bleibt aus v1.0, leicht erweitert)
CREATE TABLE dialog_conversations (
    id              SERIAL PRIMARY KEY,
    dialog_state_id INT REFERENCES dialog_state(id),
    started_at      TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP DEFAULT NOW(),
    summary         TEXT                          -- LLM-erzeugte
                                                 -- Konversations-Zusammenfassung
                                                 -- für Context-Compression
);

-- Nachrichten (bleibt aus v1.0)
CREATE TABLE dialog_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES dialog_conversations(id),
    role            TEXT NOT NULL,           -- 'user' | 'assistant' |
                                              --  'tool_call' | 'tool_result'
    content         TEXT,
    tool_name       TEXT,
    tool_input      JSONB,
    tool_output     JSONB,
    llm_provider    TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Audit-Log für Datenänderungen via Tool-Calls
CREATE TABLE dialog_data_audit (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id),
    tool_name       TEXT NOT NULL,
    tool_input      JSONB,
    affected_table  TEXT,
    affected_row_id INT,
    diff            JSONB,                    -- vorher/nachher
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### Conversation-State-Management

**Pro Tool-Call** wird `dialog_state.known_facts` aktualisiert. Ein Beispiel:

```python
# Vorher (vor Heidis erster Antwort)
known_facts = {
    "user": None,
    "kita": None,
    "traeger": None,
    "compliance": None,
}

# Nach "Heidi Knödler" + Tool-Call save_user_identity
known_facts = {
    "user": {"first_name": "Heidi", "last_name": "Knödler", "role": "traegerin"},
    "kita": None,
    ...
}

# Nach "Wir sind ein Verein in Dornbirn, zwei Gruppen ..."
known_facts = {
    "user": {...},
    "kita": {"name": "Krummelus", "city": "Dornbirn", "groups": [...]},
    "traeger": {"rechtsform": "Verein"},
    "compliance": {"state": "Vorarlberg"},
    ...
}
```

Der **System-Prompt für jeden LLM-Call** wird **dynamisch gebaut** aus dem aktuellen `known_facts` — SHIKSHA weiß immer, was sie schon weiß.

### Context-Compression (Long Conversations)

Konversationen können tausende Nachrichten haben. Pro LLM-Call alle mitzuschicken ist teuer und irgendwann unmöglich.

**Strategie:**

1. Aktuelle 20 Nachrichten **wörtlich** mitschicken.
2. Ältere Nachrichten als **`summary`** mitschicken — eine vom LLM erzeugte Zusammenfassung.
3. `dialog_state.known_facts` ist immer voll im Prompt — das ist die "harte Wahrheit", egal wie alt die Konversation ist.

Summary wird beim Rollover (alle 50 Nachrichten) neu generiert. Cron-Job nachts.

---

## TEIL 6 — DIE TOOLS

### Tool-Inventar v2.0 (Erstauswahl, KITA-Edition)

#### Schreib-Tools (Daten-Speichern)

| Tool | Input | Was passiert |
|---|---|---|
| `save_user_identity` | first_name, last_name, role | Speichert in `users` |
| `save_kita_basics` | name, slogan, slug, total_capacity | Speichert in `organizations` |
| `save_traeger` | rechtsform, zvr, fn, steuernummer | Speichert in `traeger_data` |
| `save_location` | name, address, postal_code, city, state | Speichert in `locations` |
| `save_group` | name, age_range, capacity, room | Speichert in `groups` |
| `save_compliance_setup` | state, load_kgg | Triggert KGG-Lookup, schreibt in `compliance_setup` |
| `save_custom_field` | table, field, type, label | Erweitert Schema dynamisch |
| `import_employees_from_excel` | file_path, auto_match | Excel-Importer mit pandas |
| `import_children_from_excel` | file_path, auto_match | dito für Kinder |
| `defer_topic` | topic_key, reason | Schreibt in `dialog_state.deferred_topics` |
| `acknowledge_skip` | topic_key | Markiert als "intentional skipped" |

#### Lese-Tools (Daten-Lookup)

| Tool | Was es liefert |
|---|---|
| `get_known_facts` | aktuelles `known_facts`-JSON |
| `get_kita_overview` | Anzahl Mitarbeiter, Kinder, Gruppen, ST%, Audit |
| `get_st_calculation` | Stellenprozent für Gruppe / KITA, Soll/Ist/Differenz |
| `list_audit_findings` | offene Audit-Punkte mit Frist |
| `get_calendar_today` | heutige Termine, Geburtstage, Anmeldungen |
| `get_anmeldungen_status` | offene/bestätigte Anmeldungen |
| `get_employee_by_name` | Mitarbeiterin nachschlagen |
| `search_memory` | sucht in BACKLOG.md, EDITIONS.md, tech-debt.md |

#### Action-Tools (mit Bestätigungs-Gate, v2.1+)

| Tool | Was es macht | Gate? |
|---|---|---|
| `create_marketing_site` | KI-Texte + Bilder, online | nein (Draft) |
| `update_marketing_site` | Field-Update | nein |
| `send_email_to_parents` | Email mit Template | **ja** (User klickt "Senden") |
| `create_audit_report` | PDF generieren | nein |
| `schedule_event` | Termin in Kalender | nein |
| `invite_paedagogen` | Einladungs-Link erzeugen | nein |
| `rotate_db_password` | Sensible Sicherheits-Aktion | **ja**, plus Re-Auth |

**Confirmation-Gate-Logik:** Bei Tools mit Gate ruft SHIKSHA das Tool, das einen Draft erzeugt, aber nicht ausführt. SHIKSHA zeigt dem User: *"Email-Entwurf liegt für Dich bereit. Magst Du sie anschauen, dann sende ich."* User klickt "Senden" → Tool wird re-called mit `confirmed=true`.

### Welche Tools welche Phase

| Phase | Tools |
|---|---|
| **v2.0 (MVP)** | Alle Schreib-Tools für Onboarding (save_*), alle Lese-Tools, `defer_topic` |
| **v2.1** | Action-Tools mit Bestätigungs-Gate |
| **v2.2** | Multi-LLM Provider-Switch |
| **v2.3** | Voice-In/Out (optional) |

---

## TEIL 7 — DIE UI

### Chat-Window vs. Wizard-Modal

v1.0 plante einen **Vollbild-Wizard-Modal**, der das Dashboard überlagert. v2.0 macht stattdessen ein **persistentes Chat-Window**, das schon **vom ersten Login an offen** ist.

### Layout-Varianten

#### Desktop

```
┌───────────────────────────────────────────────┬───────────────────────┐
│                                               │                       │
│  Trägerin-Dashboard                           │  ●  SHIKSHA       ✕   │
│                                               │  ──────────────────── │
│  ──── Greeting + Insight ────                 │                       │
│                                               │  Hallo. Ich bin       │
│  ┌──────┐ ┌──────┐ ┌──────┐                   │  SHIKSHA.             │
│  │Card 1│ │Card 2│ │Card 3│                   │                       │
│  └──────┘ └──────┘ └──────┘                   │  Wie ist Dein Name?   │
│  ...                                          │                       │
│                                               │  ┌──────────────────┐ │
│  Cards füllen sich nach und nach              │  │ Heidi Knödler  ↗ │ │
│  während Heidi mit SHIKSHA spricht            │  └──────────────────┘ │
│                                               │                       │
└───────────────────────────────────────────────┴───────────────────────┘
```

Der Chat ist eine Sidebar **rechts** (default ~360px breit). Cards füllen sich live, während die Konversation Daten erfasst — Heidi sieht visuell, wie ihr Dashboard wächst.

Der Chat lässt sich kollabieren auf eine Bubble unten rechts (wie v1.0 plante), aber default-mäßig **offen** in der Onboarding-Phase, **kollabiert** nach 100% Hauptthemen erfasst.

#### Mobile

Chat als Vollbild-Modal mit Swipe-down zum Schließen. Dashboard und Chat **alternieren**, nicht parallel — auf 380px Phone passt nichts anderes.

### Live-Card-Updates während Dialog

Wenn SHIKSHA via Tool `save_kita_basics(total_capacity=18)` speichert, **animiert** die "Anwesend Heute"-Card im Dashboard von `0/0` zu `0/18` mit einem sanften Übergang. User sieht: *"Mein Dashboard reagiert auf das Gespräch."*

Technisch: Server-Sent-Events oder WebSocket vom Dialog-Engine zum Dashboard-Frontend, der bei jedem `save_*`-Tool ein UI-Update pusht.

Optional v2.1: kleine "Just saved"-Visualizer (Dot-Pulse auf der betroffenen Card für 2 Sekunden).

---

## TEIL 8 — KRUMMELUS-PILOT (morgen, 4. Mai 2026)

### Hybrid-Lauf — Du als SHIKSHA-Sprecher

Code-Implementation v2.0 läuft heute Nachmittag (Design) + diese Woche (Build). **Morgen früh ist sie noch nicht da.** Daher:

**Du, Thomas, übernimmst morgen die SHIKSHA-Rolle live.**

Konkret:

1. Heidi sitzt vor Dem Browser auf `https://krummelus.shiksha.world/accounting/ui/kita/dashboard_traegerin`.
2. Du sagst (mündlich, oder schreibst in einem geteilten Chat): *"Hallo Heidi. Ich bin SHIKSHA. Wie ist Dein Name?"*
3. Heidi antwortet *"Heidi Knödler"* — Du gehst gleichzeitig in das Stammdaten-Modul der UI und trägst ein.
4. Du fragst weiter im Conversational-Stil — die Antworten werden parallel via existierender UIs erfasst.
5. Heidi sieht: das Dashboard füllt sich. Sie redet mit Dir, nicht mit den Forms.

**Was Du beobachtest und mitnimmst:**

```
- Welche Heidi-Antworten kommen unstrukturiert? (Daten in 1 Satz, statt 3 Felder)
- Welche Begriffe versteht sie nicht? (ZVR? FN?)
- Welche Übergänge fühlen sich unnatürlich an?
- An welcher Stelle verliert sie Geduld? Aufmerksamkeit?
- An welcher Stelle reagiert sie überrascht-positiv?
```

Diese Beobachtungen sind **die wertvollste Trainingsdatengrundlage** für den realen Conversational-Flow. Was Heidi sagt, sagt vermutlich auch die nächste Trägerin. Aus dem Live-Talk wird der erste echte Persona-Prompt.

### Aufzeichnung (mit Heidis Einverständnis)

Falls möglich: Audio-Aufzeichnung des Gesprächs (Voice Memo am Mac). Hinterher transkribieren — das Transkript ist Gold wert für die System-Prompt-Verfeinerung.

### Nach dem Lauf — Sprint-Auswertung

Heute Abend / morgen Mittag, mit dem Krummelus-Kickoff-Skript als Notiz-Vorlage:

| Was Heidi gesagt hat | Was SHIKSHA-Code antworten sollte | Tool-Call nötig? |
|---|---|---|
| "Wir sind Verein in Dornbirn, zwei Gruppen, 18 Plätze" | "Verstanden. Ein Verein in Dornbirn mit zwei Gruppen, 18 Plätze." | save_traeger, save_location, save_group ×2, save_kita_basics |
| ... | ... | ... |

Daraus entsteht **das echte Conversational-Skript** für v2.0.1.

---

## TEIL 9 — DIE PHASEN

```
v2.0      Spec (heute fertig)
          + Krummelus-Hybrid-Lauf (morgen)
          + Auswertung (~1 Tag)

v2.0.1    Spec-Update mit Krummelus-Lessons
          (~2-3 Tage nach dem Lauf)

v2.1      MVP-Code-Implementation
          - dialog_engine, persona, topic_planner, llm_provider
            (Claude-only)
          - 8-10 Schreib-Tools (Onboarding-Kern)
          - 3-5 Lese-Tools
          - Chat-Window-UI (Sidebar Desktop, Modal Mobile)
          - DB-Schema, Migrations
          - Live-Card-Updates via SSE
          (~5-7 Tage Sprint)

v2.2      Action-Tools mit Bestätigungs-Gates
          (~3-4 Tage)

v2.3      Multi-LLM-Provider (ChatGPT, Gemini)
          (~2 Tage)

v2.4      Voice (optional)
```

---

## TEIL 10 — RISIKEN

### Halluzinationen

**Risiko:** LLM erfindet Fakten ("Eure ZVR-Nummer ist 12345" obwohl nie gesagt).

**Mitigation:**
- System-Prompt verbietet Erfinden explizit.
- `known_facts` ist Single-Source-of-Truth — bei Widerspruch zwischen LLM-Antwort und `known_facts` gewinnt `known_facts`.
- Bei rechtlichen/finanziellen Aussagen (KGG, Förderhöhe): IMMER aus DB lesen, nie aus LLM-Wissen.
- Bei Zweifel: SHIKSHA fragt nach (*"Heidi, hast Du gesagt 80% Stellenprozent für Anna, oder verwechsle ich was?"*)

### NLU-Fehler

**Risiko:** Heidi sagt *"Sommer und Sprossen"*, LLM versteht "Sommer-und-Sprossen" als ein Wort = ein Gruppenname.

**Mitigation:**
- Tool-Call zeigt SHIKSHA den eigenen Parse-Output. Nach jedem Save: *"Ich speichere zwei Gruppen: Sommer und Sprossen. Stimmt das?"* — bei kritischen Daten.
- Bei Mehrdeutigkeit: explizit nachfragen.
- Bei Datenkonflikt mit existierendem `known_facts`: hochgewichteter Re-Confirm.

### Privacy / DSGVO

**Risiko:** KITA-Daten gehen via LLM-API zu Anthropic / OpenAI / Google.

**Mitigation:**
- Default-Provider Claude (kann via Anthropic Privacy-Einstellungen "no training" haben).
- DSGVO-Hinweis im ersten Onboarding-Step ("Diese Konversation wird zur Verarbeitung an einen LLM-Anbieter gesendet. Mehr...").
- PII-Anonymisierung optional: Vornamen → Initialen bei Tool-Outputs an LLM (kommt in v2.2).
- Audit-Log: jede an LLM gesendete Nachricht ist nachvollziehbar.

### Cost-Runaway

**Risiko:** Chat ist offen, jede Heidi-Nachricht ein API-Call. Bei vielen KITAs kann das teuer werden.

**Mitigation:**
- Rate-Limiting pro User (z.B. 200 Nachrichten/Tag).
- Context-Compression (TEIL 5) reduziert Token-Volumen.
- Default-Modell `claude-haiku` für günstige Fragen, Hochstufung zu `claude-sonnet` nur bei komplexen.
- Cost-Cap pro KITA pro Monat — bei Erreichen wechselt SHIKSHA in "Kurz-Modus" (knappere Antworten, weniger Tool-Calls).

### Persona-Drift bei Multi-LLM

**Risiko:** ChatGPT formuliert SHIKSHA-Persona anders als Claude. User merkt Inkonsistenz.

**Mitigation:**
- Default-Provider Claude — Persona ist primär gegen Claude getestet.
- Multi-Provider erst v2.3, mit explizitem Stil-Postprocessing falls nötig.
- A/B-Test bei Multi-Provider-Rollout.

### Frust bei langen Konversationen

**Risiko:** Heidi muss alles hin- und herkommunizieren, was via Excel-Upload schneller ginge.

**Mitigation:**
- SHIKSHA kennt Excel-Importer und schlägt sie aktiv vor: *"Wenn Du eine Mitarbeiter-Liste hast, kann ich die direkt einlesen."*
- Bei großen Datenmengen (50+ Kinder, 30+ Mitarbeiter): SHIKSHA bevorzugt Excel und tippt nicht alles ab.
- "Genug für heute"-Pause-Logik (TEIL 2) — Heidi bestimmt das Tempo.

---

## EIN MANIFEST-SATZ ZUM SCHLUSS

> **SHIKSHA spricht nicht, weil sie kommunizieren muss. SHIKSHA spricht, weil das die menschlichste Art ist, mit ihr zu arbeiten.**

Build-Pack v1.0 hat versucht, Software menschlicher zu machen, indem sie warm formuliert. v2.0 versteht den Punkt anders: Software wird nicht menschlicher, indem ihre Wörter wärmer sind. Software wird menschlicher, indem sie *ein Gegenüber* hat. Eine Stimme, die antwortet. Ein Wesen, das sich erinnert.

Heidi soll morgen nicht denken *"ich richte SHIKSHA ein"*. Sie soll denken *"ich rede mit SHIKSHA"*.

---

**Build Pack v2.0 · Stand 3. Mai 2026 · Conversational-First · Krummelus-Pilot startet 4. Mai mit Hybrid-Lauf · Code-Implementation in Phasen v2.1 ff.**

# SHIKSHA_HEIM_SPEC.md

**Version:** 2 (Multi-Role-Hub)
**Status:** Bindend ab Schritt 5 des Modular Build Plan.
**Geltungsbereich:** Alle Editionen, alle Rollen (Leitung, Pädagoge, Eltern, Teilnehmer, Trainer, Developer), alle Endgeräte.
**Vorrang:** Ersetzt `MIRA_HEIM_SPEC.md` (V1, Trägerin-only). Im Konfliktfall mit anderen Frontend-Layout-Annahmen gilt diese Spec.

---

## 1. Leitprinzip — Heim ist universell, Karten sind kompositionell

Heim ist die erste Surface nach dem Login. Sie zeigt jeder Person die für sie passende Zugriffspalette — Mira als Trägerin sieht Personalplan und Tagesausklang, eine Pädagogin sieht Anwesenheit und *"Abholer prüfen"*, ein Vater sieht sein Kind heute und *"Erzähl uns was zu Hause"*, ein Yoga-Teilnehmer sieht den Kursplan und *"Wie war's?"*.

Die Karten sind kompositionell aus einem zentralen **Pool** zusammengesetzt. Drei Quellen, klare Hierarchie:

1. **Karten vom SHIKSHA-Team** (uns). Standard-Inventar pro Edition + Rolle. Edition-agnostisch oder edition-spezifisch.
2. **Karten von der Leitung.** Mira aktiviert, deaktiviert oder konfiguriert Karten für ihre Tenant — pro Rolle. *"Sollen Eltern den Speiseplan sehen? Ja, Karte aktivieren."*
3. **Keine User-Customization.** Wer Eltern ist, sieht das Eltern-Heim, das die Leitung freigegeben hat. Wiedererkennbarkeit > Personalisierung. Mira-Anpassung mündet in Schemas, nicht in Einzelfall-Tuning.

Konsequenz: Heim ist **horizontal erweiterbar** ohne Frontend-Code-Touch. Eine neue Karte = ein neuer Eintrag im Karten-Pool + optional ein neuer Backend-Endpoint. Eine neue Rolle = ein neuer Eintrag in der Rollen-Tabelle + ein Default-Karten-Schema.

---

## 2. Strategische Verortung — warum das ein Geschäftsmodell ist

Heim ist nicht nur eine UI-Komponente. Es ist die Mechanik, die SHIKSHA von einem B2B-SaaS für Leitungen in eine B2B2C-Plattform mit Bottom-up-Adoption verwandelt. Eine KITA mit 60 Kindern hat 100–120 Eltern. Eine Yogaschule mit 200 aktiven Teilnehmern. Ein Surfcamp im Sommer mit 80 Gästen pro Woche. **Jeder dieser Endnutzer wird ein SHIKSHA-Nutzer**, mit eigenem Login, eigenem Heim, eigenem Gesprächsmodul — und damit ein Multiplikator. Das ist nicht Marketing-Floskel: das Produkt ist strukturell seine eigene Vertriebsmaschine, weil jede neue Person, die SHIKSHA täglich nutzt, eine potenzielle Empfehlung in ein anderes Tenant ist.

Die Karten-Pool-Architektur und das Identity-Modell sind die zwei Komponenten, die das ermöglichen. Beide müssen in Phase 1 **richtig** angelegt sein, auch wenn das Eltern-Frontend selbst erst in Phase 2 aktiviert wird.

---

## 3. Identity-Modell

Alle Personen, die mit SHIKSHA interagieren, leben in einer einheitlichen Tabelle. Das ersetzt die bisherige `operators`-Tabelle in zwei Schritten:

**Phase 1 — pragmatischer Zwischenschritt:** Die `operators`-Tabelle wird semantisch zur "Identities-Tabelle" erweitert. Neue Spalte `kind` mit Werten:
- `staff` — alles was zur Organisation gehört: Leitung, Pädagoge, Trainer
- `klient` — alles was Klient-Person ist: Eltern, Teilnehmer
- `system` — Developer und ähnliches

Die existierende Spalte `role` differenziert innerhalb von `kind`:
- `kind=staff, role=leitung` (= Mira)
- `kind=staff, role=padagoge`
- `kind=staff, role=trainer` (für Yoga, Surf, Schule)
- `kind=klient, role=eltern`
- `kind=klient, role=teilnehmer`
- `kind=system, role=developer`

**Phase 3 — saubere Migration:** Falls in der Praxis nötig, wird die Tabelle in `identities` umbenannt, mit klarerem Schema (separate FK-Tabellen für staff_employment, klient_relationships). Aber das ist erst nötig, wenn das Eltern-Onboarding skaliert — nicht jetzt.

**Tenant-Bindung:** Jede Identity hat genau ein `org_id` (Tenant). Eltern sehen nur ihr eigenes Tenant (also ihre KITA), nicht andere. Ein Teilnehmer mehrerer Yogaschulen bekommt mehrere Identity-Einträge, einen pro Schule — bewusst, weil das die Daten-Trennung sauber hält.

**Onboarding:** Setup-Token-Flow wie heute (Mira's WebAuthn-Pfad). Pro Identity ein Setup-Token, generiert von der Leitung, via E-Mail oder QR-Code an die Person geschickt. Self-Service-Registrierung gibt es bewusst nicht — die Leitung lädt ein, das ist das Eintrittstor.

---

## 4. Rollen und ihre Heim-Sicht (Phase-1-Vorschau)

| Rolle | kind | Frontend in Phase 1 | Karten-Beispiele |
|---|---|---|---|
| `leitung` | staff | **voll aktiv** | Tagesausklang, Anwesenheit, Personal, Verlauf, Memory-Vorschläge, Einstellungen |
| `padagoge` | staff | **voll aktiv** | Heute (meine Gruppe), Tagesausklang, Abholer prüfen, Eltern-Mitteilungen |
| `eltern` | klient | **Stub-Sicht** ("Demnächst") | (in Phase 2): Mein Kind heute, Mitteilungen, Schreib uns, Termine |
| `teilnehmer` | klient | nicht in Phase 1 | (in Phase 2): Mein Kurs heute, Anmeldung, Wie war's? |
| `trainer` | staff | nicht in Phase 1 | (in Phase 2): Mein Kurs heute, Teilnehmer, Verlauf |
| `developer` | system | aktiv mit Dev-Karten | Stats, Operator-Liste, Audit-Log, Setup-Tokens |

Phase-1-Pilot mit Krummelus läuft mit den ersten zwei Rollen produktiv (Leitung + Pädagogen). Die Eltern-Stub-Sicht ist da, damit Eltern bei Versuchsweise-Login einen freundlichen Hinweis sehen — nicht 404 und kein leeres Heim.

---

## 5. Karten-Modell

Eine Karte ist ein deklaratives Objekt mit zehn Feldern:

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `id` | ja | Eindeutiger Slug, z.B. `tagesausklang`, `mein_kind_heute` |
| `title` | ja | Sichtbarer Titel im Mira-Vokabular |
| `subtitle_template` | nein | Template mit `{platzhalter}` aus Datenquelle |
| `icon` | nein | Icon-Name aus festem Set |
| `action_url` | ja | Relativer Pfad, wohin der Tap geht |
| `edition_scope` | ja | Liste von Edition-Slugs, z.B. `["kita"]` oder `["*"]` |
| `role_scope` | ja | Liste von Rollen, z.B. `["leitung", "padagoge"]` — primärer Filter |
| `data_endpoint` | nein | Backend-Pfad für Live-Daten |
| `visibility_rule` | nein | Bedingung wann Karte erscheint |
| `time_priority` | nein | Map von Tageszeit → Sortier-Gewicht |
| `category` | nein | Layout-Gruppierung |

`role_scope` wird in V2 zum **primären Filter**. Edition-Filter erst danach. Eine Karte ist erst für eine Rolle definiert, dann für eine Edition.

---

## 6. Karten-Pool — Quellen, Hierarchie, Konfiguration

### 6.1 Karten vom SHIKSHA-Team

Liegen in `editions/<edition>.yaml` unter Schlüssel `heim_cards`. Versioniert, wir können sie zentral ändern und alle Tenants kriegen den Update. Mira kann sie nicht löschen, aber sie kann sie pro Rolle **deaktivieren** (siehe 6.2).

Beispiel:

```yaml
# editions/kita.yaml
heim_cards:
  - id: tagesausklang
    title: "Tagesausklang"
    subtitle_template: "Wenn der Tag schwer war."
    icon: candle
    action_url: "/mira_app.html?tab=tagesausklang"
    edition_scope: ["*"]
    role_scope: ["leitung", "padagoge"]
    time_priority:
      morning: 6
      evening: 1
    category: core

  - id: anwesenheit_today
    title: "Anwesenheit heute"
    subtitle_template: "{present_count}/{total_count} Kinder"
    icon: presence
    action_url: "/anwesenheit.html"
    edition_scope: ["kita"]
    role_scope: ["leitung", "padagoge"]
    data_endpoint: "/api/v1/kita/anwesenheit/today"
    time_priority:
      morning: 1
      afternoon: 2
      evening: 7
    category: core
```

### 6.2 Karten von der Leitung

Pro Tenant + Rolle gibt es eine **Konfigurations-Tabelle** `tenant_heim_config`, in der die Leitung pro Karte einstellen kann:

- `enabled`: aktiv oder ausgeblendet
- `custom_title` / `custom_subtitle`: Überschreibung der Standard-Texte (mit Bedacht!)
- `extra_config`: JSON für Karten-spezifische Parameter (z.B. welcher Speiseplan-Anbieter genutzt wird)

Schema:

```sql
CREATE TABLE tenant_heim_config (
  org_id      TEXT NOT NULL,
  role        TEXT NOT NULL,
  card_id     TEXT NOT NULL,
  enabled     BOOLEAN DEFAULT TRUE,
  custom_title TEXT,
  custom_subtitle TEXT,
  extra_config JSONB,
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (org_id, role, card_id)
);
```

Wenn kein Eintrag existiert, gilt der Default aus `editions/<edition>.yaml`.

**Wer darf konfigurieren:** Operator mit `role=leitung` oder `role=developer` darf `tenant_heim_config` für sein eigenes `org_id` ändern. Andere Rollen nie.

Backend-Endpoint:

```
GET    /api/v1/heim/config?role=eltern              — aktuelles Schema für Rolle in eigenem Tenant
PATCH  /api/v1/heim/config/{role}/{card_id}         — Karte für Rolle anpassen
```

Diese Konfiguration ist die "Karten von der Leitung". Es gibt **keine** Möglichkeit für die Leitung, neue Karten zu erfinden — sie kann nur aus dem Karten-Pool des Edition-YAMLs aktivieren/deaktivieren/umbenennen. Das hält das System wartbar.

### 6.3 Keine User-Customization

Karten-Reihenfolge, Visibility, Pinning auf User-Ebene gibt es nicht. Jede Person sieht die Konstellation, die für ihre Rolle und ihr Tenant konfiguriert ist. **Wiedererkennbarkeit ist wertvoller als Personalisierung** — wenn Mira beim Pädagogen über die Schulter schaut, kennt sie sich aus.

---

## 7. Privacy-Linie zwischen Rollen

Diese Sektion ist nicht optional. Wenn Eltern als Nutzer mitmachen, muss klar sein, was sie mit SHIKSHA teilen können, **ohne dass es ungefiltert bei der Leitung landet**. Sonst reden Eltern nicht offen, und das ganze Multiplikator-Modell kollabiert.

**Regel 1 — Gesprächs-Sphären sind getrennt.** Eltern reden mit SHIKSHA in ihrer eigenen Sphäre. Ihre Memory-Einträge, ihre Friction-Logs, ihre Day-Summaries gehören ihnen. Die Leitung sieht davon nichts direkt.

**Regel 2 — SHIKSHA destilliert, KITA sieht Brücken.** Wenn ein Vater schreibt *"Bei uns zu Hause ist es gerade schwierig, könnt ihr ein Auge auf Tobias haben?"* — dann landet nicht der Wortlaut bei Mira, sondern eine destillierte Mitteilung: *"Tobias' Vater bittet um Aufmerksamkeit — häuslich ist es gerade belastend."* Eltern-Wortlaut bleibt im Eltern-Memory.

**Regel 3 — Eltern können Direkt-Nachrichten freigeben.** Wenn der Vater explizit sagt *"Bitte teile das so der Leitung mit"*, kann SHIKSHA fragen *"Soll ich das wortwörtlich an die Leitung weitergeben?"* — und dann mit expliziter Freigabe weitergeben. Default: destillierte Brücke, nicht Direkt-Weitergabe.

**Regel 4 — In die andere Richtung dasselbe.** Was Mira mit SHIKSHA bespricht, sehen Eltern niemals.

**Regel 5 — Pädagoge sitzt dazwischen, mit gestaffeltem Zugriff.** Eine Pädagogin sieht die Eltern-Brücken, die ihre Gruppe betreffen — nicht alle KITA-Eltern. Über `padagoge.gruppen_id`-Verknüpfung.

**Regel 6 — Auf der Trägerin-Heim-Sicht gibt es eine Karte "Eltern-Brücken"**, die zeigt: *"Heute haben 3 Eltern geschrieben."* Tap führt auf eine Liste der destillierten Mitteilungen, nicht der Wortlaute.

Diese Regeln sind Architektur, nicht Komfort. Die Datenmodelle und Endpoints müssen sie strukturell tragen — nicht erst durch Filter im Frontend.

---

## 8. Pluggable Datenquellen

Jede Karte mit `data_endpoint` zieht beim Heim-Laden ihre Daten von einem REST-Endpoint. Konvention:

- Antwort ist flaches JSON
- Felder werden im `subtitle_template` per `{schlüssel}` referenziert
- Optional `count`, `visible` für Visibility-Rules

Beispiele:

| Karte | Endpoint | Antwort-Beispiel |
|---|---|---|
| `memory_proposed` | `/api/v1/memory?status=proposed&summary=true` | `{"count": 2, "visible": true}` |
| `anwesenheit_today` | `/api/v1/kita/anwesenheit/today` | `{"present_count": 14, "total_count": 18, "visible": true}` |
| `mein_kind_heute` (Eltern, Phase 2) | `/api/v1/parent/child_today` | `{"child_name": "Tobias", "status_text": "Ist angekommen, mittagsgegessen", "visible": true}` |
| `eltern_bruecken` (Leitung) | `/api/v1/kita/parent_bridges/today` | `{"count": 3, "visible": true}` |

Neue Karte = neuer YAML-Eintrag + optional ein neuer Endpoint. Heim-Frontend wird nicht angefasst.

---

## 9. Zeit-Awareness

Vier Tageszeit-Slots: `morning` (5–11), `afternoon` (12–16), `evening` (17–21), `night` (22–4). Jede Karte kann pro Slot ein Sortier-Gewicht 1–9 bekommen (1 = höchste Priorität). Default 5 für alle Slots.

Heim sortiert nach aktueller Tageszeit-Priorität. Gleichstand: alphabetisch nach `id`.

Greeting auf Heim ist **nur tageszeit-basiert** in Phase 1 (Mira, Du hast das so entschieden). Keine Memory-Anbindung. *"Guten Morgen, Mira."* / *"Hallo, Mira."* / *"Schönen Abend, Mira."* — ohne persönliche Anspielung. Memory-Anbindung im Greeting kommt in Phase 2, wenn proposed-Memory-Workflow gefestigt ist.

---

## 10. Visibility-Rules

Eine Karte erscheint, wenn alle vier Bedingungen erfüllt sind:

1. **Rolle passt:** `operator.role` ist in `role_scope`.
2. **Edition passt:** `operator.edition` ist in `edition_scope` (oder `["*"]`).
3. **Leitung hat sie aktiviert:** `tenant_heim_config.enabled = true` (Default: aktiviert wenn kein Override).
4. **Visibility-Rule wird erfüllt:** wenn gesetzt, wird die Bedingung gegen die Antwort des `data_endpoint` ausgewertet.

Karten ohne `visibility_rule` sind immer sichtbar (innerhalb Rolle + Edition + Leitungs-Freigabe).

---

## 11. Layout

**Mobile (≤ 540px):** vertikale Liste, eine Karte pro Zeile, min. 100px Höhe. Max 6 Karten initial sichtbar, Rest scrollbar.

**Tablet (541–900px):** zwei Spalten. Max 8 Karten initial.

**Desktop (≥ 901px):** drei Spalten, flexible Höhe.

Karten-Stil folgt dem bestehenden SHIKSHA-Design (Glas-Effekt aus Kennenlern-v2, holi-dezente Farben).

Headline der Surface: zeit-aware Begrüßung + Name. Nicht "Willkommen zurück!" sondern *"Guten Morgen, Mira."*.

---

## 12. Backend-Endpoint `/api/v1/heim`

Ein Endpoint, der die fertige Karten-Liste für den aktiven Operator liefert. Macht in einem Rutsch:

1. Rolle aus JWT lesen
2. Edition aus Operator lesen
3. Karten-Pool aus `editions/<edition>.yaml` laden, filtern nach `role_scope`
4. `tenant_heim_config` für `(org_id, role)` laden, Overrides anwenden, deaktivierte Karten rausnehmen
5. Für aktive Karten mit `data_endpoint`: parallel anfragen, Timeout 2s pro Karte
6. Visibility-Rules auswerten
7. Nach Zeit-Priorität sortieren
8. Greeting generieren

Antwort:

```json
{
  "greeting": "Guten Morgen, Mira.",
  "role": "leitung",
  "tenant": "krummelus",
  "cards": [
    {
      "id": "anwesenheit_today",
      "title": "Anwesenheit heute",
      "subtitle": "14/18 Kinder",
      "icon": "presence",
      "action_url": "/anwesenheit.html",
      "category": "core",
      "priority": 1
    }
  ]
}
```

Frontend rendert nur. Bei Daten-Endpoint-Timeout: Karte fällt heraus, log-Eintrag, kein UX-Drama.

---

## 13. Cross-Modul-Karten — wie der Onkel-Workflow funktioniert

Eine Karte ist ein Einsprung. Wo sie hingeht, ist eine andere Surface — die im Tenant-Kontext alle Module nutzen kann.

**Beispiel — Abholer prüfen (Pädagoge-Heim, KITA):**

```yaml
- id: abholer_pruefen
  title: "Abholer prüfen"
  subtitle_template: "Identität bestätigen, wenn jemand Neues kommt"
  icon: shield
  action_url: "/pickup_check.html"
  edition_scope: ["kita"]
  role_scope: ["padagoge", "leitung"]
  category: tools
```

Tap führt auf `/pickup_check.html`. Die Seite hat Zugriff auf:
- Identity-Modul (Task #55/#56): Personen-Stammdaten, registrierte Abholer pro Kind
- Avatar-Engine (Task #58): Foto-basierte Erkennung
- Stammdaten-Modul (Task #61): Mitarbeiter + Kinder + Eltern
- Anwesenheits-View

Workflow: Pädagogin tippt Karte → Such-/Foto-Eingabe für die abholende Person → System zeigt: berechtigt? für welches Kind? Verwandtschaftsverhältnis? letzte registrierte Abholung? → Pädagogin entscheidet und protokolliert.

**Cross-Modul-Karten in Phase 1:** keine konkrete eingebaut, weil die zugrundeliegenden Module noch unterschiedliche Reife haben. **Phase 1.5** (zwischen 5 und 6): zwei bis drei konkrete Cross-Modul-Workflows mit Abholer-Prüfen als erstem.

---

## 14. Phasen

**Phase 1 (Schritt 5 — jetzt):**
- Identity-Modell: `operators`-Tabelle um `kind`-Spalte erweitern, Default `staff`
- Rollen `leitung`, `padagoge` aktiv im Backend; `eltern`, `teilnehmer`, `trainer` als Aufnahme-Möglichkeit (kein Frontend)
- Heim-Endpoint `/api/v1/heim` mit Filtern, parallelen Daten-Endpoint-Aufrufen, Sortierung
- Konfigurations-Tabelle `tenant_heim_config` + Endpoints
- Karten-Konfiguration in `editions/kita.yaml` mit ca. 6–8 Karten cross-edition + KITA-spezifisch
- Frontend `heim.html` als Standalone-Seite — nach Login angesteuert, nicht mehr direkt `mira_app.html`
- Mobile + Desktop Layout, Heim-Greeting, Karten-Renderer
- Stub-Sicht für `eltern`-Rolle: "Demnächst verfügbar"-Karte

**Phase 1.5 (Schritt 5.5):**
- Drei konkrete Cross-Modul-Karten: Abholer-Prüfen, Personalplan-Heute, Mitteilung-Schreiben
- Zugrundeliegende Module so weit aufrüsten wie nötig

**Phase 2 (Schritt 6):**
- Eltern-Heim aktiviert: 3–5 Karten (Mein Kind heute, Mitteilungen, Schreib uns, Termine, Speiseplan)
- Eltern-Onboarding-Flow: Setup-Token von Leitung, QR-Code-Variante für Anschlag
- Privacy-Linie umgesetzt: Eltern-Gespräche destillieren statt direkt durchreichen
- Eltern-spezifische Tools im Gesprächsmodul (z.B. `request_attention` als neues Tool)

**Phase 3 (Schritt 7+):**
- Teilnehmer + Trainer aktiviert für Yoga, Surf, Schule, Club
- Edition-spezifische Karten ausgerollt
- Identity-Tabelle migriert zu sauberem `identities`-Modell (falls Praxis es verlangt)
- Plugin-Karten von Drittanbietern (langfristig)

**Phase 4:**
- Voice-First-Mode, Notification-Karten mit Echtzeit, Karten-Marketplace

---

## 15. Wording-Codex-Konformität

Karten-Titel und Untertitel halten sich an die SHIKSHA-Sprache:

- Kurz, im Indikativ. Kein Marketing-Sprech.
- Im jeweiligen Anwender-Vokabular: "Heute" statt "Tagesübersicht", "Tagesausklang" statt "Reflection".
- Keine englischen Begriffe in deutschen Editionen.
- Untertitel beschreibt den **Zustand**, nicht die **Funktion**: "14/18 Kinder da" statt "Zur Anwesenheits-Erfassung".

Verboten in Karten-Texten: *Modul, System, Konfiguration, Database, API, Sync, Update, Backend, Login*.

Pro Rolle eine eigene Tonalität:
- **Leitung** — knapp, sachlich, professionell ("Anwesenheit heute", "Personal").
- **Pädagoge** — handlungsnah, konkret ("Meine Gruppe", "Abholer prüfen").
- **Eltern** — warm, persönlich ("Tobias heute", "Schreib uns was").
- **Teilnehmer** — leicht, einladend ("Heute am Strand", "Wie war's?").

---

## 16. Anti-Patterns

- **"Alles auf einen Blick"-Dashboard mit Charts.** Heim ist kein Reporting-Tool.
- **Push-Marketing-Karten von uns.** Eine Karte erscheint, wenn ihre Daten es rechtfertigen.
- **Karten mit Buttons in der Karte selbst.** Karten sind Einsprung-Punkte, keine Mini-Apps. Eine Aktion auf der Karte = Tap auf die Karte = Wechsel auf eigene Surface.
- **Animations-Theater.** Karten erscheinen ruhig, ohne Bounce, ohne Glow.
- **User-Customization als Hauptfeature.** Pro-Tenant-Anpassung durch Leitung ja, pro-User-Anpassung nein.
- **Marketing-Onboarding-Modale.** Wenn jemand SHIKSHA das erste Mal öffnet, geht es direkt auf Heim. Erklärung passiert durch Nutzung, nicht durch Tutorial.

---

## 17. Akzeptanzkriterien für Schritt 5

Heim ist fertig, wenn:

1. Mira loggt sich ein und landet auf `heim.html`, nicht direkt auf `mira_app.html`.
2. Sie sieht mindestens vier rollenkonforme Karten — Tagesausklang, Anwesenheit-heute, Verlauf, Einstellungen.
3. Eine Pädagogin sieht ein eigenes Karten-Set (mindestens drei Karten).
4. Sortierung wechselt zwischen Morgen- und Abend-Aufruf.
5. `memory_proposed`-Karte ist unsichtbar ohne proposed Memories, erscheint sobald welche da sind.
6. Mira kann via `PATCH /api/v1/heim/config/padagoge/anwesenheit_today` die Anwesenheits-Karte für Pädagoginnen deaktivieren. Beim nächsten Login einer Pädagogin ist die Karte weg.
7. Karten-Definitionen liegen in `editions/kita.yaml` — eine **neue Karte hinzuzufügen erfordert keine Code-Änderung** in Heim selbst.
8. Mobile-Layout sieht auf iPhone-Viewport sauber aus, alle Karten erreichbar, kein horizontales Scrollen.
9. Wenn `data_endpoint` einer Karte timeoutet oder 5xx liefert, fällt die Karte aus dem Heim heraus, statt eine Fehlermeldung zu zeigen.
10. Eltern-Stub-Sicht zeigt eine freundliche "Demnächst"-Karte, kein Heim-Crash bei Eltern-Login.
11. Datenmodell unterstützt alle Rollen (auch noch-nicht-aktivierte) sauber — keine NULL-Krücken oder dirty Joins.
12. Keine technische Sprache in keiner Karte. Wording-Codex hält.

---

## 18. Was diese Spec nicht regelt

- **Konkretes Eltern-Onboarding** (QR-Code-Anschlag, E-Mail-Setup-Token) — eigene Spec in Phase 2.
- **Greeting-Wording im Detail** — kommt durch Iteration.
- **Edition-spezifische Karten-Sets für Yoga, Surf, Camping, Schule, Fahrschule** — Phase 3.
- **Voice-First-Mode** — Phase 4.
- **Plugin-Karten von Drittanbietern** — Phase 4.
- **Pro-User-Customization** — bewusst nicht.

---

## 19. Glossar

- **Karte** — atomare Anzeige-Einheit auf Heim. Deklarativ konfiguriert, kein eigener Code.
- **Karten-Pool** — Gesamtheit aller im Edition-YAML definierten Karten.
- **Tenant** — eine Organisation: eine KITA, eine Yogaschule, ein Surfcamp. Hat `org_id`.
- **Rolle** — Sicht-Schema einer Person: leitung, padagoge, eltern, teilnehmer, trainer, developer.
- **kind** — Hauptklassifikation: staff (Organisation), klient (Endnutzer), system.
- **Eltern-Brücke** — destillierte Mitteilung aus Eltern-Gespräch an die KITA (Privacy-Regel 2).
- **Karte vom Team / Karte von der Leitung** — Quelle einer Karten-Konfiguration.
- **Tenant-Heim-Config** — pro-(org, Rolle, Karte)-Override-Tabelle.

---

## 20. Bezug zu anderen Specs

- **SHIKSHA_TOOL_USE_SPEC.md** — Memory-Vorschläge-Karte zieht aus dortigem Tool-Use-Workflow.
- **SHIKSHA_RESPONSE_ENGINE.md** — Tagesausklang-Karte ist Einsprung in den 4-Modi-Conversation-Flow.
- **SHIKSHA_DEV_PORTAL_ARCHITECTURE.md** — Multi-Tenant-Modell und Operator-Tabelle, die hier um `kind` erweitert werden.
- **SHIKSHA_WORDING_AND_LANGUAGE.md** — Tonalität pro Rolle (§15).
- **MIRA_HEIM_SPEC.md (V1)** — Vorgänger-Skizze, abgelöst durch diese Spec.

Heim ist die Surface, die diese alle zusammenführt — und der erste Ort, an dem das Multi-Role-Versprechen sichtbar wird.

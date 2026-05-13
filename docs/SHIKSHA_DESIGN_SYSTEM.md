# SHIKSHA_DESIGN_SYSTEM.md

**Version:** 1.0 (Spec — Implementation folgt in 5.5.D.1+)
**Status:** Bindend ab Schritt 5.5.D des Modular Build Plan für alle Frontends in app.shiksha.world.
**Vorrang:** Im Konfliktfall mit bisherigen Inline-CSS-Entscheidungen (heim.html, mira_app.html, etc.) gilt diese Spec. Vorhandene Surfaces werden in 5.5.D.5 darauf refaktoriert.

---

## 1. Leitprinzipien

### 1.1 Logik vor Polish

Funktion zuerst, Schönheit als zweiter Pass. Die erste Implementierung des Design-Systems ist **bewusst nicht perfekt** — sie ist ordentlich, ist konsistent, ist edition-übergreifend tragfähig. Animations, Mikro-Interaktionen, perfekte Color-Theory, fein-abgestimmte Easing-Curves kommen als Update v1.1 / v1.2, wenn die Mechanik steht und reale Mira-Erfahrung Signal liefert. Wer perfekt vor funktional priorisiert, verschiebt Auslieferung und sammelt Schulden.

### 1.2 Eine Quelle der Wahrheit

Komponenten leben **zentral** in `shiksha-ui.css` / `shiksha-ui.js` / `shiksha-icons.svg`, ausgeliefert von `app.shiksha.world`. Keine Surface darf eigene Versionen einer Komponente bauen. Wenn eine Komponente fehlt, wird sie ins zentrale System aufgenommen, nicht lokal gehackt. Wenn sie nicht universell sinnvoll ist, ist sie keine Komponente, sondern Surface-spezifisches Markup.

### 1.3 Plattform-Update wie ein Betriebssystem

Jede Veränderung am Design-System wird über **Versionen** ausgespielt. Wir können einmal jährlich (oder häufiger) eine neue Hauptversion ausliefern, die alle Tenants automatisch erreicht — vorausgesetzt sie folgt der Semver-Disziplin (siehe §4). Endkunden erleben SHIKSHA-Updates wie iOS-Updates: zur richtigen Zeit, ohne Anstrengung, mit erkennbarem Mehrwert.

### 1.4 Evolutionäre Erweiterbarkeit

Features, die wir heute nicht kennen, müssen morgen einbaubar sein, ohne das System aufzubrechen. Drei Vorkehrungen:
- **Karten-Pool** für neue Funktions-Einsprünge ohne Frontend-Code
- **Tool-Registry** für neue Modell-Werkzeuge ohne API-Änderung
- **Tabellen-Konvention**: jede neue DB-Tabelle bekommt eine `metadata` JSONB-Spalte, damit neue Felder erst in metadata wachsen und später als eigene Spalte gehärtet werden

### 1.5 Wiedererkennbarkeit über Personalisierung

Eltern, Pädagogen, Trägerin sehen denselben Karten-Stil, dieselben Buttons, dieselbe Tages-Uhr. Inhalte unterscheiden sich, Form bleibt. Pro-User-Customization gibt es nicht. Pro-Tenant-Customization ist auf Logo + Akzentfarbe beschränkt (siehe §4.3).

---

## 2. Architektur — drei Update-Ebenen

```
┌─────────────────────────────────────────────────────────┐
│ Ebene 1: System (SHIKSHA-Team, global)                  │
│   shiksha-ui.v2.css      ← Tokens + Komponenten         │
│   shiksha-ui.v2.js       ← Verhalten + DayClock         │
│   shiksha-icons.v2.svg   ← Icon-Pool                    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ Ebene 2: Edition (SHIKSHA-Team, pro Edition)            │
│   editions-css/kita.css    ← Token-Overrides KITA       │
│   editions-css/surf.css    ← Token-Overrides Surf       │
│   editions-css/yoga.css    ← Token-Overrides Yoga       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ Ebene 3: Tenant (Leitung, pro Organisation)             │
│   tenant_branding.<org_id> ← Logo + 1 Akzentfarbe       │
│   (in DB, nicht als File — minimal!)                    │
└─────────────────────────────────────────────────────────┘
```

Jede HTML-Surface lädt alle drei Layer in dieser Reihenfolge. Spätere überschreiben frühere via CSS-Variablen-Kaskade. Komponenten-Definitionen leben ausschließlich in Ebene 1.

---

## 3. Tokens

### 3.1 Farben

```css
:root {
  /* Hauptpalette — wird durch Edition überschreibbar */
  --shk-accent-warm:   #e4a566;    /* primärer Akzent (KITA: Honig) */
  --shk-accent-cool:   #b484c8;    /* sekundärer Akzent */
  --shk-text-strong:   #f4ede0;
  --shk-text-soft:     rgba(236, 232, 223, 0.55);
  --shk-text-faint:    rgba(236, 232, 223, 0.30);
  --shk-bg-base:       #0e0d12;
  --shk-bg-card:       rgba(255, 255, 255, 0.06);
  --shk-bg-card-hover: rgba(255, 255, 255, 0.09);
  --shk-border-soft:   rgba(255, 255, 255, 0.08);
  --shk-border-active: rgba(228, 165, 102, 0.35);

  /* Statusfarben — sparsam einsetzen */
  --shk-status-ok:      #7fb888;
  --shk-status-warn:    #d4a356;
  --shk-status-belast:  #c8746a;
  --shk-status-info:    #6b9bb8;
}
```

Vergeben werden Farben nach **Bedeutung**, nicht nach Hex-Wert. Kein Code sollte je `#e4a566` schreiben — nur `var(--shk-accent-warm)`.

### 3.2 Typographie

```css
:root {
  --shk-font-serif: 'Crimson Pro', Georgia, serif;
  --shk-font-sans:  'Inter', system-ui, -apple-system, sans-serif;
  --shk-font-mono:  ui-monospace, 'SF Mono', monospace;

  /* Größen-Skala — modulare Schritte */
  --shk-text-xs:   0.78rem;
  --shk-text-sm:   0.88rem;
  --shk-text-base: 1.00rem;
  --shk-text-md:   1.08rem;
  --shk-text-lg:   1.32rem;
  --shk-text-xl:   1.80rem;
  --shk-text-display: clamp(2rem, 5vw, 3.2rem);

  /* Schriftgewichte */
  --shk-weight-light:    300;
  --shk-weight-regular:  400;
  --shk-weight-medium:   500;
  --shk-weight-semibold: 600;
}
```

Crimson Pro für Greetings und Hero-Text (warm, persönlich). Inter für UI-Text (klar, lesbar). Mono nur für Code/IDs.

### 3.3 Spacing

```css
:root {
  --shk-space-xs: 4px;
  --shk-space-sm: 8px;
  --shk-space-md: 16px;
  --shk-space-lg: 24px;
  --shk-space-xl: 40px;
  --shk-space-2xl: 64px;

  --shk-radius-soft:    12px;
  --shk-radius-md:      18px;
  --shk-radius-lg:      24px;
  --shk-radius-pill:    9999px;
}
```

### 3.4 Schatten + Blur

```css
:root {
  --shk-blur-card: 20px;

  --shk-shadow-soft:  0 1px 2px rgba(0,0,0,0.05);
  --shk-shadow-card:  0 4px 16px rgba(0,0,0,0.15);
  --shk-shadow-modal: 0 16px 48px rgba(0,0,0,0.45);
}
```

### 3.5 Bewegung

```css
:root {
  --shk-ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
  --shk-ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);

  --shk-duration-fast:   0.2s;
  --shk-duration-medium: 0.4s;
  --shk-duration-slow:   0.8s;
}
```

---

## 4. Versions-Schema und Update-Mechanik

### 4.1 Semver-Disziplin

```
shiksha-ui.v<MAJOR>.<MINOR>.<PATCH>.css

MAJOR: Breaking Changes — alte Komponenten-Klassen entfernt oder umbenannt
MINOR: Rückwärtskompatibel — neue Komponenten, neue Tokens
PATCH: Bug-Fixes — kein neuer Inhalt, nur Korrekturen
```

Beispiele:
- `v1.0.0` — Initial-Release in Schritt 5.5.D
- `v1.1.0` — neues Wetter-Widget dazu, alles andere unverändert
- `v1.1.1` — DayClock-Render-Bug auf Safari gefixt
- `v2.0.0` — Refresh-Pass mit überarbeiteten Tokens, alte Klassen-Namen umbenannt

### 4.2 Auslieferung

Jede Surface referenziert die aktive Version explizit:

```html
<link rel="stylesheet" href="/shiksha-ui.v1.0.0.css">
<script type="module" src="/shiksha-ui.v1.0.0.js"></script>
```

Beim Versions-Wechsel wird der Filename geändert (Cache-Bust ohne Header-Tricks). Alte Versionen bleiben verfügbar für eine Übergangsphase (z.B. drei Monate), damit Tenants mit altem Browser-Cache nicht abrupt brechen.

### 4.3 Tenant-Branding (Ebene 3 — minimal)

In der DB neue Tabelle:

```sql
tenant_branding (
  org_id        TEXT PRIMARY KEY REFERENCES organizations(id),
  logo_url      TEXT,
  accent_warm   TEXT,         -- Hex, überschreibt --shk-accent-warm
  metadata      JSONB DEFAULT '{}',  -- für künftige Erweiterungen
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)
```

Endpoint `GET /api/v1/branding` liefert das für den aktiven Operator. Frontend injiziert als Inline-Style ins `<head>`. Das ist die **einzige** Tenant-Anpassung.

Wenn ein Tenant kein Branding gesetzt hat, gilt das Edition-Default. Wenn Edition kein Override hat, gilt das System-Default.

### 4.4 Backward-Compatibility-Versprechen

- Minor-Updates dürfen **keine** existierenden Komponenten-Klassennamen ändern oder entfernen.
- Patches dürfen **kein** Verhalten von Komponenten ändern, nur Bugs fixen.
- Major-Updates kündigen Migrations-Bedarf an: Liste der Klassen, die umbenannt/entfernt werden, in der Release-Note. Surfaces haben Zeit zum Migrieren (3–6 Monate Übergangsfrist).

---

## 5. Komponenten-Inventar (Version 1.0)

### 5.1 Layout

- `.shk-shell` — äußerer Container mit max-width, Padding, min-height
- `.shk-header` — Greeting + Status-Zeile
- `.shk-section` — semantische Sektion innerhalb der Shell

### 5.2 Karten

- `.shk-card` — Glas-Card, default-padding, hover-state
- `.shk-card--compact` — kleinere Variante
- `.shk-card--feature` — höhere Bedeutung, leicht hervorgehoben
- `.shk-card--admin` — dezenter, sekundäre Aktionen

### 5.3 Buttons

- `.shk-btn` — Basis-Button
- `.shk-btn--primary` — Haupt-Aktion (warm-accent)
- `.shk-btn--ghost` — sekundär, kein Background
- `.shk-btn--danger` — destruktiv (selten, sparsam)
- `.shk-btn--icon-only` — nur Icon, Tooltip via title

### 5.4 Formular-Elemente

- `.shk-input` — Text-Input
- `.shk-textarea` — mehrzeilig
- `.shk-select` — Dropdown
- `.shk-toggle` — Switch (an/aus)
- `.shk-chip` — Tag/Auswahl-Indikator
- `.shk-field` — Wrapper mit Label + Input + optional Help-Text

### 5.5 Navigation

- `.shk-tabs` — Tab-Leiste
- `.shk-tab` + `.shk-tab--active`
- `.shk-breadcrumb` — Brotkrumen-Pfad (für tiefere Surfaces)

### 5.6 Listen

- `.shk-list` — Container
- `.shk-list-item` — einzelnes Item, klickbar
- `.shk-list-item__icon` — Icon vorne
- `.shk-list-item__body` — Titel + Subtitle
- `.shk-list-item__meta` — Wert oder Status rechts

### 5.7 Modal + Overlay

- `.shk-modal` — full-overlay Modal
- `.shk-modal--sheet` — von unten hereinschiebend (mobile)
- `.shk-toast` — kurze Mitteilung oben/unten (sparsam, max 2–3s)

### 5.8 Status-Indikatoren

- `.shk-status` — kleiner farbiger Indikator
- `.shk-badge` — Zahl + Status (z.B. "3 neu")
- `.shk-progress` — schmale Fortschrittsleiste

### 5.9 Spezial-Komponenten

- **`shk-dayclock`** — analoge Tages-Uhr (siehe §6)
- **`shk-calendar-month`** — Monatsansicht (siehe §7)
- **`shk-calendar-week`** — Wochenansicht
- **`shk-avatar`** — Initialen-Kreis mit Farbe aus Namen-Hash
- **`shk-weather`** — Wetter-Widget (siehe §8)

---

## 6. Tages-Uhr (`shk-dayclock`)

### 6.1 Modi

Die Komponente unterstützt drei Modi, edition-konfigurierbar via `dayclock_mode` in `editions/<edition>.yaml`:

**`analog-12h`** — klassische Analoguhr (KITA-Default):
- Zifferblatt mit 12 Stunden-Markierungen, römisch oder arabisch
- Stunden- und Minutenzeiger, aktuelle Zeit
- AM/PM-Indikator als subtiler Lichtwechsel im Zifferblatt (warmes Licht vormittags, kühl-warm nachmittags)
- Sektoren als farbige Kreissegmente HINTER dem Zifferblatt — wirken wie aufgehende Sonne
- Bei 12h-Rotation tauchen abends die Sektoren wieder auf (zweite Tageshälfte)

**`halfcircle-12h`** — Tages-Halbkreis (Alternative für Mobile):
- 6–18 Uhr (oder konfigurierbar) als oben offener Halbkreis
- Sektoren größer, lesbarer als auf Vollkreis
- Aktuelle Zeit als rotierender Punkt entlang des Bogens
- Eignet sich besonders für Eltern-Sicht (nur Bring-/Abhol-Zeiten relevant)

**`fullcircle-24h`** — 24-Stunden-Vollkreis (für Surf, Camping mit Nachtbetrieb):
- Mitternacht oben, Mittag unten
- Sektoren über alle 24h verteilbar (auch nächtliche Aktivitäten)

### 6.2 Sektoren

Ein Sektor ist ein Tageszeitraum mit zugeordneter Aktivität, Rolle und Farbe. Datenformat:

```yaml
# editions/kita.yaml — Beispiel
dayclock_sectors:
  - id: bringen
    label: "Bringen"
    start: "06:30"
    end:   "09:00"
    visible_for: ["eltern", "padagoge", "leitung"]
    color: "var(--shk-accent-warm)"

  - id: frühdienst
    label: "Frühdienst"
    start: "06:30"
    end:   "08:00"
    visible_for: ["padagoge", "leitung"]
    color: "var(--shk-status-info)"

  - id: vormittag
    label: "Vormittag"
    start: "08:30"
    end:   "11:30"
    visible_for: ["padagoge", "leitung", "eltern"]
    color: "var(--shk-accent-cool)"

  - id: mittag
    label: "Mittagsruhe"
    start: "12:30"
    end:   "14:00"
    visible_for: ["padagoge", "leitung", "eltern"]
    color: "var(--shk-text-faint)"

  - id: abholen
    label: "Abholen"
    start: "14:00"
    end:   "17:00"
    visible_for: ["eltern", "padagoge", "leitung"]
    color: "var(--shk-accent-warm)"

  - id: teambesprechung
    label: "Teambesprechung"
    start: "14:00"
    end:   "15:30"
    visible_for: ["padagoge", "leitung"]
    day_of_week: ["mittwoch"]   # nur an bestimmten Tagen
    color: "var(--shk-status-warn)"
```

### 6.3 Persona-Filter

Die Uhr rendert nur Sektoren, deren `visible_for` die aktive Rolle enthält. Heißt:
- Eltern sehen *Bringen → Vormittag → Mittagsruhe → Abholen* (große Schichten)
- Pädagogen sehen alles, inklusive Frühdienst und Teambesprechungs-Marker
- Trägerin sieht zusätzlich alle Schichten parallel mit feinerer Granularität

### 6.4 Interaktion

- Tap auf Sektor → Detail-Modal mit Aktion (z.B. *"Anwesenheit ab 08:30"* → Anwesenheits-Surface)
- Aktuelle Zeit als animierter Zeiger (oder rotierender Punkt), live-update jede Minute
- Auf großen Screens: rechts daneben Sidebar mit Liste der Sektoren als alternative Lesart

### 6.5 Implementation

SVG-basiert, kein Canvas. Rendering in `shiksha-ui.js`:

```js
ShikshaUI.renderDayClock(container, {
  mode: 'analog-12h',
  sectors: [...],
  role: 'padagoge',
  now: new Date(),
});
```

Wird minutiös live aktualisiert ohne Re-Rendering — nur Zeiger-Positions-Update.

---

## 7. Kalender-Komponenten

### 7.1 `shk-calendar-month`

- Monatsansicht im Glas-Card-Stil
- Tage als Mini-Zellen mit Event-Indikatoren (kleine Punkte unten)
- Aktueller Tag hervorgehoben
- Tap auf Tag → Day-View mit der Tages-Uhr drauf
- Vor/Nächster-Monat-Pfeile oben

### 7.2 `shk-calendar-week`

- 7 Tage horizontal, kompakter als Monat
- Pro Tag: Stundenraster oder Event-Liste
- Drag&Drop für Termine in v1.1+

### 7.3 Datenquelle

Karten konsumieren aus `/api/v1/calendar/events?from=&to=` (kommt in Schritt 5.5.4). Events haben `target_audience`-Feld — Eltern sehen andere Termine als Pädagogen.

---

## 8. Wettermodul (`shk-weather`)

### 8.1 Backend

Endpoint `/api/v1/weather?tenant_id=...`. Holt Wetter-Daten von einem öffentlichen Provider:

- **Open-Meteo** (kostenlos, keine API-Key nötig) für Standard-Editionen
- **Stormglass** oder **Surfline** (kostenpflichtig) für Surf-Edition mit Wellen-/Wind-Daten

Standort kommt aus `organization.metadata.location` (lat/lon, oder Adress-String mit Geocoding).

Antwort-Schema:

```json
{
  "current": {
    "temperature_c": 14.2,
    "condition": "regnerisch",
    "wind_kmh": 18,
    "icon": "rain"
  },
  "today": {
    "max_c": 16, "min_c": 9,
    "precipitation_mm": 8,
    "summary": "Vormittags Regen, nachmittags trocken"
  },
  "tomorrow": { ... }
}
```

### 8.2 Frontend-Varianten

- **`shk-weather--card`** — als Heim-Karte: "Heute regnerisch, 14°. Regenjacke."
- **`shk-weather--overlay`** — als Overlay über der Tages-Uhr (Wetter wandert mit der Zeit)
- **`shk-weather--micro`** — Mini-Indikator in der Header-Zeile

### 8.3 Edition-spezifische Darstellung

KITA: Temperatur + grobe Bedingung + Spielplatz-Empfehlung.
Surf: Welleneigenschaften (Höhe, Periode), Wind (Richtung+Stärke), Wassertemperatur. Komplett anderes Layout.
Yoga: Wetter spielt minimale Rolle; vielleicht nur als Outdoor-Yoga-Hinweis.
Camping: Mehrtagesprognose, Sturm-Warnungen.

Edition wählt via `dayclock_weather_mode: "kita"` (oder surf/camping/...) das passende Layout.

---

## 9. Theming-Engine

### 9.1 Drei Kontext-Dimensionen

Die Engine setzt auf `<body>` drei Data-Attribute:

```html
<body data-time="evening" data-season="autumn" data-context="tagesausklang">
```

Werte:

- **`data-time`**: `morning | afternoon | evening | night`
- **`data-season`**: `spring | summer | autumn | winter`
- **`data-context`**: `heim | gespraech | personen | kalender | anwesenheit | abholer | dashboard | notfall`

JavaScript (in `shiksha-ui.js`) setzt die Attribute beim Laden und alle 30 Minuten neu.

### 9.2 CSS-Reaktion

CSS-Variablen können basierend auf den Attributen variieren:

```css
body[data-time="morning"]   { --shk-bg-gradient-1: rgba(228, 165, 102, 0.20); }
body[data-time="evening"]   { --shk-bg-gradient-1: rgba(180, 132, 200, 0.18); }
body[data-time="night"]     { --shk-bg-gradient-1: rgba(80, 100, 130, 0.15); }

body[data-context="gespraech"] { --shk-bg-base: #0c0810; }
body[data-context="notfall"]   { --shk-accent-warm: var(--shk-status-belast); }
```

Bewusst sehr leise gemischt. Niemand soll die Tageszeit knallig erleben — sie soll sich nur richtig anfühlen.

### 9.3 Jahreszeit als Untertöne

Sehr dezent. Frühling: pastell-grüner Schimmer im Hintergrund. Sommer: warmer Honig-Ton (überschneidet sich mit KITA-Default). Herbst: erdige Rot-Töne. Winter: kühle Blau-Töne. Jahreszeiten sollen **nicht überdramatisiert** werden — sie sind Akzent, keine Farbexplosion.

### 9.4 Kontext-Switch

Verschiedene Surfaces setzen `data-context` manuell beim Laden:

```js
// heim.html
document.body.dataset.context = 'heim';

// mira_app.html im Tagesausklang-Tab
document.body.dataset.context = 'gespraech';
```

Damit kann z.B. der Tagesausklang einen wärmeren, intimeren Hintergrund haben als das Heim.

---

## 10. Icon-Strategie

Ein einziger SVG-Sprite mit allen Symbolen, ausgeliefert als `shiksha-icons.v1.0.0.svg`. Jede Surface lädt ihn einmal und referenziert über `<use>`:

```html
<svg class="shk-icon"><use href="/shiksha-icons.v1.0.0.svg#icon-calendar"/></svg>
```

### 10.1 Stil-Vorgabe

- **Stroke-basiert** (keine fills), 1.6px Strichstärke, runde Kappen
- ViewBox 24×24
- Mono-color (currentColor) — Färbung übernimmt sich aus dem Parent-Element
- Klar, ruhig — keine Schmiede-Verzierungen, kein iOS-Glanz, kein Material-Drop-Shadow

### 10.2 Initial-Set (v1.0)

Mindestens 25–30 Icons für die erste Version. Konkret:

Navigation: `home`, `calendar`, `chat`, `history`, `settings`, `chevron-left`, `chevron-right`, `close`

Karten: `candle`, `bookmark`, `presence`, `team`, `shield`, `clock`

Aktionen: `plus`, `pencil`, `trash`, `check`, `share`

Status: `info`, `warning`, `error`

Spezial: `weather-sun`, `weather-cloud`, `weather-rain`, `weather-snow`

Personen-bezogen: `person`, `users`, `parent-child`

### 10.3 Neue Icons im Update

Wenn in v1.1 ein neues Icon dazukommt, wandert es einfach in die SVG. Surfaces, die es nutzen wollen, referenzieren es. Surfaces, die es nicht brauchen, bemerken nichts.

---

## 11. Schreibweise und Wording-Codex-Kopplung

Komponenten-Texte folgen der `SHIKSHA_WORDING_AND_LANGUAGE.md`-Codex. Verboten innerhalb von Komponenten-Labels und Mira-zugewandtem Text: *Modul, System, Konfiguration, Database, API, Sync, Update*. (Im Developer-Tab erlaubt.)

Pro Rolle eine Stimmlage:
- **Leitung** — knapp, sachlich
- **Pädagoge** — handlungsnah, konkret
- **Eltern** — warm, persönlich
- **Teilnehmer** — leicht, einladend

Diese Tonalität gehört in die Texte der Komponenten-Inhalte, nicht ins CSS.

---

## 12. Phase 1.5.D Implementations-Plan

Diese Spec wird in den folgenden Sub-Schritten umgesetzt:

- **5.5.D.0** — diese Spec
- **5.5.D.1** — `shiksha-ui.v1.0.0.css` (Tokens + alle Komponenten aus §5, ohne Spezial-Komponenten)
- **5.5.D.2** — `shiksha-ui.v1.0.0.js` (DayClock-Renderer, Modal-Logic, Tab-Switch, Theming-Engine)
- **5.5.D.3** — `shiksha-icons.v1.0.0.svg` (25–30 Icons)
- **5.5.D.4** — `editions-css/kita.v1.0.0.css` (KITA-Token-Overrides, derzeit minimal)
- **5.5.D.5** — `heim.html` refaktoriert auf v1.0 (Beweis: bestehende Surface funktioniert mit System)

Wettermodul (§8) und Kalender-Komponenten (§7) werden in 5.5.4 (Kalender-Port) implementiert. Tenant-Branding-Endpoint (§4.3) wird in Phase 2 aktiviert, wenn Mira ein eigenes Logo will.

---

## 13. Akzeptanzkriterien

Phase 1.5.D ist fertig, wenn:

1. `shiksha-ui.v1.0.0.css/js/svg` deployed unter `app.shiksha.world/`
2. `heim.html` refaktoriert, sieht visuell unterscheidbar gleich aus wie vorher (oder besser, aber nicht schlechter)
3. Alle Komponenten aus §5 sind als CSS-Klassen verfügbar und in einem `style-guide.html` einzeln dokumentiert
4. DayClock funktioniert in mindestens `analog-12h`-Modus, mit den Sektoren aus `editions/kita.yaml`
5. Theming-Engine wechselt Hintergrund nach Tageszeit korrekt (morgens vs. abends sichtbar anders)
6. Icon-Set ausgeliefert, referenzierbar via `<use>`
7. Versionierte URL `/shiksha-ui.v1.0.0.*` funktioniert auf Server
8. Edition-Override-Mechanik dokumentiert und mit KITA-CSS getestet (auch wenn KITA derzeit nur minimale Overrides hat)
9. Keine Surface braucht Inline-CSS außer Surface-spezifischem Markup
10. Tenant-Branding-DB-Migration vorbereitet (für Phase 2 aktivierbar)

---

## 14. Was diese Spec nicht regelt

- **Animations-Library** — kein GSAP, kein Framer Motion, nur CSS-Transitions
- **Komponenten-Stories** wie in Storybook — wir haben `style-guide.html` als einfache Alternative
- **Internationalisierung** — Phase 3, dann mit eigener i18n-Spec
- **Dark/Light-Mode-Toggle** — wir bleiben permanent im dunklen Theme, das ist SHIKSHA-Identität. Light-Mode ist Phase 4.
- **Voice-Mode** — Phase 4, dann mit Audio-/TTS-Spec.

---

## 15. Glossar

- **Token** — eine wiederverwendbare Design-Variable (Farbe, Spacing, Typo-Größe)
- **Komponente** — eine CSS-Klasse plus optionalem JS-Verhalten, wiederverwendbar
- **Edition** — Branchenvariante (KITA, Yoga, Surf, ...)
- **Tenant** — eine Organisation innerhalb einer Edition
- **System-Update** — Versions-Wechsel des Design-Systems (Ebene 1)
- **Edition-Override** — Token-Anpassung durch das SHIKSHA-Team für eine Edition (Ebene 2)
- **Tenant-Branding** — minimale Anpassung durch eine Leitung für ihre Organisation (Ebene 3)
- **DayClock** — Tages-Uhr-Komponente mit konfigurierbaren Modi
- **Theming-Engine** — Tageszeit-/Jahreszeit-/Kontext-Switch via Data-Attribute

---

## 16. Bezug zu anderen Specs

- **SHIKSHA_HEIM_SPEC.md** — Heim-Karten werden in v1.0 als `.shk-card`-Komponenten neu gerendert
- **SHIKSHA_WORDING_AND_LANGUAGE.md** — Komponenten-Texte folgen dem Codex
- **PHASE_1_5_SPEC.md** — Frontend-Strategie pro Modul-Port nutzt dieses Design-System
- **MIRA_HEIM_SPEC.md (V1, abgelöst)** — Heim-Layout-Annahmen werden hier zentralisiert

---

## 17. Vision: jährliche SHIKSHA-Keynote

Sobald die Plattform 50+ Tenants hat und v1.x-Updates 2× erfolgreich ausgespielt wurden, wird eine jährliche SHIKSHA-Keynote denkbar — im Apple-WWDC-Format. Vorstellung neuer Features, neuer Editionen, neuer Komponenten. Das ist Marketing, Release-Disziplin und kultureller Anker in einem.

Bis dahin: jedes größere Update wird mit einer Release-Note auf `shiksha.world/updates` dokumentiert. Das ist die Vorform der Keynote — ohne Bühne, aber mit Substanz.

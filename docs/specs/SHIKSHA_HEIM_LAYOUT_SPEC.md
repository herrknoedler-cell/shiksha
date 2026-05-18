# SHIKSHA Heim-Layout-Spec

**Version:** v0.1-DRAFT (Code-First)
**Status:** Dokumentiert die in 5.5.D.5 deployed Implementation. Spec ist nachgeschrieben, nicht vorab geschrieben. Verbindlicher als jeder Bundle-Vorschlag.
**Stand:** 2026-05-18
**Vorgänger:** `SHIKSHA_DESIGN_SYSTEM.md` v1.0 (Tokens, Basis-Komponenten)
**Implementiert in:** System v1.1.0 (Card-Size-Modifier, Heim-Slider, `.shk-action`)

> **Hinweis zum Lesen:** Diese Spec wurde nach der Implementation geschrieben, weil ein Cowork-Bundle die Spec referenzierte, ohne sie vorher zu definieren. Statt eines Stop-and-Wait wurde die Implementation mit dokumentierten Detail-Entscheidungen durchgezogen — die Spec hier hält die Entscheidungen fest und dient als Pattern-Quelle für Folge-Refactors.

---

## 1. Layout-Grundregeln

### 1.1 Page-Konzept

Ein Heim besteht aus mehreren **Pages** — Vollbild-Bildschirmen, die der Operator horizontal durchwischt (auf Touch) oder per Tastatur durchschaltet (auf Desktop). Pro Rolle ist die Anzahl Pages und ihr Inhalt fest definiert in `editions/<edition>.yaml` unter `heim_layouts.<role>`.

Pages sind nicht user-personalisierbar — Vereinheitlichung über alle Mitarbeitenden derselben Rolle ist Design-Ziel (siehe Design-System §1.5).

### 1.2 Grid pro Page

Jede Page ist ein **4×6-Grid** (4 Spalten × 6 Reihen). Karten besetzen rechteckige Slot-Bereiche darin per `size` und `position`.

```
position: [col, row]    — 0-basiert, [0,0] ist oben links
size:     "WxH"         — col-span × row-span
```

Beispiel: `{size: "2x2", position: [2, 4]}` belegt Spalte 2-3, Reihe 4-5.

### 1.3 Erlaubte Größen

| `size` | col-span | row-span | typische Nutzung |
|---|---|---|---|
| `"1x1"` | 1 | 1 | Action-Tile (Tap-Button) |
| `"2x1"` | 2 | 1 | breites Action-Paar |
| `"1x2"` | 1 | 2 | hohe Statistik-Karte |
| `"2x2"` | 2 | 2 | Standard-Modul-Karte |
| `"4x2"` | 4 | 2 | Volle Breite (Live-Anwesenheit, etc.) |
| `"4x3"` | 4 | 3 | Halbes Display (Dayclock, Wochenkalender) |
| `"4x6"` | 4 | 6 | Voll-Page (Gespräche-Modul) |

Andere Größen sind nicht spezifiziert — wenn nötig in `shiksha-ui.v1.x.css` ergänzen.

### 1.4 Mobile-Reflow (< 600px Viewport)

Bei schmaler Breite wird der Grid in **Single-Column-Stack** umgebrochen: jede Karte nimmt die volle Breite, Reihenfolge nach `[row, col]`-Sortierung (zuerst Reihe, dann Spalte). Die `size`-Span-Klassen werden via Media-Query neutralisiert. Pages bleiben horizontal swipe-bar.

### 1.5 Page-Indikator

Unten am Bildschirm zentriert: kleine Punkte pro Page, aktiver Punkt akzent-warm gefärbt. Tap auf Punkt scrollt zur Page.

---

## 2. YAML-Schema

In `editions/<edition>.yaml`:

```yaml
heim_layouts:
  schema_version: 1
  <role>:                          # leitung / padagoge / eltern / developer
    - page_id: <slug>              # eindeutig pro Rolle
      label: "<Anzeige-Name>"      # für Page-Indikator-Tooltip + a11y
      cards:
        - type: <card-type-string> # Provider-Key oder Tile-Komponente
          size: "<size-string>"    # aus §1.3
          position: [col, row]     # aus §1.2
          # optional:
          accent: "warm"|"cool"|"info"|"warn"  # nur für action-tiles
          url: "<absoluter-pfad>"  # Tap-Ziel; sonst aus Provider
```

**Validierung im Loader:**
- `position` + `size` müssen ins 4×6-Grid passen (col+w ≤ 4, row+h ≤ 6) — sonst Warn-Log, Karte wird trotzdem gerendert (defensive)
- `type`-Strings ohne Provider/Komponente werden als Placeholder-Tile gerendert ("Karte noch nicht implementiert" + type-Name als Subtitle) — bewusst, damit Layout-Iteration ohne Backend-Vorlauf möglich ist
- `accent` greift nur wenn `type` mit `action_` beginnt (= `.shk-action`-Komponente)

---

## 3. Card-Type-Konventionen

Drei Klassen von `type`-Strings:

| Prefix / Pattern | Komponente | Beispiel |
|---|---|---|
| `action_<name>` | `.shk-action` (Tile-Button) | `action_neue_erfassung` |
| `dayclock` | System-Komponente `shk-dayclock` | (genau dieser Name) |
| `<freier_name>` | `.shk-card` mit Provider-Daten | `wer_ist_da`, `tech_schuld` |

Provider-Lookup im Backend: zuerst `heim_providers.<type>` versuchen, dann statische Inhalts-Lookup im Card-Pool (`heim_cards` in der YAML). Wenn beides leer: Placeholder.

---

## 4. Backend-Response-Struktur

`GET /api/v1/heim` liefert:

```json
{
  "greeting": "Guten Morgen, Mira",
  "role": "leitung",
  "tenant": "krummelus",
  "pages": [
    {
      "page_id": "heute",
      "label": "Heute",
      "cards": [
        {
          "type": "wer_ist_da",
          "size": "2x2",
          "position": [0, 0],
          "title": "Wer ist da",
          "subtitle": "0 Kinder · 0 Päd.",
          "icon": "presence",
          "url": "/anwesenheit.html",
          "accent": null,
          "data": {...}
        }
      ]
    }
  ],
  "cards": [...]
}
```

`cards` (am Top-Level) bleibt als **deprecated flat-Liste** — Aggregat aller Page-Cards plus die Karten aus der alten `heim_cards`-Sektion, die kein Page-Layout hat. Backward-Compat für nicht-v1.1-Frontends. Wird in einem Folge-Drop entfernt sobald alle Surfaces auf v1.1 sind.

Wenn `heim_layouts[role]` nicht definiert ist (z.B. `eltern` heute), bleibt `pages = []` und `cards` ist die volle alte flat-Liste — kein UI-Bruch.

---

## 5. Beispiel: Krummelus-Leitung

```yaml
heim_layouts:
  schema_version: 1
  leitung:
    - page_id: heute
      label: "Heute"
      cards:
        - {type: wer_ist_da,            size: "4x2", position: [0, 0]}
        - {type: dayclock,              size: "4x3", position: [0, 2]}
        - {type: abholer_pruefen,       size: "2x2", position: [0, 5]}
        - {type: action_neue_erfassung, size: "1x1", position: [2, 5], accent: "warm",
           url: "/identity.html"}
        - {type: action_anwesenheit,    size: "1x1", position: [3, 5], accent: "cool",
           url: "/anwesenheit.html"}
    - page_id: wochenplan
      label: "Wochenplan"
      cards:
        - {type: diese_woche,           size: "4x3", position: [0, 0]}
        - {type: anwesenheit_woche,     size: "2x2", position: [0, 3]}
        - {type: geburtstage_woche,     size: "2x2", position: [2, 3]}
    - page_id: verwaltung
      label: "Verwaltung"
      cards:
        - {type: stammdaten,            size: "2x2", position: [0, 0]}
        - {type: personal_heute,        size: "2x2", position: [2, 0]}
        - {type: tech_schuld,           size: "4x2", position: [0, 4]}
    - page_id: gespraeche
      label: "Gespräche"
      cards:
        - {type: gespraeche_modul,      size: "4x6", position: [0, 0]}
```

---

## 6. Spec-Status + offene Punkte

Diese Spec ist **v0.1-DRAFT** und beschreibt den Stand des 5.5.D.5-Refactors. Offene Punkte für Folge-Iterationen:

- **Placeholder-Karten füllen**: `tech_schuld`, `lizenzen`, `operatoren_status`, `kinder_liste_gruppe`, `eltern_kontakte`, `geburtstage_woche` etc. existieren als YAML-Referenz aber ohne Provider/Komponente. Pro Karte ein Folge-Drop mit `@register_provider` + ggf. Icon.
- **Eltern-Layout**: aktuell `eltern: []` als Stub. Kommt mit Phase-2-Onboarding.
- **Drag-and-Drop-Layout-Editor für Leitung**: aktuell nicht im Scope; alle Layouts sind YAML-fix. Wenn UX-mäßig nötig, eigenständiger Sprint.
- **Performance**: bei vielen Pages mit vielen Provider-Calls kann der Heim-Endpoint langsam werden. Aktuell synchron pro Karte; Parallelisierung via `asyncio.gather` für Identity 2.0.

Spec wird nach erstem Live-Use mit Mira auf v0.2 verfeinert.

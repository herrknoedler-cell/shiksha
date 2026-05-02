# SHIKSHA — DESIGN SYSTEM V1

**Stand:** 25. April 2026
**Status:** dokumentiert, bewusst entschieden
**Zentrale Datei:** [`shiksha_design_tokens.css`](shiksha_design_tokens.css)

---

## TL;DR

**Ja, alles ist konsistent auf CSS Custom Properties (Variablen) gebaut.**
Aber: jede HTML-Datei hat ihre eigene `:root`-Definition — bewusst, weil jede Mockup-Datei standalone an einen Pilot-Kandidaten geschickt werden können soll.

Die Variablen sind über alle 7 UI-Files **inhaltlich identisch** — bis auf zwei dokumentierte Mobile-vs.-Operator-Abweichungen.

---

## 1. WIE ES JETZT IST

### Aktueller Zustand

7 HTML-Files, jedes File hat seinen eigenen `<style>`-Block mit `:root`-Variablen:

| File | Token-Anzahl | Spezial-Tokens | Mobile-Variant? |
|---|---|---|---|
| `schule_edition/ui/operator_dashboard.html` | 14 | `--info` | nein |
| `schule_edition/ui/operator_eingabemasken.html` | 13 | — | nein |
| `schule_edition/ui/teilnehmer_app.html` | 12 | `--phone-bg` | **ja (Mobile)** |
| `camping_edition/ui/operator_dashboard.html` | 16 | `--info`, `--positive` | nein |
| `camping_edition/ui/operator_eingabemasken.html` | 13 | — | nein |
| `camping_edition/ui/gaeste_app.html` | 12 | `--phone-bg` | **ja (Mobile)** |
| `safeguarding/ui/safeguarding_dashboard.html` | 16 | `--info`, `--learn` | nein |

### Was identisch ist über alle Files

```css
--ink: #1a1a1a;           /* Hauptschrift */
--ink-soft: #55524b;      /* Sekundärschrift */
--accent: #2d7a5f;        /* SHIKSHA-Grün */
--accent-soft: #e8f1ec;
--warn: #8a6a2a;
--warn-soft: #f5ebd8;
--alert: #a0391f;
--alert-soft: #f5e1da;
--mono: "SFMono-Regular", Menlo, Consolas, monospace;
```

→ Diese 9 Tokens definieren das SHIKSHA-Branding-Fundament.

### Was bewusst abweicht (Mobile vs. Operator)

```css
/* Operator-Variant */
--bg: #f7f7f5;          /* kühles, neutrales Schreibtisch-Grau */
--line: #e6e4de;
--ink-mute: #7a7a74;

/* Mobile-Variant (Teilnehmer-App, Gäste-App) */
--bg: #f0eee9;          /* warmer, weicher Pocket-Hintergrund */
--line: #ece9e2;
--ink-mute: #8a8780;
```

**Begründung der Abweichung:**
Mobile-Apps werden "zwischen Tür und Angel" benutzt — am Strand, im Studio-Vorraum, beim Spaziergang. Ein leicht warmerer Hintergrund wirkt freundlicher. Operator-UIs werden hingegen am Schreibtisch konzentriert genutzt — kühles Neutral-Grau bremst Augen-Ermüdung.

Das ist eine bewusste Entscheidung, kein Versehen. War aber **nirgendwo dokumentiert** — bis jetzt.

---

## 2. ZENTRALE DATEI: `shiksha_design_tokens.css`

Diese Datei ist jetzt die **einzige Quelle der Wahrheit** für alle Tokens.

**Inhalt:**
- Vollständige Token-Definition mit Kommentaren zur Bedeutung
- Mobile-Variant via `.is-mobile-context` Utility-Klasse (CSS-Override)
- Gemeinsame UI-Primitive (Severity-Pills, Sentence-Blocks, Pills, Buttons, Foto-Flow)
- Naming-Konventionen

**Zwei Verwendungs-Modi:**

### Modus A — Standalone (aktuell, bis Markteinführung)
Jede HTML-Datei kopiert die Tokens in ihren eigenen `<style>`-Block. Vorteil: Datei lässt sich isoliert teilen, läuft ohne Server, wird per Doppelklick geöffnet.

### Modus B — Zentral via `<link>` (für die produktive Web-App, V2)
```html
<link rel="stylesheet" href="/static/shiksha_design_tokens.css">
```
Ein File, alle Tokens, alle Primitives. Änderungen wirken sofort überall.

**Aktuell:** Modus A bleibt für Mockups in Pilot-Phase, weil Standalone-Distribution wichtig ist.
**Geplant für V2:** Modus B nach erstem produktiven Pilot.

---

## 3. TOKEN-INVENTAR

### Basis-Flächen
| Token | Wert | Bedeutung |
|---|---|---|
| `--bg` | `#f7f7f5` (Operator) / `#f0eee9` (Mobile) | Hauptseiten-Hintergrund |
| `--card` | `#ffffff` | Kartenfläche, immer hell |
| `--phone-bg` | `#ffffff` | Mobile-Container-Inhalt |

### Linien
| Token | Wert | Bedeutung |
|---|---|---|
| `--line` | `#e6e4de` (Op) / `#ece9e2` (Mob) | Standard-Trenner |
| `--line-strong` | `#c6c2b8` | Hervorgehobene Trennung |

### Schrift-Farben
| Token | Wert | Bedeutung |
|---|---|---|
| `--ink` | `#1a1a1a` | Haupt-Body-Text |
| `--ink-soft` | `#55524b` | Sekundär (Meta, Beschriftung) |
| `--ink-mute` | `#7a7a74` (Op) / `#8a8780` (Mob) | Tertiär (Hinweise, Details) |

### Severity-Skala
| Token | Wert | Bedeutung |
|---|---|---|
| `--accent` / `--accent-soft` | `#2d7a5f` / `#e8f1ec` | Erfolg, "alles gut" |
| `--positive` / `--positive-soft` | `#4a8050` / `#e3f0e6` | Erfreulich (Stamm­gast etc., Camping-only) |
| `--info` / `--info-soft` | `#4a6a80` / `#e8eef1` | Neutral-Hinweis, Pflege |
| `--warn` / `--warn-soft` | `#8a6a2a` / `#f5ebd8` | mid-Severity, "schau hin" |
| `--alert` / `--alert-soft` | `#a0391f` / `#f5e1da` | high-Severity, "handeln" |
| `--learn` / `--learn-soft` | `#6a4faf` / `#efeaf5` | **Nur safeguarding** — Lern-UI |

### Schrift
| Token | Wert | Bedeutung |
|---|---|---|
| `--mono` | `SFMono-Regular, Menlo, Consolas, monospace` | Code, Zähler, IDs |

---

## 4. KONSISTENZ-AUDIT (heute)

```
✓ 9 Tokens identisch über alle 7 Files
✓ Mobile-Variant in 2 Files konsistent abweichend
✓ Spezial-Tokens (--info, --positive, --learn) nur dort wo gebraucht
✗ Tokens waren NICHT in zentraler Datei (jetzt: ✓ in shiksha_design_tokens.css)
✗ Mobile-vs-Operator-Abweichung war NICHT dokumentiert (jetzt: ✓ in dieser Datei)
```

---

## 5. WIE DIE MIGRATION ZU MODUS B AUSSEHEN WÜRDE

Wann die Migration sinnvoll ist:
1. Erster Pilot ist live, läuft stabil
2. Wir produktiv die UIs auf shiksha.tun.zone hosten (statt lokal als Mockups)
3. Mehr als 7 Files existieren (z. B. CLUB.EDITION dazu, mehr Editionen)

Migrationsschritt (1 Stunde Aufwand):

```bash
# 1. Tokens-File auf Server packen
scp shiksha_design_tokens.css \
    root@88.99.174.186:/opt/shiksha/static/

# 2. Alle HTML-Mockups: <style>-Block ersetzen durch
#    <link rel="stylesheet" href="/static/shiksha_design_tokens.css">
#    + nur file-spezifisches CSS im inline <style>

# 3. FastAPI: static-Mount sicherstellen
#    (in main.py)
#    from fastapi.staticfiles import StaticFiles
#    app.mount("/static", StaticFiles(directory="static"), name="static")
```

Danach: jede Token-Änderung wirkt überall. Aber: Standalone-Distribution funktioniert nicht mehr, ohne die CSS-Datei mitzuschicken.

**Empfehlung:** Hybrid-Modus für die Pilot-Phase:
- Mockups bleiben standalone (für Mail-Versand)
- Die LIVE-UI auf shiksha.tun.zone nutzt das zentrale CSS
- Bei jedem Update: Tokens zentral ändern, dann in alle Mockup-Files re-deployen via Build-Script (kann ich später schreiben)

---

## 6. PRINZIPIEN (V4-konform)

Die SHIKSHA-Design-Tokens folgen denselben Prinzipien wie der Code:

1. **Semantische Naming, keine Farb-Naming.** `--accent`, nicht `--green`. Wenn wir morgen blau werden, ist das eine Token-Änderung.

2. **Soft-Varianten konsistent.** Jede Severity-Farbe hat ein `-soft` für Hintergründe.

3. **Severity-Skala vollständig.** info → accent → warn → alert. Plus `learn` für safeguarding-Lern-Kontext, plus `positive` für Camping-Stamm­gast-Marker.

4. **Mobile vs. Operator dokumentiert abweichend.** Nicht zufällig, sondern absichtlich.

5. **Confidence in Sprache, nicht Farbe.** Wir nutzen Farbe für Severity, nicht für Confidence — Confidence lebt im Sprache-Layer.

6. **Mono nur dort wo es um Genauigkeit geht.** Zähler, IDs, Codes. NIE für Marketing-Text.

---

## 7. WAS NICHT IM TOKEN-FILE IST

Bewusst ausgelassen, weil File-spezifisch:

- **Schatten / Box-Shadows** — pro Komponente unterschiedlich (Phone vs. Card vs. Modal)
- **Border-Radius-Werte** — pro Komponente unterschiedlich (Pills 999px, Cards 10px, Buttons 6px)
- **Spacing-Skala** — wir nutzen direkt Pixel-Werte, keine `--space-*` Tokens. Bewusst V1-pragmatisch.
- **Animations** — kommen erst, wenn nötig, nicht jetzt.

Wenn V2 eine vollständige Skala braucht (8-Punkt-Grid, t-shirt-sizes), kann das ergänzt werden. V1 ist absichtlich schlank.

---

Stand: 25. April 2026 · Audit bestanden · Tokens zentral · Modus-Migration dokumentiert

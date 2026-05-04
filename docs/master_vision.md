# SHIKSHA — Master Vision

**Author:** Strategie-Partner (via Founder)
**Status:** Alpha-Direktive für SHIKSHA.OS
**Context:** Pre-Launch KITA-Edition (Dornbirn)
**Stand:** 3. Mai 2026
**Verbindlichkeit:** Diese Datei ist die **primäre Leitplanke** für alle Code-Generierung. Bei Konflikt zwischen einer Implementations-Idee und dieser Vision gewinnt die Vision — sofern sie nicht durch Pilot-Lessons explizit revidiert wurde.

---

## 1. Die Kern-Philosophie

### Kein Onboarding

Ersetzung durch einen **10-15-minütigen Kennenlern-Dialog**. Die KI extrahiert alle Geschäftsdaten (Mitglieder, Zeiten, Regeln) autonom in die FastAPI-Struktur.

→ Implementiert in: `docs/build-packs/SHIKSHA_DIALOG_BUILD_PACK_V2.md`
→ Beispiel-Dialog: TEIL 3 dort
→ Krummelus-Pilot-Start: 4. Mai 2026

### No Configuration

Der Nutzer darf **nichts konfigurieren müssen**. SHIKSHA lernt, beobachtet und optimiert sich selbst.

Konsequenz für Code:
- Keine Settings-Seiten ohne klaren Zweck
- Defaults sind so gewählt, dass 95% der Nutzer:innen sie nie ändern müssen
- Wenn doch konfiguriert werden muss: SHIKSHA fragt im Dialog, nicht der User klickt sich durch Menüs

### Der Preis-Anker

**Radikale 50 € / Monat.** Keine psychologischen Preise (keine 49,99 €).

In der Zukunft (globale Skalierung): **Vision von 1 € / Monat** — 90 % Social Impact.

Konsequenz für Code:
- Pricing-Variable im System hinterlegen, nicht im Frontend hartkodieren
- Kein "Special Offer"-Tricks, kein "nur jetzt 39€"-Marketing
- Preis-Klarheit im UI: ein Satz, ein Betrag, kein Sternchen

---

## 2. Edition-Logik & Module

### KITA-Edition (Live ab 4. Mai 2026)

Fokus auf:
- **Identity-Check-in** der Pädagog:innen am Morgen
- **Echtzeit-Berechnung des ST%-Schlüssels** (Stellenprozent nach KGG-Förderstaffel)
- **Proaktive Warnung bei Personalengpässen** — Push an Leitung, Mitarbeiter und Eltern

→ Pilotpartner: Krummelus, Dornbirn (Trägerin: Mira Fiel)
→ Status: **live ab morgen**, Hybrid-Lauf mit Founder als SHIKSHA-Sprecher
→ Build-Packs: `docs/build-packs/SHIKSHA_DIALOG_BUILD_PACK_V2.md`

### GASTRO-Edition — LUNCHBOX-Konzept (Vision)

Drei strategische Säulen:

**17% Wareneinsatz-Logik**
- Fokus auf **vegetarisches Cook & Chill**
- 12 Tage Haltbarkeit bei 3°C
- Erlaubt Skalierung ohne tägliche Frisch-Logistik

**Idle-Time-Production**
- Gastronomen produzieren in **toten Zeiten** (14-17 Uhr)
- Via **Kombidämpfer-Batches** (100 Portionen/h)
- Maximiert vorhandene Hardware-Auslastung, nicht zusätzliche Investition

**Veredelungs-Modul**
- Technik erledigt **Logistik**
- Mensch erledigt das **Lächeln** (Olive Jacke, frischer Parmesan, Kürbiskerne)
- Differenzierungs-Kern: das industriell Hergestellte wird im letzten Schritt von Hand veredelt

→ Status: **Vision**, Build-Pack noch zu schreiben
→ Backlog-Eintrag: `SHIKSHA_BACKLOG.md` → Editionen-System

### MOBILITY / CAMPING-Edition (Vision)

Zwei strategische Säulen:

**Hardware-Integration**
- GPS/Tankdaten (Vercharterer)
- IoT-Hardware: Schranken, Strom-Säulen, Schließanlagen
- Auto-Check-in via Geofencing

**Dynamic Pricing**
- Wetter- und auslastungsabhängige Preissteuerung
- **Vollautomatisch nach Regeln** — der Mensch setzt die Regeln, das System wendet sie an

→ Status: **Vision**, Camping-Build-Pack existiert (`CAMPING_EDITION_*`), wird um Hardware-Layer erweitert

---

## 3. Technische Imperative für Claude

### Farbraum-Automatik

Synchronisation der Frontend-Anmutung mit Tageszeit + Standort.

Beispiel-Mapping (Dornbirn):
- 07:00 = Shiksha-Sunrise-Yellow
- 12:00 = Mittag-Klarweiß / Holi-Pastell
- 17:00 = Späte-Nachmittag-Apricot
- 20:00 = Strategic-Deep-Blue

Implementation:
- Backend-Funktion `get_color_palette(time, location)` mit `astral` oder `pyephem`
- Output: Hex-Codes als CSS-Custom-Properties via SSE-Push
- Frontend: CSS variables, sanfte Übergänge

→ Backlog: `SHIKSHA_BACKLOG.md` → Plattform-Site Premium-Polish

### Theorie-Brücke

Bei Wetterumschwung (via Wetter-API):
- Outdoor-Aktivitäten → Online-Theorie oder Indoor-Alternativen
- Anwendungs-Beispiel KITA: Ausflug fällt aus → Vorschlag: "Bilderbuch-Stunde im Bewegungsraum, Material X im Lager"
- Anwendungs-Beispiel SCHULE: Sportstunde fällt aus → "30-Min-Theorie-Modul Y, Quiz Z dazu"

→ Backlog: neuer Eintrag, Wetter-API-Integration als Cross-Edition-Modul

### Circular Economy

- **STITCH.ENGINE-Integration** — Stickprogramme als Service in jeder Edition (KITA: Namens-Aufnäher, Camping: Equipment-Markierung, etc.)
- **3D-Druck-Netzwerk** für lokale Ersatzteilproduktion
- Branding: **"shiksha-smart" Reparaturservice**

→ STITCH läuft als eigenständiges Repo (`herrknoedler-cell/stitch-engine`)
→ Cross-Plattform-Integration via Edition-Karte mit `external_url`
→ 3D-Druck: noch zu konzipieren, kandidiert für eigenes Build-Pack

---

## 4. Der "Amazon-Moment"

> SHIKSHA ist **kein Tool**, sondern ein **digitaler Mitarbeiter**.
>
> Ziel: **Maximierung der Umsatzrendite** durch **Eliminierung administrativer Leerläufe**.
>
> Wir bauen keine App, sondern eine **Matrix der Wertschätzung**.

Konsequenz für jeden Implementations-Sprint: bei jedem Feature die Frage stellen — *spart das jemandem echte Lebenszeit, oder ist es nur Spielerei?*

Der Efficiency-Tracker (siehe Build-Pack v2 TEIL 6) macht diese Frage messbar: pro Aktion eine Zeitersparnis-Berechnung. Aggregiert über Wochen ergibt das den **ROI-Beweis** für jede Trägerin, die SHIKSHA bezahlt.

### 4.1 Pilot-Validierung — Mira spricht den Vision-Satz

Im ersten echten Pilot-Gespräch (Mira Fiel, Krummelus Dornbirn, 4. Mai 2026) hat Mira den Kern der Master-Vision **in eigenen Worten formuliert** — ohne unsere Architektur zu kennen:

> *"Ein Programm, was mir die ganze Zettelei und Denkerei abnimmt."*
> 
> — **Mira Fiel**, Trägerin · Krummelus, Dornbirn

Dass eine Trägerin den Vision-Satz selbst sagt, bevor sie das Produkt vollständig sieht, ist **die stärkste Validierung dafür, dass die Master-Vision Marktrealität ist** — nicht nur strategische Hoffnung.

**Konsequenz für die Marken-Kommunikation:** Mira-Wortlaut wird zur Marken-Subline. Statt der ursprünglichen Tech-orientierten Tagline (*"Plattform, die mitlernt"*) wird die Mira-Stimme zum Hero-Element auf der Plattform-Site und auf Edition-Sales-Pages — siehe `docs/proposals/HERO_UPDATE_MIRA_STIMME.md` für die konkrete Umsetzung.

Pflege-Regel: Mit jedem neuen Pilot kommen weitere Stimmen dazu. Camping-Pilot, Schule-Pilot, Surfschule-Pilot — alle dürfen ihre eigenen Mira-Sätze beitragen. Das ist nicht "Marketing-Material sammeln", das ist **Marken-Realität durch Pilot-Stimmen erweitern**.

---

## 5. Verbindlichkeit & Pflege

**Diese Datei ist Pflicht-Lektüre für jede Code-Session.** Wenn Claude beim nächsten Sprint eingreift:
1. CLAUDE.md lesen (Architektur-Regeln, Lessons)
2. **`master_vision.md` lesen (Philosophie, Pricing, Marken-DNA)** ← diese Datei
3. **`docs/WORDING_AND_LANGUAGE.md` lesen (bindender Sprach-Codex für UI-Texte und Persona)**
4. SHIKSHA_BACKLOG.md lesen (was geplant ist)
5. tech-debt.md lesen (was als Schulden bekannt ist)

**Wann wird master_vision.md aktualisiert?**

- Wenn Pilot-Lessons eine Vision revidieren
- Wenn eine neue Edition strategisch dazukommt
- Wenn ein Pricing-Anker bewusst geändert wird

Aktualisierungen passieren über Git-Commits mit Conventional-Commit-Message `vision:`. Beispiel:

```
vision: revise pricing anchor from 50€ to 39€ after Krummelus-Lessons
```

Niemals ohne expliziten Founder-Beschluss. Die Vision ist heilig, bis der Founder sie ändert.

---

## 6. Status der Konzepte (Tableau)

| Konzept | Status | Build-Pack | Pilot |
|---|---|---|---|
| Kennenlern-Dialog (statt Onboarding) | **Live ab 4. Mai** | `SHIKSHA_DIALOG_BUILD_PACK_V2.md` | Krummelus |
| ST%-Engpass-Push | **Build, Backlog** | `SHIKSHA_BACKLOG.md` → VAPID + Subscribe | Krummelus |
| Identity-Check-in | **Live, im Modul** | Identity-Modul existiert | Krummelus |
| 50€-Pricing-Anker | **Direktive** | im MANIFEST | — |
| 1€-Vision (Social Impact) | **Vision** | langfristig | — |
| GASTRO-Edition LUNCHBOX | **Vision** | noch zu schreiben | — |
| Cook&Chill / 17% Wareneinsatz | **Vision** | Teil von GASTRO-Build-Pack | — |
| MOBILITY/CAMPING + IoT | **Vision** (CAMPING-Build existiert) | Erweiterung um Hardware-Layer | — |
| Dynamic Pricing | **Vision** | Teil von MOBILITY-Build-Pack | — |
| Farbraum-Automatik (Sonnenstand) | **Backlog** | `SHIKSHA_BACKLOG.md` Premium-Polish | — |
| Theorie-Brücke (Wetter-API) | **Backlog** | neuer Eintrag | — |
| STITCH-Integration | **In Arbeit** | eigenes Repo, V6.1 morgen | — |
| 3D-Druck-Netzwerk | **Vision** | noch zu konzipieren | — |
| Efficiency-Tracker | **Backlog** | `SHIKSHA_BACKLOG.md` | — |

---

## 7. Addendum — SHIKSHA.REPAIR (Lokal-Netzwerk)

**Status:** Vision (kein Code-Sprint vor 2027). Konzept dokumentiert in `docs/build-packs/SHIKSHA_REPAIR_NETWORK_CONCEPT_V0_1.md`.

### Die Vision — schärfer formuliert

**SHIKSHA baut keinen Scanner und keine Drucker. SHIKSHA verkürzt Lieferwege.**

Wenn ein Camping-Beschlag bricht, eine KITA-Spielzeug-Lasche fehlt, ein Boots-Bauteil weg ist — bisher: Versand aus dem Lager, oft aus dem Ausland, Wartezeit Tage bis Wochen. **Mit SHIKSHA: das Teil wird im Nachbardorf gedruckt, in 4 Stunden abgeholt.**

Der Wert ist nicht der Druck. Der Wert ist die **Verbindung von lokaler Druckkapazität und lokalem Bedarf** — zwei Dinge, die heute nicht miteinander reden.

### Drei Komponenten — und wer sie baut

1. **Scan** — *baut SHIKSHA NICHT.* User nutzt was schon existiert (Luma AI, Polycam, native iPhone Object Capture). User lädt fertige `.stl` oder `.obj` Datei bei SHIKSHA hoch.

2. **Repair** — *baut SHIKSHA NICHT.* Wenn Scan unvollständig ist, leitet SHIKSHA an existierenden Cloud-Service weiter (Meshy, CSM). Oder: der Drucker-Operator macht eine Mini-Korrektur in der Slicer-Software, das ist Handwerk, nicht KI.

3. **Lokal-Netzwerk** — *das baut SHIKSHA.* Datenbank von 3D-Druckern (geografisch), Auftragsvermittlung, Bezahlung, Bewertung. **Hier liegt der echte Wert.**

### Strategische Klammer

**Climate-Win:** Lokal drucken statt international versenden — CO2-Ersparnis pro Auftrag berechnet und sichtbar.

**Time-Win:** 4 Stunden statt 4 Tage — gerade bei kleinen Reparatur-Teilen oft der Game-Changer.

**Community-Win:** Maker-Spaces, lokale Werkstätten, Hobby-Drucker mit freier Kapazität verdienen mit. Geld bleibt vor Ort.

**Cross-Edition-Wert:** Camping-Edition meldet defekte Stellplatz-Beschläge, KITA-Edition meldet kaputtes Spielzeug, Mobility-Edition meldet Boots-Komponenten. **Eine Reparatur-Engine, alle Editionen profitieren.**

### Realistischer Pfad

**MVP (1-2 Wochen, wenn Strategie-Slot frei):**
- SHIKSHA-Reparatur-Marktplatz für Mitglieder der Editionen
- Drucker-Registry (manuell gepflegt zu Beginn — Vorarlberger Maker)
- Auftrag-Routing nach Distanz + Material
- Trust via SHIKSHA-Membership (Pilot-Operatoren bekannt)

**Skalierung (3-6 Monate):**
- Self-Service-Drucker-Onboarding (Maker registrieren sich)
- Bezahlungs-Layer (Stripe Connect)
- Bewertungssystem
- Optional: Integration mit existierenden Cloud-Plattformen (Treatstock, Craftcloud)

**Vision (12+ Monate):**
- Eigene "shiksha-smart"-Repair-KI für defekte Scans (falls sich der Eigenbau lohnt)
- Internationales Drucker-Netzwerk
- Materialien-Marktplatz

**Empfehlung:** Starten mit lokalem Vorarlberg-Cluster. KITA-Krummelus als erster Test-Case ("Wir haben eine kaputte Spielzeug-Lasche, kannst Du sie drucken lassen?"). Daraus lernen.

→ Detail-Konzept: `docs/build-packs/SHIKSHA_REPAIR_NETWORK_CONCEPT_V0_1.md`

---

## 8. Anweisung an Claude

> *"Claude, lege diese Datei unter `docs/master_vision.md` an. Nutze diese Vision als primäre Leitplanke für alle kommenden Code-Generierungen. Wenn ich dich morgen nach dem Feedback der KITA-Leitung frage, beziehe dich auf diese strategischen Ankerpunkte."*

— Founder, 3. Mai 2026

---

**Der Grundstein ist gelegt.**

# SHIKSHA — Hero Journey

**Status:** Flow-Spec · der durchgehende Bogen vom ersten Klick bis zum täglichen Ritual
**Stand:** 11. Mai 2026
**Cross-Reference:**
- `SHIKSHA_RESPONSE_ENGINE.md` — 4 Modi
- `VERDICHTEN_PHASE_SPEC.md` — Phasen-Architektur Kennenlernen → Verdichten
- `SHIKSHA_DEV_PORTAL_ARCHITECTURE.md` — Backend-Foundation
- `presence_switch.html` — Eintrittsgeste
- `krummelus_kennenlernen_v2.html` — Kennenlernen-Frontend
- `mira_app.html` — Mobile-PWA

---

## 1. Was die Journey ist

Ein einziger zusammenhängender Bogen, der eine Trägerin (oder Wirt, Lehrer, …) führt von:

```
"Was ist SHIKSHA?"
       ↓
"Ich erzähle dir, was bei uns los ist."
       ↓
"Das passt zu uns, lass uns das einrichten."
       ↓
"Hier ist unsere Webseite. Hier ist unser Dashboard."
       ↓
"Ich nehm SHIKSHA mit aufs Phone."
       ↓
"Heute war so. Ich erzähl's dir."
       ↓
(täglich, ohne Bruch, ohne dass es sich wie Software anfühlt)
```

Sieben Phasen. Sieben Übergänge. Eine durchgängige Stimme: SHIKSHA.

---

## 2. Phasen-Übersicht

```
A  PRÄSENTATION         ~3-4 Min · Slides · vor-Account · optional skipbar
B  KENNENLERNGESPRÄCH   ~15-30 Min · Chat · Daten entstehen unsichtbar
C  ZEITGESPRÄCH         ~10-20 Min · Wiederbeginn, Vertiefung, Bestätigung
D  AUTO-GENERATION      ~30-90 Sek · Webseite + Dashboard werden gebaut
E  DASHBOARD-ÜBERGANG   ~3-5 Min · Schaufenster zeigen, Dashboard-Tour
F  MOBILE-HANDOVER      ~2 Min · QR-Code, PWA-Install, Passkey aufs Phone
G  TAGESRITUAL          täglich · 5-10 Min · Tagesausklang, Streak, Verdichten
```

---

## 3. Phase A — PRÄSENTATION

**Wo:** `https://shiksha.world` oder Edition-spezifisch `kita.shiksha.world`, `camping.shiksha.world`, …

**Was passiert:**

```
Hero-Video läuft (das Holi-Smoke-Video).
SHIKSHA-Schriftzug schreibt sich.
Begrüßung "Guten Tag. Ich bin SHIKSHA. Ich höre zu."
Vier Inhalts-Slides:
  1. Das hier ist ein Gespräch.
  2. Du musst nichts erklären.
  3. Es geht um Dich.
  4. Warum es das gibt.
"Beginnen"-Button → Phase B.
```

**Bestand:** `krummelus_kennenlernen_v2.html` deckt das schon ab.

**Was fehlt:** Edition-Routing. `kita.shiksha.world` sollte zur KITA-Variante führen, `camping.shiksha.world` zur Camping-Variante. Heute ist alles eine Datei.

**Transition zu B:** Klick *„Beginnen"* → der Gesprächsraum erscheint, die Slides verblassen. Kein Kontext-Wechsel.

---

## 4. Phase B — KENNENLERNGESPRÄCH

**Wo:** Direkt im selben Tab/Browser, Gesprächsraum.

**Was passiert (Mira-Sicht):**

```
Headline: "Erzähl mir."
Subline: "Fang einfach irgendwo an."

Mira tippt los, was sie gerade beschäftigt.
SHIKSHA reagiert in den 4 Modi (PRÄSENZ / FOKUS / VERDICHTEN / AUSKLANG).
SHIKSHA fragt nicht aus Gewohnheit. Sie hört, spiegelt, vertieft sanft.

Über 15-30 Minuten entwickelt sich ein echtes Gespräch. Kein Formular.
```

**Was passiert im Hintergrund (Mira sieht es nicht):**

```
SHIKSHA-Tool-Calling extrahiert systematisch:
- Wer (Name, Rolle)
- Was für ein Ort (KITA, Camping, Schule, …) → bestimmt Edition
- Wie groß (Mitarbeiter, Kinder, Gäste, …)
- Was schmerzt (Pain-Points)
- Wie der Tag läuft (Tagesablauf)
- Wer noch da ist (Familie, Team, Mama)
- Sprach-Vokabular (für Persona-Adaption)

Tools (server-side, transparent):
  log_observation(kind, text)
  log_friction(where, text)
  extract_org_info(name, type, region, size)
  save_pain_point(text, severity)
```

**Trigger zum Ende:**

```
SHIKSHA spürt "genug für jetzt", weil:
- Hauptthemen einmal benannt
- Stimmung beruhigt
- Mira erschöpft klingt oder sagt "lass uns weitermachen"

ODER explizit:
- Mira tippt "lass uns weitermachen"
- Mira tippt "ich hab grad nicht mehr Zeit"
- Mira drückt subtilen "Für heute reicht's"-Button
```

**Übergang zum Abschluss:**

```
SHIKSHA: "Für heute reicht das. Ich nehm es mit."
SHIKSHA: "Magst Du, dass ich uns das Schaufenster baue? Du musst nicht
         nochmal vorbei kommen, ich melde mich, wenn's so weit ist."

[Ja, bau los]   [Lieber morgen]
```

**Bestand:** Conversation-Room in `krummelus_kennenlernen_v2.html`, mit 4-Modus-Engine. LLM-Call funktioniert.

**Was fehlt:**

- Tool-Calling (Backend-Endpoints `log_observation` etc. müssen aktiv genutzt werden, nicht nur als Skelett da)
- Automatische Edition-Erkennung aus dem Gespräch
- Mehr Kontext-Extraktion (org_info, pain_points, vocabulary)
- Ein klarer Abschluss-Trigger (heute fehlt der bewusste Übergang zu Phase C)

**Transition zu C:**

```
Wenn Mira "Lieber morgen" wählt:
  → SHIKSHA: "Schön. Ich melde mich, wenn der Moment kommt."
  → Verabredung speichern (next_session_at)
  → Mira bekommt Push am verabredeten Tag

Wenn Mira "Ja, bau los" wählt:
  → Phase B endet
  → Phase D wird ausgelöst PARALLEL zu Phase C
  → Phase C kann am Folgetag stattfinden (asynchron)

ODER: B endet sofort, C startet später (asynchron, beim nächsten Besuch).
```

---

## 5. Phase C — ZEITGESPRÄCH (Erkennung)

**Wo:** Mira besucht `kita.shiksha.world` erneut, oder bekommt eine Einladungs-URL.

**Was passiert (Mira-Sicht):**

```
Stage:
  "Schön, Dich wiederzusehen, Mira."
  
Wiederbeginn-Zusammenfassung:
  "Letztes Mal hast Du mir das erzählt:
   - Krummelus ist eine Familien-KITA in Dornbirn,
     gemeinsam mit Deiner Mama.
   - Die Zettelei nimmt Euch Energie.
   - Wochenend-Anrufe sind ein Reibungspunkt.
   - Fünf Mitarbeiterinnen, [N] Kinder.

   Stimmt das so?"
  
  [Ja, weiter]   [Etwas ist nicht ganz richtig]

→ Wenn etwas falsch: SHIKSHA fragt nach Korrektur (FOKUS).
→ Wenn richtig: Übergang ins Vertiefungs-Gespräch.

Vertiefung:
  SHIKSHA hat nach dem ersten Gespräch eine interne Liste offener
  Themen. Sie geht ein bis drei davon an — eines nach dem anderen,
  nie alle auf einmal.

  Beispiele:
  - "Letztes Mal hast Du erzählt, dass Wochenend-Anrufe oft niemand
    mitbekommt. Magst Du, dass wir uns ansehen, wie ich das morgen
    abfangen könnte?"
  - "Du hast von Lukas erzählt. Magst Du, dass wir ihm einen Platz
    geben?"

Stammdaten-Vertiefung (sanft, nicht als Formular):
  SHIKSHA: "Soll ich die Mitarbeiterinnen-Namen jetzt aufnehmen?"
  Mira: "Ja."
  SHIKSHA: zeigt vorgefasste Liste aus erstem Gespräch + Korrektur-
           Möglichkeit. Oder Mira tippt sie ein. Oder Mira lädt
           eine Excel hoch.

Bestätigung & Generation-Trigger:
  SHIKSHA: "Eure Adresse wird krummelus.shiksha.world. Magst Du, dass
           ich uns das Schaufenster baue?"
  
  [Ja, perfekt]   [Anderer Name]
```

**Was passiert im Hintergrund:**

```
- Wiederbeginn-Zusammenfassung wird aus Memory-Block + erster Session
  zusammengesetzt (LLM-Call mit Sonder-Prompt).
- Tool-Calls für jede Korrektur, jeden Stammdaten-Update.
- Edition-Detection: aus Gespräch → "kita" → KITA-Edition-Templates werden vorgeladen.
- Trigger für Generation aktiviert (Phase D startet).
```

**Bestand:** keine — Wiederbeginn-Logik ist noch nicht gebaut.

**Was fehlt:**

- Wiederbeginn-Zusammenfassungs-Generator (LLM-Call mit Sonder-Prompt)
- Korrektur-UI im Chat (Mira sagt "Lisa heißt Lissi", Backend updated Stammdaten)
- Stammdaten-Karte (kompakt im Chat, mit Edit-Icons)
- Excel-Upload für Stammdaten (mit pandas-Parser, der schon existiert)
- Generation-Trigger im Backend

**Transition zu D:**

```
Klick [Ja, bau los] → 
  Frontend: Stage wechselt zur Bauanimation
  Backend: Asynchroner Generation-Job startet
  Mira: kann weitererzählen während es läuft
```

---

## 6. Phase D — AUTO-GENERATION

**Was passiert (Mira-Sicht):**

```
"Ich brauch ein paar Minuten. Du kannst weitererzählen, ich höre mit."

[Atmende Animation, kein Spinner — irgendwas warmes, ruhiges]

(Mira kann zu SHIKSHA weiter reden während es läuft — die Chat-
Inputs werden eingesammelt, aber nicht beantwortet bis Generation
fertig ist. Oder SHIKSHA antwortet im PRÄSENZ-Modus während sie baut.)

[~30-90 Sekunden später]

"Da ist Euer Schaufenster."
→ Link öffnet sich, Vorschau erscheint
```

**Was passiert im Hintergrund:**

```
Generation-Pipeline (alles parallel oder sequenziell):

1. Subdomain provisioning
   - DNS-Eintrag krummelus.shiksha.world → Server-IP
   - Caddy-Config für TLS + Routing
   
2. Webseiten-Generation
   - Template aus Marketing-Site-Generator (existiert: Phase 1 Build-Pack)
   - Inhalte werden gefüllt aus dem Gespräch:
     * Name, Region, Edition
     * Mitarbeiter-Liste (mit Avataren-Placeholder oder Initialen)
     * Pain-Points → werden zu "Was wir gut können"
     * Anmelde-Möglichkeit für Eltern
   - Theme: Holi-Verlauf, Edition-Akzent
   
3. Dashboard-Setup
   - Trägerin-Dashboard erstellt mit Card-System (existiert)
   - Cards basierend auf Pain-Points:
     * "Eltern-Push-Inbox" wenn Wochenend-Anrufe genannt wurden
     * "Beobachtungen" wenn Kinder erwähnt wurden
     * "Kalender" wenn Termine genannt
   - Default-Cards: Stammdaten, Compliance, Tagesausklang-Status
   
4. PWA-Manifest + Service Worker
   - mira.krummelus.shiksha.world oder krummelus.shiksha.world/app
   - Icons (Edition-spezifisch)
   - manifest.json gefüllt
   
5. Operator-Account
   - shiksha_core.operators wird angelegt
   - WebAuthn-Credential für Mira (sie registriert beim ersten Mobile-Login)
   
6. Database-Seed
   - shiksha_core.organizations[krummelus]
   - persona_prompts (cross-edition + ggf. KITA-spezifisch)
   - Mitarbeiter aus Stammdaten-Vertiefung
   - Compliance-Checkliste (KGG für KITA)
```

**Was generiert wird ist edition-spezifisch:**

| Edition | Webseite | Dashboard-Cards |
|---|---|---|
| KITA | Eltern-Anmeldung, Team, Tagesablauf | Compliance, ST%-Rechner, Eltern-Inbox |
| Camping | Buchung, Plätze, Highlights | Belegung, Anmeldungen, Wetter |
| Schule | Kurse, Termine, Anmeldung | Teilnehmer, Stundenpläne |
| Surf | Spots, Kurse, Verleih | Wetter, Buchungen, Equipment |
| Yoga | Stundenplan, Lehrer, Pakete | Teilnahmen, 10er-Karten |
| Club | Mitglieder, Events | Mitgliedschaften, Beiträge |

**Bestand:** Marketing-Site-Generator und Trägerin-Dashboard existieren (Tasks #64, #66 completed). Auto-Provision aus Conversation-Input nicht.

**Was fehlt:**

- Generation-Endpoint `POST /api/v1/orchestration/provision`
- Conversation-zu-Daten-Extraktion (heute noch nicht implementiert)
- Subdomain-Provisioning (Caddy + DNS API)
- Sicht-bare Bauanimation während Generation
- Live-Push wenn Generation fertig

**Transition zu E:**

```
Generation fertig → SHIKSHA: "Da ist Euer Schaufenster."
→ Link wird im Chat eingeblendet (groß, klickbar)
→ Optional: Vorschau-Frame inline im Chat
→ Mira klickt → Webseite öffnet sich neu
→ Mira kommt zurück → SHIKSHA: "Wie fühlt sich das an?"
```

---

## 7. Phase E — DASHBOARD-ÜBERGANG

**Was passiert:**

```
SHIKSHA: "Schön. Jetzt zeig ich Dir Dein SHIKSHA."

[Sanfter Übergang: Chat-Raum verblasst, Dashboard erscheint]
[Statt einer Tour mit Erklär-Pfeilen: einfach ist es da, 3-5 Karten,
ruhig, atmender Hintergrund]

Begrüßungs-Card oben:
  "Hier bin ich. Ich passe auf, was wichtig ist."

Drei bis fünf Karten:
  - Heute (was passiert ist + was bevorsteht)
  - Eltern-Inbox (wenn relevant)
  - Compliance (ST%, KGG-Status)
  - Beobachtungen (das was Mira erzählt hat)
  - Tagesausklang-Verabredung
```

**Mira kann:**

- Karten neu anordnen (Gridstack — existiert)
- In eine Karte zoomen → Detail-Sicht
- Aus jeder Karte heraus mit SHIKSHA reden (kleiner Chat-Trigger oben rechts)
- Anpassungen: "Mira, ändere die Farbe der Webseite" → öffnet Mini-Chat

**Bestand:** Trägerin-Dashboard mit Gridstack + Card-System komplett (Task #64). Hero-Card mit Begrüßung (Task #65).

**Was fehlt:**

- Übergang vom Chat-Raum ins Dashboard (Animation, Choreographie)
- Pain-Point-zu-Card-Mapping-Logik (welche Cards bekommt Mira)
- Anpassungs-Trigger aus Dashboard heraus

**Transition zu F:**

```
Nach 3-5 Minuten Dashboard-Erkundung oder explizit:

SHIKSHA-Hero-Card: "Ich möchte Dich auch unterwegs begleiten."
                   [Magst Du mich aufs Phone holen?]

Klick → Phase F.
```

---

## 8. Phase F — MOBILE-HANDOVER

**Was passiert:**

```
Modal/Vollbild:

"Magst Du mich aufs Phone holen?"

[Großer QR-Code]

"Scan mit Deinem Phone — ich bin gleich da."

[oder: SMS-Link an Telefonnummer / E-Mail-Link]
```

**Mira's Phone-Sicht:**

```
QR scannt → öffnet shiksha.world/setup?token=...
PWA-Installations-Aufforderung erscheint
"Zum Home-Bildschirm hinzufügen" (iOS) / "App installieren" (Android)
→ App startet
→ Presence-Switch erscheint mit nur einer Karte: Mira
→ Klick → Passkey-Registrierung (Face ID / Touch ID)
→ "Willkommen, Mira."
→ Heute-Tab der App
```

**Was passiert im Hintergrund:**

```
- Setup-Token wird vom Backend ausgestellt (lebt 10 Min)
- Token in QR-URL eingebettet
- Phone-Browser ruft mit Token /api/v1/auth/setup auf
- Backend gibt temp-Session → Mira registriert Passkey
- Passkey-Public-Key landet in operators.webauthn_credentials
- Dauerhafter JWT wird ausgestellt
- Phone bookmarkt sich, PWA installiert
```

**Bestand:** mira_app.html (PWA + Manifest + Service Worker) existiert. Presence-Switch-Skelett existiert.

**Was fehlt:**

- QR-Code-Generator im Dashboard
- Setup-Token-Endpoint
- Onboarding-Flow auf Mobile (One-Card-Variante des Presence-Switch)
- WebAuthn-Registrations-Flow

**Transition zu G:**

```
Mira's Phone zeigt Heute-Tab.
SHIKSHA: "Schön, dass Du mich mitgenommen hast.
         Wir reden später nochmal — kurz nach Feierabend.
         Ich melde mich."

→ Push-Permission-Request
→ Reminder geplant (17:30 Standard, anpassbar)

Heute-Tab zeigt:
  "Wir sehen uns abends. Bis dahin gehe Deinen Tag."
```

---

## 9. Phase G — TAGESRITUAL

**Was passiert (täglich):**

```
17:30 — Push: "Magst Du fünf Minuten erzählen, wie heute war?"
→ Klick → Mira-App öffnet sich auf Tagesausklang-Tab

Tagesausklang-Card:
  "Wie war heute?"
  [Beginnen]

Mira klickt → Chat öffnet sich → SHIKSHA-Opener
→ Gespräch in 4 Modi
→ Mira beendet ("Für heute reicht's")
→ LLM extrahiert Summary + 1-3 Insights
→ Session wird gespeichert, Insights in Memory
→ Streak wird hochgezählt

Heute-Tab updated:
  "Heute schon erledigt."
  Streak: "4 Tage in Folge."
  Insights-Card: die letzten 5 "Was bei mir bleibt"

Im Hintergrund über die Woche:
  - Memory wächst (15+ Einträge)
  - Trägerin-Dashboard zeigt sichtbare Pattern (in Web-Dashboard sichtbar)
  - SHIKSHA wird in jedem Gespräch klüger über Mira
```

**Bestand:** mira_app.html komplett, inkl. Tagesausklang, Streak, Insights. Local-Storage-basiert.

**Was fehlt für die volle Tiefe:**

- Server-Persistenz statt localStorage (Phase 2 der Backend-Roadmap)
- Echte Push-Notifications via Server (Phase 4 der Backend-Roadmap, VAPID + Push-Subscriptions)
- Cross-Device-Sync (wenn Mira im Browser was sagt, sieht sie's auf Mobile)
- Wochenrückblick (jeden Sonntag eine Mini-Summary der Woche)
- Insights-Visualisierung im Web-Dashboard (was hat sich über die Woche verdichtet)

---

## 10. Bestand vs. Gap — Zusammengefasst

```
                         BESTAND                    GAP
                         
A · Präsentation         krummelus_kennenlernen     Edition-Routing
                         _v2.html (Slides)          (kita/camping/...)
                         
B · Kennenlerngespräch   v2-Conversation-Room       Tool-Calling aktiv
                         4-Modi-Engine              Daten-Extraktion
                         LLM-Call (direct)          Backend-Migration
                         
C · Zeitgespräch         —                          Komplett: Wiederbeginn,
                                                    Vertiefung, Stammdaten-
                                                    Korrektur, Generation-
                                                    Trigger
                                                    
D · Auto-Generation      Marketing-Site-Generator   Conversation-to-Data
                         Trägerin-Dashboard         Subdomain-Provisioning
                         (Cards-System, Gridstack)  Bauanimation
                                                    Pain-zu-Card-Mapping
                                                    
E · Dashboard-Übergang   Dashboard existiert        Übergangs-Choreographie
                         Hero-Card existiert        Anpassungs-Trigger
                                                    aus Dashboard
                                                    
F · Mobile-Handover      mira_app.html              QR-Code-Generator
                         PWA-Manifest               Setup-Token-Flow
                         Service Worker             WebAuthn-Registration
                         Presence-Switch-Prototyp   PWA-Install-Prompt
                         
G · Tagesritual          mira_app komplett          Server-Persistenz
                         (Tagesausklang, Streak,    Server-Push (VAPID)
                          Insights, 3 Tabs)         Cross-Device-Sync
                                                    Wochenrückblick
```

**Erkennbar:** A, B, D, E, F, G existieren in **Pieces**. Was fehlt:

1. **Phase C** komplett (Zeitgespräch / Wiederbeginn / Generation-Trigger)
2. **Die Verbindungen zwischen den Phasen** (Transitions, State-Übergaben)
3. **Backend, das alles trägt** (siehe `SHIKSHA_DEV_PORTAL_ARCHITECTURE.md`)

Anders gesagt: einzelne Räume stehen. Es fehlen die Türen dazwischen, und das Haus, in dem sie alle sind.

---

## 11. Drei mögliche Wege — wie wir zur durchgehenden Journey kommen

### Weg 1 — Backend-First (sauber, aber langsam zum Erlebnis)

```
1. Phase 1-2 der Backend-Roadmap durchziehen (Backend + Frontend-Migration)
2. Dann Phase C im Frontend bauen (Wiederbeginn, Generation-Trigger)
3. Dann Übergangs-Choreographie A → B → C → D → E → F → G
4. Dann Server-Push für Tagesritual
```

Dauer: ~3-4 Wochen, am Ende ist alles auf festem Fundament. Mira erlebt die Journey erst spät.

### Weg 2 — Demo-First (schnell zum Erlebnis, später aufräumen)

```
1. Eine einzige große HTML-Datei bauen, die alle 7 Phasen durchläuft.
2. Mit Mock-Daten, ohne echtes Backend, ohne echte Subdomain-Generation.
3. Aber: vollständige Choreographie, alle Übergänge spielen.
4. Mira erlebt die Journey END-TO-END in 30 Minuten als Klick-Demo.
5. Dann: Backend bauen und schrittweise echte Teile einsetzen.
```

Dauer: ~3-5 Tage für die Demo, am Ende sieht Mira das fertige Erlebnis. Aber: nichts ist „echt", Mira-Daten kommen aus Mocks.

### Weg 3 — Hybrid (empfohlen)

```
1. Backend-Phase 1 + 2 durchziehen (~6 Tage) — Fundament
2. Demo-Choreographie der Übergänge bauen (HTML-only, Click-Through)
   — was nicht echt funktioniert, ist sichtbar als "noch nicht live"
3. Phase C im Code bauen, an Backend andocken (~3 Tage)
4. Generation-Pipeline an existierenden Site-Generator andocken (~2 Tage)
5. Übergänge polieren (~2 Tage)
6. Phase 4 Backend-Roadmap (Tools, Push) (~2 Tage)

Gesamt: ~15 Tage, am Ende läuft alles echt.
```

---

## 12. Was wir messen, wenn die Journey läuft

```
Funnel-Metriken (im Dev-Portal sichtbar):

A → B :   Wie viele klicken nach Präsentation auf "Beginnen"?
B → C :   Wie viele kommen zum 2. Termin / loggen sich ein?
C → D :   Wie viele drücken "Ja, bau los"?
D → E :   Wie viele schauen auf die generierte Webseite?
E → F :   Wie viele scannen den QR-Code?
F → G :   Wie viele machen den ersten Tagesausklang?
G → G :   Streak — wie viele bleiben dabei?

Pilot-Marker:
- Mira komplett durch alle 7 Phasen: erfolgreichster Pilot
- Mira hängt bei Phase X: dort haben wir Reibung zu lösen
```

---

## 13. Zielgefühl der ganzen Journey

Mira soll **nicht** denken:

> *„Wow, das war ein komplexer Onboarding-Prozess."*

Sondern:

> *„Schön. Das passt. Ich nehm das mit."*

Sieben Phasen — keine sieben gefühlten Schritte. Ein Bogen.

---

**Spec · 11. Mai 2026 · Hero-Journey · Sieben Phasen · Ein Bogen · Drei Wege zur Umsetzung**

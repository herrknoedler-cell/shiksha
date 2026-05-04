# Krummelus-Pilot — Lessons v1

**Datum:** 4. Mai 2026, ~13:00–13:35
**Trägerin:** Mira Fiel (Tochter, ko-leitend mit Mutter)
**Methode:** Hybrid-Lauf — Founder als SHIKSHA-Sprecher, Audio-Aufnahme, Apple-Transkript
**Status:** v1 nach Erst-Auswertung Audio + Nachgespräch
**Cross-Reference:** `docs/build-packs/SHIKSHA_DIALOG_BUILD_PACK_V2.md` · `docs/WORDING_AND_LANGUAGE.md`

---

## 1. Mira-Persona — wie sie wirklich tickt

### Selbstbild

> *"Ich hasse Unsicherheit. Sicherheit im Alltag gibt mir Struktur."*
>
> *"Ich bin froh, dass ich oft ins Büro komme."*
>
> *"Du musst ständig an alles denken."*

Mira ist **operativ kompetent** und sucht **System statt Dialog**. Sie braucht keine Pädagogik-Beratung von SHIKSHA — sie braucht eine Mit-Arbeiterin für die *Verwaltung*. Ihre Kindergarten-Arbeit selbst beschreibt sie als *"ein bisschen anstrengend, aber okay"*. Die Verwaltung ist Atempause — wenn sie funktioniert.

### Familie-KITA-Konstellation

> *"Wenn ich kein System vorgebe, weil Mama gerade andere Sachen zum tun hat, dann geht es so quasi stehen."*

Krummelus ist eine **Familien-KITA** — Mira (Tochter) + Mama (Mutter, vermutlich Inhaberin / Hauptträgerin). Beide arbeiten zusammen, das System hängt von dieser Konstellation ab. Single-Point-of-Failure: wenn eine ausfällt, steht's still.

→ **Konsequenz:** SHIKSHA muss Multi-Operator-fähig sein. Beide brauchen eigene Zugänge mit klaren Rollen, geteilte Sicht aufs Tagesgeschehen.

---

## 2. Pain-Cluster (priorisiert nach Mira-Häufigkeit)

### 🟥 Pain #1 — Die Zettelei

> *"Die ganze Zertlerei. Überall Papier, überall Zettel, Sucher, überall."*
>
> *"Fünf verschiedene Baustellen in irgendwelchen Ordnern."*
>
> *"Du schiebst einfach viel durch."*

**Kern-Schmerz.** Wenn SHIKSHA das löst, ist alles andere Bonus.

Konkret: Ablagen für Wochen-, Monats-, Jahres-Material. Anwesenheitslisten. Beobachtungen handschriftlich. Portfolios. Formulare zum Ausdrucken. *"Schon mehr"*-haftes Drift.

### 🟥 Pain #2 — System-Inkonsistenz zwischen Mira und Mama

> *"Es funktioniert nur, wenn Mama oder jemand anderes [da ist]."*
>
> *"Da wohnt ja ganz klare Vorgehensweise, weil sonst funktioniert gar nichts und das stresst mich."*

Mira hat ein System, Mama hat ein anderes. Zwischen-den-beiden geht Material verloren.

### 🟥 Pain #3 — Wochenend-Erreichbarkeit

> *"Die hat dreimal am Wochenende angerufen … wir haben nichts, dass die dreimal angerufen hat."*

Eine Mutter hat 3× am Wochenende angerufen, Mira hatte das Handy nicht zur Hand, am Montag stand das Problem da. Mira nennt das *"systemisch dosiert"* — sie hätte gern eine **gefilterte, gesammelte Bereitschafts-Sicht**, kein Klingel-Stress.

### 🟥 Pain #4 — Verloren-gegangene Dokumente

> *"Ohne dass sie einen Zettel vom Jahr 22 nochmal findest."*

Volltext-Suche über alles, was je geschrieben wurde — mit der Sicherheit, dass nichts wegkommt.

### 🟥 Pain #5 — Überblick bei viel Aktivität

> *"Ich gefühlt jeden Tag, weil es so viel ist und weil es momentan viel los ist mit Beobachtungen im Kindergarten und Land-Evaluierungen."*

Wenn parallel viele Sachen laufen, verliert Mira den Überblick. SHIKSHA müsste Filter / Priorisierung anbieten.

---

## 3. Tagesablauf — was wiederholt sich (Miras eigene Liste)

```
✓ Anwesenheits-Check der Kinder
   - sind sie da
   - sind sie entschuldigt
   - sind sie krank
   - Mama/Papa-Wechsel (Sorgerechts-Wechsel)

✓ Schließzeiten / Feiertage tracken

✓ Vorbereitung (Material, Räume)

✓ Portfolio-Pflege

✓ Anwesenheitslisten ablegen

✓ Neue Ausdrucke

✓ Kinderbeobachtungen verschriftlichen

✓ Angebote planen + verschriftlichen

✓ Zettel ablegen (Wochen-, Monats-, Jahres-Ableger)
```

**Das ist das operative Pflichtenheft.** Wenn SHIKSHA jeden dieser Punkte adressiert, spart Mira spürbar Zeit. Backlog-Vorlage.

---

## 4. Architektur-Erkenntnisse aus dem Nachgespräch

### 4.1 Kennenlerngespräch zweiteilen

Mira hat im Nachgespräch klar formuliert:

> *"Schritt 1 — wie jetzt gemacht, allerdings hätte ich es lieber getippt (Chat). Schritt 2 — Erfassung der Daten + Webseite + Daten einrichten."*

**Implikation für Build-Pack v2.0** (kanonisierte Phasen-Architektur — siehe `VERDICHTEN_PHASE_SPEC.md`):

```
Phase 1 — Kennenlernen (Conversational, getippt)
  Themen: Wer bist Du, was tut Euch weh, was wünschst Du Dir
  Format: Chat-Eingabe (Tastatur), nicht Audio-Sprecher
  Dauer: 15-20 Min
  Output: Ein erster "Steckbrief" + offene Themen-Liste
  
  → Kein Druck, nichts wird "fertig" am ersten Tag.

Bridge — Einrichten (zwischen Phase 1 und Phase 2)
  Themen: Mitarbeiter-Daten, Kinder-Daten, Webseite, Subdomain,
           Compliance-Setup
  Format: Geführt, schrittweise, mit Excel-Import-Option
  Dauer: 30-45 Min, gerne über Tage verteilt
  Output: System ist live mit echten Daten
  
  → Keine eigene Phase. Eine praktische Bridge.

Phase 2 — Verdichten (im Alltag, nicht als Termin)
  Themen: Beobachtungen, Tagesausklang, Wochen-Rückblick
  Format: tägliche und wöchentliche Rituale, kein Workshop
  Output: wiederkehrende Situationen werden sichtbar,
          Aussagen werden zu Mustern, erste Klarheit entsteht
```

> **Anmerkung:** Was Mira oben "Schritt 2" nannte (Daten einrichten), ist in der finalen Architektur die **Bridge**, nicht Phase 2. Phase 2 ist *Verdichten* — und beginnt, sobald Mira mit dem System lebt. Die Trennung ist bewusst: Einrichten ist Pflicht-Praktisch, Verdichten ist Atem-Räumig.

**Schlüssel-Insight:** Mira will **getippt**, nicht **Audio**. Audio-Konversation ist Thomas-präferiert (er ist Sprecher-Typ), Mira ist Tipp-Typ. Conversational-First-Pattern aus v2.0 stimmt — aber das **Eingabe-Medium** ist Text, nicht Sprache.

→ **Wording-Codex-Konsequenz:** Persona muss textlich funktionieren. Kein "ich höre Dir zu" als Audio-Geste — sondern "ich lese mit".

### 4.2 PWA-Installation nach Gespräch

> *"Nach dem Kennenlerngespräch, bekommt der Gesprächspartner einen Link und QR-Code um die PWA am Handy zu installieren (Anleitung auf Anfrage)."*

**Konzept:**

```
Ende von Phase 1
       ↓
SHIKSHA: "Schön, dass wir uns kennen. Magst Du mich aufs Handy mitnehmen?"
       ↓
[Link]              [QR-Code]              [Anleitung anzeigen]
       ↓                  ↓                       ↓
Klick öffnet       Scan mit Phone           Schritt-für-Schritt-
SHIKSHA im        öffnet SHIKSHA            Anleitung pro OS
Mobile-Browser    direkt
       ↓
PWA-Install-Prompt:
"Zum Home-Screen hinzufügen"
       ↓
SHIKSHA ist als App installiert
       ↓
Push-Subscribe-Trigger erscheint
"Soll ich Dich erreichen können?"
```

**Implikation:** Subscribe-Trigger im Frontend ist nicht nur Backlog-Item, sondern direkter Bestandteil des Onboarding-Flows. Plus: Eltern-Anleitungs-Texte pro OS (iOS Safari "Teilen → Zum Home-Screen", Android Chrome "Installieren").

### 4.3 Folge-Termin mit Verbindlichkeit

> *"Es wird für den nächsten Tag ein Termin vereinbart (schon ein bisschen Verbindlichkeit einfordern). Zusammenfassung des gestrigen Gesprächs, eventuell Rückfragen."*

**Konzept:**

Am Ende von Phase 1 sagt SHIKSHA:

> *"Magst Du morgen kurz wieder mit mir sprechen? Ich fasse Dir zusammen, was wir besprochen haben — und wenn ich was missverstanden habe, korrigieren wir's."*

Mira bestätigt einen 15-Min-Slot. Am nächsten Tag öffnet sie die PWA → SHIKSHA hat eine vorbereitete Zusammenfassung mit 2-3 Rückfragen. Iterativer Onboarding-Aufbau.

**Implikation:**

- Termin-Vereinbarung als Tool-Call (`schedule_followup_meeting`)
- Zusammenfassung-Generierung am nächsten Tag (Claude API mit Context aus Phase 1)
- Rückfragen-Liste aus den unklaren Stellen des Gesprächs

### 4.4 Tagesritual — Tagesausklang-Modul

> *"Sie kann sich auch gut vorstellen, kurz vor Feierabend ein Ritual von 5-10 Minuten einzuführen, an dem sie an SHIKSHA die Beobachtungen des Tages mitteilt und auf Fragen von SHIKSHA antwortet."*

**Das ist eine eigenständige Modul-Idee.** Verdient eigenen Namen.

**Vorschlag-Name: TAGESAUSKLANG.**

**Konzept:**

```
17:30 (oder konfigurierbar)
       ↓
Push-Notification: "Tagesausklang. 5 Minuten?"
       ↓
Mira öffnet PWA → SHIKSHA fragt:

  "Wie war heute?"
   → Mira tippt frei (oder spricht, wenn sie mag)

  "Welches Kind hat Dich heute überrascht?"
   → Beobachtungs-Eintrag entsteht

  "Was musst Du Dir merken für morgen?"
   → Aufgaben-Eintrag entsteht

  "Hast Du etwas dem Land zu melden?"
   → Audit-Trigger
```

SHIKSHA passt die Fragen kontextuell an:

- Bei viel Aktivität (z.B. Krankmeldung heute): konkretere Folgefragen
- Bei ruhigem Tag: kürzere, leichtere Fragen
- Bei wiederkehrenden Themen: Erinnerung *"Du hattest gestern X erwähnt — gibt's was Neues?"*

**Wert:**

1. **Beobachtungen werden täglich erfasst** — kein "ich schreibe das später ab"-Drift
2. **Habitualisierung** — Mira lernt SHIKSHA als Partnerin kennen, täglich 5-10 Min
3. **Daten-Aktualität** — System ist nie veraltet
4. **Mit-Lernen** — SHIKSHA versteht über Wochen, was wiederkehrt

Das ist die Antwort auf Miras *"ich hasse Unsicherheit"*: ein **ritualisierter Sicherheits-Anker** am Tagesende.

---

## 5. Marken-Stimme aus Mira-Vokabular

Folgende Wörter/Wendungen kommen aus Miras Mund und sollten in den Wording-Codex aufgenommen werden:

| Mira-Wort | Bedeutung | Verwendung in SHIKSHA-Stimme |
|---|---|---|
| **speisen** | eingeben, eintragen | *"Magst Du das einspeisen?"* statt *"Bitte eingeben"* |
| **Ableger** | Ablage | *"Dein Wochen-Ableger ist leer."* |
| **verschriftlichen** | dokumentieren | *"Magst Du das verschriftlichen?"* statt *"dokumentieren"* |
| **durchschieben** | abarbeiten | (in Mira-Beschreibungen — nicht in SHIKSHA-Stimme aktiv nutzen) |
| **die ganze Zettelei** | das Verwaltungs-Chaos | als Kunden-Zitat im Marketing |
| **systemisch dosiert** | proaktiv-strukturiert | als Marken-Versprechen |

**Persona-Konsequenz:** SHIKSHAs Stimme darf **leicht dialektgefärbt** sein, ohne in Vorarlbergerisch zu kippen. Sätze wie *"Magst Du das einspeisen?"* sind Hochdeutsch + Mira-Vokabular = goldene Mitte.

---

## 6. Stimmungs-Bilanz

```
Anfang     leicht skeptisch, abwartend
Mitte      konkret, sachlich, problemorientiert
Ende       interessiert, fragt nach Details
Ende+1     "Cool."  ← Vorarlberger Höchstlob
```

**Wichtigster Indikator:** Mira hat **eigene Wünsche formuliert** (Wochenend-Bereitschaft, Beobachtungen sofort, Tagesausklang-Ritual). Sie hat sich ins Konzept eingedacht — das passiert nur, wenn sie es **glaubt**.

---

## 7. Rohe Pilot-Quotes (für späteres Marketing-Polish)

Sätze, die direkt aus Mira-Mund kommen und marketingfähig sind (mit Zustimmung von Mira):

> *"Ein Programm, was mir die ganze Zettelei und Denkerei abnimmt."*

> *"Die Arbeit generell mit dem Kind ist ein bisschen anstrengend, aber ich bin froh, dass ich oft ins Büro komme."*

> *"Wenn alles so läuft, wie es geplant ist."*

> *"Ich hasse Unsicherheit. Sicherheit im Alltag gibt mir Struktur."*

Drei davon können mit Mira-Einverständnis 1:1 auf shiksha.world/kita als Pilot-Testimonial.

---

## 8. Lessons → Konkrete Aktionen

### Sofort (heute Nachmittag / morgen)

```
□ Backlog-Items aus Sektion 4 ergänzen
□ Wording-Codex um Mira-Vokabular erweitern (siehe Sektion 5)
□ Build-Pack v2.0 → v2.1 Anpassung: zwei-Phasen-Onboarding
```

### Nächste Woche

```
□ Tagesausklang-Modul Build-Pack-Skizze schreiben
□ PWA-Install-Onboarding-Flow konzipieren (Link/QR + Anleitung)
□ Folge-Termin-Vereinbarungs-Logik im Conversational-Flow
□ Wochenend-Bereitschafts-Modus als Mini-Spec
```

### Mittel-Sprint (2-3 Wochen)

```
□ Multi-Operator-Logik (Mira + Mama) als Datenmodell-Erweiterung
□ Volltext-Suche über alle Module
□ Beobachtungen direkt eingeben (Pädagogen-PWA-Erweiterung)
```

### Marketing-Polish (langfristig)

```
□ shiksha.world/kita Sales-Page mit Mira-Zitaten
□ Zwei-Phasen-Onboarding als USP nach außen kommunizieren
   ("Erst zuhören, dann einrichten — kein Termin-Marathon.")
```

---

## 9. Was wir aus diesem Pilot fundamental gelernt haben

### Über die Persona

**Mira will Klarheit, nicht Verkaufsgespräch.** Sie braucht keine pädagogische Theorie, keine Inspiration — sie braucht eine **Verwaltungs-Mitarbeiterin**, die mitlernt. Das verschiebt den Schwerpunkt von "Marken-Inspiration" zu "Operative Entlastung".

### Über das Onboarding

**Conversational-First stimmt — aber Text statt Audio.** Audio ist persönlich, aber zu langsam für Daten-Erfassung. Text ist **schneller und überblickbarer**. SHIKSHA kann Audio später anbieten (für Beobachtungen on-the-go), aber das Onboarding muss tippbar sein.

### Über den Lebenszyklus

**Tagesausklang ist der Schlüssel zur Beziehung.** Onboarding ist einmalig — was zählt, ist der **tägliche 5-10-Min-Kontakt**. Wenn der ritualisiert ist, wird SHIKSHA zur echten Mit-Arbeiterin. Sonst bleibt's eine "manchmal genutzte App".

### Über die Marke

**Mira-Vokabular ist Marken-Asset.** *"Speisen"*, *"Ableger"*, *"verschriftlichen"* sind Worte, die sie selbst nutzt. Wenn SHIKSHA diese Worte aufnimmt, fühlt sich das **nicht nach Marketing**, sondern nach **echter Begegnung** an. Wording-Codex muss dynamisch wachsen mit jedem Pilot.

---

**Krummelus-Lessons v1 · 4. Mai 2026 · Erste Pilotbegegnung mit Mira Fiel · Tagesausklang als Schlüssel-Erkenntnis**

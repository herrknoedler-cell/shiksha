# Wir lernen uns kennen — Krummelus-Kickoff

**Für Thomas + Heidi · Montag, 4. Mai 2026 · ~15-18 Min**

Diese Checkliste ist die *analoge Version* der "Wir lernen uns kennen"-Tour. Sie ersetzt für den Pilot-Start den noch nicht implementierten Wizard. Inhalte und Schritte entsprechen 1:1 dem Build-Pack v1.0 — aus diesem Lauf entstehen die Lessons für die Code-Implementation.

**Was Thomas vorbereitet:**
- Laptop mit shiksha.world / kita.shiksha.world geöffnet
- SSH-Zugang verfügbar (für Subdomain + DB-Eintragungen)
- Heidi sitzt daneben (oder Bildschirm-Sharing)
- Dieses Dokument als Skript

**Was Heidi vorbereitet:**
- Vereinsregisterauszug (für ZVR)
- Steuerbescheid oder Schreiben vom Finanzamt (für Steuernummer)
- Mitarbeiterliste (Excel oder als ausgedruckte Liste — egal)
- Personalausweis (für Identity-Step)
- 30 Min Zeit, einen Kaffee, gute Stimmung

**Tonalität für Thomas:** Lies die Texte in Anführungszeichen so, als würde SHIKSHA sie sagen — warm, persönlich, immer Du. Nicht ablesen wie aus einem Handbuch. Wenn Heidi was nicht versteht, antworte als SHIKSHA, nicht als Thomas.

**Notiz-Spalten ausfüllen während des Laufs.** Die werden Goldwert für Tour v1.1.

---

## Schritt 1 — Willkommen (1 Min)

**Was sagen:**

> *"Hallo Heidi, schön dass Du da bist. Ich bin SHIKSHA — die Plattform, die Krummelus von jetzt an begleitet. Bevor wir loslegen: in den nächsten 15 Minuten lernen wir uns kennen. Ich frag Dich ein paar Sachen, Du fragst mich was Du wissen willst. Wir können jederzeit pausieren — ich merke mir, wo wir waren. Bereit?"*

**Wenn Heidi zögert:** *"Du musst nicht heute alles ausfüllen. Wir machen, was geht. Den Rest später."*

**Notiz Heidi:**
```
Reaktion auf "ich":  ___________________________________

Wirkt's natürlich?:  ___________________________________

Zögert sie?:         ___________________________________
```

---

## Schritt 2 — Wer steht hinter der KITA? (2-3 Min)

**Was sammeln:**

| Feld | Wert |
|---|---|
| Träger-Name (offiziell) | _______________________ |
| Rechtsform | ☐ Verein  ☐ GmbH  ☐ Stiftung  ☐ Sonstiges |
| ZVR-Nummer | _______________________ |
| Firmenbuch-Nummer (FN) | _______________________ (optional) |
| Steuernummer | _______________________ |
| Träger-Adresse | _______________________ |

**Hilfe-Texte (vorlesen wenn Heidi unsicher):**

- ZVR-Nummer: *"Findest Du auf Eurem Vereinsregisterauszug, oben links — eine 6-9-stellige Zahl."*
- FN-Nummer: *"Nur falls Ihr eine GmbH oder ein eingetragener Verein mit Firmenbuch-Eintrag seid. Sonst lass leer."*
- Steuernummer: *"Vom letzten Steuerbescheid oder Brief vom Finanzamt."*

**Wo eintragen (Thomas):** kita.shiksha.world/accounting/ui/kita/dashboard_traegerin → Stammdaten-Card

**Notiz:**
```
Hatte sie alle Unterlagen dabei?:  ___________________________

Welche Begriffe musste ich erklären?:  _______________________

Dauer:  ____ Min
```

---

## Schritt 3 — Wer bist Du? (1-2 Min)

**Was sagen:**

> *"Heidi, jetzt brauche ich kurz Dich selbst. Damit Audit-Reports später Deine Unterschrift tragen können und ich weiß, mit wem ich rede. Personalausweis bitte einscannen — das macht das Identity-Modul automatisch, Du musst nur ein Foto vom Ausweis machen und eines von Dir."*

**Wo eintragen:** Identity-Wizard im Trägerin-Dashboard → Card "Identity"

**Schritte im Wizard:**
1. Ausweis fotografieren (OCR + MRZ-Check läuft automatisch)
2. Selfie machen
3. Bestätigen

**Notiz:**
```
Hat OCR die Daten korrekt erkannt?:  _________________________

Wie lange hat der Wizard gedauert?:  ____ Min

Probleme bei Foto/Selfie?:  __________________________________
```

---

## Schritt 4 — Wie heißt die KITA? (1 Min)

**Was sammeln:**

| Feld | Wert |
|---|---|
| KITA-Name (öffentlich) | Krummelus |
| Untertitel | _______________________ |
| Slogan / Anspruch | _______________________ |

**Vorschlag falls Heidi keine Idee hat:**
> *"Wie würdest Du Krummelus jemand beschreiben, der Eure KITA noch nicht kennt? Drei Worte reichen."*

**Wo eintragen:** Marketing-Setup-Card im Dashboard

**Notiz:**
```
Slogan-Vorschlag von Heidi:  ________________________________
```

---

## Schritt 5 — Eure Adresse im Internet (1 Min)

**Was sagen:**

> *"Ich richte Euch eine Webseite ein. Vorschlag: krummelus.shiksha.world — das wird Eure offizielle Online-Adresse. Eltern können da nachlesen, was Euch ausmacht. Du kannst später Eure eigene Domain dranhängen, wenn Ihr eine habt — z.B. krummelus.at."*

**Was eintragen:**

| Feld | Wert |
|---|---|
| Subdomain | krummelus |
| → ergibt | https://krummelus.shiksha.world |

**Was Thomas serverseitig macht (während Heidi Pause hat):**

```bash
# DNS A-Record bei united-domains setzen für *.shiksha.world
# (oder spezifisch krummelus → 88.99.174.186)

# nginx-server-Block:
ssh root@88.99.174.186
cat > /etc/nginx/sites-available/krummelus.shiksha.world <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name krummelus.shiksha.world;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Org-Slug "krummelus";
    }
}
EOF
ln -sf /etc/nginx/sites-available/krummelus.shiksha.world /etc/nginx/sites-enabled/
certbot --nginx -d krummelus.shiksha.world --non-interactive --agree-tos \
    --email herrknoedler@gmail.com --redirect
nginx -t && systemctl reload nginx
```

**Notiz:**
```
Hat Heidi Vorschläge zur Domain?:  __________________________

Bekommen sie eine eigene .at-Domain?:  ☐ ja  ☐ nein  ☐ später
```

---

## Schritt 6 — Wo ist die KITA? (1-2 Min)

**Was sammeln (pro Standort):**

| Feld | Standort 1 |
|---|---|
| Name (intern) | Hauptgebäude |
| Adresse + PLZ + Ort | _______________________ |
| Telefon | _______________________ |
| Email | _______________________ |

Mehrere Standorte? Heidi-Kontext: *vermutlich nur einer*. Falls doch mehr, [+ Standort hinzufügen].

**Wo eintragen:** Personen-Stammdaten-Modul → Standorte

---

## Schritt 7 — Eure Gruppen (1-2 Min)

**Was sammeln:**

| Gruppe | Alter | Plätze | Räume |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

**Frage zur Gruppen-Struktur:** *"Wie nennt Ihr Eure Gruppen? Bären, Igel, Marienkäfer? Sind die altershomogen oder gemischt?"*

**Wo eintragen:** Gruppen-Section im Stammdaten-Modul

**Notiz:**
```
Krummelus-Gruppen-Namen:  ___________________________________

Altersstruktur:  _________________________________________________

Anzahl Plätze gesamt:  ____
```

---

## Schritt 8 — Wer arbeitet bei Euch? (3-5 Min)

**Was sagen:**

> *"Hast Du eine Mitarbeiter-Liste? Excel oder CSV ist am einfachsten — ich erkenne automatisch Spalten wie Name, Vorname, Stellenprozent, Funktion. Wenn Du keine Datei hast, machen wir's einzeln, das geht auch. Lieber später? Wir können das auch nach unserem Termin nachholen."*

**Drei Wege:**
- **A** — Excel-Import: Heidi gibt Datei, Thomas lädt hoch
- **B** — Manuell: Pro Person ein neuer Eintrag im Stammdaten-Modul
- **C** — Skip: Kommt später

**Spalten, die der Importer erkennt:**

| Spalte | Pflicht? | Beispiel |
|---|---|---|
| Name | ✓ | Müller |
| Vorname | ✓ | Anna |
| Stellenprozent | (empfohlen) | 80 |
| Funktion | (empfohlen) | Pädagogin |
| Eintrittsdatum | optional | 2024-09-01 |
| Email | optional | anna@krummelus.at |
| Telefon | optional | +43 664 ... |
| Gruppe | optional | Bären |

**Notiz:**
```
Welcher Weg?:  ☐ Excel  ☐ Manuell  ☐ Skip

Anzahl Mitarbeiter:  ____

Probleme beim Import (falls A):  ____________________________

Wenn A: welche Spalten waren in Heidis Excel, die ich nicht
        automatisch erkannt habe?

  ____________________________________________________________
```

---

## Schritt 9 — Wer wird betreut? (3-5 Min, oder Skip)

**Was sagen:**

> *"Kinder kannst Du jetzt importieren oder später. Wenn Anmeldungen über Eltern reinkommen, tragen sie ihre Kinder ja ohnehin selbst ein. Du sparst Dir die Mehrfacharbeit, wenn Du jetzt skipst."*

**Empfehlung:** *Skip*, außer Heidi hat eine fertige Liste, die sie loswerden will.

**Wenn Import:**

| Spalte | Pflicht? |
|---|---|
| Name, Vorname | ✓ |
| Geburtsdatum | (empfohlen) |
| Eltern-Email | (empfohlen) |
| Adresse | optional |
| Gruppe (zugeordnet) | optional |
| Stunden / Tage / Woche | optional |

**Notiz:**
```
Heidis Wahl:  ☐ Excel  ☐ Manuell  ☐ Skip (empfohlen)

Anzahl Kinder (falls bekannt):  ____
```

---

## Schritt 10 — Compliance-Setup (1-2 Min)

**Was sagen:**

> *"Welches Bundesland? Bei Vorarlberg lade ich Euch automatisch die KGG-Förderstaffel — Tagsätze, Personalschlüssel, Audit-Punkte. Ab dann schau ich für Euch mit, ob Ihr beim Soll bleibt. Wenn was knapp wird, melde ich mich."*

**Was eintragen:**

| Feld | Wert |
|---|---|
| Bundesland | Vorarlberg |
| (Auto-Lookup) | KGG-Förderstaffel 2023 |

**Was passiert automatisch:**
- ST%-Soll-Berechnung pro Gruppe
- Audit-Punkte aus Vorarlberger KGG
- Live-Monitoring-Cron läuft täglich

**Wo eintragen:** Compliance-Card im Dashboard

**Notiz:**
```
ST%-Stand am ersten Tag:  ____% (sollte irgendwas zwischen 70-100 sein)

Audit-Punkte initial:  ____ offen

Heidis Reaktion auf Compliance-Anzeige:  ____________________
```

---

## Schritt 11 — Eure Webseite (3-5 Min)

**Was sagen:**

> *"Magst Du Eure Online-Visitenkarte jetzt anlegen? Ich texte Dir was vor — basierend auf dem was Du mir bisher erzählt hast, plus Holi-Bildern, die zu KITAs passen. Du verfeinerst, dann ist sie online."*

**Wo gehen:** Marketing-Builder → "Neue Site für krummelus"

**Was passiert:**
1. KI-getextet (Claude API) auf Basis der Daten aus Schritt 4 + 6 + 7
2. Bilder vorgeschlagen aus dem Pool (oder hochladen)
3. Heidi liest, korrigiert, bestätigt
4. "Veröffentlichen" → live unter https://krummelus.shiksha.world

**Notiz:**
```
KI-Texte gut?:  _______________________________

Was hat Heidi geändert?:  _____________________

War sie überrascht/begeistert/skeptisch?:  ____________________
```

---

## Schritt 12 — Bilder aus dem Pool (2-3 Min)

**Was sagen:**

> *"Ich habe Bilder vorbereitet, die zu KITAs passen — Holi-Atmosphären, Frühling, lachende Kinder. Such Dir aus, was zur Stimmung von Krummelus passt."*

**Status (3. Mai 2026):** Bilder-Pool ist noch nicht live (Phase A geplant). Provisorium für morgen: Thomas zeigt Heidi 5-10 Beispielbilder lokal und sagt, *"sobald der Pool steht, kannst Du das selbst aussuchen."*

**Notiz:**
```
Welche Bildstimmung gefällt Heidi?:  ________________________

Wünsche an den Pool (Tags, Themen)?:  _______________________
```

---

## Schritt 13 — Push-Benachrichtigungen (1 Min)

**Was sagen:**

> *"Eltern können Erinnerungen direkt im Browser bekommen — kein App-Store, kein Login-Marathon. Sollen wir das aktivieren? Was genau wann gesendet wird, kannst Du später anpassen."*

**Status:** Push-Modul ist gebaut, aber VAPID-Keys fehlen noch (im SHIKSHA-Backlog).

**Aktion morgen:**
- VAPID-Keys generieren (5 Min Server-Arbeit)
- Subscribe-Trigger in Pädagogen-PWA aktivieren

**Notiz:**
```
VAPID-Generation gemacht?:  ☐ ja  ☐ nein, später

Test-Notification gesendet?:  ☐ ja  ☐ nein
```

---

## Schritt 14 — Pädagog:innen anbinden (2 Min)

**Was sagen:**

> *"Anna und die anderen brauchen Zugang zur Pädagogen-PWA. Sie installieren sich das in 30 Sekunden auf ihrem Handy — kein App-Store. Ich erstelle Dir einen QR-Code, den Du im Pausenraum aushängen kannst."*

**Aktion:**
- Einladungs-Link generieren mit QR-Code
- Drucken oder per Mail an Mitarbeiter:innen

**Notiz:**
```
Anzahl Mitarbeiter, die PWA installieren:  ____

Probleme beim Installieren (falls heute getestet):  ___________

Aushang im Pausenraum?:  ☐ gemacht  ☐ kommt
```

---

## Schritt 15 — Eltern anbinden (2 Min)

**Was sagen:**

> *"Eltern bekommen Anmeldelinks per Email. Ich habe Dir eine erste Begrüßungs-Email vorbereitet — Du musst nur auf Senden klicken, wenn Du fertig bist."*

**Email-Vorschau zeigen.** Heidi liest. Wenn ok: senden. Wenn nicht: gemeinsam anpassen.

**Aktion:** Erste Eltern-Email versenden

**Notiz:**
```
Wie viele Eltern bekommen Email?:  ____

Email-Text 1:1 übernommen?:  ☐ ja  ☐ Heidi hat geändert: _______
```

---

## Schritt 16 — Wir kennen uns (2 Min)

**Was sagen (langsam, mit Pausen):**

> *"Heidi, wir kennen uns jetzt.*
>
> *Wenn Du Fragen zu Stellenprozent hast, frag mich.*
>
> *Wenn ein Kind krank wird und Eltern Bescheid geben, sage ich Dir Bescheid.*
>
> *Wenn ein Audit ansteht, sehe ich es kommen.*
>
> *Ich bin Eure neue Fachkraft, wenn es um KITA-Verwaltung geht."*

**Demonstrieren:**
- Dashboard mit Greeting zeigen ("Schönen Mittag · Montag im Frühling, Heidi.")
- Cards anordnen (Drag & Drop)
- Pinker Bubble unten rechts (Chat — auch wenn der noch nicht implementiert ist, *erwähnen*: *"Hier wirst Du mich bald jederzeit erreichen können — Chat-Modul kommt in den nächsten Wochen."*)

**Notiz:**
```
Heidi-Reaktion auf Versprechen:  ___________________________

Was findet sie unklar / überfordernd?:  _____________________

Was findet sie besonders gut?:  ____________________________

Was möchte sie als Allernächstes tun?:  _____________________
```

---

## Nach dem Lauf — Lessons-Sammlung (für Tour v1.1)

**5-10 Min mit Heidi nachbesprechen:**

```
1. War 15-18 Min eine angemessene Dauer?  ____________________

2. Welcher Schritt war zu lang?  ___________________________

3. Welcher Schritt war zu kurz / zu wenig erklärt?  __________

4. Welcher Begriff war neu für Dich?  _______________________

5. Was hättest Du Dir an SHIKSHA-Stelle anders gewünscht?
   _________________________________________________________

6. Möchtest Du nochmal durchgehen, oder reicht Dir der erste Lauf?
   _________________________________________________________

7. Was ist Dein erster Eindruck — Software oder Mit-Arbeiterin?
   _________________________________________________________
```

---

## Für Thomas: Auswertung am Abend

```
GESAMT-DAUER tatsächlich:  ____ Min  (vs. geplant 15-18)

SKIPS:  Schritt(e) ____________________________________

NACHARBEIT (was muss noch passieren):
  - _________________________________________________________
  - _________________________________________________________

LESSONS für Tour v1.1:
  - _________________________________________________________
  - _________________________________________________________

STIMMUNG: ☐ begeistert  ☐ ruhig-zufrieden  ☐ skeptisch  ☐ überfordert
```

**Diese Lessons fließen in:**
- `INTRO_AND_CHAT_MODULE_BUILD_PACK_V1.md` → v1.1 Update
- `SHIKSHA_BACKLOG.md` → konkrete Issues unter "Pilot-Aktivierung"
- Tour-Sequenz (Schritt-Reihenfolge, Hilfe-Texte, Skip-Defaults)

---

**Viel Erfolg morgen, Thomas. Die wichtigste Erkenntnis kommt nicht aus dem, was glatt läuft — sondern aus dem, was hakt. Schreib mit. SHIKSHA wird besser durch Heidi.**

# SHIKSHA · KITA · Excel-Vorlage für die Pilot-Erfassung

**Adressat:** Pilot-KITA-Leitung, Dornbirn
**Zweck:** Strukturierte Erfassung der letzten 12-60 Monate für ein erstes Compliance-Audit
**Format:** EINE Excel-Datei mit den unten genannten Tabs

---

## Vorgehen

1. Eine neue Excel-Datei anlegen, **5 Tabs** (Sheets)
2. Spaltennamen wie unten — Reihenfolge egal, Schreibweise egal (das System ist tolerant)
3. Die letzten 12 Monate sind das Pflichtprogramm, weitere 48 Monate optional
4. **Hochladen über** `https://shiksha.tun.zone/kita/ui/dashboard` → Tab "Excel-Import"

---

## Tab 1: **Mitarbeiter** (Pflicht)

Alle pädagogischen Mitarbeiter:innen — Reinigungskräfte und Köch:innen NICHT mit aufnehmen, die zählen separat.

| Name | Qualifikation | BAfEP | Eintritt | Austritt | Notizen |
|---|---|---|---|---|---|
| Andrea Müller | Pädagoge | ✓ | 2020-08-01 | | |
| Lukas Bauer | Assistent | | 2022-09-01 | | Quereinsteiger, 3J Erfahrung |
| Eva Hofer | Helfer | | 2023-01-15 | 2024-06-30 | |
| Julia Sauter | Pädagoge | ✓ | 2024-09-01 | | Leitung Marienkäfer |

**Zulässige Werte für Qualifikation:**
- `Pädagoge` (BAfEP-Absolvent:in oder Quereinstieg mit 2+ Jahren Erfahrung)
- `Assistent` (KIBI-Assistenz)
- `Helfer` (Betreuungskraft)
- `Leitung` (mit Leitungs-Funktion)
- `Springer` (nicht fest zugeordnet)

---

## Tab 2: **Verträge** (Pflicht — Stellen%-Historie)

**Wichtig:** Pro Mitarbeiter:in EINE Zeile pro Vertrags-Phase. Wenn jemand 100% → 75% reduziert, sind das **zwei Zeilen** (alter Vertrag schließt mit `Gültig bis`, neuer beginnt).

| Name | Gültig ab | Gültig bis | Stellen% | Wochenstunden | Direkte Arbeit (h) |
|---|---|---|---|---|---|
| Andrea Müller | 2020-08-01 | 2022-07-31 | 100 | 38.5 | 33 |
| Andrea Müller | 2022-08-01 | | 75 | 28.88 | 24 |
| Lukas Bauer | 2022-09-01 | | 100 | 38.5 | 33 |

**„Direkte Arbeit (h)"** = Stunden am Kind pro Woche (förderrelevant). Vorbereitung NICHT mitzählen — die ist im Stellenprozent eingerechnet.

---

## Tab 3: **Belegung** (Pflicht — Kinder pro Gruppe pro Monat)

Ein Aggregat pro Gruppe + Monat reicht (Tagesgenauigkeit nur wenn vorhanden).

| Gruppe | Gruppentyp | Monat | Kinder Ø | Kinder max | Ø Stunden pro Kind/Wo |
|---|---|---|---|---|---|
| Marienkäfer Krippe | Kleinkindgruppe | 2024-09 | 11.5 | 12 | 38.5 |
| Marienkäfer Krippe | Kleinkindgruppe | 2024-10 | 12.0 | 12 | 39.0 |
| Sonnenkinder Kiga | Kindergarten | 2024-09 | 22.5 | 25 | 42.0 |

**Zulässige Gruppentypen:**
- `Kleinkindgruppe` (0-3 Jahre, max 12)
- `Kindergarten` (3-6 Jahre, max 25)
- `Hort` (6-14 Jahre, max 30)

---

## Tab 4: **Dienstplan** (Pflicht — Wochen-Aggregat reicht)

Einfachste Form: **eine Zeile pro Mitarbeiter pro Woche pro Gruppe**.

| Name | Gruppe | KW | Geplante h | Ist h | Abwesenheit |
|---|---|---|---|---|---|
| Andrea Müller | Marienkäfer Krippe | 2024-W37 | 38.5 | 38.5 | |
| Andrea Müller | Marienkäfer Krippe | 2024-W38 | 38.5 | 15.0 | krank |
| Lukas Bauer | Marienkäfer Krippe | 2024-W37 | 38.5 | 38.5 | |
| Lukas Bauer | Sonnenkinder Kiga | 2024-W37 | — | — | (zweite Gruppe) |

**KW-Format:** `2024-W37` (ISO 8601) oder `KW37/2024` — beides funktioniert.

**Falls Du statt KW ein Datum hast** (z.B. der 9. September): auch ok, ich verarbeite das.

---

## Tab 5: **Krankheit** (Optional — wenn nicht im Dienstplan erfasst)

Falls Krankheits-Tage separat geführt sind:

| Name | Krank von | Krank bis | Grund | Vertretung? | Vertretung Name |
|---|---|---|---|---|---|
| Andrea Müller | 2024-09-12 | 2024-09-13 | krank | nein | |
| Lukas Bauer | 2024-10-22 | 2024-10-25 | krank | ja | Eva Hofer |

---

## Tab 6: **Förderbescheid** (sehr wichtig — wenn vorhanden)

Falls die Tagsätze des Förderers bekannt sind:

| Förderzeitraum von | Förderzeitraum bis | Gruppentyp | Tagessatz | Monatssatz |
|---|---|---|---|---|
| 2024-09-01 | 2025-08-31 | Kleinkindgruppe | 18.50 | 380 |
| 2024-09-01 | 2025-08-31 | Kindergarten | 11.20 | 235 |

→ **Diese Werte ersetzen die voreingestellten Schätzwerte!** 1:1 abschreiben aus dem Bescheid.

---

## Tipps für die Datenerfassung

**Wenn die Daten bereits in einem Programm sind** (KIBE-Manager, KITA-Plus, MS Outlook, Excel-Listen):
- → Export auf Excel nutzen (alle gängigen Programme können das)
- Auch wenn die Spalten anders heißen, bekommt das System es heuristisch hin

**Wenn nur Papier-Dienstpläne existieren:**
- Vorrang: **letzte 12 Monate**
- Nur Wochen-Aggregat (Stunden pro Mitarbeiter pro Woche), keine Tagesgenauigkeit nötig
- Ein einziger Tag manuell-erfasst ist besser als gar nichts

**Wenn Du unsicher bist:**
- Lade die Datei einfach hoch — der Importer zeigt, was er erkannt hat. Lücken kannst Du im Dashboard nachpflegen.

---

## Was passiert nach dem Upload

1. Das System erkennt heuristisch, welcher Sheet was enthält
2. Du siehst sofort: "Mitarbeiter: 12 importiert, Verträge: 18, Belegung: 24 Monate, Dienstplan: 4.832 Zeilen"
3. Tab "Audit (Monat)" zeigt den aktuellen Monat
4. Tab "Audit (Jahr)" zeigt 12 Monate als Heatmap (grün/gelb/rot)
5. Button "60 Monate" macht das Rückwärts-Audit für 5 Jahre
6. **Konkret pro Tag mit Lücke:** Was hat gefehlt, wieviel Euro Risiko, was wäre die Lösung gewesen

---

## Datenschutz

- **Kinder werden anonymisiert** (`child_anon_id` ist eine technische ID, der Name wird NICHT gespeichert)
- Mitarbeiter:innen-Namen werden gespeichert (für Wiederfindung), aber nicht weitergegeben
- Daten liegen auf dem SHIKSHA-Server (Hetzner Deutschland, DSGVO-konform)
- Jederzeit komplett löschbar via Lösch-Button

---

## Kontakt bei Fragen

Thomas Knödler — herrknoedler@gmail.com
Stand: 28.04.2026

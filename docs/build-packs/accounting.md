# SHIKSHA — ACCOUNTING MODUL BUILD PACK V1

**Stand:** 25. April 2026
**Aufbaut auf:** SHIKSHA V4 (`accounting` als bestehendes Modul, `documents`-Tabelle existiert), document.module V1.2 + V2-Erweiterung, compression.py
**Zweck:** PDF-Rechnungen hochladen, verwalten, mit Bank-Buchungen verknüpfen — exakt für Lunchbox Gastro und alle Pilot-Partner einsetzbar.

---

## 1. STATUS IN EINEM SATZ

`accounting` ist das SHIKSHA-Modul, das offene Posten in beide Richtungen führt — PDF-Eingangsrechnungen + eigene Ausgangsrechnungen werden per Foto/Upload erfasst, Bank-Statements werden importiert, und SHIKSHA schlägt Matches vor (review_required), aus denen ein vollständiges Forderungs-/Verbindlichkeits-Bild entsteht.

---

## 2. MODUL-PROFIL

```json
{
  "module": "accounting",
  "version": "1.0.0",
  "scope": "cross-edition",
  "applicable_editions": ["business.shiksha", "schule.shiksha", "camping.shiksha", "club.shiksha"],
  "is_phase_1_required": true,
  "depends_on": [
    "documents",
    "customers",
    "document.module V1.2",
    "document.module V2 extensions"
  ],
  "policies": [
    {
      "key": "accounting.no_auto_match",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Auch bei Confidence > 0.95 braucht ein Match Operator-Bestätigung."
    },
    {
      "key": "accounting.no_auto_dunning",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Mahnungen werden vorgeschlagen, nie automatisch erzeugt."
    },
    {
      "key": "accounting.iban_strict_validation",
      "level": "warn",
      "scope": "Gate 1 — Intake",
      "rationale": "IBAN muss strukturell valide sein (V4-Validator), sonst review_required."
    },
    {
      "key": "accounting.duplicate_invoice_block",
      "level": "warn",
      "scope": "Gate 1 — Intake",
      "rationale": "Zweimal dieselbe Rechnungsnummer derselben Entity → Operator-Check."
    },
    {
      "key": "accounting.partial_payment_explicit",
      "level": "warn",
      "scope": "Gate 4 — Learning",
      "rationale": "Teil-Zahlungen werden nie als 'bezahlt' interpretiert — bleiben offen mit Restbetrag."
    },
    {
      "key": "accounting.aufbewahrung_7_jahre",
      "level": "block",
      "scope": "Gate 4 — Learning",
      "rationale": "§ 132 BAO Österreich / § 257 HGB Deutschland — Rechnungsdaten dürfen nicht gelöscht werden."
    }
  ],
  "review_required_default": true
}
```

---

## 3. WORKFLOW (END-TO-END)

```
PDF/Foto upload                Bank-Statement-Import
       │                                │
       ▼                                ▼
document.module V1.2/V2          bank_statement_parser
(OCR + Klassifikation)           (CSV/CAMT.053/MT940)
       │                                │
       ▼                                ▼
documents-Tabelle           bank_transactions-Tabelle
(invoice/dunning erkannt)     (mit IBAN, Betrag, Verwendungszweck)
       │                                │
       └──────────┬─────────────────────┘
                  ▼
          MATCHING-ENGINE
   (Score-basiert: IBAN+Betrag+Ref+Datum)
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    Score≥85  Score 50-85   Score<50
   "Soll ich  "Vermutlich   "Für wen ist
    matchen?"  X — passt?"   das?"
        │         │           │
        └─────────┴───────────┘
                  ▼
          OPERATOR ENTSCHEIDET
          (review_required = true)
                  │
                  ▼
          payment_matches-Tabelle
          (gebucht, mit Audit-Spur)
                  │
                  ▼
        invoice_status_history
        (open → paid → archived)
```

---

## 4. DATENBANK-ERWEITERUNGEN

Erweitert die V4-Tabellen `documents`, `customers` und `document_links` um vier neue Tabellen.

### Übersicht

| Tabelle | Zweck |
|---|---|
| `bank_transactions` | importierte Bank-Buchungen (Eingang/Ausgang) |
| `statement_imports` | Audit-Spur jedes Import-Vorgangs |
| `payment_matches` | bestätigte Zuordnungen Bank-Buchung ↔ Rechnung |
| `invoice_status_history` | Lebens-Lauf jeder Rechnung (open → mahnung → paid → archiviert) |

Vollständige SQL siehe `server/accounting_db_migration.sql`.

---

## 5. MATCHING-ALGORITHMUS

Score-basiert, **deterministisch**, in Python-Code reproduzierbar (kein ML in V1).

### Score-Komponenten

| Kriterium | Punkte | Bedingung |
|---|---:|---|
| IBAN-Match exakt | 40 | `customer.iban == bank_transaction.counterparty_iban` |
| Betrag-Match exakt | 30 | `abs(invoice.amount - tx.amount) < 0.01 €` |
| Betrag-Match ≤ 1 % Toleranz | 20 | falls nicht exakt |
| Verwendungszweck enthält Rechnungs-Nr. | 20 | `invoice.invoice_number in tx.purpose` |
| Verwendungszweck enthält Kunden-Name | 10 | (zusätzlich oder statt Rechnungs-Nr.) |
| Datum-Plausibilität | 10 | `tx.value_date - invoice.invoice_date` ∈ [0, 90] Tage |
| Datum-Strafe | -10 | falls Datum ausserhalb Fenster |

### Score-Schwellen

| Score | Sprache | Operator-Aufwand |
|---|---|---|
| ≥ 90 | „Soll ich Eurogast-Buchung der Rechnung 1142 zuordnen?" | 1 Klick: Ja/Nein |
| 70–89 | „Vermutlich Eurogast — passt das?" | Operator prüft, bestätigt |
| 40–69 | „Drei Kandidaten für diese Buchung. Welcher?" | Operator wählt aus Liste |
| < 40 | „Für wen ist das?" | Manueller Match |
| 0 (alle Felder fehlen) | „Konnten wir nicht zuordnen — eigene Verwendung?" | Manuell oder ignorieren |

**Confidence in Sprache, nicht Prozent (V4-Prinzip 14):** keine Operator-UI zeigt jemals Score-Zahlen.

---

## 6. SPRACHE — ACCOUNTING-VOKABULAR

```yaml
accounting.invoice.uploaded:
  flow:    "Rechnung verstanden"
  action:  "Stimmen die Felder?"
  alert:   "—"

accounting.invoice.duplicate_warning:
  flow:    "Diese Rechnung kennen wir"
  action:  "Trotzdem speichern?"
  alert:   "—"

accounting.invoice.iban_invalid:
  flow:    "IBAN unsicher"
  action:  "IBAN korrigieren?"
  alert:   "—"

accounting.match.high_confidence:
  flow:    "Match gefunden"
  action:  "Soll ich {entity} der Rechnung zuordnen?"
  alert:   "—"

accounting.match.medium_confidence:
  flow:    "Wahrscheinlicher Match"
  action:  "Vermutlich {entity}. Stimmt das?"
  alert:   "—"

accounting.match.low_confidence:
  flow:    "Unklar"
  action:  "Für wen ist diese Buchung?"
  alert:   "—"

accounting.match.no_candidate:
  flow:    "Keine Rechnung gefunden"
  action:  "Eigene Verwendung oder ignorieren?"
  alert:   "—"

accounting.invoice.partial_payment:
  flow:    "Teilzahlung — {amount}€ bleibt offen"
  action:  "Restbetrag nachfordern?"
  alert:   "—"

accounting.invoice.overdue:
  flow:    "{invoice} {days} Tage überfällig"
  action:  "Mahnstufe 1 vorbereiten?"
  alert:   "{invoice} stark überfällig"

accounting.invoice.partial_match_amount_off:
  flow:    "Betrag passt nicht ganz"
  action:  "{difference}€ Differenz — Skonto oder Tippfehler?"
  alert:   "—"

accounting.invoice.aged_no_match:
  flow:    "Keine Bewegung"
  action:  "Mit {entity} nachhaken?"
  alert:   "—"
```

---

## 7. RECHNUNGS-LIFECYCLE

```
open (just uploaded)
   │
   ├── matched (Bank-Buchung gefunden) → paid
   │
   ├── partially_matched (Teil-Zahlung) → bleibt open mit Restbetrag
   │       │
   │       └── matched (Restzahlung kommt) → paid
   │
   ├── due_date_passed
   │       │
   │       └── reminder_due → reminder_1_sent → reminder_2_sent → ...
   │
   ├── written_off (manuell vom Operator markiert)
   │
   └── disputed (manuell, mit Notiz)

Status-Übergänge:
- Alle Übergänge vom Operator bestätigt
- invoice_status_history dokumentiert jede Änderung
- DSGVO/BAO/HGB: Rechnungsdaten bleiben 7 Jahre, auch bei written_off
```

---

## 8. PDF-UPLOAD-WORKFLOW

### Eingangsrechnung (z. B. Eurogast-Rechnung an Lunchbox)

1. Drag&Drop / Datei wählen
2. document.module läuft → Klassifikation `invoice`
3. Felder erkannt: customer_name, invoice_number, amount_total, due_date, IBAN, ...
4. Operator sieht Result-Screen mit erkannten Feldern + Confidence in Sprache
5. Klick „Passt" → Eintrag in `documents` + `customers`-Match (oder neue Entity)
6. Status: `open`
7. Sobald Bank-Statement importiert wird, beginnt Matching automatisch

### Eigene Ausgangsrechnung

Hier ist die Lage anders: SHIKSHA generiert (V1) keine eigenen Rechnungen — das macht typischerweise die externe Buchhaltung oder Software wie sevDesk/billbee. Stattdessen:

1. Rechnung wird extern erstellt
2. PDF-Kopie wird in SHIKSHA hochgeladen
3. document.module erkennt: Du als Empfänger oder Absender?
4. Wenn Absender = Lunchbox/Studio → eigene Rechnung
5. Status: `open` (warten auf Zahlung)
6. Bank-Eingang matcht automatisch via Matching-Engine

**V2-Vision (nicht jetzt):** SHIKSHA selbst erstellt Rechnungen aus Reservation/Enrollment/etc.

---

## 9. BANK-IMPORT-WORKFLOW

### Unterstützte Formate (V1)

| Format | Quelle | Status V1 |
|---|---|---|
| **CSV (generisch)** | Manuell exportiert aus Online-Banking | ✅ implementiert |
| **CAMT.053** | SEPA-Standard XML, alle DACH-Banken | ✅ implementiert |
| **MT940** | SWIFT-Standard, ältere Banken | ✅ implementiert |
| Bank-API direkt | FinTS / PSD2 / Banking-APIs | später (V2) |

### Bank-Profile vorgemerkt

| Bank | IBAN-Prefix | Standard-Format | Sonderlogik |
|---|---|---|---|
| Hypo Vorarlberg | AT...58 | CSV / CAMT.053 | Verwendungszweck oft mit `R-XXXX` |
| Sparkasse Berchtesgadener Land | DE...71 | CAMT.053 | Standard |
| Erste Bank Wien | AT...20 | CSV / CAMT.053 | Standard |
| Raiffeisen-Landesbank Tirol | AT...36 | CAMT.053 | Standard |
| Nord-Ostsee Sparkasse | DE...21 | CAMT.053 | Standard |

### Import-Lauf

1. Operator wählt CSV/XML
2. Parser erkennt Format, parst Buchungen
3. Vorschau-Liste (alle Buchungen, neu vs. duplikat erkannt via `bank_reference + value_date + amount`)
4. Operator bestätigt Import
5. Buchungen landen in `bank_transactions`
6. Matching-Engine läuft automatisch über alle offenen Rechnungen
7. Match-Vorschläge erscheinen im UI

---

## 10. AUSWERTUNGEN

### Operator-Sicht „Heute"

**Sprachfähige Tageszusammenfassung:**

> *"Eurogast-Eingang 106,40€ — passt zur Rechnung 4421. VLV 75,22€ ausgegangen — VLV-Mahnung beglichen. Eine Buchung 47,80€ konnten wir nicht zuordnen."*

### Drilldowns

- **Offene Posten Eingang** (Sie schulden uns) — sortiert nach Alter
- **Offene Posten Ausgang** (Wir schulden) — sortiert nach Fälligkeit
- **Heute eingegangen / ausgegangen** — Bank-Bewegung des Tages
- **Mahnstufen-Trichter** — wie viele in Mahnung 1, 2, 3
- **Top-Schuldner** — wer hat am längsten am meisten offen
- **Verlässlichkeits-Pattern** — wer zahlt immer pünktlich (positiv-Pattern)

---

## 11. INTEGRATION MIT EDITION-ORCHESTRATOREN

Der Accounting-Modul ist Cross-Edition. Edition-Orchestratoren (SCHULE, CAMPING, CLUB) lesen Accounting-Signale und integrieren sie in ihren Tages-State.

**Beispiele:**

- SCHULE: `package_template`-Verkauf → `invoice` → SHIKSHA-Sprache: „Anna hat 10er-Karte gekauft, 180€ — Rechnung erzeugt, wartet auf Bank-Eingang"
- CAMPING: `reservation.deposit_paid = false` → Rechnung overdue → Edition-Signal `camping.reservation.payment_overdue`
- CLUB: `membership.payment_late` ist genau der Cross-Edition-Bridge zu Accounting

---

## 12. API-ENDPOINTS

```
ACCOUNTING MODUL
================
POST   /accounting/invoices/upload       — PDF/Foto hochladen + analysieren
GET    /accounting/invoices              — Liste mit Filtern (open/paid/overdue/...)
GET    /accounting/invoices/{id}         — Detail mit Status-History
PATCH  /accounting/invoices/{id}/status  — Status manuell setzen (write-off, dispute)

POST   /accounting/statements/upload     — Bank-Statement (CSV/CAMT.053/MT940)
GET    /accounting/statements            — Import-Historie
GET    /accounting/statements/{id}       — Detail eines Imports

GET    /accounting/transactions          — Bank-Buchungen, filterbar
POST   /accounting/transactions/{id}/match  — Manueller Match
DELETE /accounting/transactions/{id}/match  — Match auflösen

POST   /accounting/match/run             — Matching-Engine manuell ausführen
GET    /accounting/match/proposals       — offene Match-Vorschläge
POST   /accounting/match/proposals/{id}/accept   — Vorschlag annehmen
POST   /accounting/match/proposals/{id}/reject   — Vorschlag verwerfen

GET    /accounting/state                 — Sprachfähige Übersicht
GET    /accounting/aging                 — Offene Posten nach Alter
GET    /accounting/dunning/candidates    — Vorschlag für Mahnungen (review_required)
```

---

## 13. DEPLOY-ANLEITUNG

```bash
# 1. Code hochladen
scp -i ~/.ssh/shiksha_key \
    accounting/server/accounting_db_migration.sql \
    accounting/server/accounting_models.py \
    accounting/server/accounting_orchestrator.py \
    accounting/server/bank_statement_parser.py \
    root@88.99.174.186:/opt/shiksha/

# 2. DB-Migration
ssh -i ~/.ssh/shiksha_key root@88.99.174.186
sudo -u postgres psql -d shiksha -f /opt/shiksha/accounting_db_migration.sql

# 3. main.py patchen (analog SCHULE/CAMPING)

# 4. Service neu starten
systemctl restart shiksha
curl http://shiksha.tun.zone/accounting/state
```

---

## 14. PILOT-VORTEIL: DEIN EIGENES TESTBED

**Lunchbox Gastro ist dein perfektes Testbed.**

V4-Doku zeigt: Du hast schon 6+ reale Dokumente in der DB (VLV-Erstrechnung, vkw-Mahnung, BZ-458FI Anonymverfügung, VLV-Mahnung KFZ-002-1, 5 Täler Lieferschein, Eurogast 106,40€).

**Erster Schritt nach Deploy:** Deine Hypo-Vorarlberg-Online-Banking-CSV der letzten 90 Tage exportieren, hochladen, schauen wie viel SHIKSHA matcht.

Erwartete Ergebnisse für deine echten Daten:
- Eurogast 106,40€ → Match auf Rechnung d94204c2 (sicher, IBAN + Betrag + Verwendungszweck)
- VLV-Zahlungen → wenn beglichen, Match auf Polizze 60745393
- vkw 116,11€ → Match auf Mahnung 67cb9021
- BZ-458FI 60€ → Match auf Anonymverfügung b4383d84

**Das wird DEIN bester Demo-Moment** im Pilot-Gespräch nächste Woche: „Schau, das sind keine Mockups, das sind meine eigenen Buchungen."

---

## 15. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL)

1. SHIKSHA bucht NIE automatisch. Auch bei Match-Score 100. Operator bestätigt.
2. Teil-Zahlungen werden als Teil-Zahlungen erkannt — Rechnung bleibt offen mit Restbetrag.
3. IBAN strukturell validiert (V4-Validator). Truncated → review_required.
4. Aufbewahrungsfristen national: Österreich 7 Jahre BAO § 132, Deutschland 10 Jahre HGB § 257. Daten werden nicht gelöscht.
5. Bank-Format-Profile sind versioniert — bei Format-Änderung der Bank wird Profil migriert, alte Imports bleiben unverändert.
6. Matching ist deterministisch: derselbe Input → gleicher Score → gleicher Vorschlag. Keine Random-Komponenten.
7. Mahnungen sind immer Vorschläge. Auch bei 14 Tagen überfällig — SHIKSHA wartet auf den Operator.
8. Ein Bank-Statement kann nicht doppelt importiert werden (Hash über bank_reference + value_date + amount).
9. Cross-Edition: Accounting-Signale (z. B. `package.payment_late` aus SCHULE) werden vom Edition-Orchestrator gelesen, nicht hier produziert.
10. Multi-Currency vorgesehen, V1 nur EUR — Schema unterstützt aber Currency-Feld pro Buchung.

---

## 16. WIEDEREINSTIEG

```
1. Accounting-Modul V1 fertig (25.04.2026)
2. Status:
   - Master-Doc: dieses File
   - DB-Schema: server/accounting_db_migration.sql (4 neue Tabellen)
   - Models: server/accounting_models.py
   - Orchestrator + Matcher: server/accounting_orchestrator.py
   - Bank-Parser: server/bank_statement_parser.py (CSV + CAMT.053 + MT940)
   - UI: ui/accounting_dashboard.html
   - Test-Daten: test_data/lunchbox_bank_statement_demo.csv + Smoke-Test
3. Cross-Edition-Integration: Edition-Orchestratoren konsumieren accounting-Signale
4. Nächster Schritt:
   - Deploy auf shiksha.tun.zone (analog SCHULE/CAMPING)
   - Erstes Hypo-Vorarlberg-CSV importieren
   - Echtes Match-Ergebnis dokumentieren — best demo asset für Pilot-Gespräch
```

---

## 17. LETZTER SATZ

Wenn du nächste Woche bei einem Pilot-Kandidaten sitzt und fragst „Wie schaut deine offene-Posten-Lage aus?", und der Kandidat sagt „Ehrlich gesagt, ich weiß nicht genau, müsste mal in den Mails graben" — dann öffnest du dein iPad, zeigst die SHIKSHA-Accounting-Übersicht von Lunchbox Gastro mit fünf realen offenen Posten und einem ungemachten Match — und sagst: „Genau das nicht-mehr-graben-müssen ist der Punkt."

Stand: 25. April 2026 · Build-Pack V1 · Bereit zum Deploy

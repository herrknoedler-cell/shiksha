# SHIKSHA — CAMPING.EDITION BUILD PACK V1

**Stand:** 25. April 2026
**Aufbaut auf:** SHIKSHA V4, CLUB.EDITION Architektur, SCHULE.EDITION Build-Pack V1
**Zweck:** CAMPING.EDITION soweit deploy-bereit machen, dass mit Leuchtturm-Partnern in Bayern und Tirol echte Daten in das System fließen können.

---

## 1. STATUS IN EINEM SATZ

CAMPING.EDITION ist die sechste SHIKSHA-Edition (nach business, restaurant, camp, stitch, schule), spezialisiert auf inhaber-geführte Campingplätze 80–250 Pitches mit Glamping-Ergänzung, mit zwei voll spezifizierten Fiktiv-Beispielen (Camping Allweglehen Berchtesgaden, Camping Inntalblick Tirol) und integriertem `safeguarding`-Modul für Familienbetriebe mit Pool, Spielplatz und Aufsichtspflicht.

**Wichtige Abgrenzung zu camp.shiksha (V4):**
camp.shiksha ist die ältere Edition mit Schwerpunkt Kursbetriebe und KURS_001-Referenzfall. CAMPING.EDITION ist die neue Edition mit Schwerpunkt Übernachtungs-Gewerbe (Pitch-Vermietung, Mobilheime, Glamping). Beide bleiben parallel; sie teilen sich generische Module aber haben getrennte Orchestratoren.

---

## 2. EDITION-PROFIL (DEPLOY-FERTIG)

```json
{
  "edition": "camping.shiksha",
  "version": "1.0.0",
  "lead_domain": "hospitality",
  "supporting_domains": [
    "scheduling",
    "weather",
    "communications",
    "payments",
    "safeguarding",
    "operations"
  ],
  "modules_reused": [
    "people",
    "resource",
    "partnership",
    "community",
    "accounting",
    "document",
    "calendar",
    "safeguarding",
    "assessment",
    "access"
  ],
  "modules_new": [
    "pitch",
    "reservation",
    "check_in_out",
    "seasonal_pricing",
    "utility_metering",
    "guest_journey"
  ],
  "entities": [
    "Campsite",
    "Pitch",
    "Accommodation",
    "Guest",
    "Reservation",
    "Stay",
    "Service",
    "UtilityReading",
    "GuestRequest",
    "Supplier"
  ],
  "policies": [
    {
      "key": "camping.no_auto_rebooking",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Pitch-Wechsel braucht Operator-Bestätigung. Auch beim Stamm­gast."
    },
    {
      "key": "camping.guest_data_minimal",
      "level": "warn",
      "scope": "Gate 4 — Learning",
      "rationale": "Meldedaten nur so lang behalten wie behördlich nötig. Anonymisierung nach Abreise + 12 Monate."
    },
    {
      "key": "camping.minor_supervision_required",
      "level": "warn",
      "scope": "Gate 1 — Intake",
      "rationale": "Reservierung mit Minderjährigen ohne erwachsene Begleitung wird vom Operator bestätigt."
    },
    {
      "key": "camping.weather_advisory_only",
      "level": "warn",
      "scope": "Gate 2 — Routing",
      "rationale": "Sturm-Warnungen werden Gästen nur nach Operator-Freigabe geschickt."
    },
    {
      "key": "camping.utility_overage_alert",
      "level": "warn",
      "scope": "Gate 2 — Routing",
      "rationale": "Strom-Verbrauch deutlich über Erwartung → Operator wird informiert, nicht der Gast."
    },
    {
      "key": "camping.no_auto_review_request",
      "level": "block",
      "scope": "Gate 3 — Action",
      "rationale": "Bewertungs-Bitten gehen erst nach Operator-Freigabe — kein Spam-Risiko."
    }
  ],
  "language_modes": ["flow", "action", "alert"],
  "reference_cases": [
    "CAMPING_001 (Familien-Campingplatz Bayern, 120 Pitches + 8 Mobilheime + 4 Glamping)",
    "CAMPING_002 (Inntal-Campingplatz Tirol, 180 Pitches + 12 Mobilheime, hund-erlaubt)"
  ],
  "fixtures_path": "/fixtures/camping_edition/",
  "review_required_default": true
}
```

---

## 3. MODUL-KOMPOSITION

### 3.1 Wiederverwendete Module

| Modul | CAMPING-spezifische Verwendung |
|---|---|
| `people` | Gäste (mit Meldepflicht), Mitarbeiter, Lieferanten-Personen |
| `resource` | Pitches, Mobilheime, Glamping-Zelte, Boote, Fahrräder, Pool-/Spielplatz-Bereiche |
| `partnership` | Bäcker, Metzger, Schreiner, Versorger, Tourismusverband, Versicherung |
| `community` | Gäste-Pinnwand, Mitfahr-Gelegenheit, Materialverleih (BBQ, Boot) |
| `accounting` | Gästekonten, offene Posten, Kurtaxe, Stornogebühren |
| `document` | Reservierungs-Bestätigung, Lieferscheine, Behördenpost — **Foto-Flow zentral** |
| `calendar` | Saison, Schulferien (für Familien-Belegung), Events, Gemeinde-Termine |
| `safeguarding` | Pflichtmodul bei Pool/Spielplatz: Aufsichtskonzept, Background-Checks, Incidents |
| `assessment` | Saisonale Inspektionen (Strom, Wasser, Hygiene, Pool-Wasser) |
| `access` | Schranken, NFC, Spind, Kiosk — koppelt an Stay-Status |

### 3.2 CAMPING-spezifische Module

#### `pitch`
Stellplatz-Inventar als komplexe Resource.

**Objekte:**
- `pitch` — A12, B07 etc. mit Eigenschaften (Strom 16A, Wasseranschluss, Schatten, Größe in m², Hund-erlaubt)
- `pitch_type` — "Komfort", "Standard", "Naturplatz", "Servicepitch"
- `pitch_blockage` — Wartung, Reparatur, längere Einzelbuchung
- `pitch_history` — wer war wann hier, Bewertungen

**Signale:**
- `pitch.utilization_low` — Pitch X seit 14 Tagen leer in Hochsaison
- `pitch.repeat_complaint` — gleicher Pitch dreimal in Folge negativ erwähnt
- `pitch.maintenance_overdue` — saisonale Wartung steht aus

**Abhängigkeiten:** `resource`, `seasonal_pricing`

#### `reservation`
Buchung im Vorfeld (vor `stay` = Aufenthalt).

**Objekte:**
- `reservation` — Familie X für Pitch A12 vom 15.07. bis 28.07.
- `reservation_status` — `inquiry`, `pending_payment`, `confirmed`, `cancelled`, `no_show`
- `cancellation_record` — wann, warum, Gebühr
- `wait_list_entry` — wer wartet auf welchen Zeitraum

**Signale:**
- `reservation.payment_overdue` — Reservierung steht, Anzahlung fehlt
- `reservation.cancellation_late` — Storno innerhalb der Karenzfrist → Gebühr
- `reservation.no_show_pattern` — Gast bucht häufig und kommt nicht
- `reservation.early_bird_window` — Stamm­gäste-Buchungs-Fenster läuft aus

**Abhängigkeiten:** `pitch`, `people`, `seasonal_pricing`, `accounting`

#### `check_in_out`
An- und Abreise-Logik mit Meldepflicht.

**Objekte:**
- `stay` — der tatsächliche Aufenthalt (vom check_in bis check_out)
- `meldeschein` — meldebehördliche Erfassung
- `check_in_record` — wer, wann, mit welchem Personenstand
- `check_out_record` — Endabrechnung, Pitch-Rückgabe

**Signale:**
- `check_in.late_arrival` — angekündigte Spät-Anreise (nach 19 Uhr)
- `check_out.delayed` — Pitch nicht freigegeben am vereinbarten Tag
- `check_out.damages_reported` — Schäden festgestellt

**Abhängigkeiten:** `reservation`, `people`, `pitch`, `safeguarding` (bei Familien)

#### `seasonal_pricing`
Preise variieren nach Saison, Wochentag, Pitch-Typ.

**Objekte:**
- `pricing_period` — "Hochsaison" (15.07.–25.08.), "Nebensaison" (vor/nach), "Winter"
- `pricing_rule` — Pitch-Typ × Period × Personen × Tarif (€/Nacht)
- `surcharge` — Hund, Strom-Pauschale, Endreinigung, Kurtaxe
- `discount` — Frühbucher, Stammgast, Längeraufenthalt

**Signale:**
- `pricing.period_transition_due` — Übergang Hoch→Nebensaison in 7 Tagen
- `pricing.competitor_drift` — Region-Vergleichs-Hinweis (V2)

#### `utility_metering`
Strom- und Wasserablesung pro Pitch (oder Mobilheim).

**Objekte:**
- `meter` — Zähler-ID pro Pitch
- `utility_reading` — Ablese-Wert mit Foto-Beleg
- `consumption_record` — Verbrauch zwischen zwei Ablesungen
- `cost_passthrough` — was dem Gast in Rechnung geht

**Signale:**
- `utility.unusual_consumption` — Verbrauch ≥ 200% Schnitt vergleichbarer Pitches
- `utility.reading_overdue` — letzte Ablesung > 14 Tage
- `utility.discrepancy` — Foto und manueller Wert weichen ab

**Abhängigkeiten:** `pitch`, `accounting`, `document`

#### `guest_journey`
Vom Reservierungs-Eingang bis zur Bewertungs-Bitte als zusammenhängende Reise.

**Objekte:**
- `journey_stage` — `inquiry` → `booked` → `pre_stay` → `arrival` → `stay` → `departure` → `post_stay`
- `journey_event` — automatischer Touchpoint (z.B. "Anreise-Hinweise verschickt")
- `journey_intervention` — manueller Operator-Schritt

**Signale:**
- `journey.silent_during_stay` — Gast war 3 Tage da, keine Interaktion (Service, Brötchen, Frage)
- `journey.repeat_pattern` — dritter Aufenthalt in Folge → Stamm­gast
- `journey.pre_arrival_question_window` — 48h vor Anreise, häufige Fragen-Phase

### 3.3 Modul-Abhängigkeitsgraph

```
                ┌──────────────────────────────────┐
                │  CAMPING_ORCHESTRATOR            │
                │  Sprache · Patterns · Focus      │
                └──────────────────────────────────┘
                        ▲ alle Signale, gewichtet
                        │
        ┌───────────────┼─────────────────────────────┐
        │               │                             │
   reservation  →  check_in_out  →  guest_journey
        │               │                  │
        ▼               ▼                  ▼
     pitch ←──── seasonal_pricing       community
        │
        ▼
   utility_metering ──► document.module (Ablese-Foto)
        │
        ▼
   accounting

   safeguarding (cross-edition!) ──► alerts in alle Module
   partnership ─► document.module (Lieferschein-Foto)
```

---

## 4. POLICY GATES

### Gate 1 — Intake

| Trigger | Policy | Verhalten |
|---|---|---|
| Reservierung mit nicht volljähriger Hauptperson | `camping.minor_supervision_required` | warn — Operator bestätigt manuell |
| Foto-Reservierungs-Anfrage unleserlich | `document.unreadable` | warn — Foto neu anfordern |

### Gate 2 — Routing

| Trigger | Policy | Verhalten |
|---|---|---|
| Sturm-Warnung 24h vor Anreise | `camping.weather_advisory_only` | warn — Vorschlag, nicht versenden |
| Strom-Verbrauch ≥ 200% Schnitt | `camping.utility_overage_alert` | warn — Operator informiert, prüft |
| Pitch-Wechsel-Anfrage von Gast | `camping.no_auto_rebooking` | block — Operator entscheidet |

### Gate 3 — Action

| Trigger | Policy | Verhalten |
|---|---|---|
| Bewertungs-Bitte versenden | `camping.no_auto_review_request` | block — Operator-Freigabe pro Gast |
| Stornorechnung erzeugen | `camping.cancellation_review` | warn — Vorschlag, nicht senden |
| Pitch automatisch sperren wegen Wartung | `camping.no_auto_rebooking` | block — manuell |

### Gate 4 — Learning

| Trigger | Policy | Verhalten |
|---|---|---|
| Gast-Profil-Aggregation (Vorlieben) | `camping.guest_data_minimal` | warn — pro-Gast-Speicherung nur 12 Mo nach Abreise |
| Lieferanten-Verhalten lernen | `camping.pattern_promotion_with_consent` | erlaubt — auf Lieferanten-Ebene anonym |

---

## 5. LANGUAGE LAYER — CAMPING-SPEZIFISCH

```yaml
camping.reservation.payment_overdue:
  flow:    "Familie Berger Anzahlung offen"
  action:  "Familie Berger erinnern?"
  alert:   "Familie Berger — Buchung verfällt morgen"

camping.reservation.no_show_pattern:
  flow:    "Becker bucht öfter, kommt selten"
  action:  "Becker um Vorab-Bestätigung bitten?"
  alert:   "—"

camping.utility.unusual_consumption:
  flow:    "Pitch B07 Strom auffällig"
  action:  "Beim Gast nachhören?"
  alert:   "—"

camping.pitch.maintenance_overdue:
  flow:    "Pitch C03 Wartung fällig"
  action:  "Schreiner anrufen?"
  alert:   "—"

camping.partnership.delivery_today:
  flow:    "Bäcker bringt um 7"
  action:  "Bestellung bestätigen?"
  alert:   "—"

camping.guest.silent_during_stay:
  flow:    "{guest} schweigt seit 3 Tagen"
  action:  "Kurz vorbeischauen?"
  alert:   "—"

camping.weather.storm_warning:
  flow:    "Sturm Donnerstag"
  action:  "Reisemobil-Gäste anschreiben?"
  alert:   "Sturm in 12h — handeln"

camping.check_in.late_arrival:
  flow:    "Familie Vogel kommt nach 22h"
  action:  "Späten Schlüssel-Plan vorbereiten?"
  alert:   "—"

camping.safeguarding.pool_supervision:
  flow:    "Pool-Aufsicht heute lückig"
  action:  "Marc bitten einzuspringen?"
  alert:   "Pool ohne Aufsicht — sperren"

camping.journey.repeat_pattern:
  flow:    "Familie Schmidt — dritter Sommer"
  action:  "Persönlich begrüßen?"
  alert:   "—"
```

---

## 6. REFERENZFÄLLE

### CAMPING_001 — Camping Allweglehen Berchtesgaden

**Platz:** "Camping Allweglehen" (fiktiv) — 120 Pitches, 8 Mobilheime, 4 Glamping-Zelte
**Standort:** Berchtesgaden, Bayern (alpennah, Familien-Schwerpunkt)
**Saison:** April–Oktober + Wintercamping Dezember–Februar
**Geschäftsmodell:** Pitch-Vermietung saison­abhängig, Glamping-Premium, Stamm­gast-Bindung

**Komplexität, die SHIKSHA validiert:**
- Pool + Spielplatz → safeguarding-Pflichtmodul
- Strom-Ablesung pro Pitch (Foto-Flow!)
- 18 lokale Lieferanten (Bäcker, Metzger, Brennholz, Schreiner)
- Behördenpost: Gemeinde, Gesundheitsamt, Gewerbeordnung
- Wintercamping mit komplett anderer Logik (Skipässe, Strom, Heizung)
- Mehrgenerations-Familienbetrieb in Übergabe

### CAMPING_002 — Camping Inntalblick Tirol

**Platz:** "Camping Inntalblick" (fiktiv) — 180 Pitches, 12 Mobilheime
**Standort:** Inntal, Tirol (Wandern + Radfahren + Outdoor)
**Saison:** Mai–September, hund-erlaubt
**Geschäftsmodell:** Outdoor-affine Gäste, kürzere Aufenthalte (3–7 Nächte)

**Komplexität:**
- Hunde-Erlaubt → eigene Stellplatz-Kategorie + Hundewiese (safeguarding!)
- Längere Aufenthalte saisonal (Dauercamper)
- Multi-Sprache (Deutsch, Italienisch, Englisch)
- Wetter-Sensitivität wegen Outdoor-Aktivitäten
- Hohe Stamm­gast-Quote (35%)
- Tourismusverband-Kurtaxe-Pflicht

---

## 7. DATENBANK-ERWEITERUNGEN

Vollständige SQL-Migration: siehe `server/camping_db_migration.sql`.

Neue Tabellen: `campsites`, `pitches`, `accommodations`, `guests`, `guardians_camping`, `reservations`, `stays`, `meldescheine`, `pricing_periods`, `pricing_rules`, `meters`, `utility_readings`, `services`, `service_consumptions`, `guest_requests`, `journey_events`, `camping_signals`, `camping_state_snapshots`.

---

## 8. API-ENDPOINTS

```
CAMPING EDITION
================
GET    /camping/state                      — CampState (sprachfähig)
GET    /camping/state/summary              — Kompakt, ein Satz

POST   /camping/reservations               — Buchung anlegen
GET    /camping/reservations?filter=open
POST   /camping/reservations/{id}/confirm
POST   /camping/reservations/{id}/cancel

POST   /camping/check-in                   — Anreise verarbeiten
POST   /camping/check-out                  — Abreise + Endabrechnung

POST   /camping/pitches                    — Pitch anlegen
GET    /camping/pitches/{id}/availability  — Verfügbarkeit + Wartung

POST   /camping/utility/readings           — Ablese-Wert (mit Foto-Link)
GET    /camping/utility/anomalies          — auffällige Verbräuche

POST   /camping/services/consumed          — Brötchen, Wasch, Sauna
GET    /camping/services/today

POST   /camping/orchestrate                — vollständig
POST   /camping/orchestrate/summary        — kompakt
```

---

## 9. EINGABEMASKEN

Datei: `ui/operator_eingabemasken.html` mit Tabs:
- **Heute** — Anreisen, Abreisen, Lieferanten heute, Wetter
- **Pitch verwalten** — Pitch-Karte mit Eigenschaften, Wartung, Sperren
- **Reservierung** — Foto-Anmeldung-Flow + Konsente
- **Check-in** — Meldepflicht + Mehrpersonen-Familien
- **Strom-Ablesung** — Foto + Wert + Pitch-Zuordnung
- **Lieferschein** — Bäcker / Metzger Foto-Flow

---

## 10. MOBILE-APP (GÄSTE-SICHT)

Datei: `ui/gaeste_app.html`

**Drei Phone-Sichten:**
1. **Vor Anreise** — Familie Schmidt (Bayern, dritte Saison) — was kommt: Anreise, Pitch, Pool, Brötchen-Service
2. **Während Aufenthalt** — Holländischer Gast Inntal — was passiert heute: Wetter, Wanderung, Hund auf Wiese
3. **Nach Abreise** — Stamm­gast — Eindrücke, Bewertung-Bitte (review_required), nächste Buchung

---

## 11. AUSWERTUNGEN (DASHBOARD)

Datei: `ui/operator_dashboard.html`

**CampState analog SchoolState:**
- Sprachliche Tageszusammenfassung
- Recent Signals
- Patterns ("Pitch B07 dreimal Beschwerde", "Bäcker Müller letzte Lieferung 9 Tage her")
- Recommended Focus
- Drilldowns: Belegung, Strom-Anomalien, Lieferanten-Pflege, Stamm­gäste-Quote

---

## 12. INTEGRATION SAFEGUARDING-MODUL

CAMPING.EDITION nutzt das `safeguarding`-Modul über die generische Schicht (siehe separater Build-Pack `safeguarding/SAFEGUARDING_BUILD_PACK_V1.md`).

**Kritische Bereiche bei Camping:**
- Pool-Aufsicht (Stunden, Personal-Lizenz, Incident-Reports)
- Spielplatz-Sicherheit (jährliche Inspektion, Schadens-Tracking)
- Familien mit Kindern und schwimmenden Gefahren
- Hundewiese + spielende Kinder = Konflikt-Potential
- Behördenauflage Gewerbeordnung Bayern/Tirol unterschiedlich

Der Orchestrator dieser Edition liest Safeguarding-Signale **mit erhöhter Severity**, weil Familienbetrieb + Pool die Konsequenzen unmittelbar machen.

---

## 13. DEPLOY-ANLEITUNG

```bash
# 1. Code auf Server
scp -i ~/.ssh/shiksha_key \
    server/camping_models.py \
    server/camping_orchestrator.py \
    server/camping_db_migration.sql \
    root@88.99.174.186:/opt/shiksha/

# 2. DB-Migration
ssh -i ~/.ssh/shiksha_key root@88.99.174.186
sudo -u postgres psql -d shiksha -f /opt/shiksha/camping_db_migration.sql

# 3. main.py patchen → siehe MAIN_PY_PATCH_CAMPING.md

# 4. Service neu starten
systemctl restart shiksha
systemctl status shiksha

# 5. Smoke-Test
curl http://shiksha.tun.zone/camping/profile

# 6. Fixtures laden
curl -X POST http://shiksha.tun.zone/camping/import \
     -H "Content-Type: application/json" \
     -d @fixtures/camping_allweglehen_bayern.json
```

---

## 14. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL)

1. CAMPING.EDITION ist eine Komposition aus 10 generischen + 6 spezifischen Modulen.
2. `safeguarding` ist Pflicht, sobald Pool, Spielplatz oder Aufsichtspflicht-Bereiche existieren.
3. Wetter-Warnungen an Gäste sind immer Vorschlag.
4. Pitch-Wechsel braucht immer Operator-Bestätigung.
5. Strom-Foto-Ablesung priorisiert Foto-Flow über manuellen Eingabe-Pfad.
6. CampState (Sprache) entsteht im Orchestrator.
7. Bewertungs-Bitten gehen nie automatisch.
8. Mehrere Adressen pro Gast erlaubt (Wohnsitz + Anschrift Wohnmobil-Halter).
9. Behördenauflagen sind regions-spezifisch (Bayern ≠ Tirol ≠ Schweiz) — Edition kennt das Schema, lädt regional die Auflagen.
10. Stammgast-Erkennung läuft über `journey.repeat_pattern` — frühestens beim dritten Aufenthalt promotion-fähig.

---

## 15. WIEDEREINSTIEG NACH CHAT-VERLUST

```
1. CAMPING.EDITION Build-Pack V1 fertig (25.04.2026)
2. Status:
   - Master-Doc: dieses File
   - Edition-Profile: section 2 (deploy-ready JSON)
   - DB-Schema: server/camping_db_migration.sql
   - Pydantic-Models: server/camping_models.py
   - Orchestrator: server/camping_orchestrator.py
   - Fixtures: fixtures/camping_allweglehen_bayern.json + camping_inntalblick_tirol.json
   - AI-Dokumente: fixtures/camping_edition/ai_documents/ (8 Stück)
   - Operator-UI: ui/operator_eingabemasken.html
   - Gäste-App: ui/gaeste_app.html
   - Dashboard: ui/operator_dashboard.html
3. Safeguarding (cross-edition): outputs/safeguarding/
4. Nächster Schritt: Server-Deploy + erster Pilot-Kontakt zu Camping-Familienbetrieb in Tirol/Vorarlberg
```

---

## 16. LETZTER SATZ

CAMPING.EDITION ist nicht erst dann real, wenn der erste Tiroler Familienbetrieb morgens den Bäcker-Lieferschein abfotografiert — sondern jetzt schon, weil das System weiß, was ein Stammgast ist, was ein lückiger Pool-Tag ist, und was ein Sturm in zwölf Stunden bedeutet.

Stand: 25. April 2026 · Build-Pack V1 · Bereit zum Deploy

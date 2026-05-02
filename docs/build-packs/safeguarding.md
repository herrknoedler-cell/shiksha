# SHIKSHA — SAFEGUARDING MODUL BUILD PACK V1

**Stand:** 25. April 2026
**Aufbaut auf:** SHIKSHA V4, CLUB.EDITION (safeguarding ist Phase-1-Pflichtmodul), SCHULE.EDITION, CAMPING.EDITION
**Zweck:** Cross-edition `safeguarding`-Modul mit realer Lernfähigkeit auf Pattern-Ebene — ohne ML-Libraries, mit klar nachvollziehbarer Operator-Promotion-Logik.

---

## 1. STATUS IN EINEM SATZ

`safeguarding` ist ein generisches SHIKSHA-Modul, das in CLUB, SCHULE, CAMPING (und künftig anderen Editionen) wiederverwendet wird, um Schutzkonzept, Background-Checks, Einverständnisse und Vorfälle zu verwalten — und zusätzlich aus Operator-Feedback und Saisonal-Daten lernt, ohne jemals selbst zu handeln.

---

## 2. WAS BEDEUTET „LERNFÄHIG" HIER?

In SHIKSHA gibt es kein Machine-Learning im klassischen Sinn. Statt dessen lernt das `safeguarding`-Modul auf vier Achsen, alle mit nachvollziehbaren Regeln und immer mit Operator-Promotion-Pflicht (V4-Prinzip 7: conservative, V4-Prinzip 11: review_required, CLUB-Architektur: pattern_promotion_with_consent):

### 2.1 Pattern-Lernen aus Historie

Wenn dasselbe Signal ≥ 3-mal innerhalb eines definierten Fensters auftritt, erzeugt das Modul einen **Pattern-Kandidaten** (`safeguarding_pattern_candidate`). Ein Kandidat ist sichtbar, aber **nicht aktiv** — er feuert keine eigenen Signale, schlägt keine eigenen Aktionen vor. Der Operator sieht ihn, kann ihn einmalig prüfen und entweder **promoten** (wird zu `safeguarding_pattern_promoted`) oder **verwerfen**.

**Beispiele:**
- "Hund Bruno → Beschwerde in Saison 2024, 2025, 2026" → Kandidat „Hund-Eignung-Familie-Maier-prüfen"
- "Pool-Inspektion immer Mitte April" → Kandidat „Pool-Vorbereitung ab März einleiten"
- "Saison-Lehrer Tom — Lizenz-Erneuerung erst spät begonnen" → Kandidat „Lehrer-Lizenz-Reminder 90 Tage vorher"

Erst nach Operator-Promotion erzeugt der Pattern eigene Aktionen.

### 2.2 Severity-Adjustment aus Operator-Feedback

Jedes Signal trägt einen Default-Severity-Wert. Bei jedem Resolved-Vorgang wird festgehalten, **wie der Operator gehandelt hat**:

| Operator-Handlung | Lern-Signal |
|---|---|
| sofort gelöst (< 1 Std) | severity_correct = +1 |
| in 1–24 Std gelöst | severity_correct = 0 (passt) |
| > 24 Std gelöst | severity_correct = -0.5 (war zu hoch?) |
| dismissed ohne Aktion | severity_correct = -2 (war zu hoch) |
| eskaliert (alert ausgelöst nach Operator) | severity_correct = +2 (war zu niedrig) |

Über 50+ Vorkommen eines Signal-Keys aggregiert das Modul → **Default-Severity-Anpassungs-Vorschlag**. Operator sieht den Vorschlag im Dashboard und entscheidet einmalig: ja oder nein.

**Beispiel:**
- `safeguarding.consent_missing` startet als severity=mid
- Über 60 Vorkommen wird 48× sofort gelöst, 12× < 24h
- Aggregat → Vorschlag: "diesen Key auf severity=high anheben?"
- Operator promotet → ab dem Moment ist Default = high

### 2.3 Cross-Edition-Lernen

Das `safeguarding`-Modul lebt in einer Edition, lernt aber editions-übergreifend. Wenn in SCHULE.EDITION das Signal `consent_missing` häufig in der ersten Probestunde fehlt, erzeugt das Modul einen Hinweis für CAMPING.EDITION beim Kinder-Camp-Check-in: "Achte besonders auf Fotokonsens — fehlt in 40 % der Erstkontakte."

**Mechanismus:**
- Pattern-Kandidaten haben einen `applicable_editions: list[str]` Feld
- Bei Promotion in einer Edition kann Operator wählen, welche Editionen profitieren
- Cross-Edition-Hinweise erscheinen als `info`-Severity-Signale in den Ziel-Editionen

### 2.4 Saisonale Patterns

Ein zeitliches Sonder-Pattern: wenn ein Signal exakt einmal pro Jahr in einem ähnlichen Zeitfenster auftritt, wird es als **Saisonpattern** klassifiziert. Das Modul schlägt dann in der Vor-Saison eine Vorbereitungs-Aktion vor.

**Beispiele:**
- Pool-Inspektion: jährlich Mitte April → Vorschlag „Schreinerei + Reinigung anrufen ab 20. März"
- Sturm-Saison: jährlich Oktober/November → Vorschlag „Reisemobil-Gäste vor­warnen"
- Background-Check Saison-Personal: vor Mai → Vorschlag „neue Mitarbeiter spätestens 30 Tage vor Saison-Start prüfen"

Saisonal-Patterns brauchen mindestens 2 historische Vorkommen, bevor sie Kandidaten werden — sonst sind sie nur Zufall.

---

## 3. MODUL-ARCHITEKTUR

```
                     ┌─────────────────────────────┐
                     │  EDITION-ORCHESTRATOREN     │
                     │  (CLUB · SCHULE · CAMPING)  │
                     └─────────────────────────────┘
                              ▲      ▲
                signals_in   │      │   patterns_out
                              │      │
                     ┌─────────────────────────────┐
                     │  safeguarding_orchestrator  │
                     │  - signal_aggregation       │
                     │  - pattern_candidate_detect │
                     │  - severity_feedback_track  │
                     │  - cross_edition_propagate  │
                     │  - seasonal_pattern_detect  │
                     └─────────────────────────────┘
                              ▲           ▲
                              │           │
                ┌─────────────┴──┐   ┌────┴───────────────┐
                │ safeguarding   │   │ pattern_promotion  │
                │ database       │   │ ui (operator)      │
                └────────────────┘   └────────────────────┘
```

---

## 4. ENTITIES UND TABELLEN

| Tabelle | Zweck |
|---|---|
| `protection_policies` | Schutzkonzept einer Organisation (Schule, Camping, Verein) |
| `person_protection_status` | Pro Person: hat Background-Check, hat Erste-Hilfe, etc. |
| `background_checks` | Historie aller Background-Checks mit Verfallsdatum |
| `safeguarding_consents` | zentralisierte Konsente (Foto, Datenweitergabe, etc.) |
| `incident_reports` | Vorfälle mit Schweregrad, Zeitpunkt, Beteiligten |
| `safeguarding_signals` | Edition-übergreifende Signale (Cross-Edition) |
| `safeguarding_pattern_candidates` | Gelernte Hypothesen, NICHT aktiv |
| `safeguarding_pattern_promoted` | Vom Operator bestätigt, aktiv |
| `safeguarding_severity_feedback` | Operator-Verhalten pro Signal-Key, aggregiert |
| `safeguarding_action_templates` | Was schlägt SHIKSHA vor, wenn Pattern aktiv? |

---

## 5. POLICY GATES

| Gate | Trigger | Verhalten |
|---|---|---|
| Gate 1 — Intake | Neuer Mitarbeiter ohne Background-Check, Kontakt zu Minderjährigen | block — Anlage erst nach Foto/Scan-Beleg |
| Gate 1 — Intake | Reservation/Anmeldung mit Minderjährigem ohne Guardian | block — Consent-Anforderung erst |
| Gate 2 — Routing | Pattern-Kandidat wird relevant (Person, Vorfall) | warn — Operator sieht Hinweis im Edition-Dashboard |
| Gate 3 — Action | Severity-Anpassung wird vorgeschlagen | block — Operator bestätigt einmalig oder lehnt ab |
| Gate 4 — Learning | Cross-Edition-Pattern-Vorschlag | warn — Operator wählt aktiv "in welche Editionen übertragen" |

**Iron rule:** Das `safeguarding`-Modul kommuniziert NIE direkt mit Schülern, Gästen oder Eltern. Es informiert nur den Operator-Edition-Orchestrator, der Sprache erzeugt.

---

## 6. SIGNAL-VOKABULAR

```yaml
safeguarding.background_check_expiring:
  default_severity: mid
  flow:    "{person} Führungszeugnis läuft"
  action:  "{person} an Erneuerung erinnern?"
  alert:   "{person} Führungszeugnis endet morgen"

safeguarding.consent_missing:
  default_severity: mid
  flow:    "{person} Konsent {type} fehlt"
  action:  "{guardian} um {type} bitten?"
  alert:   "{person} darf nicht {context}"

safeguarding.pool_inspection_due:
  default_severity: high
  flow:    "Pool-Prüfung naht"
  action:  "Termin Gesundheitsamt vereinbaren?"
  alert:   "Pool-Prüfung in {days_left} Tagen"

safeguarding.pool_supervision_lueckig:
  default_severity: high
  flow:    "Pool-Aufsicht lückig"
  action:  "{candidate} bitten einzuspringen?"
  alert:   "Pool ohne Aufsicht — sperren"

safeguarding.playground_inspection_due:
  default_severity: mid
  flow:    "Spielplatz-Prüfung fällig"
  action:  "TÜV-Termin buchen?"

safeguarding.dog_repeat_complaint:
  default_severity: mid
  flow:    "Hund {dog} — wiederholte Beschwerde"
  action:  "Mit {guest} reden?"

safeguarding.incident_unresolved:
  default_severity: high
  flow:    "Vorfall offen seit {days}"
  action:  "Status klären + dokumentieren?"
  alert:   "Vorfall {id} braucht Antwort"

safeguarding.first_aid_kit_expired:
  default_severity: low
  flow:    "Verbandsmaterial alt"
  action:  "Neue Kits bestellen?"

safeguarding.staff_first_aid_expiring:
  default_severity: mid
  flow:    "{person} Erste-Hilfe-Schein läuft"
  action:  "{person} zu Auffrischungs-Kurs?"
```

---

## 7. LERN-WORKFLOW IM DETAIL

### 7.1 Pattern-Candidate-Detection

```
trigger: alle 24h Cron-Job

input: alle safeguarding_signals der letzten 36 Monate

logik:
  for signal_key in distinct(signals.signal_key):
    occurrences = signals where signal_key = X

    # Pattern-Typ A: Frequenz-Cluster
    if count(occurrences) >= 3 in 12 Monaten:
        if recurring_entity_match(occurrences):  # gleiche Person/Pitch/etc
            create candidate "{signal_key}.recurring_entity_X"

    # Pattern-Typ B: Saisonal
    if exact_one_per_year(occurrences) and years >= 2:
        create candidate "{signal_key}.seasonal"
        suggest_action_template("vorher prüfen + vorbereiten")

    # Pattern-Typ C: Cross-Edition
    if signal_key occurrence_count_in_other_edition_high:
        create candidate "{signal_key}.cross_edition_hint"

output: candidates landen in safeguarding_pattern_candidates
        Operator sieht sie im Dashboard, kann promoten/verwerfen
```

### 7.2 Severity-Feedback-Loop

```
trigger: jeder resolve-Vorgang an einem safeguarding_signal

logik:
  signal_key = signal.signal_key
  resolution_time = signal.resolved_at - signal.created_at
  current_default = severity_lookup(signal_key)

  # Score (siehe Tabelle 2.2)
  score = score_from_resolution_time_or_dismiss(resolution_time, was_dismissed)

  # Aggregation in safeguarding_severity_feedback
  upsert (signal_key, total_score += score, count += 1)

  # Vorschlag wenn count > 50 und mean_score auseinanderfällt
  if count >= 50:
    mean = total_score / count
    if abs(mean) > 0.7:
        suggest severity adjustment to operator
```

### 7.3 Promotion-UI

Ein eigener Tab im Operator-Dashboard zeigt **Pattern-Kandidaten + Severity-Vorschläge**. Operator sieht:
- Welche Beobachtung dahintersteht
- Wie oft, in welchem Zeitraum
- Was SHIKSHA vorschlagen würde, wenn promoted
- "Ja, promoten" / "Nein, ist Zufall" / "Verschieben"

Promotion ist immer reversibel — der Operator kann ein Pattern jederzeit deaktivieren.

---

## 8. INTEGRATION IN EDITIONEN

### CLUB.EDITION
`safeguarding` ist Phase-1-Pflichtmodul (Kinder/Jugendsport). Cross-Edition: Lernt aus SCHULE-Yoga-Kinder und CAMPING-Familienbetrieb-Vorfällen.

### SCHULE.EDITION
Pflicht bei `school.has_minors = true` (Kinder-Yoga, Surf-Camp Kids, Skischule, etc.). Häufigste Signale: Konsent-fehlt, Lehrer-Lizenz-läuft, Erste-Hilfe-Auffrischung.

### CAMPING.EDITION
Pflicht bei `campsite.has_pool || has_playground`. Häufigste Signale: Pool-Inspektion, Aufsichts-Lücken, Hund-Wiederholungs-Beschwerden, Background-Check-Saisonal-Personal.

**Severity-Boost in CAMPING:** Pool-Aufsicht lückig wird in CAMPING zu `high` (siehe `camping_orchestrator.CAMPING_SAFEGUARDING_BOOSTERS`), weil unmittelbare Lebensgefahr. In SCHULE-Yoga-Studio wäre derselbe Signal-Key irrelevant.

---

## 9. UI: SAFEGUARDING-DASHBOARD

Datei: `safeguarding/ui/safeguarding_dashboard.html`

**Drei Bereiche:**
1. **Pflicht-Status** — Background-Checks, Konsente, Pool-/Spielplatz-Inspektionen je Standort. Wer ist drin, wer nicht?
2. **Offene Signale** — wie in den Edition-Dashboards, aber speziell safeguarding-bezogen, mit Severity-Boost-Hinweis
3. **Lern-Status** — Pattern-Kandidaten, Severity-Feedback-Aggregate, Cross-Edition-Hinweise. Operator promotet/verwirft hier.

---

## 10. DEPLOY-ANLEITUNG

```bash
# 1. Code auf Server
scp -i ~/.ssh/shiksha_key \
    safeguarding_models.py \
    safeguarding_orchestrator.py \
    safeguarding_db_migration.sql \
    root@88.99.174.186:/opt/shiksha/

# 2. DB-Migration
ssh -i ~/.ssh/shiksha_key root@88.99.174.186
sudo -u postgres psql -d shiksha -f /opt/shiksha/safeguarding_db_migration.sql

# 3. main.py erweitern (Router)
# (siehe MAIN_PY_PATCH_SAFEGUARDING.md)

# 4. Service neu starten
systemctl restart shiksha
curl http://shiksha.tun.zone/safeguarding/profile

# 5. Cron für Pattern-Detection (täglich nachts)
crontab -e
# Zeile hinzufügen:
# 0 3 * * * /opt/shiksha/venv/bin/python /opt/shiksha/safeguarding_cron.py >> /var/log/shiksha-safeguarding.log 2>&1
```

---

## 11. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL)

1. `safeguarding` ist eigenständiges Modul, nicht Teil einer Edition.
2. Lernen passiert auf Pattern-Ebene, nicht auf ML-Ebene — alle Schritte sind nachvollziehbar in SQL nachzulesen.
3. Patterns sind erst nach Operator-Promotion aktiv. „pattern_promotion_with_consent" (CLUB-Architektur).
4. Severity-Anpassungen brauchen ≥ 50 Vorkommen + signifikantes Operator-Feedback-Signal.
5. Cross-Edition-Hinweise erscheinen als info-Signale, nie als Aktionen.
6. Saisonal-Patterns brauchen ≥ 2 jährliche Vorkommen, bevor sie als Kandidaten erscheinen.
7. Das Modul kommuniziert nie direkt mit Endkunden — Operator-Edition-Orchestrator macht Sprache.
8. Edition-spezifische Severity-Boosts (z.B. Pool in CAMPING) werden im Edition-Code definiert, nicht hier.
9. Promotion-Aktionen sind reversibel.
10. Lern-Daten haben eigene Retention-Pflicht: 36 Monate, dann anonymisierte Aggregate.

---

## 12. WAS NACH DIESER SESSION FEHLT

| Fehlt | Wer | Wann |
|---|---|---|
| Cron-Job für Pattern-Detection produktiv | Build | nächste Session |
| Cross-Edition Signal-Bridge live (CLUB ↔ SCHULE ↔ CAMPING) | Build | nächste Session |
| ML-Light Severity-Klassifikation (V2) | später | nicht in V1 |
| TÜV-/Inspektions-Kalender-Integration | Build | nach erstem Pilot |
| Mobile-First Incident-Report-Erfassung (für Pool-Aufsichts-Personal) | Build | nach erstem Pilot |

---

## 13. WIEDEREINSTIEG NACH CHAT-VERLUST

```
1. Safeguarding-Modul V1 fertig (25.04.2026)
2. Status:
   - Master-Doc: dieses File
   - DB-Schema: safeguarding/server/safeguarding_db_migration.sql
   - Models: safeguarding/server/safeguarding_models.py
   - Orchestrator (mit Lernfunktionen): safeguarding/server/safeguarding_orchestrator.py
   - UI: safeguarding/ui/safeguarding_dashboard.html
3. Integration: SCHULE.EDITION + CAMPING.EDITION lesen safeguarding-Signale
4. Lernen: Pattern-Kandidaten + Severity-Feedback laufen, Promotion via UI
5. Nächster Schritt: Deploy, Cron-Job, Pilot mit erstem Camping- oder Yoga-Partner
```

---

## 14. LETZTER SATZ

`safeguarding` ist nicht das Modul, das alles regelt — sondern das Modul, das aufpasst, wo Menschen am verletzlichsten sind, und das mit jedem Operator-Feedback ein bisschen klüger wird, ohne je die Verantwortung zu übernehmen.

Stand: 25. April 2026 · Build-Pack V1 · Bereit zum Deploy

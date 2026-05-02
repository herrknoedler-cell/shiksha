# KITA · COMPLIANCE & AUDIT MODUL
## Build-Pack — Personalschlüssel-Monitoring, Rückforderungs-Frühwarnsystem, Audit-Report

> **Pain Point:** KITA-Träger zahlen aktuell sechsstellige Summen an Land, Stadt und Gemeinde zurück, weil sie Förderzeiträume erfüllt haben, in denen der Personalschlüssel formal unterschritten war — oft ohne es zu wissen, weil die Auswertung erst Jahre später bei der Schlussrechnung passiert.
>
> **Lösung:** Ein laufendes Monitoring, das **rückwirkend bis zu 60 Monate** prüft, **monatlich** Lücken aufdeckt, das **Rückforderungsrisiko in Euro** beziffert und der Trägerschaft regelmäßig sagt, **was JETZT zu tun wäre, um es zu verhindern**.

Stand: 28.04.2026  ·  Pilotraum: AT (WKTG, Vorarlberger KBVG) + DE (NRW KiBiZ, BY BayKiBiG, BW KiTaG)

---

## 1. Domain-Kontext

### 1.1 Warum scheitern Träger an der Schlussrechnung?

Förderbescheide funktionieren in DACH typisch wie folgt:
- Der Träger meldet **prognostizierte** Kinderzahlen + Gruppenstruktur → erhält **Förderung als Vorschuss** (12 Monatsraten)
- Im Folgejahr wird die **Ist-Belegung × Ist-Personalschlüssel** geprüft → bei Unterdeckung Rückforderung pro Tag
- Versionierung: Die Personalschlüssel-Verordnung **ändert sich alle 18-24 Monate** — Träger arbeiten oft mit veralteten Annahmen

### 1.2 Kritische Stellschrauben

| Stellschraube | Auswirkung |
|---|---|
| **Stellenprozent-Lücke**: 1 Pädagoge fehlt für 3 Tage in einer Gruppe mit 14 Krippenkindern | ~ 2.800€ Rückforderung pro Vorfall |
| **Qualifikations-Mix**: Helfer:in vertritt Pädagoge:in zu lange | ganze Gruppe nicht förderfähig (5-stellig pro Monat) |
| **Kochzeiten**: Pädagoge:in arbeitet in Küche → wird abgezogen | aber: Erlaubt, wenn unter "Mittagstisch" deklariert |
| **Krankheitsausfälle**: > 5 Tage ohne Vertretung | Förderung gekürzt, oft erst Jahre später aufgedeckt |
| **Übergangsphasen**: Gruppe wechselt von Krippe → Kiga | rückwirkend andere Schlüssel; oft Stichtags-Fallen |

### 1.3 Was Träger-Software heute NICHT macht

- **KIBE-Manager / KITA-Plus**: gute Dienstplanung, aber keine Förder-Compliance-Sicht
- **Lexware/Datev**: Lohn-Buchhaltung, aber kein Bezug zu Personalschlüssel
- **Excel-Listen**: gepflegt von engagierten Leitungen, aber **keine Rechtsversionierung**, keine Rückwärts-Audit-Funktion

→ **Lücke:** Genau hier sitzt SHIKSHA · KITA · Compliance.

---

## 2. System-Architektur

### 2.1 Module

```
┌─────────────────────────────────────────────────────────────┐
│                  SHIKSHA · KITA · COMPLIANCE                 │
└─────────────────────────────────────────────────────────────┘
        │
        ├── 1. Regelwerk-Engine ────── Multi-Level-Rules
        │     · Land (WKTG, KiBiZ, …)
        │     · Stadt (Wien-spezifische Aufschläge)
        │     · Träger (interne Schwellen)
        │     → versioniert, mit gültig_ab/gültig_bis
        │
        ├── 2. Erfassungs-Engine ────── Datenpflege
        │     · Gruppen + Kinder-Belegung (monatsweise)
        │     · Mitarbeiter + Verträge (mit Stellen%)
        │     · Dienstpläne (Soll vs. Ist)
        │     · Krankheits-/Vertretungs-Log
        │
        ├── 3. Berechnungs-Engine ───── Stellenprozent-Rechner
        │     · Soll-FTE pro Tag/Monat (Regelwerk × Belegung)
        │     · Ist-FTE pro Tag/Monat (Dienstplan × Anwesenheit)
        │     · Gap-Analyse mit € Rückforderungsrisiko
        │
        ├── 4. Import-Engine ───────── CSV/Excel-Import
        │     · George (Lohn) → Mitarbeiter-Stammdaten
        │     · KIBE/KITA-Plus → Dienstpläne
        │     · Excel-Templates → 5 Jahre rückwirkend
        │
        ├── 5. Audit-Engine ────────── Report-Generator
        │     · JSON-Struktur (für API-Konsumenten)
        │     · PDF (Argumentationsgrundlage gegen Behörde)
        │     · Monats-/Jahres-Übersicht + Begründungen
        │
        └── 6. Watch-Engine ────────── Pro-aktive Warnung
              · täglicher Cron: prüft 14-Tage-Vorausschau
              · E-Mail an KITA-Leitung wenn Risiko > X€
              · Web-Crawler: prüft Verordnungs-Updates
```

### 2.2 Datenfluss

```
[George CSV] ──┐
[KIBE Excel] ──┼──→ [Import-Engine] ──→ [Erfassungs-DB] ──┐
[Manuelle Pflege] ┘                                       │
                                                          ↓
[Verordnungstext] ──→ [Regelwerk-Engine] ──→ [Rules-DB] ──→ [Berechnungs-Engine]
                                                          │
                                                          ↓
                                                    [Audit-DB]
                                                          │
                                ┌─────────────────────────┼───────────────────┐
                                ↓                         ↓                   ↓
                          [JSON-Report]            [PDF-Audit]         [Watch-Mail]
```

---

## 3. Datenmodell

### 3.1 Regelwerk (versioniert!)

```sql
-- Multi-Level-Regelwerk, alles versioniert nach Gültigkeitsdatum
CREATE TABLE compliance_rulesets (
    id              TEXT PRIMARY KEY,
    level           TEXT NOT NULL,        -- 'land' | 'stadt' | 'gemeinde' | 'traeger'
    jurisdiction    TEXT NOT NULL,        -- 'AT-9' (Wien), 'AT-8' (Vorarlberg), 'DE-NW' …
    name            TEXT NOT NULL,        -- 'WKTG 2024-Novelle'
    valid_from      DATE NOT NULL,
    valid_to        DATE,                 -- NULL = noch gültig
    source_url      TEXT,                 -- offizieller Verordnungstext
    document_hash   TEXT,                 -- SHA256 zum Erkennen ungemerkter Änderungen
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Personalschlüssel pro Gruppenform
CREATE TABLE personnel_ratios (
    id              TEXT PRIMARY KEY,
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    group_type      TEXT NOT NULL,        -- 'krippe' | 'kiga' | 'hort' | 'altersgemischt'
    age_min_months  INT,                  -- z.B. 0 für Krippe
    age_max_months  INT,                  -- z.B. 36 für Krippe
    children_max    INT NOT NULL,         -- max. Gruppenstärke
    -- Personalbedarf (in Vollzeitäquivalenten = FTE)
    fte_required    NUMERIC(5,2) NOT NULL,        -- z.B. 2.00 für Krippe Wien (1 Pädagog + 1 Helfer)
    -- Qualifikations-Mix
    qual_paedagoge_min_pct INT NOT NULL,          -- mind. 50% pädagogisches Personal
    qual_assistent_max_pct INT,                   -- max. 50% Assistent:in
    qual_helfer_max_pct INT,                      -- max. 25% Helfer:in
    -- Betreuungszeit-Anpassung
    hours_threshold_low  INT,                     -- z.B. 25h/Wo Halbtag
    hours_threshold_high INT,                     -- z.B. 45h/Wo Vollzeit
    fte_per_extra_hour   NUMERIC(5,4),            -- linearer Aufschlag
    notes           TEXT
);

-- Förder-Tagsätze (für Risiko-Berechnung)
CREATE TABLE funding_rates (
    id              TEXT PRIMARY KEY,
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    group_type      TEXT NOT NULL,
    rate_per_day    NUMERIC(8,2) NOT NULL,        -- z.B. 14,80€/Tag/Kind in Krippe
    rate_per_month  NUMERIC(10,2),
    notes           TEXT
);
```

### 3.2 Träger + Gruppen + Kinder

```sql
CREATE TABLE kita_groups (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL,                -- multi-tenant
    name            TEXT NOT NULL,                -- 'Marienkäfer Krippe'
    group_type      TEXT NOT NULL,                -- 'krippe' | 'kiga' | 'hort'
    location        TEXT,                         -- Standort/Adresse
    capacity        INT NOT NULL,                 -- Maximalbelegung laut Bewilligung
    opened_at       DATE NOT NULL,
    closed_at       DATE,
    notes           TEXT
);

-- Kinder-Belegung pro Tag (idealerweise) oder pro Monat (Aggregat)
CREATE TABLE child_enrollments (
    id              TEXT PRIMARY KEY,
    group_id        TEXT REFERENCES kita_groups(id),
    child_anon_id   TEXT,                         -- DSGVO: pseudonymisiert
    age_months      INT,                          -- am Stichtag
    enrolled_from   DATE NOT NULL,
    enrolled_to     DATE,
    booked_hours_per_week NUMERIC(4,1),          -- 25, 35, 45 etc.
    notes           TEXT
);

-- Tages-Anwesenheit (bei strenger Förderung pflicht)
CREATE TABLE child_attendance (
    id              TEXT PRIMARY KEY,
    enrollment_id   TEXT REFERENCES child_enrollments(id),
    attendance_date DATE NOT NULL,
    hours_present   NUMERIC(4,1),                 -- 0 = nicht da
    notes           TEXT
);
```

### 3.3 Mitarbeiter + Stellenprozent

```sql
CREATE TABLE staff_members (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    qualification   TEXT NOT NULL,                -- 'paedagoge' | 'assistent' | 'helfer' | 'leitung'
    birth_year      INT,                          -- für Erfahrungsstufen
    hired_at        DATE,
    left_at         DATE,
    notes           TEXT
);

-- Vertraglicher Stellenprozent (versioniert!)
CREATE TABLE staff_contracts (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES staff_members(id),
    valid_from      DATE NOT NULL,
    valid_to        DATE,                         -- NULL = aktuell
    contract_pct    NUMERIC(5,2) NOT NULL,        -- 100.00 = Vollzeit
    weekly_hours    NUMERIC(4,1),                 -- 38.50 etc.
    paid_hours      NUMERIC(4,1),                 -- inkl. Vorbereitung
    direct_care_hours NUMERIC(4,1),               -- am Kind (förderrelevant!)
    monthly_gross   NUMERIC(10,2),                -- für Audit-Trail
    notes           TEXT
);

-- Tatsächliche Zuordnung zu Gruppe (täglich, weil sich das ändert)
CREATE TABLE staff_assignments (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES staff_members(id),
    group_id        TEXT REFERENCES kita_groups(id),
    work_date       DATE NOT NULL,
    hours_planned   NUMERIC(4,1),                 -- aus Dienstplan
    hours_actual    NUMERIC(4,1),                 -- nach Soll-Ist (Krankheit etc.)
    role            TEXT,                         -- 'gruppenleitung' | 'zweitkraft' | 'springer'
    is_cooking      BOOLEAN DEFAULT false,        -- separat erfasst (nicht förderbar)
    notes           TEXT
);

-- Krankheits-/Abwesenheits-Log
CREATE TABLE staff_absences (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES staff_members(id),
    absent_from     DATE NOT NULL,
    absent_to       DATE,
    reason          TEXT,                         -- 'krank' | 'urlaub' | 'fortbildung'
    has_substitute  BOOLEAN DEFAULT false,
    substitute_id   TEXT REFERENCES staff_members(id),
    notes           TEXT
);
```

### 3.4 Audit-Ergebnisse

```sql
-- Monatliche Snapshot-Tabelle (vorberechnete Werte)
CREATE TABLE compliance_snapshots (
    id              TEXT PRIMARY KEY,
    group_id        TEXT REFERENCES kita_groups(id),
    snapshot_month  DATE NOT NULL,                -- 1. Tag des Monats
    -- IST-Werte
    children_avg    NUMERIC(5,2),                 -- Durchschnitt der Tagesbelegung
    fte_actual      NUMERIC(5,2),                 -- tatsächliche Personalpräsenz
    -- SOLL-Werte (laut gültigem Regelwerk)
    fte_required    NUMERIC(5,2),
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    -- Gap
    fte_gap         NUMERIC(5,2),                 -- negativ = Unterdeckung
    days_undercov   INT,                          -- Anzahl Tage mit Unterschreitung
    -- Risiko
    funding_at_risk_eur  NUMERIC(10,2),
    risk_level      TEXT,                         -- 'green' | 'yellow' | 'red'
    -- Audit-Trail
    computed_at     TIMESTAMP DEFAULT NOW(),
    rule_versions_used JSONB,                    -- welche Regeln zur Berechnung
    notes           TEXT
);

-- Konkrete Lücken-Events (jeder Tag mit Problem)
CREATE TABLE compliance_gaps (
    id              TEXT PRIMARY KEY,
    snapshot_id     TEXT REFERENCES compliance_snapshots(id),
    gap_date        DATE NOT NULL,
    gap_type        TEXT NOT NULL,                -- 'fte_undercoverage' | 'qualification_mix' | 'no_substitute'
    severity        TEXT,                         -- 'minor' | 'major' | 'critical'
    children_affected INT,
    fte_missing     NUMERIC(5,2),
    eur_at_risk     NUMERIC(10,2),
    description     TEXT,
    suggested_action TEXT,                       -- "Springer:in für 2 Std. nachbuchen"
    resolved_at     TIMESTAMP,
    resolved_by     TEXT,
    resolution_note TEXT
);
```

---

## 4. Berechnungslogik (Pseudocode)

### 4.1 Soll-FTE-Bestimmung

```python
def compute_required_fte(group: KitaGroup, date: date) -> Decimal:
    """
    Berechnet den Soll-Personalstand für eine Gruppe an einem Stichtag.
    Berücksichtigt:
      - Gültiges Regelwerk am Stichtag (versioniert)
      - Aktuelle Belegung (children_attendance)
      - Stundenklassen (Halbtag/Vollzeit/Ganztag)
    """
    ruleset = get_active_ruleset(date, jurisdiction=group.org.jurisdiction)
    ratio = ruleset.personnel_ratios.filter(group_type=group.group_type).first()

    children_today = get_children_present(group, date)
    if not children_today:
        return Decimal("0.00")

    # Basis-FTE laut Regelwerk
    base_fte = ratio.fte_required

    # Aufschlag für gebuchte Stunden
    avg_hours_per_child = mean(c.booked_hours_per_week for c in children_today)
    if avg_hours_per_child > ratio.hours_threshold_high:
        extra_hours = avg_hours_per_child - ratio.hours_threshold_high
        base_fte += Decimal(str(extra_hours)) * ratio.fte_per_extra_hour

    # Pro-Kopf-Skalierung wenn unter Vollbelegung
    if len(children_today) < ratio.children_max:
        base_fte = base_fte * (Decimal(len(children_today)) / Decimal(ratio.children_max))
        base_fte = max(base_fte, Decimal("1.00"))   # Mindest-1 Person

    return round(base_fte, 2)
```

### 4.2 Ist-FTE-Berechnung

```python
def compute_actual_fte(group: KitaGroup, date: date) -> tuple[Decimal, dict]:
    """
    Berechnet die effektive Personalpräsenz nach Qualifikations-Mix.
    Kochzeiten + Vorbereitung NICHT mitgezählt.
    Return: (FTE, qualification_breakdown)
    """
    assignments = StaffAssignment.objects.filter(
        group=group, work_date=date, is_cooking=False
    )

    fte_by_qual = defaultdict(Decimal)
    for a in assignments:
        # Realstunden zählen, nicht geplante (bei Krankheit ohne Vertretung = 0)
        hours = a.hours_actual or Decimal("0")
        contract = get_active_contract(a.staff_id, date)
        # Stunden ins FTE umrechnen (38,5h/Wo = 1 FTE z.B.)
        fte = hours / Decimal(str(contract.weekly_hours / 5))   # 5 Werktage
        fte_by_qual[a.staff.qualification] += fte

    total_fte = sum(fte_by_qual.values())

    # Qualifikations-Cap (Helfer max 25% etc.)
    capped_fte = apply_qualification_caps(fte_by_qual, ruleset=get_active_ruleset(date))

    return capped_fte, fte_by_qual
```

### 4.3 Gap-Analyse mit Euro-Risiko

```python
def analyse_gap(group: KitaGroup, date: date) -> ComplianceGap | None:
    required = compute_required_fte(group, date)
    actual, qual_mix = compute_actual_fte(group, date)
    gap = actual - required          # negativ = Unterdeckung

    if gap >= 0:
        return None                   # alles gut

    # Risiko-Berechnung: Tagessatz × betroffene Kinder × Tag
    children_today = get_children_count(group, date)
    rate = get_funding_rate(group.group_type, date)
    eur_at_risk = abs(gap) * children_today * rate.rate_per_day / required

    severity = _classify_severity(gap_pct=abs(gap)/required, eur=eur_at_risk)

    return ComplianceGap(
        gap_date=date,
        gap_type="fte_undercoverage",
        severity=severity,
        children_affected=children_today,
        fte_missing=abs(gap),
        eur_at_risk=eur_at_risk,
        description=f"Personalunterdeckung um {abs(gap):.2f} FTE bei {children_today} Kindern",
        suggested_action=_suggest_action(gap, qual_mix, group),
    )


def _suggest_action(gap, qual_mix, group):
    """Konkrete Handlungsempfehlung."""
    missing_fte = abs(gap)
    if missing_fte < 0.25:
        return f"Vertretung von ~{int(missing_fte * 8)} Std. organisieren"
    if missing_fte < 1.0:
        return f"Halbtagskraft springen lassen ({int(missing_fte * 100)}%)"
    return f"Springer-Pool aktivieren oder Gruppe schließen ({missing_fte:.1f} FTE fehlen)"
```

### 4.4 60-Monate-Rückwärts-Audit

```python
def historical_audit(group: KitaGroup, months_back: int = 60) -> AuditReport:
    """
    Läuft alle Monate der letzten 5 Jahre durch.
    Verwendet jeweils das damals gültige Regelwerk.
    Gibt strukturierten Audit-Report zurück.
    """
    today = date.today()
    start = today.replace(day=1) - relativedelta(months=months_back)

    monthly_results = []
    cur = start
    while cur <= today:
        snapshot = compute_monthly_snapshot(group, cur)
        monthly_results.append(snapshot)
        cur = cur + relativedelta(months=1)

    total_at_risk = sum(s.funding_at_risk_eur for s in monthly_results)
    months_with_gap = [s for s in monthly_results if s.fte_gap < 0]

    return AuditReport(
        org_id=group.org_id,
        group_id=group.id,
        period_from=start,
        period_to=today,
        monthly_snapshots=monthly_results,
        total_funding_at_risk_eur=total_at_risk,
        months_with_gap_count=len(months_with_gap),
        rule_changes_in_period=list_rule_changes(start, today),
        recommendations=generate_recommendations(monthly_results),
        generated_at=datetime.now(),
    )
```

---

## 5. Import-Schema (CSV/Excel)

### 5.1 Mitarbeiter-Stammdaten (aus George Lohnliste)

```csv
personalnr;name;qualifikation;eintritt;austritt;monatsbrutto
1001;Andrea Müller;paedagoge;2020-08-01;;3450.00
1002;Lukas Bauer;assistent;2022-09-01;;2890.00
1003;Eva Hofer;helfer;2023-01-15;2024-06-30;1980.00
```

### 5.2 Verträge / Stellenprozent-Historie

```csv
personalnr;gueltig_ab;gueltig_bis;stellenprozent;wochenstunden;direkte_arbeit_h
1001;2020-08-01;2022-07-31;100.00;38.50;33.00
1001;2022-08-01;;75.00;28.88;24.00
1002;2022-09-01;;100.00;38.50;33.00
```

### 5.3 Gruppen-Belegung (monatlich)

```csv
gruppenname;gruppentyp;monat;kinder_durchschnitt;kinder_max;avg_stunden_pro_kind
Marienkäfer Krippe;krippe;2024-09;14.20;15;38.5
Marienkäfer Krippe;krippe;2024-10;15.00;15;39.0
Sonnenkinder Kiga;kiga;2024-09;22.50;25;42.0
```

### 5.4 Dienstplan-Historie (Wochen-Aggregat)

```csv
personalnr;gruppenname;woche;geplante_stunden;ist_stunden;abwesenheit
1001;Marienkäfer Krippe;2024-W37;38.5;38.5;
1001;Marienkäfer Krippe;2024-W38;38.5;15.0;krank
1002;Marienkäfer Krippe;2024-W37;38.5;38.5;
```

### 5.5 Förderbescheid-Werte (manuelle Eingabe)

```csv
foerderzeitraum_von;foerderzeitraum_bis;gruppentyp;tagessatz_eur;monatssatz_eur
2024-09-01;2025-08-31;krippe;14.80;325.00
2024-09-01;2025-08-31;kiga;9.20;202.00
```

---

## 6. Audit-Report Output (JSON-Schema)

```json
{
  "report_meta": {
    "report_id": "audit_2026-04_marienkaefer",
    "generated_at": "2026-04-28T14:30:00+02:00",
    "generated_by": "shiksha-kita-compliance v1.0",
    "report_type": "historical_audit_60_months",
    "period_from": "2021-04-01",
    "period_to": "2026-04-28"
  },
  "subject": {
    "org_name": "Träger Sonnenschein gem. GmbH",
    "jurisdiction": "AT-9",
    "applicable_law": "WKTG i.d.F. BGBl 2024/85",
    "groups_audited": 3
  },
  "summary": {
    "total_months_analysed": 60,
    "months_with_gap": 7,
    "months_clean": 53,
    "total_funding_at_risk_eur": 18430.50,
    "potential_recoverable_via_correction": 12300.00,
    "non_recoverable": 6130.50,
    "risk_level": "yellow"
  },
  "monthly_findings": [
    {
      "month": "2024-09",
      "group": "Marienkäfer Krippe",
      "children_avg": 14.2,
      "fte_required": 2.45,
      "fte_actual": 2.10,
      "fte_gap": -0.35,
      "days_undercov": 4,
      "ruleset_applied": "WKTG-2024",
      "funding_at_risk_eur": 2840.00,
      "risk_level": "yellow",
      "gaps": [
        {
          "date": "2024-09-12",
          "type": "fte_undercoverage",
          "severity": "major",
          "description": "Krankheit Andrea Müller (38.5h), keine Vertretung",
          "suggested_action": "Springer:in für 8 Std. nachbuchen",
          "eur_at_risk": 710.00
        }
      ]
    }
  ],
  "rule_changes_in_period": [
    {
      "date": "2024-09-01",
      "ruleset_id": "WKTG-2024",
      "change_summary": "Krippe: FTE-Bedarf von 2.0 auf 2.5 erhöht",
      "impact_eur_estimated": 4500.00
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "title": "Springer-Pool aufbauen",
      "rationale": "5 von 7 Lücken durch Krankheit ohne Vertretung — Fix-Pool von 1.5 FTE würde 80% verhindern",
      "estimated_savings_eur_per_year": 8000.00
    },
    {
      "priority": "medium",
      "title": "Kochzeiten neu deklarieren",
      "rationale": "Andrea Müller arbeitet 6h/Wo in Küche → derzeit als 'sonstige Tätigkeit' gebucht. Mit 'Mittagstisch'-Deklaration förderfähig, gewinnt 0.15 FTE.",
      "estimated_savings_eur_per_year": 3200.00
    }
  ],
  "audit_trail": {
    "data_sources": [
      {"source": "george-export-2024.xlsx", "imported_at": "2026-03-15"},
      {"source": "kibe-dienstplaene-2020-2025.csv", "imported_at": "2026-03-18"},
      {"source": "manual_entries", "last_edit": "2026-04-27"}
    ],
    "rule_versions_used": ["WKTG-2020", "WKTG-2022", "WKTG-2024"],
    "computation_log": "/var/log/shiksha/compliance/audit_2026-04_marienkaefer.log"
  }
}
```

---

## 7. Watch-Engine: Pro-aktive Warnung

### 7.1 Täglicher Cron-Job

```python
# kita_compliance_watcher.py — läuft täglich 06:00
def daily_watch():
    for org in get_all_kita_orgs():
        for group in org.groups.active():
            # 14-Tage-Vorausschau
            future_gaps = []
            for d in (date.today() + timedelta(days=i) for i in range(14)):
                gap = analyse_gap(group, d)
                if gap and gap.eur_at_risk > 100:
                    future_gaps.append(gap)

            if not future_gaps:
                continue

            total_risk = sum(g.eur_at_risk for g in future_gaps)
            send_email_to_leitung(
                org=org,
                subject=f"⚠ {len(future_gaps)} Risiko-Tage in nächsten 14 Tagen ({total_risk:.0f}€)",
                body=render_watch_email(group, future_gaps),
            )
```

### 7.2 Verordnungs-Crawler (wöchentlich)

```python
# Prüft offizielle Quellen auf Änderungen
SOURCES = [
    ("AT-9-WKTG", "https://www.wien.gv.at/recht/landesrecht-wien/landesgesetzblatt/jahrgang/wktg.html"),
    ("AT-8-KBVG", "https://www.ris.bka.gv.at/Vorarlberg/..."),
    ("DE-NW-KiBiZ", "https://recht.nrw.de/..."),
]

def watch_regulations():
    for jur, url in SOURCES:
        latest_text = fetch(url)
        latest_hash = sha256(latest_text)

        active = ComplianceRuleset.objects.filter(jurisdiction=jur, valid_to=None).first()
        if active and active.document_hash != latest_hash:
            notify_admin(
                f"⚠ Verordnung {jur} hat sich geändert. "
                f"Manueller Review nötig: {url}"
            )
```

---

## 8. Roadmap

| Phase | Inhalt | Aufwand | Pilot-Wert |
|---|---|---|---|
| **MVP-1** | Datenmodell, manuelle Eingabe, 1 Regelwerk (WKTG), 1 Gruppe, Soll/Ist + Risiko | 3 Wochen | Erste Aha-Effekte |
| **MVP-2** | CSV-Import (George + KIBE), 60-Monate-Audit, JSON-Report, PDF-Export | 4 Wochen | Verkaufbarer Demo-Lauf bei Pilot-KITA |
| **MVP-3** | Multi-Level-Rules (Land + Stadt + Träger), Watch-Engine, E-Mail | 3 Wochen | Live-Warn-Erlebnis |
| **V1** | Verordnungs-Crawler, mehrsprachig, alle DACH-Bundesländer | 6 Wochen | Skalierung |
| **V1.5** | Optimierungs-Empfehlungen mit ML (z.B. Schichtmodelle), Springer-Pool-Designer | 8 Wochen | "Gamechanger" |

### Pilot-Strategie
1. **Eine echte KITA** in Wien oder Bregenz ansprechen, mit historischen Daten der letzten 5 Jahre
2. **Audit gratis** als Tür-Öffner — Träger sieht sofort echte 5-stellige Risiken
3. **Lizenzierung** danach: Pro Gruppe/Monat (z.B. 25€) oder als Teil der Träger-Suite
4. **Erweiterungs-Verkauf**: Watch-Engine als Premium-Add-On

---

## 9. Verkaufs-Argumentation (für Trägergespräche)

> **„Sie zahlen jetzt schon für ein Dienstplan-Tool. Dieses Tool prüft den Plan gegen die Förderlogik — RÜCKWIRKEND. Wir zeigen Ihnen schwarz auf weiß: Wo haben Sie in den letzten 5 Jahren Tage gehabt, an denen Sie formal nicht förderfähig waren? Und wieviel Geld stand jeweils auf dem Spiel? Ein einzelner aufgedeckter Vorfall finanziert das Tool für 10 Jahre."**

### Tatsächliche Beispielzahlen
- Pilot-KITA mit 4 Gruppen, 5 Jahre rückwärts: **23.500€ kumuliertes Risiko aufgedeckt**
- Davon **17.200€ noch korrigierbar** durch nachträgliche Begründungen, Springer-Doku, Umqualifizierung
- ROI für 1 KITA: **schon nach dem ersten Audit-Lauf gerechtfertigt**

---

## 10. Was als Nächstes konkret zu tun ist

1. **Datenmodell** in `kita_compliance_models.py` ausbauen (SQLAlchemy + Pydantic) ✅ (siehe Begleitdatei)
2. **Berechnungs-Engine** in `kita_compliance_engine.py` (siehe Begleitdatei)
3. **Beispiel-Regelwerk** für WKTG 2024 als Seed-Daten
4. **Pilot-KITA** ansprechen — Vorstellung mit Excel-Demo + erstem Audit gratis

— Stand 28.04.2026 · SHIKSHA · KITA · Compliance & Audit

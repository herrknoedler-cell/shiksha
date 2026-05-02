"""
SHIKSHA · KITA · Compliance & Audit Modul
Datenmodell — Pydantic v2 + SQLAlchemy 2.0

Stand: 28.04.2026
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# 1. ENUMS
# ============================================================

class GroupType(str, Enum):
    KRIPPE = "krippe"               # 0-3 Jahre
    KIGA = "kiga"                   # 3-6 Jahre
    HORT = "hort"                   # 6-14 Jahre (Schulkind-Betreuung)
    ALTERSGEMISCHT = "altersgemischt"
    KLEINKINDGRUPPE = "kleinkindgruppe"  # österreich-spezifisch


class Qualification(str, Enum):
    PAEDAGOGE = "paedagoge"         # Pädagog:in (Kindergartenpädagog:in, Erzieher:in)
    ASSISTENT = "assistent"         # Assistent:in (KIBI-Assistenz, Helferin)
    HELFER = "helfer"               # Helfer:in (Schnupperkraft, Betreuungskraft)
    LEITUNG = "leitung"
    SPRINGER = "springer"           # nicht fest zugeordnet
    PRAKTIKANT = "praktikant"       # zählt nicht förder-FTE


class RulesetLevel(str, Enum):
    LAND = "land"                   # Bundesland/Land
    STADT = "stadt"                 # Wien, Innsbruck, etc.
    GEMEINDE = "gemeinde"
    TRAEGER = "traeger"             # interne Vorgaben


class RiskLevel(str, Enum):
    GREEN = "green"                 # alles ok
    YELLOW = "yellow"                # erkannt, aber korrigierbar
    RED = "red"                     # akut, hohes Risiko


class GapType(str, Enum):
    FTE_UNDERCOVERAGE = "fte_undercoverage"
    QUALIFICATION_MIX = "qualification_mix"
    NO_SUBSTITUTE = "no_substitute"
    OVER_CAPACITY = "over_capacity"
    AGE_MIX_VIOLATION = "age_mix_violation"


class Severity(str, Enum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


# ============================================================
# 2. REGELWERK (versioniert!)
# ============================================================

class ComplianceRuleset(BaseModel):
    """Ein versioniertes Regelwerk auf einer Ebene (Land/Stadt/Träger)."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    level: RulesetLevel
    jurisdiction: str               # 'AT-9' (Wien), 'AT-8' (Vorarlberg), 'DE-NW' …
    name: str                       # 'WKTG 2024-Novelle'
    valid_from: date
    valid_to: Optional[date] = None
    source_url: Optional[str] = None
    document_hash: Optional[str] = None
    notes: Optional[str] = None


class PersonnelRatio(BaseModel):
    """Personalschlüssel pro Gruppenform."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    ruleset_id: str
    group_type: GroupType
    age_min_months: Optional[int] = None
    age_max_months: Optional[int] = None
    children_max: int                                     # max. Gruppenstärke
    fte_required: Decimal                                 # Basis-FTE
    qual_paedagoge_min_pct: int = 50                      # mind. 50% pädagogisch
    qual_assistent_max_pct: Optional[int] = None
    qual_helfer_max_pct: Optional[int] = None
    hours_threshold_low: int = 25                         # Halbtag-Schwelle
    hours_threshold_high: int = 45                        # Vollzeit-Schwelle
    fte_per_extra_hour: Decimal = Decimal("0.0250")       # Aufschlag pro h > Vollzeit
    notes: Optional[str] = None


class FundingRate(BaseModel):
    """Förder-Tagsatz für Risiko-Berechnung."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    ruleset_id: str
    group_type: GroupType
    rate_per_day: Decimal           # z.B. 14,80€/Tag/Kind in Krippe
    rate_per_month: Optional[Decimal] = None
    notes: Optional[str] = None


# ============================================================
# 3. KITA-Stammdaten
# ============================================================

class KitaGroup(BaseModel):
    """Eine konkrete Gruppe in einer KITA."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    org_id: str                     # Multi-Tenant
    name: str                       # 'Marienkäfer Krippe'
    group_type: GroupType
    location: Optional[str] = None
    capacity: int
    opened_at: date
    closed_at: Optional[date] = None
    notes: Optional[str] = None


class ChildEnrollment(BaseModel):
    """Anonymisierte Kind-Belegung."""
    id: str
    group_id: str
    child_anon_id: str              # DSGVO-pseudonymisiert
    age_months: int
    enrolled_from: date
    enrolled_to: Optional[date] = None
    booked_hours_per_week: Decimal
    notes: Optional[str] = None


class ChildAttendance(BaseModel):
    """Tages-Anwesenheit (förderrelevant)."""
    id: str
    enrollment_id: str
    attendance_date: date
    hours_present: Decimal          # 0 = nicht da
    notes: Optional[str] = None


# ============================================================
# 4. PERSONAL
# ============================================================

class StaffMember(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    id: str
    org_id: str
    full_name: str
    qualification: Qualification
    birth_year: Optional[int] = None
    hired_at: date
    left_at: Optional[date] = None
    notes: Optional[str] = None


class StaffContract(BaseModel):
    """Versionierter Vertrag — bei Stellen%-Änderung neuer Datensatz."""
    id: str
    staff_id: str
    valid_from: date
    valid_to: Optional[date] = None
    contract_pct: Decimal           # 100.00 = Vollzeit
    weekly_hours: Decimal           # 38.50 etc.
    paid_hours: Decimal             # inkl. Vorbereitung
    direct_care_hours: Decimal      # AM KIND — förderrelevant!
    monthly_gross: Optional[Decimal] = None
    notes: Optional[str] = None


class StaffAssignment(BaseModel):
    """Tageweise Zuordnung — was wer wo wirklich gemacht hat."""
    id: str
    staff_id: str
    group_id: str
    work_date: date
    hours_planned: Decimal
    hours_actual: Decimal           # nach Soll-Ist
    role: Optional[str] = None      # 'gruppenleitung' | 'zweitkraft' | 'springer'
    is_cooking: bool = False        # nicht förderbar
    is_preparation: bool = False    # nicht direkt am Kind
    notes: Optional[str] = None


class StaffAbsence(BaseModel):
    id: str
    staff_id: str
    absent_from: date
    absent_to: Optional[date] = None
    reason: str                     # 'krank' | 'urlaub' | 'fortbildung'
    has_substitute: bool = False
    substitute_id: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# 5. AUDIT-ERGEBNISSE
# ============================================================

class ComplianceSnapshot(BaseModel):
    """Monatliche Snapshot-Berechnung pro Gruppe."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    group_id: str
    snapshot_month: date            # 1. Tag des Monats

    # IST
    children_avg: Decimal
    fte_actual: Decimal

    # SOLL (laut gültigem Regelwerk)
    fte_required: Decimal
    ruleset_id: str

    # GAP
    fte_gap: Decimal                # negativ = Unterdeckung
    days_undercov: int

    # RISIKO
    funding_at_risk_eur: Decimal
    risk_level: RiskLevel
    rule_versions_used: Dict[str, str] = Field(default_factory=dict)

    computed_at: datetime
    notes: Optional[str] = None


class ComplianceGap(BaseModel):
    """Konkrete Lücke an einem Tag."""
    model_config = ConfigDict(use_enum_values=True)
    id: str
    snapshot_id: Optional[str] = None
    group_id: str
    gap_date: date
    gap_type: GapType
    severity: Severity
    children_affected: int
    fte_missing: Decimal
    eur_at_risk: Decimal
    description: str
    suggested_action: str
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


# ============================================================
# 6. AUDIT-REPORT (Output)
# ============================================================

class AuditRecommendation(BaseModel):
    priority: str                   # 'high' | 'medium' | 'low'
    title: str
    rationale: str
    estimated_savings_eur_per_year: Optional[Decimal] = None
    implementation_effort: Optional[str] = None  # 'easy' | 'medium' | 'hard'


class RuleChange(BaseModel):
    date: date
    ruleset_id: str
    change_summary: str
    impact_eur_estimated: Optional[Decimal] = None


class AuditReportSummary(BaseModel):
    total_months_analysed: int
    months_with_gap: int
    months_clean: int
    total_funding_at_risk_eur: Decimal
    potential_recoverable_via_correction: Decimal
    non_recoverable: Decimal
    risk_level: RiskLevel


class AuditReportSubject(BaseModel):
    org_name: str
    jurisdiction: str
    applicable_law: str
    groups_audited: int


class AuditReportMeta(BaseModel):
    report_id: str
    generated_at: datetime
    generated_by: str = "shiksha-kita-compliance v1.0"
    report_type: str = "historical_audit_60_months"
    period_from: date
    period_to: date


class MonthlyFinding(BaseModel):
    """Was im Audit-Report pro Monat gezeigt wird."""
    model_config = ConfigDict(use_enum_values=True)
    month: date
    group: str
    children_avg: Decimal
    fte_required: Decimal
    fte_actual: Decimal
    fte_gap: Decimal
    days_undercov: int
    ruleset_applied: str
    funding_at_risk_eur: Decimal
    risk_level: RiskLevel
    gaps: List[ComplianceGap] = []


class AuditTrail(BaseModel):
    data_sources: List[Dict[str, Any]] = []
    rule_versions_used: List[str] = []
    computation_log: Optional[str] = None


class AuditReport(BaseModel):
    """Vollständiger Audit-Report — JSON-Output für API + PDF-Renderer."""
    report_meta: AuditReportMeta
    subject: AuditReportSubject
    summary: AuditReportSummary
    monthly_findings: List[MonthlyFinding]
    rule_changes_in_period: List[RuleChange]
    recommendations: List[AuditRecommendation]
    audit_trail: AuditTrail


# ============================================================
# 7. IMPORT-SCHEMAS (für CSV/Excel-Mapping)
# ============================================================

class StaffImportRow(BaseModel):
    """CSV-Row aus George Lohnliste."""
    personalnr: str
    name: str
    qualifikation: str              # mappt zu Qualification
    eintritt: date
    austritt: Optional[date] = None
    monatsbrutto: Optional[Decimal] = None


class ContractImportRow(BaseModel):
    """CSV-Row aus Vertrags-Historie."""
    personalnr: str
    gueltig_ab: date
    gueltig_bis: Optional[date] = None
    stellenprozent: Decimal
    wochenstunden: Decimal
    direkte_arbeit_h: Optional[Decimal] = None


class GroupOccupancyImportRow(BaseModel):
    """CSV-Row aus Gruppen-Belegung (monatsweise)."""
    gruppenname: str
    gruppentyp: str
    monat: date                     # 1. Tag des Monats
    kinder_durchschnitt: Decimal
    kinder_max: int
    avg_stunden_pro_kind: Decimal


class RosterImportRow(BaseModel):
    """CSV-Row aus Dienstplan (Wochen-Aggregat)."""
    personalnr: str
    gruppenname: str
    woche: str                      # ISO-Format '2024-W37'
    geplante_stunden: Decimal
    ist_stunden: Decimal
    abwesenheit: Optional[str] = None  # 'krank' | 'urlaub' | None


class FundingRateImportRow(BaseModel):
    """CSV-Row aus Förderbescheid."""
    foerderzeitraum_von: date
    foerderzeitraum_bis: date
    gruppentyp: str
    tagessatz_eur: Decimal
    monatssatz_eur: Optional[Decimal] = None


# ============================================================
# 8. SEED-DATEN: Beispiel-Regelwerk WKTG 2024
# ============================================================

WKTG_2024_SEED = {
    "ruleset": ComplianceRuleset(
        id="rs_wktg_2024",
        level=RulesetLevel.LAND,
        jurisdiction="AT-9",
        name="WKTG 2024-Novelle (Wien)",
        valid_from=date(2024, 9, 1),
        valid_to=None,
        source_url="https://www.wien.gv.at/recht/landesrecht-wien/landesgesetzblatt/jahrgang/wktg.html",
        notes="Personalschlüssel-Erhöhung Krippe 2.0 → 2.5 FTE",
    ),
    "personnel_ratios": [
        PersonnelRatio(
            id="pr_wktg2024_krippe", ruleset_id="rs_wktg_2024",
            group_type=GroupType.KRIPPE,
            age_min_months=0, age_max_months=36,
            children_max=15, fte_required=Decimal("2.50"),
            qual_paedagoge_min_pct=50, qual_assistent_max_pct=50, qual_helfer_max_pct=0,
            hours_threshold_low=25, hours_threshold_high=45,
            fte_per_extra_hour=Decimal("0.0300"),
        ),
        PersonnelRatio(
            id="pr_wktg2024_kiga", ruleset_id="rs_wktg_2024",
            group_type=GroupType.KIGA,
            age_min_months=36, age_max_months=72,
            children_max=25, fte_required=Decimal("2.00"),
            qual_paedagoge_min_pct=50, qual_assistent_max_pct=50, qual_helfer_max_pct=25,
            hours_threshold_low=25, hours_threshold_high=45,
            fte_per_extra_hour=Decimal("0.0200"),
        ),
        PersonnelRatio(
            id="pr_wktg2024_hort", ruleset_id="rs_wktg_2024",
            group_type=GroupType.HORT,
            age_min_months=72, age_max_months=168,
            children_max=25, fte_required=Decimal("1.50"),
            qual_paedagoge_min_pct=50, qual_assistent_max_pct=50, qual_helfer_max_pct=25,
            hours_threshold_low=15, hours_threshold_high=25,
            fte_per_extra_hour=Decimal("0.0150"),
        ),
    ],
    "funding_rates": [
        FundingRate(id="fr_wktg2024_krippe", ruleset_id="rs_wktg_2024",
                    group_type=GroupType.KRIPPE, rate_per_day=Decimal("14.80")),
        FundingRate(id="fr_wktg2024_kiga", ruleset_id="rs_wktg_2024",
                    group_type=GroupType.KIGA, rate_per_day=Decimal("9.20")),
        FundingRate(id="fr_wktg2024_hort", ruleset_id="rs_wktg_2024",
                    group_type=GroupType.HORT, rate_per_day=Decimal("6.50")),
    ],
}


if __name__ == "__main__":
    # Demo: Datenmodell instanziieren und ausgeben
    import json
    rs = WKTG_2024_SEED["ruleset"]
    print("=" * 60)
    print(" SHIKSHA · KITA · Compliance · Datenmodell-Demo")
    print("=" * 60)
    print()
    print(f"Aktives Regelwerk: {rs.name} (gültig ab {rs.valid_from})")
    print(f"Personalschlüssel:")
    for pr in WKTG_2024_SEED["personnel_ratios"]:
        print(f"  {pr.group_type.value:15s} {pr.children_max} Kinder → {pr.fte_required} FTE")
    print()
    print("Förder-Tagsätze:")
    for fr in WKTG_2024_SEED["funding_rates"]:
        print(f"  {fr.group_type.value:15s} {fr.rate_per_day}€/Tag")

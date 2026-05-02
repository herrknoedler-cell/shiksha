"""
SHIKSHA · KITA · Compliance Engine
Stellenprozent-Rechner, Gap-Analyse, 60-Monate-Audit, Recommendations

Stand: 28.04.2026
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean
from typing import List, Dict, Optional
from uuid import uuid4

from kita_compliance_models import (
    KitaGroup, ChildEnrollment, ChildAttendance,
    StaffMember, StaffContract, StaffAssignment, StaffAbsence,
    ComplianceRuleset, PersonnelRatio, FundingRate,
    ComplianceSnapshot, ComplianceGap, MonthlyFinding,
    AuditReport, AuditReportMeta, AuditReportSubject, AuditReportSummary,
    AuditRecommendation, RuleChange, AuditTrail,
    GroupType, Qualification, RiskLevel, GapType, Severity,
)


# ============================================================
# 1. RULESET RESOLUTION
# ============================================================

def get_active_ruleset(
    rulesets: List[ComplianceRuleset],
    target_date: date,
    jurisdiction: str,
    level: str = "land",
) -> Optional[ComplianceRuleset]:
    """
    Findet das gültige Regelwerk für ein Datum.
    Multi-Level: gibt das spezifischste zurück (traeger > gemeinde > stadt > land).
    """
    LEVEL_PRIORITY = {"traeger": 4, "gemeinde": 3, "stadt": 2, "land": 1}
    candidates = [
        r for r in rulesets
        if r.jurisdiction == jurisdiction
        and r.valid_from <= target_date
        and (r.valid_to is None or r.valid_to >= target_date)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: LEVEL_PRIORITY.get(r.level, 0), reverse=True)
    return candidates[0]


def get_personnel_ratio(
    ratios: List[PersonnelRatio],
    ruleset_id: str,
    group_type: GroupType,
) -> Optional[PersonnelRatio]:
    for pr in ratios:
        if pr.ruleset_id == ruleset_id and pr.group_type == group_type:
            return pr
    return None


def get_funding_rate(
    rates: List[FundingRate],
    ruleset_id: str,
    group_type: GroupType,
) -> Optional[FundingRate]:
    for fr in rates:
        if fr.ruleset_id == ruleset_id and fr.group_type == group_type:
            return fr
    return None


# ============================================================
# 2. SOLL-FTE BERECHNEN
# ============================================================

def compute_required_fte(
    group: KitaGroup,
    target_date: date,
    enrollments: List[ChildEnrollment],
    attendance: List[ChildAttendance],
    ruleset: ComplianceRuleset,
    ratio: PersonnelRatio,
) -> Dict[str, Decimal]:
    """
    Berechnet Soll-FTE-Bedarf an einem Stichtag basierend auf
    aktueller Belegung + Stunden-Mix.

    Returns: {
        "children_present": N,
        "avg_hours": H,
        "fte_required": F,
        "ruleset_used": rs_id,
    }
    """
    # 1. Aktive Enrollments am Stichtag
    active_enrollments = [
        e for e in enrollments
        if e.group_id == group.id
        and e.enrolled_from <= target_date
        and (e.enrolled_to is None or e.enrolled_to >= target_date)
    ]

    # 2. Anwesenheit (wenn Daten da sind, sonst Annahme: alle da)
    attendance_today = [
        a for a in attendance
        if a.attendance_date == target_date
        and any(e.id == a.enrollment_id for e in active_enrollments)
        and a.hours_present > 0
    ]
    if attendance_today:
        children_today = [
            e for e in active_enrollments
            if any(a.enrollment_id == e.id for a in attendance_today)
        ]
    else:
        children_today = active_enrollments    # fallback: alle gemeldeten

    n = len(children_today)
    if n == 0:
        return {
            "children_present": 0,
            "avg_hours": Decimal("0"),
            "fte_required": Decimal("0"),
            "ruleset_used": ruleset.id,
        }

    # 3. Durchschnittliche Buchungs-Stunden pro Kind
    hours_list = [float(e.booked_hours_per_week) for e in children_today]
    avg_hours = Decimal(str(mean(hours_list)))

    # 4. Basis-FTE laut Regelwerk
    fte = ratio.fte_required

    # 5. Aufschlag für überlange Buchungen
    if avg_hours > Decimal(str(ratio.hours_threshold_high)):
        extra = avg_hours - Decimal(str(ratio.hours_threshold_high))
        fte = fte + (extra * ratio.fte_per_extra_hour)

    # 6. Pro-Kopf-Skalierung wenn unter Vollbelegung
    if n < ratio.children_max:
        scale = Decimal(n) / Decimal(ratio.children_max)
        fte = fte * scale
        # Mindest-1 Person muss immer da sein
        fte = max(fte, Decimal("1.00"))

    return {
        "children_present": n,
        "avg_hours": avg_hours.quantize(Decimal("0.01")),
        "fte_required": fte.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "ruleset_used": ruleset.id,
    }


# ============================================================
# 3. IST-FTE BERECHNEN
# ============================================================

def compute_actual_fte(
    group: KitaGroup,
    target_date: date,
    assignments: List[StaffAssignment],
    contracts: List[StaffContract],
    staff: List[StaffMember],
    absences: List[StaffAbsence],
    ratio: PersonnelRatio,
) -> Dict[str, Decimal]:
    """
    Berechnet effektive Personalpräsenz nach Qualifikations-Mix.
    Kochzeiten / Vorbereitung NICHT förderrelevant.
    """
    # Heutige Zuordnungen für diese Gruppe (excl. Koch-/Vorbereitungszeiten)
    today_assignments = [
        a for a in assignments
        if a.group_id == group.id
        and a.work_date == target_date
        and not a.is_cooking
        and not a.is_preparation
    ]

    fte_by_qual: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    paedagoge_pct = Decimal("0")
    total_hours = Decimal("0")

    for a in today_assignments:
        # Krankheits-Check: ist der Mitarbeiter heute krank?
        is_absent = any(
            ab.staff_id == a.staff_id
            and ab.absent_from <= target_date
            and (ab.absent_to is None or ab.absent_to >= target_date)
            for ab in absences
        )
        if is_absent:
            continue   # Auch wenn im Plan, faktisch nicht da

        # Stunden zählen (ist_stunden, falls erfasst)
        hours = a.hours_actual if a.hours_actual is not None else a.hours_planned

        # Qualifikation des Mitarbeiters finden
        member = next((s for s in staff if s.id == a.staff_id), None)
        if not member or member.qualification == Qualification.PRAKTIKANT.value:
            continue   # Praktikanten zählen nicht förder-FTE

        # Aktiver Vertrag → Wochenstunden
        contract = next(
            (c for c in contracts
             if c.staff_id == a.staff_id
             and c.valid_from <= target_date
             and (c.valid_to is None or c.valid_to >= target_date)),
            None
        )
        if not contract:
            continue

        # FTE: Tages-Stunden / (Wochen-FTE-Stunden / 5)
        daily_fte_hours = contract.weekly_hours / Decimal("5")
        fte = hours / daily_fte_hours if daily_fte_hours > 0 else Decimal("0")

        qual = member.qualification if isinstance(member.qualification, str) else member.qualification.value
        fte_by_qual[qual] += fte
        total_hours += hours

    total_fte = sum(fte_by_qual.values()) if fte_by_qual else Decimal("0")

    # Qualifikations-Cap anwenden
    capped_fte, cap_violations = _apply_qualification_caps(fte_by_qual, ratio)

    return {
        "fte_actual_raw": total_fte.quantize(Decimal("0.01")),
        "fte_actual_capped": capped_fte.quantize(Decimal("0.01")),
        "fte_by_qualification": {k: v.quantize(Decimal("0.01")) for k, v in fte_by_qual.items()},
        "cap_violations": cap_violations,
        "total_hours": total_hours.quantize(Decimal("0.01")),
    }


def _apply_qualification_caps(
    fte_by_qual: Dict[str, Decimal],
    ratio: PersonnelRatio,
) -> tuple[Decimal, List[str]]:
    """
    Wendet Qualifikations-Caps an:
    - Helfer max X% → über X% wird abgezogen
    - Mindest-Pädagogenanteil → wenn unterschritten, wird gestaucht
    """
    total = sum(fte_by_qual.values()) or Decimal("0.0001")
    violations = []

    paed_share = (fte_by_qual.get("paedagoge", Decimal("0")) / total) * 100
    if paed_share < ratio.qual_paedagoge_min_pct:
        violations.append(
            f"Pädagogen-Anteil {paed_share:.1f}% unter Soll {ratio.qual_paedagoge_min_pct}%"
        )

    if ratio.qual_helfer_max_pct is not None:
        helfer_share = (fte_by_qual.get("helfer", Decimal("0")) / total) * 100
        if helfer_share > ratio.qual_helfer_max_pct:
            excess_pct = helfer_share - Decimal(ratio.qual_helfer_max_pct)
            excess_fte = (excess_pct / 100) * total
            violations.append(
                f"Helfer-Anteil {helfer_share:.1f}% über Cap {ratio.qual_helfer_max_pct}% — {excess_fte:.2f} FTE nicht zählbar"
            )
            total -= excess_fte

    return total, violations


# ============================================================
# 4. GAP-ANALYSE + RISIKO
# ============================================================

def analyse_daily_gap(
    group: KitaGroup,
    target_date: date,
    enrollments: List[ChildEnrollment],
    attendance: List[ChildAttendance],
    assignments: List[StaffAssignment],
    contracts: List[StaffContract],
    staff: List[StaffMember],
    absences: List[StaffAbsence],
    ruleset: ComplianceRuleset,
    ratio: PersonnelRatio,
    rate: FundingRate,
) -> Optional[ComplianceGap]:
    """Prüft einen Tag, gibt None zurück wenn alles ok."""
    soll = compute_required_fte(group, target_date, enrollments, attendance, ruleset, ratio)
    ist = compute_actual_fte(group, target_date, assignments, contracts, staff, absences, ratio)

    fte_required = soll["fte_required"]
    fte_actual = ist["fte_actual_capped"]
    gap = fte_actual - fte_required

    if gap >= Decimal("-0.05"):    # 5% Toleranz
        return None

    n_children = soll["children_present"]
    fte_missing = abs(gap)

    # Risiko: anteilig betroffene Kinder × Tagessatz
    affected_children_eq = (fte_missing / fte_required) * Decimal(n_children) if fte_required > 0 else Decimal("0")
    eur_at_risk = (affected_children_eq * rate.rate_per_day).quantize(Decimal("0.01"))

    # Severity klassifizieren
    gap_pct = (fte_missing / fte_required) * 100 if fte_required > 0 else Decimal("0")
    if gap_pct >= 50:
        severity = Severity.CRITICAL
    elif gap_pct >= 20:
        severity = Severity.MAJOR
    else:
        severity = Severity.MINOR

    # Suggested action
    if fte_missing < Decimal("0.25"):
        action = f"Vertretung von ~{int(fte_missing * 8)} Std. nachorganisieren oder Springer:in"
    elif fte_missing < Decimal("1.0"):
        action = f"Halbtagskraft springen lassen ({int(fte_missing * 100)}%)"
    else:
        action = f"Springer-Pool aktivieren oder Gruppe schließen ({fte_missing:.1f} FTE fehlen)"

    desc_parts = [f"Personalunterdeckung um {fte_missing:.2f} FTE bei {n_children} Kindern"]
    if ist.get("cap_violations"):
        desc_parts.append("· " + " · ".join(ist["cap_violations"]))
    description = " ".join(desc_parts)

    return ComplianceGap(
        id=f"gap_{uuid4().hex[:12]}",
        group_id=group.id,
        gap_date=target_date,
        gap_type=GapType.FTE_UNDERCOVERAGE,
        severity=severity,
        children_affected=n_children,
        fte_missing=fte_missing,
        eur_at_risk=eur_at_risk,
        description=description,
        suggested_action=action,
    )


# ============================================================
# 5. MONATS-SNAPSHOT
# ============================================================

def compute_monthly_snapshot(
    group: KitaGroup,
    snapshot_month: date,
    rulesets: List[ComplianceRuleset],
    ratios: List[PersonnelRatio],
    rates: List[FundingRate],
    enrollments: List[ChildEnrollment],
    attendance: List[ChildAttendance],
    assignments: List[StaffAssignment],
    contracts: List[StaffContract],
    staff: List[StaffMember],
    absences: List[StaffAbsence],
    jurisdiction: str = "AT-9",
) -> tuple[ComplianceSnapshot, List[ComplianceGap]]:
    """
    Berechnet einen Monats-Snapshot: für jeden Tag Soll/Ist, aggregiert.
    Verwendet das jeweils gültige Regelwerk pro Tag (rule-aware Audit).
    """
    # Tage des Monats erzeugen
    if snapshot_month.month == 12:
        next_month = date(snapshot_month.year + 1, 1, 1)
    else:
        next_month = date(snapshot_month.year, snapshot_month.month + 1, 1)

    days = []
    cur = snapshot_month.replace(day=1)
    while cur < next_month:
        if cur.weekday() < 5:  # nur Werktage Mo-Fr
            days.append(cur)
        cur += timedelta(days=1)

    daily_gaps: List[ComplianceGap] = []
    daily_required: List[Decimal] = []
    daily_actual: List[Decimal] = []
    daily_children: List[int] = []
    rule_versions_used: Dict[str, str] = {}
    total_eur_risk = Decimal("0")

    for d in days:
        rs = get_active_ruleset(rulesets, d, jurisdiction)
        if not rs:
            continue
        rule_versions_used[d.isoformat()] = rs.id

        ratio = get_personnel_ratio(ratios, rs.id, group.group_type)
        rate = get_funding_rate(rates, rs.id, group.group_type)
        if not ratio or not rate:
            continue

        soll = compute_required_fte(group, d, enrollments, attendance, rs, ratio)
        ist = compute_actual_fte(group, d, assignments, contracts, staff, absences, ratio)

        daily_required.append(soll["fte_required"])
        daily_actual.append(ist["fte_actual_capped"])
        daily_children.append(soll["children_present"])

        gap = analyse_daily_gap(
            group, d, enrollments, attendance, assignments, contracts,
            staff, absences, rs, ratio, rate,
        )
        if gap:
            daily_gaps.append(gap)
            total_eur_risk += gap.eur_at_risk

    # Aggregation
    children_avg = (
        Decimal(str(mean([c for c in daily_children if c > 0])))
        if any(c > 0 for c in daily_children) else Decimal("0")
    )
    fte_required_avg = (
        Decimal(str(mean([float(f) for f in daily_required])))
        if daily_required else Decimal("0")
    )
    fte_actual_avg = (
        Decimal(str(mean([float(f) for f in daily_actual])))
        if daily_actual else Decimal("0")
    )
    fte_gap = fte_actual_avg - fte_required_avg

    # Risk-Level
    if total_eur_risk >= Decimal("2000"):
        risk = RiskLevel.RED
    elif total_eur_risk >= Decimal("500") or len(daily_gaps) >= 3:
        risk = RiskLevel.YELLOW
    else:
        risk = RiskLevel.GREEN

    snapshot = ComplianceSnapshot(
        id=f"snap_{uuid4().hex[:12]}",
        group_id=group.id,
        snapshot_month=snapshot_month.replace(day=1),
        children_avg=children_avg.quantize(Decimal("0.01")),
        fte_actual=fte_actual_avg.quantize(Decimal("0.01")),
        fte_required=fte_required_avg.quantize(Decimal("0.01")),
        fte_gap=fte_gap.quantize(Decimal("0.01")),
        days_undercov=len(daily_gaps),
        ruleset_id=list(rule_versions_used.values())[0] if rule_versions_used else "",
        funding_at_risk_eur=total_eur_risk.quantize(Decimal("0.01")),
        risk_level=risk,
        rule_versions_used=rule_versions_used,
        computed_at=datetime.now(),
    )
    return snapshot, daily_gaps


# ============================================================
# 6. 60-MONATE-RÜCKWÄRTS-AUDIT
# ============================================================

def historical_audit(
    group: KitaGroup,
    months_back: int = 60,
    rulesets: List[ComplianceRuleset] = None,
    ratios: List[PersonnelRatio] = None,
    rates: List[FundingRate] = None,
    enrollments: List[ChildEnrollment] = None,
    attendance: List[ChildAttendance] = None,
    assignments: List[StaffAssignment] = None,
    contracts: List[StaffContract] = None,
    staff: List[StaffMember] = None,
    absences: List[StaffAbsence] = None,
    org_name: str = "—",
    jurisdiction: str = "AT-9",
    applicable_law: str = "WKTG i.d.F. BGBl 2024/85",
) -> AuditReport:
    """Generiert kompletten Audit-Report über 60 Monate."""
    today = date.today()
    period_to = today
    # 60 Monate zurück
    year = today.year - (months_back // 12)
    month = today.month - (months_back % 12)
    while month <= 0:
        year -= 1
        month += 12
    period_from = date(year, month, 1)

    monthly_findings: List[MonthlyFinding] = []
    rule_changes: List[RuleChange] = []
    total_at_risk = Decimal("0")
    months_with_gap = 0
    months_clean = 0

    cur = period_from
    while cur <= period_to:
        snapshot, gaps = compute_monthly_snapshot(
            group, cur, rulesets or [], ratios or [], rates or [],
            enrollments or [], attendance or [], assignments or [],
            contracts or [], staff or [], absences or [],
            jurisdiction=jurisdiction,
        )
        rs_id = snapshot.ruleset_id or "unbekannt"
        finding = MonthlyFinding(
            month=cur,
            group=group.name,
            children_avg=snapshot.children_avg,
            fte_required=snapshot.fte_required,
            fte_actual=snapshot.fte_actual,
            fte_gap=snapshot.fte_gap,
            days_undercov=snapshot.days_undercov,
            ruleset_applied=rs_id,
            funding_at_risk_eur=snapshot.funding_at_risk_eur,
            risk_level=snapshot.risk_level,
            gaps=gaps,
        )
        monthly_findings.append(finding)
        total_at_risk += snapshot.funding_at_risk_eur
        if snapshot.fte_gap < 0 and snapshot.days_undercov > 0:
            months_with_gap += 1
        else:
            months_clean += 1

        # Nächster Monat
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    # Rule-Changes im Zeitraum
    for rs in rulesets or []:
        if period_from <= rs.valid_from <= period_to:
            rule_changes.append(RuleChange(
                date=rs.valid_from,
                ruleset_id=rs.id,
                change_summary=rs.name,
            ))

    # Empfehlungen aus Patterns ableiten
    recommendations = generate_recommendations(monthly_findings, group)

    # Gesamt-Risk-Level
    if total_at_risk >= Decimal("10000"):
        overall_risk = RiskLevel.RED
    elif total_at_risk >= Decimal("2000"):
        overall_risk = RiskLevel.YELLOW
    else:
        overall_risk = RiskLevel.GREEN

    return AuditReport(
        report_meta=AuditReportMeta(
            report_id=f"audit_{period_to.isoformat()}_{group.name.lower().replace(' ', '_')}",
            generated_at=datetime.now(),
            period_from=period_from,
            period_to=period_to,
        ),
        subject=AuditReportSubject(
            org_name=org_name,
            jurisdiction=jurisdiction,
            applicable_law=applicable_law,
            groups_audited=1,
        ),
        summary=AuditReportSummary(
            total_months_analysed=len(monthly_findings),
            months_with_gap=months_with_gap,
            months_clean=months_clean,
            total_funding_at_risk_eur=total_at_risk,
            potential_recoverable_via_correction=total_at_risk * Decimal("0.65"),  # Erfahrungswert
            non_recoverable=total_at_risk * Decimal("0.35"),
            risk_level=overall_risk,
        ),
        monthly_findings=monthly_findings,
        rule_changes_in_period=rule_changes,
        recommendations=recommendations,
        audit_trail=AuditTrail(
            data_sources=[],
            rule_versions_used=list(set(f.ruleset_applied for f in monthly_findings)),
            computation_log=None,
        ),
    )


# ============================================================
# 7. EMPFEHLUNGS-ENGINE
# ============================================================

def generate_recommendations(
    findings: List[MonthlyFinding],
    group: KitaGroup,
) -> List[AuditRecommendation]:
    """Leitet aus Pattern in den Findings konkrete Empfehlungen ab."""
    recs: List[AuditRecommendation] = []

    # Pattern 1: Häufige Krankheits-Lücken → Springer-Pool
    krankheit_count = sum(
        1 for f in findings for g in f.gaps
        if "krankheit" in g.description.lower() or "ohne vertretung" in g.description.lower()
    )
    if krankheit_count >= 3:
        savings = Decimal(krankheit_count * 800)
        recs.append(AuditRecommendation(
            priority="high",
            title="Springer-Pool aufbauen",
            rationale=f"{krankheit_count} Lücken durch Krankheit ohne Vertretung — "
                      f"Fix-Pool von 1.5 FTE würde ca. 80% verhindern",
            estimated_savings_eur_per_year=savings,
            implementation_effort="medium",
        ))

    # Pattern 2: Kochzeiten falsch deklariert
    # (würde aus assignments.is_cooking + heuristics kommen)

    # Pattern 3: Hohe Kappung wegen zu vielen Helfern
    capped = sum(
        1 for f in findings for g in f.gaps
        if "helfer" in g.description.lower() and "cap" in g.description.lower()
    )
    if capped >= 2:
        recs.append(AuditRecommendation(
            priority="medium",
            title="Helfer-Anteil reduzieren oder umschulen",
            rationale=f"{capped} mal Cap-Verletzung — Quereinstieg / Umschulung "
                      f"einer Helfer:in zur Assistent:in würde Cap entlasten",
            estimated_savings_eur_per_year=Decimal("3500"),
            implementation_effort="hard",
        ))

    # Pattern 4: Jeder Monat Risiko > Schwellwert → strukturelles Problem
    high_risk_months = [f for f in findings if f.funding_at_risk_eur > Decimal("500")]
    if len(high_risk_months) >= 12:
        recs.append(AuditRecommendation(
            priority="high",
            title="Strukturelle Personalunterdeckung",
            rationale=f"In {len(high_risk_months)} Monaten Risiko > 500€ — "
                      f"vermutlich strukturell zu wenig Personal eingestellt. "
                      f"Vertragsanpassung oder Neueinstellung prüfen.",
            estimated_savings_eur_per_year=Decimal(len(high_risk_months) * 800),
            implementation_effort="hard",
        ))

    return recs


# ============================================================
# 8. DEMO-LAUF (vorzeigbar)
# ============================================================

if __name__ == "__main__":
    from kita_compliance_models import WKTG_2024_SEED
    import json

    print("=" * 70)
    print(" SHIKSHA · KITA · Compliance Engine — Demo-Lauf")
    print("=" * 70)
    print()

    # Mini-Setup
    group = KitaGroup(
        id="grp_marienkaefer",
        org_id="org_traeger_sonnenschein",
        name="Marienkäfer Krippe",
        group_type=GroupType.KRIPPE,
        capacity=15,
        opened_at=date(2020, 9, 1),
    )

    # Beispiel-Personal
    staff_list = [
        StaffMember(id="s1", org_id="org_traeger_sonnenschein", full_name="Andrea Müller",
                    qualification=Qualification.PAEDAGOGE, hired_at=date(2020, 8, 1)),
        StaffMember(id="s2", org_id="org_traeger_sonnenschein", full_name="Lukas Bauer",
                    qualification=Qualification.ASSISTENT, hired_at=date(2022, 9, 1)),
    ]
    contracts = [
        StaffContract(id="c1", staff_id="s1", valid_from=date(2020, 8, 1),
                      contract_pct=Decimal("100"), weekly_hours=Decimal("38.5"),
                      paid_hours=Decimal("38.5"), direct_care_hours=Decimal("33")),
        StaffContract(id="c2", staff_id="s2", valid_from=date(2022, 9, 1),
                      contract_pct=Decimal("100"), weekly_hours=Decimal("38.5"),
                      paid_hours=Decimal("38.5"), direct_care_hours=Decimal("33")),
    ]
    enrollments = [
        ChildEnrollment(id=f"e{i}", group_id="grp_marienkaefer", child_anon_id=f"k{i}",
                        age_months=24+i, enrolled_from=date(2024, 9, 1),
                        booked_hours_per_week=Decimal("38.5"))
        for i in range(14)
    ]
    # Tag 12.9.2024: Andrea krank, KEINE Vertretung
    absences = [
        StaffAbsence(id="ab1", staff_id="s1", absent_from=date(2024, 9, 12),
                     absent_to=date(2024, 9, 12), reason="krank", has_substitute=False),
    ]
    assignments = []
    for d in range(1, 31):
        try:
            wd = date(2024, 9, d)
            if wd.weekday() < 5:
                for s in staff_list:
                    assignments.append(StaffAssignment(
                        id=f"a_{s.id}_{d}", staff_id=s.id, group_id="grp_marienkaefer",
                        work_date=wd, hours_planned=Decimal("7.7"),
                        hours_actual=Decimal("7.7"),
                    ))
        except ValueError:
            pass

    # Audit über 1 Monat
    rs = WKTG_2024_SEED["ruleset"]
    snapshot, gaps = compute_monthly_snapshot(
        group, date(2024, 9, 1),
        rulesets=[rs],
        ratios=WKTG_2024_SEED["personnel_ratios"],
        rates=WKTG_2024_SEED["funding_rates"],
        enrollments=enrollments, attendance=[],
        assignments=assignments, contracts=contracts,
        staff=staff_list, absences=absences,
    )

    print(f"Monat: {snapshot.snapshot_month}")
    print(f"Gruppe: {group.name}")
    print(f"Kinder Ø: {snapshot.children_avg}")
    print(f"FTE Soll: {snapshot.fte_required}")
    print(f"FTE Ist:  {snapshot.fte_actual}")
    print(f"Gap:      {snapshot.fte_gap}")
    print(f"Tage mit Unterdeckung: {snapshot.days_undercov}")
    print(f"Risiko: {snapshot.funding_at_risk_eur}€")
    print(f"Risk-Level: {snapshot.risk_level}")
    print()
    print("Konkrete Lücken-Tage:")
    for g in gaps:
        print(f"  · {g.gap_date} {g.severity}: {g.description}")
        print(f"    → {g.suggested_action} ({g.eur_at_risk}€ Risiko)")

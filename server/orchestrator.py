# ============================================================
# SHIKSHA — orchestrator.py
# Orchestrator-Logik — KURS_001 Flow
# Sequentiell, Multi-Domain, Policy-Druck, action_proposal
# ============================================================

from __future__ import annotations
import uuid
from datetime import date, datetime, timezone, timedelta
from weather_domain import get_weather_for_location
from models import (
    OrchestratorRequest, OrchestratorObject,
    RequestSource, Intent, Scope, DomainSelection, DomainResult,
    ExecutionPlan, ExecutionStep, DecisionCheckpoint, MergeStrategy,
    IntermediateResult, PolicyCheck, PolicyRestriction, PolicyWarning,
    Output, Proposal, PreparedAction, NextStep,
    ReviewRequired, ConflictResolution, Learning, LearningCandidate,
    IntentType, ScopeType, ScopeSubtype, ExecutionMode, OutputMode,
    PolicyEffect, ReviewPriority, LearningCandidateType, ValidationPath,
    SourceType, ConflictState,
)


# ------------------------------------------------------------
# POLICY REGISTRY
# Minimal — nur die Policies, die für KURS_001 relevant sind
# ------------------------------------------------------------

POLICIES = {
    "camp.no_auto_rebooking": {
        "type": "action",
        "description": "Keine automatische verbindliche Umbuchung von Kursen. Operator muss bestätigen.",
        "effect": PolicyEffect.restrict,
        "output_downgrade": (OutputMode.action_execution, OutputMode.action_proposal),
    },
    "camp.no_auto_participant_notification": {
        "type": "action",
        "description": "Keine automatische Benachrichtigung von Teilnehmern ohne Freigabe.",
        "effect": PolicyEffect.restrict,
        "output_downgrade": (OutputMode.action_execution, OutputMode.draft),
    },
}


# ------------------------------------------------------------
# SIMULATED DOMAIN CALLS
# In V1: hardcodierte Ergebnisse, später echte Domain-Module
# ------------------------------------------------------------

async def call_weather_domain(location_id: str, target_date: date) -> DomainResult:
    """Wetter-Domain: echter Call via Open-Meteo API."""
    return await get_weather_for_location(
        location_id=location_id,
        target_date=target_date,
    )

def call_operations_domain(course_id: str) -> DomainResult:
    """Operations-Domain: Ressourcenverfügbarkeit nächste 5 Tage."""
    return DomainResult(
        domain="operations",
        query=f"Ressourcenverfügbarkeit {course_id} — nächste 5 Tage",
        result={
            "alternatives": [
                {
                    "date": "2026-04-19",
                    "time": "09:00",
                    "instructor_available": True,
                    "boat_available": True,
                    "location_available": True,
                    "weather_forecast": "suitable",
                    "conflict": None,
                },
                {
                    "date": "2026-04-20",
                    "time": "10:00",
                    "instructor_available": True,
                    "boat_available": False,
                    "location_available": True,
                    "weather_forecast": "suitable",
                    "conflict": "boat_conflict_course_048",
                },
            ],
            "confidence": 0.87,
            "data_freshness": "live",
        },
        decision_impact="high",
        checkpoint_passed=True,
    )


def call_communications_domain(course_id: str) -> DomainResult:
    """Communications-Domain: Teilnehmerkontakte."""
    return DomainResult(
        domain="communications",
        query=f"Teilnehmerkontakte {course_id}",
        result={
            "reachable_participants": 8,
            "preferred_channel": "email",
            "notification_lead_time_required_hours": 12,
            "draft_possible": True,
            "send_possible": False,         # Policy: kein Auto-Versand
        },
        decision_impact="medium",
        checkpoint_passed=True,
    )


# ------------------------------------------------------------
# POLICY GATE
# Prüft aktive Policies — gibt PolicyCheck zurück
# ------------------------------------------------------------

def run_policy_gate(
    edition: str,
    intent: Intent,
    domain_results: list[DomainResult],
) -> PolicyCheck:
    """Gate 3 — Action Gate: Was darf ausgeführt werden?"""

    restrictions: list[PolicyRestriction] = []
    warnings: list[PolicyWarning] = []

    # Aktions-Policies für camp.shiksha
    if edition == "camp.shiksha":
        if intent.primary_intent == IntentType.trigger:
            restrictions.append(PolicyRestriction(
                policy_id="camp.no_auto_rebooking",
                description=POLICIES["camp.no_auto_rebooking"]["description"],
                effect=PolicyEffect.restrict,
                triggered_at_step=4,
            ))
            restrictions.append(PolicyRestriction(
                policy_id="camp.no_auto_participant_notification",
                description=POLICIES["camp.no_auto_participant_notification"]["description"],
                effect=PolicyEffect.restrict,
                triggered_at_step=5,
            ))

    # Warnungen aus Domain-Ergebnissen
    for dr in domain_results:
        if dr.domain == "weather" and dr.result.get("condition") == "storm_warning":
            warnings.append(PolicyWarning(
                type="weather_critical",
                note=f"Sturmwarnung: {dr.result.get('wind_speed_kmh')} km/h — Kurs nicht durchführbar.",
            ))
        if dr.domain == "operations":
            alts = dr.result.get("alternatives", [])
            if any(not a.get("boat_available") for a in alts):
                warnings.append(PolicyWarning(
                    type="boat_conflict_on_backup_date",
                    note="20.04. als Ausweichtermin nicht verfügbar — Boot-Konflikt mit course_048.",
                ))

    requires_review = len(restrictions) > 0

    return PolicyCheck(
        blocked=False,
        active_restrictions=restrictions,
        warnings=warnings,
        requires_review=requires_review,
        escalation_reason=(
            "Verbindliche Umbuchung und Teilnehmerbenachrichtigung erfordern explizite Freigabe."
            if requires_review else None
        ),
    )


# ------------------------------------------------------------
# OUTPUT BUILDER
# Baut den Output auf Basis von Domain-Ergebnissen + Policy
# ------------------------------------------------------------

def build_output(
    domain_results: list[DomainResult],
    policy_check: PolicyCheck,
    late_arrivals: int = 2,
) -> Output:
    """Baut action_proposal für Kursverschiebung."""

    # Bester Alternativtermin aus Operations
    ops_result = next((dr for dr in domain_results if dr.domain == "operations"), None)
    best_date = "2026-04-19"
    best_time = "12:00"                    # Angepasst wegen später Ankunft (2 TN ab 11:30)

    proposal = Proposal(
        action=f"Kurs course_sail_042 verschieben auf {best_date}, {best_time}",
        confidence=0.87,
        rationale=(
            "Einziger verfügbarer Termin mit Instructor, Boot, Location und Wetter "
            "in den nächsten 5 Tagen. Spätere Ankunft von 2 Teilnehmern berücksichtigt."
        ),
        trade_off=(
            "Kurszeit verkürzt sich von 5h auf 2h. "
            "Operator muss entscheiden, ob das akzeptabel ist."
        ),
        requires_confirmation=True,
        target="operator",
    )

    prepared = [
        PreparedAction(
            action="Verbindliche Umbuchung in System",
            status="waiting_for_approval",
            target="operator",
        ),
        PreparedAction(
            action="Teilnehmerbenachrichtigung per E-Mail",
            status="draft_ready",
            target="operator",
        ),
    ]

    next_steps = [
        NextStep(
            action="Operator bestätigt oder lehnt Verschiebungsvorschlag ab.",
            type="approval_required",
            target="operator",
        ),
        NextStep(
            action="Nach Bestätigung: Umbuchung ausführen + Kommunikation versenden.",
            type="action_execution_pending",
            target="system",
        ),
        NextStep(
            action="Falls Kurszeit-Reduktion nicht akzeptabel: alternative Lösung besprechen.",
            type="escalation_option",
            target="operator",
        ),
    ]

    return Output(
        mode=OutputMode.action_proposal,   # Policy hat action_execution verhindert
        summary=(
            f"Kurs morgen nicht durchführbar (Sturm, 68 km/h). "
            f"Empfohlene Verschiebung: {best_date}, {best_time} Uhr. "
            "Alle Ressourcen verfügbar. "
            "Kommunikationsentwurf liegt bereit — wartet auf Freigabe."
        ),
        proposal=proposal,
        prepared_but_not_executed=prepared,
        next_steps=next_steps,
    )


# ------------------------------------------------------------
# HAUPTFUNKTION — process_request
# ------------------------------------------------------------

async def process_request(req: OrchestratorRequest) -> OrchestratorObject:
    """
    Verarbeitet einen eingehenden Request durch den SHIKSHA Orchestrator.
    KURS_001 Flow: sequentiell, multi-domain, policy-druck, action_proposal.
    """

    request_id = f"KURS_{uuid.uuid4().hex[:6].upper()}"
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()

    # --------------------------------------------------------
    # STEP 1 — Intent Classification
    # --------------------------------------------------------
    intent = Intent(
        primary_intent=IntentType.trigger,
        secondary_intents=[IntentType.plan, IntentType.inform],
        confidence=0.85,
        confidence_breakdown={
            "trigger": 0.85,
            "plan": 0.71,
            "inform": 0.54,
        },
        intent_notes="Operator will Handlung auslösen. Policy entscheidet ob direkt oder als Proposal.",
    )

    # --------------------------------------------------------
    # STEP 2 — Scope Detection
    # --------------------------------------------------------
    scope = Scope(
        type=ScopeType.domain_multi,
        subtype=ScopeSubtype.sequential,
        requires_real_world_feedback=True,
        requires_action=True,
        requires_edition_data=True,
        cross_edition=False,
    )

    # --------------------------------------------------------
    # STEP 3 — Domain Calls (sequentiell)
    # Wetter → Operations → Communications
    # --------------------------------------------------------
    weather_result = await call_weather_domain("loc_lake_02", tomorrow)
    ops_result     = call_operations_domain("course_sail_042")
    comm_result    = call_communications_domain("course_sail_042")

    domain_selection = DomainSelection(
        lead_domain="scheduling",
        rationale_lead=(
            "Das Ergebnisobjekt ist ein verbindlicher Terminentscheid. "
            "scheduling besitzt Ressourcenlogik, Konfliktprüfung und Freigaberegeln."
        ),
        supporting_domains=["weather", "operations", "communications"],
        supporting_domain_results=[weather_result, ops_result, comm_result],
        core_reasoning=True,
    )

    # --------------------------------------------------------
    # STEP 4 — Execution Plan
    # --------------------------------------------------------
    execution_plan = ExecutionPlan(
        mode=ExecutionMode.sequential_multi_domain,
        rationale=(
            "Jeder Schritt hängt vom Ergebnis des vorherigen ab. "
            "Ohne Wetter-Entscheid kein Ressourcencheck. "
            "Ohne Ressourcencheck kein Kommunikationsentwurf."
        ),
        steps=[
            ExecutionStep(
                step=1, action="weather_assessment",
                description="Ist der Kurs morgen wetterbedingt durchführbar?",
                input=["weather_forecast_tomorrow"], output="weather_decision",
                decision_checkpoint=DecisionCheckpoint(
                    question="Ist Durchführung morgen möglich?",
                    result="no", confidence=0.91, next="step_2",
                ),
            ),
            ExecutionStep(
                step=2, action="resource_availability_check",
                description="Welche Alternativtermine sind mit allen Ressourcen möglich?",
                input=["course_resource_availability", "weather_decision"],
                output="available_alternatives",
                decision_checkpoint=DecisionCheckpoint(
                    question="Gibt es mindestens einen vollständig verfügbaren Alternativtermin?",
                    result="yes", confidence=0.87, next="step_3",
                ),
            ),
            ExecutionStep(
                step=3, action="late_arrival_check",
                description="Ist der Alternativtermin mit späten Anreisen kompatibel?",
                input=["available_alternatives", "pgroup_042"],
                output="participant_compatibility",
                decision_checkpoint=DecisionCheckpoint(
                    question="Können alle Teilnehmer den Alternativtermin wahrnehmen?",
                    result="conditional",
                    adjustment="Kursstart 19.04 auf 12:00 verschieben statt 09:00",
                    confidence=0.79, next="step_4",
                ),
            ),
            ExecutionStep(
                step=4, action="scheduling_decision",
                description="Lead Domain scheduling bildet finalen Entscheid.",
                input=["available_alternatives", "participant_compatibility", "course_policy_rules"],
                output="scheduling_proposal",
                decision_checkpoint=DecisionCheckpoint(
                    question="Darf SHIKSHA die Verschiebung direkt ausführen?",
                    result="no", policy_id="camp.no_auto_rebooking", next="step_5",
                ),
            ),
            ExecutionStep(
                step=5, action="communication_draft",
                description="Kommunikationsentwurf vorbereiten — nicht versenden.",
                input=["scheduling_proposal", "participant_contact_data"],
                output="communication_draft",
            ),
        ],
        merge_strategy=MergeStrategy(
            method="sequence",
            description=(
                "Keine parallele Zusammenführung. "
                "Jeder Schritt liefert ein Zwischenergebnis, das den nächsten steuert."
            ),
            intermediate_results=[
                IntermediateResult(after_step=1, result="weather_decision",          value="not_suitable"),
                IntermediateResult(after_step=2, result="best_alternative",          value="2026-04-19"),
                IntermediateResult(after_step=3, result="adjusted_start_time",       value="12:00"),
                IntermediateResult(after_step=4, result="policy_gate_triggered",     value="camp.no_auto_rebooking"),
                IntermediateResult(after_step=5, result="communication_draft_ready", value=True),
            ],
        ),
    )

    # --------------------------------------------------------
    # STEP 5 — Policy Gate
    # --------------------------------------------------------
    policy_check = run_policy_gate(
        edition=req.edition,
        intent=intent,
        domain_results=[weather_result, ops_result, comm_result],
    )

    # --------------------------------------------------------
    # STEP 6 — Output
    # --------------------------------------------------------
    output = build_output(
        domain_results=[weather_result, ops_result, comm_result],
        policy_check=policy_check,
    )

    # --------------------------------------------------------
    # STEP 7 — Review Required (Policy hat gegriffen)
    # --------------------------------------------------------
    review_required = ReviewRequired(
        roles=["domain_reviewer", "owner"],
        assigned_to=[],
        reason="high_impact_action",
        priority=ReviewPriority.high,
        deadline=now + timedelta(hours=3),  # heute Abend — Kurs ist morgen früh
        conflict_state=ConflictState.pending,
    ) if policy_check.requires_review else None

    conflict_resolution = ConflictResolution(
        mode="conservative",
        override_required_by="owner",
    ) if review_required else None

    # --------------------------------------------------------
    # STEP 8 — Learning
    # --------------------------------------------------------
    learning = Learning(
        event_created=True,
        event_id=f"evt_{request_id}",
        session_id=session_id,
        observation_possible=True,
        learning_candidate_created=True,
        learning_candidate=LearningCandidate(
            id=f"lc_{request_id}",
            type=LearningCandidateType.operational_pattern_candidate,
            domain="scheduling",
            hypothesis=(
                "Sturm > 60 km/h am Wolfgangsee = automatische Verschiebungsempfehlung sinnvoll. "
                "Schwellenwert könnte als Domain-Regel etabliert werden."
            ),
            initial_confidence=0.34,
            status="pending_validation",
            validation_path=ValidationPath.pattern_based,
            review_deadline=now + timedelta(days=30),
            direct_domain_memory_update=False,
        ),
        event_only=False,
    )

    # --------------------------------------------------------
    # Objekt zusammenbauen
    # --------------------------------------------------------
    return OrchestratorObject(
        request_id=request_id,
        session_id=session_id,
        raw_input=req.raw_input,
        source=RequestSource(type=req.source_type, id=req.source_id),
        timestamp=now,
        edition=req.edition,
        context={
            "edition": req.edition,
            "user_role": req.user_role,
            "language": "de",
            "active_entities": req.active_entity_ids,
            "available_domains": ["scheduling", "weather", "operations", "communications"],
        },
        intent=intent,
        scope=scope,
        domain_selection=domain_selection,
        execution_plan=execution_plan,
        policy_check=policy_check,
        output=output,
        review_required=review_required,
        conflict_resolution=conflict_resolution,
        learning=learning,
    )

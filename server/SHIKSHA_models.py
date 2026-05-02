# ============================================================
# SHIKSHA — models.py
# Pydantic-Datenmodelle für den Orchestrator
# Basis: Orchestrator Template V1.1 + KURS_001 V2.0
# ============================================================

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------
# ENUMS
# ------------------------------------------------------------

class SourceType(str, Enum):
    operator = "operator"
    guest    = "guest"
    system   = "system"
    external = "external"

class IntentType(str, Enum):
    inform    = "inform"
    recommend = "recommend"
    diagnose  = "diagnose"
    plan      = "plan"
    draft     = "draft"
    update    = "update"
    trigger   = "trigger"
    request   = "request"

class ScopeType(str, Enum):
    core_only        = "core_only"
    domain_single    = "domain_single"
    domain_multi     = "domain_multi"
    edition_specific = "edition_specific"
    cross_edition    = "cross_edition"

class ScopeSubtype(str, Enum):
    sequential = "sequential"
    parallel   = "parallel"
    hybrid     = "hybrid"

class ExecutionMode(str, Enum):
    core_only               = "core_only"
    single_domain_analysis  = "single_domain_analysis"
    sequential_multi_domain = "sequential_multi_domain"
    parallel_multi_domain   = "parallel_multi_domain"
    hybrid_multi_domain     = "hybrid_multi_domain"

class OutputMode(str, Enum):
    answer           = "answer"
    recommendation   = "recommendation"
    diagnosis        = "diagnosis"
    draft            = "draft"
    action_proposal  = "action_proposal"
    action_execution = "action_execution"
    warning          = "warning"
    escalation       = "escalation"

class PolicyEffect(str, Enum):
    allow    = "allow"
    warn     = "warn"
    restrict = "restrict"
    escalate = "escalate"
    block    = "block"

class ConflictState(str, Enum):
    pending   = "pending"
    resolved  = "resolved"
    escalated = "escalated"

class ReviewPriority(str, Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"

class LearningCandidateType(str, Enum):
    domain_pattern_candidate      = "domain_pattern_candidate"
    operational_pattern_candidate = "operational_pattern_candidate"
    edition_specific_candidate    = "edition_specific_candidate"

class ValidationPath(str, Enum):
    automatic      = "automatic"
    pattern_based  = "pattern_based"
    owner_review   = "owner_review"


# ------------------------------------------------------------
# SUB-MODELS
# ------------------------------------------------------------

class RequestSource(BaseModel):
    type: SourceType
    id: Optional[str] = None

class ActiveEntity(BaseModel):
    type: str
    id: str
    # Zusätzliche state-Felder werden als freies Dict mitgegeben
    extra: dict[str, Any] = Field(default_factory=dict)

class Intent(BaseModel):
    primary_intent: IntentType
    secondary_intents: list[IntentType] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)
    intent_notes: Optional[str] = None

class Scope(BaseModel):
    type: ScopeType
    subtype: Optional[ScopeSubtype] = None
    requires_real_world_feedback: bool = False
    requires_action: bool = False
    requires_edition_data: bool = False
    cross_edition: bool = False

class DomainResult(BaseModel):
    domain: str
    query: str
    result: dict[str, Any]
    decision_impact: str                   # "critical" | "high" | "medium" | "low"
    checkpoint_passed: bool = True

class DomainSelection(BaseModel):
    lead_domain: str
    rationale_lead: str
    supporting_domains: list[str] = Field(default_factory=list)
    supporting_domain_results: list[DomainResult] = Field(default_factory=list)
    core_reasoning: bool = True

class DecisionCheckpoint(BaseModel):
    question: str
    result: str                            # "yes" | "no" | "conditional"
    confidence: Optional[float] = None
    next: Optional[str] = None
    adjustment: Optional[str] = None
    policy_id: Optional[str] = None

class ExecutionStep(BaseModel):
    step: int
    action: str
    description: str
    input: list[str] | str
    output: str
    parallel: bool = False
    decision_checkpoint: Optional[DecisionCheckpoint] = None

class IntermediateResult(BaseModel):
    after_step: int
    result: str
    value: Any

class MergeStrategy(BaseModel):
    method: Optional[str] = None           # "weighted_filter" | "sequence" | "parallel_merge"
    description: Optional[str] = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    intermediate_results: list[IntermediateResult] = Field(default_factory=list)

class ExecutionPlan(BaseModel):
    mode: ExecutionMode
    rationale: str
    steps: list[ExecutionStep]
    merge_strategy: MergeStrategy = Field(default_factory=MergeStrategy)

class PolicyRestriction(BaseModel):
    policy_id: str
    description: str
    effect: PolicyEffect
    triggered_at_step: Optional[int] = None

class PolicyWarning(BaseModel):
    type: str
    note: str

class PolicyCheck(BaseModel):
    blocked: bool = False
    active_restrictions: list[PolicyRestriction] = Field(default_factory=list)
    warnings: list[PolicyWarning] = Field(default_factory=list)
    requires_review: bool = False
    escalation_reason: Optional[str] = None

class Proposal(BaseModel):
    action: str
    confidence: float
    rationale: str
    trade_off: Optional[str] = None
    requires_confirmation: bool = True
    target: str

class PreparedAction(BaseModel):
    action: str
    status: str                            # "waiting_for_approval" | "draft_ready"
    target: str

class NextStep(BaseModel):
    action: str
    type: str
    target: str

class ContextualNote(BaseModel):
    note: str
    source: str
    target: str

class Output(BaseModel):
    mode: OutputMode
    summary: str
    ranked_probable_causes: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    proposal: Optional[Proposal] = None
    prepared_but_not_executed: list[PreparedAction] = Field(default_factory=list)
    next_steps: list[NextStep] = Field(default_factory=list)
    contextual_notes: list[ContextualNote] = Field(default_factory=list)

class ReviewRequired(BaseModel):
    roles: list[str]
    assigned_to: list[str] = Field(default_factory=list)
    reason: str
    priority: ReviewPriority
    deadline: Optional[datetime] = None
    conflict_state: ConflictState = ConflictState.pending

class ConflictResolution(BaseModel):
    mode: str = "conservative"
    override_required_by: str = "owner"

class LearningCandidate(BaseModel):
    id: str
    type: LearningCandidateType
    domain: str
    hypothesis: str
    initial_confidence: float = Field(ge=0.0, le=1.0)
    status: str = "pending_validation"
    validation_path: ValidationPath
    review_deadline: Optional[datetime] = None
    direct_domain_memory_update: bool = False

class Learning(BaseModel):
    event_created: bool = False
    event_id: Optional[str] = None
    session_id: str
    observation_possible: bool = False
    observation_fields_required: list[str] = Field(
        default_factory=lambda: ["source_type", "source_id", "timestamp", "confidence"]
    )
    learning_candidate_created: bool = False
    learning_candidate: Optional[LearningCandidate] = None
    event_only: bool = False
    reason: Optional[str] = None


# ------------------------------------------------------------
# HAUPT-OBJEKTE
# ------------------------------------------------------------

class OrchestratorRequest(BaseModel):
    """Eingehender Request — was der Aufrufer sendet."""
    raw_input: str
    edition: str
    user_role: str
    source_type: SourceType = SourceType.operator
    source_id: Optional[str] = None
    session_id: Optional[str] = None
    active_entity_ids: list[str] = Field(default_factory=list)

class OrchestratorObject(BaseModel):
    """Vollständiges Orchestrator-Objekt — intern gebaut, nach außen zurückgegeben."""

    # Request
    request_id: str
    session_id: str
    raw_input: str
    source: RequestSource
    timestamp: datetime
    edition: str

    # Context
    context: dict[str, Any]

    # Intent
    intent: Intent

    # Scope
    scope: Scope

    # Domain Selection
    domain_selection: DomainSelection

    # Execution Plan
    execution_plan: ExecutionPlan

    # Policy Check
    policy_check: PolicyCheck

    # Output
    output: Output

    # Review
    review_required: Optional[ReviewRequired] = None
    conflict_resolution: Optional[ConflictResolution] = None

    # Learning
    learning: Learning

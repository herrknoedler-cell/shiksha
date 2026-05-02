"""
SHIKSHA · SAFEGUARDING MODUL · Pydantic Models V1 (cross-edition, lernfähig)
Stand: 25.04.2026
"""

from datetime import date, datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------

OrganizationType = Literal["school", "campsite", "club", "other"]
SignalSeverity = Literal["high", "mid", "low", "info"]
PatternType = Literal["frequency_cluster", "seasonal", "cross_edition", "recurring_entity"]
PatternStatus = Literal["pending", "promoted", "dismissed"]
IncidentStatus = Literal["open", "under_review", "resolved", "archived"]
ConsentType = Literal["kursteilnahme", "fotoeinverständnis", "datenweitergabe", "medizinisch", "schwimmaufsicht", "other"]


# ---------------------------------------------------------------------------
# 2. Schutzkonzept und Personen-Status
# ---------------------------------------------------------------------------

class ProtectionPolicy(BaseModel):
    id: str
    organization_id: str
    organization_type: OrganizationType
    title: str
    document_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    last_review_at: Optional[date] = None
    next_review_due: Optional[date] = None
    metadata: dict = Field(default_factory=dict)


class PersonProtectionStatus(BaseModel):
    id: str
    person_id: str
    organization_id: str
    organization_type: OrganizationType
    role: Optional[str] = None
    background_check_valid_until: Optional[date] = None
    first_aid_valid_until: Optional[date] = None
    rescue_swim_valid_until: Optional[date] = None
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.now)

    def has_expiring_credential(self, within_days: int = 60, on_date: Optional[date] = None) -> Optional[str]:
        """Returns the field name of the soonest-expiring credential within window, or None."""
        check_date = on_date or date.today()
        threshold = date.fromordinal(check_date.toordinal() + within_days)
        candidates: list[tuple[date, str]] = []
        for label, dt in (
            ("background_check", self.background_check_valid_until),
            ("first_aid", self.first_aid_valid_until),
            ("rescue_swim", self.rescue_swim_valid_until),
        ):
            if dt is not None and check_date <= dt <= threshold:
                candidates.append((dt, label))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]


class BackgroundCheck(BaseModel):
    id: str
    person_id: str
    type: str
    issued_by: Optional[str] = None
    issued_at: date
    valid_until: date
    document_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 3. Konsente (zentral für alle Editionen)
# ---------------------------------------------------------------------------

class SafeguardingConsent(BaseModel):
    id: str
    subject_id: str
    consent_type: ConsentType
    consenter_id: str
    consent_text: Optional[str] = None
    document_id: Optional[str] = None
    given_at: datetime = Field(default_factory=datetime.now)
    valid_until: Optional[date] = None
    revoked_at: Optional[datetime] = None
    organization_id: Optional[str] = None
    organization_type: Optional[OrganizationType] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4. Incidents
# ---------------------------------------------------------------------------

class IncidentReport(BaseModel):
    id: str
    organization_id: str
    organization_type: OrganizationType
    occurred_at: datetime
    reported_by: Optional[str] = None
    severity: Literal["low", "mid", "high", "critical"]
    category: Optional[Literal["pool", "playground", "animal", "minor_safety", "transport", "other"]] = None
    description: str
    persons_involved: list[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    status: IncidentStatus = "open"
    document_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5. Signale
# ---------------------------------------------------------------------------

class SafeguardingSignal(BaseModel):
    id: Optional[int] = None
    organization_id: Optional[str] = None
    organization_type: Optional[OrganizationType] = None
    edition: Optional[str] = None
    signal_key: str
    severity: SignalSeverity = "mid"
    params: dict = Field(default_factory=dict)
    related_person_id: Optional[str] = None
    related_entity: dict = Field(default_factory=dict)
    status: Literal["open", "acknowledged", "resolved", "ignored"] = "open"
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[str] = None


# ---------------------------------------------------------------------------
# 6. Pattern-Kandidat (gelernt, NICHT aktiv)
# ---------------------------------------------------------------------------

class PatternCandidate(BaseModel):
    id: Optional[int] = None
    pattern_type: PatternType
    pattern_key: str
    description: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    occurrences: int
    related_signal_keys: list[str] = Field(default_factory=list)
    related_entities: dict = Field(default_factory=dict)
    applicable_editions: list[str] = Field(default_factory=list)
    suggested_action: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    status: PatternStatus = "pending"
    promoted_at: Optional[datetime] = None
    promoted_by: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 7. Pattern-Promoted (aktiv)
# ---------------------------------------------------------------------------

class PromotedPattern(BaseModel):
    id: Optional[int] = None
    candidate_id: Optional[int] = None
    pattern_key: str
    description: Optional[str] = None
    pattern_type: PatternType
    active_since: datetime = Field(default_factory=datetime.now)
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    fires_signal: Optional[str] = None
    fires_severity: SignalSeverity = "mid"
    affecting_organizations: list[dict] = Field(default_factory=list)
    last_fired_at: Optional[datetime] = None
    fire_count: int = 0
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 8. Severity-Feedback (aggregiert)
# ---------------------------------------------------------------------------

class SeverityFeedback(BaseModel):
    signal_key: str
    current_default_severity: SignalSeverity
    feedback_count: int = 0
    feedback_score_sum: float = 0.0
    proposed_severity: Optional[SignalSeverity] = None
    proposed_at: Optional[datetime] = None
    last_resolution_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)

    @property
    def mean_score(self) -> float:
        if self.feedback_count == 0:
            return 0.0
        return self.feedback_score_sum / self.feedback_count


# ---------------------------------------------------------------------------
# 9. Action-Templates
# ---------------------------------------------------------------------------

class ActionTemplate(BaseModel):
    id: Optional[int] = None
    pattern_key: str
    action_type: Literal["alert", "pre_warn", "block_action", "remind", "suggest"]
    text_key: str
    params_template: dict = Field(default_factory=dict)
    timing: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 10. Cross-Edition Hints
# ---------------------------------------------------------------------------

class CrossEditionHint(BaseModel):
    id: Optional[int] = None
    source_edition: str
    target_edition: str
    pattern_key: str
    hint_text_key: str
    sent_at: datetime = Field(default_factory=datetime.now)
    accepted_by_target: bool = False
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 11. Request/Response Wrapper
# ---------------------------------------------------------------------------

class PromoteCandidateRequest(BaseModel):
    candidate_id: int
    promoted_by: str
    fires_signal: Optional[str] = None
    fires_severity: SignalSeverity = "mid"
    affecting_organizations: list[dict] = Field(default_factory=list)


class DismissCandidateRequest(BaseModel):
    candidate_id: int
    dismissed_by: str
    reason: Optional[str] = None


class RecordFeedbackRequest(BaseModel):
    signal_id: int
    resolution_action: str  # 'resolved_immediately', 'resolved_within_24h', 'resolved_late', 'dismissed', 'escalated'
    resolved_by: str


class AcceptSeverityProposalRequest(BaseModel):
    signal_key: str
    accepted_by: str
    accept: bool


# ---------------------------------------------------------------------------
# 12. Module-Profile
# ---------------------------------------------------------------------------

SAFEGUARDING_MODULE_PROFILE: dict[str, Any] = {
    "module": "safeguarding",
    "version": "1.0.0",
    "scope": "cross-edition",
    "applicable_editions": ["club.shiksha", "schule.shiksha", "camping.shiksha"],
    "is_phase_1_required": True,
    "learning_modes": [
        "frequency_cluster_pattern",
        "seasonal_pattern",
        "cross_edition_pattern",
        "severity_feedback_adjustment",
    ],
    "policy_promotion_required": True,
    "review_required_default": True,
}


__all__ = [
    "OrganizationType", "SignalSeverity", "PatternType", "PatternStatus", "IncidentStatus", "ConsentType",
    "ProtectionPolicy", "PersonProtectionStatus", "BackgroundCheck",
    "SafeguardingConsent", "IncidentReport", "SafeguardingSignal",
    "PatternCandidate", "PromotedPattern", "SeverityFeedback", "ActionTemplate", "CrossEditionHint",
    "PromoteCandidateRequest", "DismissCandidateRequest",
    "RecordFeedbackRequest", "AcceptSeverityProposalRequest",
    "SAFEGUARDING_MODULE_PROFILE",
]

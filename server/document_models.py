# document_models.py
# document.module V1.1 — business.shiksha
# Replaces V1. Extended: dunning, penalty_notice, multi-address, debug layer.

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# INTAKE
# ---------------------------------------------------------------------------

class DocumentIntakeRequest(BaseModel):
    edition: str = "business.shiksha"
    source_type: str = "text"           # text | image_scan | pdf
    raw_text: str
    language: Optional[str] = "de"


# ---------------------------------------------------------------------------
# EXTRACTION — Candidates, never facts
# ---------------------------------------------------------------------------

class DocumentFieldCandidate(BaseModel):
    field_key: str
    field_value: str
    confidence: float                       # 0.0–1.0, always visible
    confidence_note: Optional[str] = None   # why this confidence


# ---------------------------------------------------------------------------
# DETECTION DEBUG — why was this type chosen?
# ---------------------------------------------------------------------------

class DetectionDebug(BaseModel):
    scores: dict                    # all type scores, e.g. {"invoice": 2, "dunning": 5}
    winning_signals: List[str]      # keywords that triggered the winner
    runner_up: Optional[str] = None
    runner_up_score: int = 0
    decision_note: str              # human-readable explanation


# ---------------------------------------------------------------------------
# ENTITY ADDRESS — structured, not a flat string
# ---------------------------------------------------------------------------

class EntityAddress(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address_raw: Optional[str] = None      # original string always preserved
    match_contribution: float = 0.0        # how much this address raised confidence


# ---------------------------------------------------------------------------
# ENTITY SUGGESTION — proposed link, never automatic
# ---------------------------------------------------------------------------

class DocumentEntitySuggestion(BaseModel):
    target_type: str = "customer"
    suggested_entity_id: Optional[str] = None
    suggested_entity_name: Optional[str] = None
    match_basis: Optional[str] = None      # "name" | "name+address" | "address_only"
    name_score: float = 0.0
    address_score: float = 0.0
    confidence: float = 0.0                # combined final score
    address_note: Optional[str] = None     # e.g. "known secondary address"
    review_required: bool = True           # always True in V1


# ---------------------------------------------------------------------------
# ANALYSIS RESPONSE
# ---------------------------------------------------------------------------

class DocumentAnalysisResponse(BaseModel):
    document_id: str
    edition: str
    detected_document_type: str
    # invoice | dunning | penalty_notice | offer | contract | note | unknown
    source_quality: str = "text"           # text | image_scan | pdf
    extracted_fields: List[DocumentFieldCandidate]
    entity_suggestion: DocumentEntitySuggestion
    review_required: bool = True
    status: str = "analyzed"
    created_at: datetime
    detection_debug: Optional[DetectionDebug] = None


# ---------------------------------------------------------------------------
# CONFIRM LINK
# ---------------------------------------------------------------------------

class DocumentConfirmLinkRequest(BaseModel):
    document_id: str
    entity_type: str = "customer"
    entity_id: str
    operator_decision: str              # confirm | correct
    operator_note: Optional[str] = None


class SavedLink(BaseModel):
    link_id: str
    document_id: str
    entity_type: str
    entity_id: str
    link_type: str = "belongs_to"
    review_status: str
    confirmed_at: datetime


class DocumentConfirmLinkResponse(BaseModel):
    success: bool
    document_status: str = "linked"
    saved_link: SavedLink

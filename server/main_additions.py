# main_additions.py
# document.module V1 — new endpoints for main.py
#
# HOW TO INTEGRATE:
# 1. Add these imports to the top of main.py:
#
#    from document_models import (
#        DocumentIntakeRequest, DocumentAnalysisResponse,
#        DocumentConfirmLinkRequest, DocumentConfirmLinkResponse, SavedLink,
#    )
#    from document_module import build_document_analysis
#    from database_additions import (
#        define_document_tables, init_document_tables,
#        save_document, save_field_candidates,
#        save_document_link, update_document_status,
#    )
#
# 2. After your existing table setup in main.py, add:
#
#    doc_tables_tuple = define_document_tables(metadata)
#    tables = {
#        "documents":                 doc_tables_tuple[0],
#        "document_field_candidates": doc_tables_tuple[1],
#        "document_links":            doc_tables_tuple[2],
#    }
#    init_document_tables(engine, metadata)
#
# 3. Paste the two route functions below into main.py.

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from document_models import (
    DocumentIntakeRequest,
    DocumentAnalysisResponse,
    DocumentConfirmLinkRequest,
    DocumentConfirmLinkResponse,
    SavedLink,
)
from document_module import build_document_analysis
from database_additions import (
    save_document,
    save_field_candidates,
    save_document_link,
    update_document_status,
)

# If you use APIRouter in main.py, adjust accordingly.
# These examples use `app` directly — replace with your router if needed.

# ---------------------------------------------------------------------------
# POST /documents/analyze
# ---------------------------------------------------------------------------

# @app.post("/documents/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(request: DocumentIntakeRequest):
    """
    Intake and analyze a document.
    - Detects document type
    - Extracts field candidates with confidence
    - Suggests a customer entity (never links automatically)
    - Persists document + candidates to DB
    - Always returns review_required = true
    """

    # 1. Run analysis (pure logic, no side effects)
    analysis = build_document_analysis(
        raw_text=request.raw_text,
        edition=request.edition,
    )

    # 2. Persist document
    with engine.begin() as conn:
        save_document(
            conn=conn,
            tables=tables,
            document_id=analysis.document_id,
            edition=analysis.edition,
            document_type=analysis.detected_document_type,
            source_type=request.source_type,
            raw_text=request.raw_text,
            status="analyzed",
        )
        save_field_candidates(
            conn=conn,
            tables=tables,
            document_id=analysis.document_id,
            candidates=analysis.extracted_fields,
        )

    return analysis


# ---------------------------------------------------------------------------
# POST /documents/confirm-link
# ---------------------------------------------------------------------------

# @app.post("/documents/confirm-link", response_model=DocumentConfirmLinkResponse)
async def confirm_document_link(request: DocumentConfirmLinkRequest):
    """
    Operator confirms or corrects a proposed entity link.
    - operator_decision: "confirm" → uses suggested entity
    - operator_decision: "correct" → uses operator-provided entity_id
    Only after this call is the DocumentLink persisted.
    Document status is updated to "linked".
    """

    if request.operator_decision not in ("confirm", "correct"):
        raise HTTPException(
            status_code=400,
            detail="operator_decision must be 'confirm' or 'correct'"
        )

    review_status = (
        "confirmed" if request.operator_decision == "confirm" else "corrected"
    )

    # Confidence: confirmed = 1.0 (operator verified), corrected = 1.0 (operator override)
    # We record 1.0 because the operator is the source of truth at this point.
    with engine.begin() as conn:
        link_id = save_document_link(
            conn=conn,
            tables=tables,
            document_id=request.document_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            link_type="belongs_to",
            confidence=1.0,
            review_status=review_status,
        )
        update_document_status(
            conn=conn,
            tables=tables,
            document_id=request.document_id,
            new_status="linked",
        )

    return DocumentConfirmLinkResponse(
        success=True,
        document_status="linked",
        saved_link=SavedLink(
            link_id=link_id,
            document_id=request.document_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            link_type="belongs_to",
            review_status=review_status,
            confirmed_at=datetime.now(timezone.utc),
        ),
    )

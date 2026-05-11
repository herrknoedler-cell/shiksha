"""Memory-Router — CRUD über die persistenten Erinnerungen pro Operator."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import get_current_operator, require_developer
from ..models import MemoryEntry, Operator
from ..schemas.memory import MemoryCreateRequest, MemoryEntryOut, MemoryPatchRequest

router = APIRouter()


# ===================================================================
# GET — eigene Memory listen
# ===================================================================

@router.get("", response_model=list[MemoryEntryOut], operation_id="memory_list")
def list_memory(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    target_operator_id: str | None = Query(
        None,
        description="Nur für Developer: Memory eines anderen Operators ansehen",
    ),
) -> list[MemoryEntryOut]:
    """Operator sieht eigene Einträge; Developer kann via target_operator_id andere ansehen."""
    target_id = operator.id
    if target_operator_id and target_operator_id != operator.id:
        if operator.role != "developer":
            raise HTTPException(status_code=403, detail="Cross-operator access requires developer role")
        target_id = target_operator_id

    rows = db.execute(
        select(MemoryEntry)
        .where(MemoryEntry.operator_id == target_id)
        .order_by(MemoryEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return [MemoryEntryOut.model_validate(r) for r in rows]


# ===================================================================
# POST — Eintrag anlegen
# ===================================================================

@router.post("", response_model=MemoryEntryOut, status_code=status.HTTP_201_CREATED, operation_id="memory_create")
def create_memory(
    payload: MemoryCreateRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MemoryEntryOut:
    """Eintrag für eigenen Operator (oder für anderen wenn Developer)."""
    target_id = operator.id
    target_edition = operator.edition

    if payload.operator_id and payload.operator_id != operator.id:
        if operator.role != "developer":
            raise HTTPException(status_code=403, detail="Cross-operator write requires developer role")
        target_op = db.get(Operator, payload.operator_id)
        if target_op is None:
            raise HTTPException(status_code=404, detail="Target operator not found")
        target_id = target_op.id
        target_edition = target_op.edition

    entry = MemoryEntry(
        operator_id=target_id,
        edition=target_edition,
        text=payload.text.strip(),
        source_session_id=payload.source_session_id,
    )
    db.add(entry)
    db.flush()
    return MemoryEntryOut.model_validate(entry)


# ===================================================================
# PATCH — Eintrag editieren
# ===================================================================

@router.patch("/{memory_id}", response_model=MemoryEntryOut, operation_id="memory_patch")
def patch_memory(
    memory_id: int,
    payload: MemoryPatchRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MemoryEntryOut:
    entry = db.get(MemoryEntry, memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if entry.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your memory entry")

    entry.text = payload.text.strip()
    db.add(entry)
    db.flush()
    return MemoryEntryOut.model_validate(entry)


# ===================================================================
# DELETE — Eintrag entfernen
# ===================================================================

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="memory_delete")
def delete_memory(
    memory_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> None:
    entry = db.get(MemoryEntry, memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if entry.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your memory entry")

    db.delete(entry)
    db.flush()


# ===================================================================
# GET /count — wie viele Einträge hat ein Operator
# ===================================================================

@router.get("/count", operation_id="memory_count")
def count_memory(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> dict:
    from sqlalchemy import func
    count = db.execute(
        select(func.count(MemoryEntry.id)).where(MemoryEntry.operator_id == operator.id)
    ).scalar_one()
    return {"operator_id": operator.id, "memory_count": count}

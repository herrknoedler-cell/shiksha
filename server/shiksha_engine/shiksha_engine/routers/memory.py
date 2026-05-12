"""Memory-Router — CRUD über die persistenten Erinnerungen pro Operator.

Memory-Statuses (Spec Abschnitt 9):
  active    — gilt im System-Prompt
  proposed  — inline von Tool-Call angelegt, wartet auf Bestätigung
  dismissed — abgelehnt, geht nicht in den Prompt
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import get_current_operator, require_developer
from ..models import MemoryEntry, Operator
from ..models.memory import MEMORY_STATUSES
from ..schemas.memory import MemoryCreateRequest, MemoryEntryOut, MemoryPatchRequest

router = APIRouter()


def _check_status_filter(value: str) -> str:
    if value not in MEMORY_STATUSES and value != "all":
        raise HTTPException(
            status_code=400,
            detail=f"status must be 'all' or one of {MEMORY_STATUSES}",
        )
    return value


# ===================================================================
# GET — eigene Memory listen
# ===================================================================

@router.get("", response_model=list[MemoryEntryOut], operation_id="memory_list")
def list_memory(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str = Query(
        "active",
        alias="status",
        description="active | proposed | dismissed | all (Default: active)",
    ),
    include_deleted: bool = Query(False, description="Soft-deleted mit anzeigen"),
    target_operator_id: str | None = Query(
        None,
        description="Nur für Developer: Memory eines anderen Operators ansehen",
    ),
) -> list[MemoryEntryOut]:
    """Operator sieht eigene Einträge; Developer kann via target_operator_id andere ansehen.

    Default: nur active und non-deleted. Mit `?status=proposed` sieht die
    Trägerin die Tool-erzeugten Vorschläge zum Bestätigen/Verwerfen.
    """
    _check_status_filter(status_filter)

    target_id = operator.id
    if target_operator_id and target_operator_id != operator.id:
        if operator.role != "developer":
            raise HTTPException(status_code=403, detail="Cross-operator access requires developer role")
        target_id = target_operator_id

    query = select(MemoryEntry).where(MemoryEntry.operator_id == target_id)
    if status_filter != "all":
        query = query.where(MemoryEntry.status == status_filter)
    if not include_deleted:
        query = query.where(MemoryEntry.deleted_at.is_(None))

    rows = db.execute(
        query
        .order_by(MemoryEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return [MemoryEntryOut.model_validate(r) for r in rows]


# ===================================================================
# POST — Eintrag anlegen (manuell, immer status='active')
# ===================================================================

@router.post("", response_model=MemoryEntryOut, status_code=status.HTTP_201_CREATED, operation_id="memory_create")
def create_memory(
    payload: MemoryCreateRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MemoryEntryOut:
    """Eintrag für eigenen Operator (oder für anderen wenn Developer).

    Manuell angelegte Memory wird immer mit status='active' gespeichert.
    Tool-erzeugte Memory landet auf status='proposed' (siehe tools_runtime).
    """
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
        status="active",
    )
    db.add(entry)
    db.flush()
    return MemoryEntryOut.model_validate(entry)


# ===================================================================
# POST /{id}/confirm — proposed → active
# ===================================================================

@router.post(
    "/{memory_id}/confirm",
    response_model=MemoryEntryOut,
    operation_id="memory_confirm",
)
def confirm_memory(
    memory_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MemoryEntryOut:
    """Einen 'proposed' Memory-Eintrag bestätigen → wird 'active'.

    Nur erlaubt für Operator selbst (oder Developer für andere).
    Memory geht damit in den System-Prompt zukünftiger Sessions ein.
    """
    entry = db.get(MemoryEntry, memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if entry.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your memory entry")
    if entry.deleted_at is not None:
        raise HTTPException(status_code=410, detail="Memory entry is deleted")
    if entry.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail=f"Only proposed memory can be confirmed (current: {entry.status})",
        )

    entry.status = "active"
    db.add(entry)
    db.flush()
    return MemoryEntryOut.model_validate(entry)


# ===================================================================
# POST /{id}/dismiss — proposed → dismissed
# ===================================================================

@router.post(
    "/{memory_id}/dismiss",
    response_model=MemoryEntryOut,
    operation_id="memory_dismiss",
)
def dismiss_memory(
    memory_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MemoryEntryOut:
    """Einen 'proposed' Memory-Eintrag verwerfen → 'dismissed'.

    Eintrag bleibt für Audit-Spur erhalten, geht aber nie in den Prompt.
    """
    entry = db.get(MemoryEntry, memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if entry.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your memory entry")
    if entry.deleted_at is not None:
        raise HTTPException(status_code=410, detail="Memory entry is deleted")
    if entry.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail=f"Only proposed memory can be dismissed (current: {entry.status})",
        )

    entry.status = "dismissed"
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
# DELETE — Soft-Delete (Spec Abschnitt 8)
# ===================================================================

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="memory_delete")
def delete_memory(
    memory_id: int,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> None:
    """Soft-Delete: setzt deleted_at, Eintrag bleibt für Audit erhalten."""
    entry = db.get(MemoryEntry, memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if entry.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your memory entry")

    if entry.deleted_at is None:
        entry.deleted_at = datetime.now(timezone.utc)
        db.add(entry)
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

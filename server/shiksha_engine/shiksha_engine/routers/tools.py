"""Tools-Router — Endpoints für SHIKSHA's Function-Calls.

Phase 1: Endpoints stehen als Skelett, sind direkt aufrufbar.
Phase 4: Anthropic ruft sie automatisch via Function-Calling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import require_operator_or_developer
from ..models import FrictionPoint, MemoryEntry, Observation, Operator, Session

router = APIRouter()


# ===================================================================
# Schemas
# ===================================================================

class LogObservationRequest(BaseModel):
    session_id: str
    kind: str | None = Field(default=None, max_length=32)
    text: str = Field(min_length=1, max_length=2000)
    metadata: dict = Field(default_factory=dict)


class LogFrictionRequest(BaseModel):
    session_id: str
    where: str | None = Field(default=None, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


class SaveDaySummaryRequest(BaseModel):
    session_id: str
    summary: str = Field(min_length=1, max_length=2000)
    insights: list[str] = Field(default_factory=list)


class AddMemoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    source_session_id: str | None = None


# ===================================================================
# Helpers
# ===================================================================

def _own_session(db: DBSession, session_id: str, operator: Operator) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your session")
    return session


# ===================================================================
# Endpoints
# ===================================================================

@router.post("/log_observation")
def log_observation(
    payload: LogObservationRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> dict:
    """SHIKSHA: 'Lukas war heute besonders.' → eine Beobachtung wird abgelegt."""
    session = _own_session(db, payload.session_id, operator)

    obs = Observation(
        session_id=session.id,
        edition=session.edition,
        kind=payload.kind,
        text=payload.text,
        metadata_=payload.metadata or {},
    )
    db.add(obs)
    db.flush()
    return {"observation_id": obs.id, "logged_at": obs.ts.isoformat()}


@router.post("/log_friction")
def log_friction(
    payload: LogFrictionRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> dict:
    """SHIKSHA: 'Du warst Dir bei der Warnung nicht sicher.' → offene Stelle."""
    session = _own_session(db, payload.session_id, operator)

    fp = FrictionPoint(
        session_id=session.id,
        edition=session.edition,
        where_label=payload.where,
        text=payload.text,
    )
    db.add(fp)
    db.flush()
    return {"friction_id": fp.id, "logged_at": fp.ts.isoformat()}


@router.post("/save_day_summary")
def save_day_summary(
    payload: SaveDaySummaryRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> dict:
    """Am Session-Ende: Zusammenfassung + Insights speichern."""
    session = _own_session(db, payload.session_id, operator)

    session.summary = payload.summary
    session.insights = payload.insights
    if not session.closed_at:
        session.closed_at = datetime.utcnow()
    db.add(session)

    # Insights wandern auch ins Memory
    for insight in payload.insights:
        if insight.strip():
            db.add(MemoryEntry(
                operator_id=operator.id,
                edition=operator.edition,
                text=insight.strip(),
                source_session_id=session.id,
            ))

    db.flush()
    return {
        "session_id": session.id,
        "summary": session.summary,
        "insights_count": len(payload.insights),
    }


@router.post("/add_memory")
def add_memory(
    payload: AddMemoryRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> dict:
    """Direkt ein Memory-Eintrag anlegen (Phase-1 manuell, später automatisch via Tool)."""
    entry = MemoryEntry(
        operator_id=operator.id,
        edition=operator.edition,
        text=payload.text,
        source_session_id=payload.source_session_id,
    )
    db.add(entry)
    db.flush()
    return {"memory_id": entry.id, "text": entry.text}

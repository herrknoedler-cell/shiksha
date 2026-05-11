"""Sessions-Router — Liste mit Filter, Detail, Search."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import get_current_operator
from ..models import Message, Operator, Session

router = APIRouter()


@router.get("", operation_id="sessions_list")
def list_sessions(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    edition: str | None = Query(None, description="Filter nach Edition (kita, camping, ...)"),
    persona: str | None = Query(None, description="Filter nach Persona (tagesausklang, kennenlernen, ...)"),
    since: datetime | None = Query(None, description="Nur Sessions gestartet ab diesem Zeitpunkt"),
    until: datetime | None = Query(None, description="Nur Sessions gestartet bis zu diesem Zeitpunkt"),
    has_summary: bool | None = Query(None, description="True: nur Sessions mit Summary; False: nur ohne"),
    q: str | None = Query(None, min_length=2, description="Volltext-Suche in summary"),
    target_operator_id: str | None = Query(
        None,
        description="Nur für Developer: Sessions eines anderen Operators",
    ),
) -> list[dict]:
    """Eigene Sessions (operator) oder gefilterte Cross-Operator-Liste (developer)."""

    stmt = select(Session).order_by(Session.started_at.desc())

    # Scope
    if operator.role == "developer":
        if target_operator_id:
            stmt = stmt.where(Session.operator_id == target_operator_id)
        # else: alle Sessions (developer sieht alle)
    else:
        if target_operator_id and target_operator_id != operator.id:
            raise HTTPException(status_code=403, detail="Cross-operator listing requires developer role")
        stmt = stmt.where(Session.operator_id == operator.id)

    # Filter
    if edition:
        stmt = stmt.where(Session.edition == edition)
    if persona:
        stmt = stmt.where(Session.persona == persona)
    if since:
        stmt = stmt.where(Session.started_at >= since)
    if until:
        stmt = stmt.where(Session.started_at <= until)
    if has_summary is True:
        stmt = stmt.where(Session.summary.is_not(None))
    elif has_summary is False:
        stmt = stmt.where(Session.summary.is_(None))
    if q:
        # Simpler ILIKE — Volltextsearch wenn Postgres-FTS später eingerichtet
        stmt = stmt.where(Session.summary.ilike(f"%{q}%"))

    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()

    return [
        {
            "id":          s.id,
            "operator_id": s.operator_id,
            "edition":     s.edition,
            "persona":     s.persona,
            "started_at":  s.started_at.isoformat(),
            "closed_at":   s.closed_at.isoformat() if s.closed_at else None,
            "summary":     s.summary,
            "insights":    s.insights,
            "tokens_used": s.tokens_used,
        }
        for s in rows
    ]


@router.get("/{session_id}", operation_id="sessions_detail")
def get_session(
    session_id: str,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> dict:
    """Session-Detail mit Messages."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your session")

    messages = db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.ts)
    ).scalars().all()

    return {
        "id":          session.id,
        "operator_id": session.operator_id,
        "edition":     session.edition,
        "persona":     session.persona,
        "started_at":  session.started_at.isoformat(),
        "closed_at":   session.closed_at.isoformat() if session.closed_at else None,
        "summary":     session.summary,
        "insights":    session.insights,
        "tokens_used": session.tokens_used,
        "messages": [
            {
                "id":      m.id,
                "role":    m.role,
                "content": m.content,
                "mode":    m.mode,
                "ts":      m.ts.isoformat(),
            }
            for m in messages
        ],
    }

"""Sessions-Router — Liste, Detail, eigene Daten."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import get_current_operator
from ..models import Message, Operator, Session

router = APIRouter()


@router.get("")
def list_sessions(
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(get_current_operator)],
    limit: int = 50,
) -> list[dict]:
    """Eigene Sessions (operator) bzw. alle (developer)."""
    stmt = select(Session).order_by(Session.started_at.desc()).limit(limit)
    if operator.role != "developer":
        stmt = stmt.where(Session.operator_id == operator.id)

    results = db.execute(stmt).scalars().all()
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
        for s in results
    ]


@router.get("/{session_id}")
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

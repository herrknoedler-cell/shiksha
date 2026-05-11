"""Chat-Router — /respond (block) und /stream (SSE)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from sse_starlette.sse import EventSourceResponse

from ..db import get_db
from ..deps import require_operator_or_developer
from ..models import Message, Operator, Session
from ..schemas.chat import ChatRequest, ChatResponse
from ..services import anthropic_client, persona_loader

router = APIRouter()


def _make_session_id() -> str:
    return "ses_" + secrets.token_urlsafe(12)


def _ensure_session(
    db: DBSession,
    *,
    session_id: str | None,
    operator: Operator,
    persona: str,
) -> Session:
    if session_id:
        session = db.get(Session, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.operator_id != operator.id and operator.role != "developer":
            raise HTTPException(status_code=403, detail="Not your session")
        return session

    session = Session(
        id=_make_session_id(),
        operator_id=operator.id,
        org_id=operator.org_id,
        edition=operator.edition,
        persona=persona,
    )
    db.add(session)
    db.flush()
    return session


def _build_message_history(db: DBSession, session: Session) -> list[dict]:
    msgs = db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.ts)
    ).scalars().all()
    return [{"role": m.role, "content": m.content} for m in msgs]


@router.post("/respond", response_model=ChatResponse)
def respond(
    payload: ChatRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> ChatResponse:
    """Sync-Endpoint — gibt die komplette Antwort als JSON."""
    session = _ensure_session(
        db, session_id=payload.session_id, operator=operator, persona=payload.persona
    )

    # Persona-Prompt laden
    system_prompt = persona_loader.load_system_prompt(
        db, operator=operator, persona=payload.persona
    )
    if system_prompt is None:
        raise HTTPException(status_code=404, detail=f"No persona prompt for '{payload.persona}'")

    # User-Message persistieren
    user_msg = Message(session_id=session.id, role="user", content=payload.user_message)
    db.add(user_msg)
    db.flush()

    # History laden + an Claude geben
    history = _build_message_history(db, session)
    result = anthropic_client.respond_block(
        system_prompt=system_prompt, messages=history
    )

    # Assistant-Message persistieren
    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=result.text,
        mode=result.mode,
    )
    db.add(asst_msg)

    # Tokens aufaddieren
    session.tokens_used = (session.tokens_used or 0) + result.tokens_used
    db.add(session)
    db.flush()

    return ChatResponse(
        session_id=session.id,
        shiksha_response=result.text,
        mode=result.mode,
        tokens_used=result.tokens_used,
    )


@router.post("/stream")
async def stream(
    payload: ChatRequest,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
):
    """SSE-Endpoint — streamt Wort-für-Wort.

    Events:
      data: {"session_id": "..."}          — Session-ID am Anfang
      data: {"delta": "Wort"}               — pro Chunk
      data: {"done": true, "mode": "...", "tokens_used": N}  — am Ende
    """
    session = _ensure_session(
        db, session_id=payload.session_id, operator=operator, persona=payload.persona
    )

    system_prompt = persona_loader.load_system_prompt(
        db, operator=operator, persona=payload.persona
    )
    if system_prompt is None:
        raise HTTPException(status_code=404, detail=f"No persona prompt for '{payload.persona}'")

    user_msg = Message(session_id=session.id, role="user", content=payload.user_message)
    db.add(user_msg)
    db.flush()
    history = _build_message_history(db, session)
    session_id = session.id
    operator_id = operator.id  # capture for closure

    async def event_generator():
        yield {"data": json.dumps({"session_id": session_id})}

        final_text = ""
        final_mode = None
        tokens_used = 0

        async for chunk in anthropic_client.respond_stream(
            system_prompt=system_prompt, messages=history
        ):
            if "delta" in chunk:
                yield {"data": json.dumps({"delta": chunk["delta"]})}
            elif chunk.get("done"):
                final_text = chunk["text"]
                final_mode = chunk["mode"]
                tokens_used = chunk["tokens_used"]
                yield {"data": json.dumps({
                    "done": True,
                    "mode": final_mode,
                    "tokens_used": tokens_used,
                })}

        # Nach Stream-Ende: persistieren — eigene Session, weil
        # die FastAPI-Dependency-Session nach yield bereits weg ist.
        from ..db import SessionLocal
        with SessionLocal() as save_db:
            save_session = save_db.get(Session, session_id)
            if save_session:
                save_db.add(Message(
                    session_id=session_id,
                    role="assistant",
                    content=final_text,
                    mode=final_mode,
                ))
                save_session.tokens_used = (save_session.tokens_used or 0) + tokens_used
                save_db.add(save_session)
                save_db.commit()

    return EventSourceResponse(event_generator())


@router.post("/close/{session_id}")
def close_session(
    session_id: str,
    db: Annotated[DBSession, Depends(get_db)],
    operator: Annotated[Operator, Depends(require_operator_or_developer)],
) -> dict:
    """Markiert eine Session als geschlossen. Insight-Extraktion kommt in Phase 4."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.operator_id != operator.id and operator.role != "developer":
        raise HTTPException(status_code=403, detail="Not your session")

    session.closed_at = datetime.utcnow()
    db.add(session)
    db.flush()
    return {"session_id": session.id, "closed_at": session.closed_at.isoformat()}

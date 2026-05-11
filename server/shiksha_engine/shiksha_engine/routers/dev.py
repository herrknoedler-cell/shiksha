"""Developer-only Endpoints — Stats, Persona-CRUD, Memory-Management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import require_developer
from ..models import AuditLog, MemoryEntry, Operator, PersonaPrompt, Session

router = APIRouter()


@router.get("/stats")
def stats(
    db: Annotated[DBSession, Depends(get_db)],
    _: Annotated[Operator, Depends(require_developer)],
) -> dict:
    """Pilot-Statistik."""
    total_sessions = db.execute(select(func.count(Session.id))).scalar_one()
    total_operators = db.execute(select(func.count(Operator.id))).scalar_one()
    total_memory = db.execute(select(func.count(MemoryEntry.id))).scalar_one()

    by_edition = db.execute(
        select(Session.edition, func.count(Session.id))
        .group_by(Session.edition)
    ).all()

    return {
        "sessions_total":  total_sessions,
        "operators_total": total_operators,
        "memory_total":    total_memory,
        "sessions_by_edition": dict(by_edition),
    }


@router.get("/operators")
def list_operators(
    db: Annotated[DBSession, Depends(get_db)],
    _: Annotated[Operator, Depends(require_developer)],
) -> list[dict]:
    operators = db.execute(select(Operator).order_by(Operator.created_at.desc())).scalars().all()
    return [
        {
            "id":           o.id,
            "display_name": o.display_name,
            "role":         o.role,
            "edition":      o.edition,
            "org_id":       o.org_id,
            "email":        o.email,
            "passkeys":     len(o.webauthn_credentials or []),
            "created_at":   o.created_at.isoformat(),
        }
        for o in operators
    ]


@router.get("/persona-prompts")
def list_personas(
    db: Annotated[DBSession, Depends(get_db)],
    _: Annotated[Operator, Depends(require_developer)],
) -> list[dict]:
    rows = db.execute(
        select(PersonaPrompt).order_by(
            PersonaPrompt.name, PersonaPrompt.edition, PersonaPrompt.version.desc()
        )
    ).scalars().all()
    return [
        {
            "name":         p.name,
            "edition":      p.edition,
            "version":      p.version,
            "description":  p.description,
            "system_prompt": p.system_prompt,
            "updated_at":   p.updated_at.isoformat(),
        }
        for p in rows
    ]


class PersonaUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    edition: str = Field(min_length=1, max_length=32, default="*")
    system_prompt: str = Field(min_length=10)
    description: str | None = None


@router.put("/persona-prompts")
def update_persona(
    payload: PersonaUpdate,
    db: Annotated[DBSession, Depends(get_db)],
    developer: Annotated[Operator, Depends(require_developer)],
) -> dict:
    """Speichert eine neue Version. Alte Versionen bleiben erhalten."""
    latest = db.execute(
        select(func.max(PersonaPrompt.version))
        .where(PersonaPrompt.name == payload.name)
        .where(PersonaPrompt.edition == payload.edition)
    ).scalar()
    next_version = (latest or 0) + 1

    new_row = PersonaPrompt(
        name=payload.name,
        edition=payload.edition,
        version=next_version,
        system_prompt=payload.system_prompt,
        description=payload.description,
        updated_by=developer.id,
    )
    db.add(new_row)
    db.flush()

    return {
        "name":    new_row.name,
        "edition": new_row.edition,
        "version": new_row.version,
    }


@router.post("/setup-tokens", operation_id="dev_setup_token_create")
def create_setup_token(
    payload: dict,
    _: Annotated[Operator, Depends(require_developer)],
    db: Annotated[DBSession, Depends(get_db)],
) -> dict:
    """Generiert einen Setup-Token für einen Operator.

    Token lebt 10 Min. URL für die Operator-Person:
        https://shiksha.world/presence_switch.html?setup=<TOKEN>

    Beim Klick auf eine Operator-Karte im Presence-Switch wird statt
    Login der Register-Flow ausgeführt → Operator-Phone bekommt Passkey.

    Body: {"operator_id": "krummelus_mira"}
    """
    from ..services import setup_token_service

    operator_id = payload.get("operator_id")
    if not operator_id:
        raise HTTPException(status_code=400, detail="operator_id required")

    operator = db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator not found")

    token, expires_at = setup_token_service.issue(operator_id)
    return {
        "token":       token,
        "operator_id": operator_id,
        "expires_at":  expires_at,
        "expires_in":  600,
        "setup_url":   f"https://shiksha.world/presence_switch.html?setup={token}",
    }


@router.get("/setup-tokens", operation_id="dev_setup_tokens_list")
def list_setup_tokens(
    _: Annotated[Operator, Depends(require_developer)],
) -> list[dict]:
    """Liste aktiver Setup-Tokens (Prefix + Operator + Restzeit)."""
    from ..services import setup_token_service
    return setup_token_service.list_active()


@router.get("/audit-logs")
def list_audit_logs(
    db: Annotated[DBSession, Depends(get_db)],
    _: Annotated[Operator, Depends(require_developer)],
    limit: int = 100,
) -> list[dict]:
    rows = db.execute(
        select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id":             r.id,
            "ts":             r.ts.isoformat(),
            "actor_id":       r.actor_id,
            "actor_role":     r.actor_role,
            "action":         r.action,
            "target_type":    r.target_type,
            "target_id":      r.target_id,
            "request_path":   r.request_path,
            "request_method": r.request_method,
            "ip_address":     r.ip_address,
        }
        for r in rows
    ]

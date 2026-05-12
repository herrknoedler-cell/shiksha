"""Common FastAPI Dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DBSession

from .db import get_db
from .models import Operator
from .services.jwt_service import TokenError, verify_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict:
    """Extrahiert und validiert das JWT, gibt die Claims zurück."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_token(credentials.credentials)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_operator(
    request: Request,
    payload: Annotated[dict, Depends(get_current_payload)],
    db: Annotated[DBSession, Depends(get_db)],
) -> Operator:
    """Lädt den Operator aus dem JWT-Subject."""
    operator_id = payload["sub"]
    operator = db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator not found",
        )
    # Audit-Middleware kann das später lesen
    request.state.actor_id = operator.id
    request.state.actor_role = operator.role
    return operator


async def require_developer(
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> Operator:
    """Nur Developer dürfen weiter."""
    if operator.role != "developer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer role required",
        )
    return operator


async def require_operator_or_developer(
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> Operator:
    """Operator oder Developer — Observer nicht.

    Legacy-Helper: erlaubt 'operator' (legacy) + alle staff-Rollen
    (leitung, padagoge, trainer) + developer.
    Klient-Rollen (eltern, teilnehmer) werden hier abgewiesen — die
    haben eigene Endpoints in Phase 2.
    """
    allowed_roles = ("operator", "leitung", "padagoge", "trainer", "developer")
    if operator.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff role required for this endpoint",
        )
    return operator


async def require_leitung_or_developer(
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> Operator:
    """Nur Leitung (Trägerin) und Developer — z.B. für Tenant-Konfiguration.

    Legacy: 'operator' wird als Leitung interpretiert (vor Identity-Migration).
    """
    if operator.role not in ("operator", "leitung", "developer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leitung role required",
        )
    return operator


async def require_authenticated(
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> Operator:
    """Beliebige authentifizierte Person — staff, klient oder system.

    Für Endpoints, die jede eingeloggte Identity bedienen müssen:
    /api/v1/heim, /api/v1/auth/me, /api/v1/auth/refresh.
    Wir geben hier nur abgewiesen, wenn die Identity einen unbekannten
    Rollen-Wert hat (sollte nicht passieren, aber defensive).
    """
    from .models.operator import ALL_ROLES
    if operator.role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role: {operator.role}",
        )
    return operator

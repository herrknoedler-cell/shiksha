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
    """Operator oder Developer — Observer nicht."""
    if operator.role not in ("operator", "developer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only access — not allowed for mutations",
        )
    return operator

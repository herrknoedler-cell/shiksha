"""Audit-Log-Middleware — loggt alle Mutations automatisch.

Was geloggt wird:
  - POST / PUT / PATCH / DELETE Requests
  - Status-Code >= 200 < 400 (also nur erfolgreich)
  - Operator-ID + Rolle (falls authentifiziert)
  - Pfad + Method + IP

Was NICHT geloggt wird:
  - GET-Requests (kein State-Change)
  - /health, /docs, /openapi.json
  - Body-Inhalte (Privacy — Diff wird in Phase 4 von einzelnen Endpoints gesetzt)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..db import SessionLocal
from ..models import AuditLog


_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_SKIP_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}
_SKIP_PREFIXES = ("/api/v1/auth/login/", "/api/v1/auth/register/begin/")


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Schnell rauslassen wenn nicht relevant
        if request.method not in _MUTATION_METHODS:
            return response
        if request.url.path in _SKIP_PATHS:
            return response
        if any(request.url.path.startswith(p) for p in _SKIP_PREFIXES):
            return response
        if not (200 <= response.status_code < 400):
            return response

        # Actor aus Request-State (von deps.get_current_operator gesetzt)
        actor_id = getattr(request.state, "actor_id", None)
        actor_role = getattr(request.state, "actor_role", None)
        diff = getattr(request.state, "audit_diff", None)
        target_type = getattr(request.state, "audit_target_type", None)
        target_id = getattr(request.state, "audit_target_id", None)
        action = getattr(request.state, "audit_action", None) or _action_from_path(
            request.method, request.url.path
        )

        client_host = request.client.host if request.client else None

        # Eigene DB-Session, da die Request-Session ggf. schon committed wurde
        try:
            with SessionLocal() as db:
                db.add(AuditLog(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    diff=diff,
                    request_path=request.url.path,
                    request_method=request.method,
                    ip_address=client_host,
                ))
                db.commit()
        except Exception:
            # Audit-Log darf den Request nicht killen
            pass

        return response


def _action_from_path(method: str, path: str) -> str:
    """Fallback-Action aus Method + Path."""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "api":
        # /api/v1/chat/respond → "chat.respond.POST"
        return f"{parts[2]}.{'.'.join(parts[3:])}.{method}"
    return f"http.{method}.{path}"

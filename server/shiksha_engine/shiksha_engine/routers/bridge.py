"""Bridge-Router — Auth-Proxy zur alten Welt (kita_compliance_router).

Spec: PHASE_1_5_SPEC.md §5.

Pro Request:
  1. JWT-Auth via require_authenticated
  2. Path-Whitelist-Check
  3. Audit-Log (separate Session — überlebt evtl. Proxy-Fehler)
  4. HTTPX-Anfrage an OLD_BACKEND_BASE_URL
  5. Response durchreichen

Konfiguration via BRIDGE_OLD_BASE_URL in .env. Leer = Bridge deaktiviert.
Sobald ein Modul nativ portiert ist, wird sein Prefix aus ALLOWED_PREFIXES
entfernt und die Heim-Karte auf den nativen Endpoint umgeschaltet.
"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from ..db import SessionLocal, get_db
from ..deps import require_authenticated
from ..models import AuditLog, Operator
from ..settings import get_settings

log = logging.getLogger("shiksha.bridge")

router = APIRouter()


# Whitelist erlaubter Path-Prefixes (Spec §5.2).
# Diese Prefixes referenzieren Endpoints der alten Welt, die wir
# pro-Modul-Port aus dieser Liste streichen werden.
#
# Bereits portiert (NICHT mehr in der Whitelist):
#   /kita/children  → shiksha_core.persons (kind=kind),  Schritt 5.5.3
#   /kita/staff     → shiksha_core.persons (kind=staff), Schritt 5.5.3
ALLOWED_PREFIXES = (
    "/kita/calendar",
    "/kita/anwesenheit",
    "/kita/identity",
    "/kita/push",
    "/kita/compliance",
)

# Header, die wir NICHT durchreichen — Auth ist neu, Host wird httpx setzen.
_STRIP_REQUEST_HEADERS = {
    "host", "authorization", "cookie",
    "content-length",  # httpx setzt selbst
}
_STRIP_RESPONSE_HEADERS = {
    "content-length",       # FastAPI setzt selbst
    "transfer-encoding",
    "connection",
    "keep-alive",
}


def _path_allowed(path: str) -> bool:
    """True wenn der Pfad mit einem unserer Whitelist-Prefixes beginnt."""
    if not path.startswith("/"):
        path = "/" + path
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _audit(
    operator: Operator,
    method: str,
    path: str,
    success: bool,
    status_code: int | None = None,
    error: str | None = None,
) -> None:
    """Bridge-Audit in eigener Session — überlebt Proxy-Fehler."""
    try:
        with SessionLocal() as db:
            db.add(AuditLog(
                actor_id=operator.id,
                actor_role=operator.role,
                action=f"bridge.{method.lower()}.{'ok' if success else 'fail'}",
                target_type="bridge",
                target_id=path,
                diff={"status": status_code, "error": error} if not success else {"status": status_code},
                request_path=path,
                request_method=method,
                ip_address=None,
            ))
            db.commit()
    except Exception:
        log.exception("Bridge-Audit konnte nicht geschrieben werden")


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    operation_id="bridge_proxy",
)
async def bridge(
    full_path: str,
    request: Request,
    operator: Annotated[Operator, Depends(require_authenticated)],
) -> Response:
    """Generischer Proxy-Endpoint zur alten Welt.

    Aufruf:
        GET  /api/v1/bridge/kita/children?group_id=2
        →    GET  <OLD_BACKEND>/kita/children?group_id=2

    Antwort wird 1:1 durchgereicht (Status, Body, relevante Header).
    """
    settings = get_settings()
    base_url = (settings.bridge_old_base_url or "").rstrip("/")

    if not base_url:
        raise HTTPException(
            status_code=503,
            detail="Bridge nicht konfiguriert (BRIDGE_OLD_BASE_URL leer)",
        )

    # Pfad normalisieren — full_path kommt ohne führenden Slash
    path = "/" + full_path

    # Whitelist-Check
    if not _path_allowed(path):
        _audit(operator, request.method, path, success=False,
               error="path not in whitelist")
        raise HTTPException(
            status_code=404,
            detail=f"Bridge-Pfad nicht in Whitelist: {path}",
        )

    target_url = f"{base_url}{path}"

    # Request-Header filtern — die alte Welt soll Auth nicht sehen
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _STRIP_REQUEST_HEADERS
    }

    try:
        body = await request.body()
    except Exception:
        body = b""

    try:
        async with httpx.AsyncClient(timeout=settings.bridge_timeout_seconds) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                params=dict(request.query_params),
                headers=headers,
                content=body,
            )
    except httpx.TimeoutException:
        _audit(operator, request.method, path, success=False, error="timeout")
        raise HTTPException(
            status_code=504,
            detail="Bridge-Timeout — alte Welt antwortet nicht",
        )
    except httpx.RequestError as e:
        _audit(operator, request.method, path, success=False, error=str(e))
        log.warning("Bridge-Request fehlgeschlagen: %s — %s", target_url, e)
        raise HTTPException(
            status_code=502,
            detail="Bridge-Fehler — alte Welt nicht erreichbar",
        )

    _audit(
        operator, request.method, path,
        success=200 <= upstream.status_code < 400,
        status_code=upstream.status_code,
    )

    # Response durchreichen — strip Header die FastAPI selbst setzt
    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _STRIP_RESPONSE_HEADERS
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )

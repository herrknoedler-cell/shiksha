"""Auth-Router — WebAuthn-Registration + Login + /me."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from ..db import get_db
from ..deps import get_current_operator
from ..models import Operator, Organization
from ..schemas.auth import (
    AuthenticationFinishRequest,
    AuthenticationStartRequest,
    AuthenticationStartResponse,
    MeResponse,
    RegistrationFinishRequest,
    RegistrationStartResponse,
    TokenResponse,
)
from ..services import jwt_service, webauthn_service

router = APIRouter()


@router.post("/register/begin/{operator_id}", response_model=RegistrationStartResponse)
def register_begin(
    operator_id: str,
    db: Annotated[DBSession, Depends(get_db)],
    setup_token: str | None = None,
) -> RegistrationStartResponse:
    """Beginne Passkey-Registrierung.

    Auth-Regeln:
      - Operator hat NOCH KEINE webauthn_credentials → öffentlicher Zugang
        (Erst-Setup-Fall, z.B. nach Seed)
      - Operator hat schon Credentials → setup_token erforderlich
        (verhindert Account-Übernahme)

    Setup-Token wird via Query-Param ?setup_token=... übergeben. Er
    wird vom Developer via /api/v1/dev/setup-tokens generiert und ist
    10 Minuten gültig.
    """
    from ..services import setup_token_service

    operator = db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator unknown")

    has_existing_credentials = bool(operator.webauthn_credentials)

    if has_existing_credentials:
        # Schutz: nur mit gültigem Setup-Token
        if not setup_token:
            raise HTTPException(
                status_code=403,
                detail="Operator hat bereits einen Passkey. Setup-Token nötig um neuen anzulegen.",
            )
        if not setup_token_service.verify(setup_token, operator_id=operator_id):
            raise HTTPException(
                status_code=403,
                detail="Setup-Token ungültig oder abgelaufen.",
            )

    existing_ids = [c["credential_id"] for c in (operator.webauthn_credentials or [])]
    start = webauthn_service.start_registration(
        operator_id=operator.id,
        operator_display_name=operator.display_name,
        existing_credential_ids=existing_ids,
    )

    return RegistrationStartResponse(
        options=json.loads(start.options_json),
        operator_id=operator.id,
    )


@router.post("/register/finish", response_model=TokenResponse)
def register_finish(
    payload: RegistrationFinishRequest,
    db: Annotated[DBSession, Depends(get_db)],
    setup_token: str | None = None,
) -> TokenResponse:
    """Verifiziere die Registration-Response, speichere Credential, gib Token aus.

    Wenn Setup-Token mitgegeben wurde: wird beim Erfolg konsumiert.
    """
    from ..services import setup_token_service

    operator = db.get(Operator, payload.operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator unknown")

    try:
        cred = webauthn_service.finish_registration(operator.id, payload.credential)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Setup-Token konsumieren wenn vorhanden
    if setup_token:
        setup_token_service.consume(setup_token)

    # Anhängen — copy on write damit SQLAlchemy die Änderung sieht
    creds = list(operator.webauthn_credentials or [])
    creds.append({
        "credential_id": cred.credential_id,
        "public_key":    cred.public_key,
        "sign_count":    cred.sign_count,
        "transports":    cred.transports,
        "registered_at": cred.registered_at,
    })
    operator.webauthn_credentials = creds
    db.add(operator)
    db.flush()

    org = db.get(Organization, operator.org_id) if operator.org_id else None
    token = jwt_service.issue_token(
        operator_id=operator.id,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
        org_timezone=org.timezone if org else None,
    )

    return TokenResponse(
        token=token,
        role=operator.role,
        edition=operator.edition,
        operator_id=operator.id,
        display_name=operator.display_name,
    )


@router.post("/login/begin", response_model=AuthenticationStartResponse)
def login_begin(
    payload: AuthenticationStartRequest,
    db: Annotated[DBSession, Depends(get_db)],
) -> AuthenticationStartResponse:
    """Beginne Passkey-Login."""
    operator = db.get(Operator, payload.operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator unknown")

    if not operator.webauthn_credentials:
        raise HTTPException(
            status_code=400,
            detail="No passkey registered. Use /register/begin first.",
        )

    start = webauthn_service.start_authentication(
        operator_id=operator.id,
        stored_credentials=operator.webauthn_credentials,
    )
    return AuthenticationStartResponse(options=json.loads(start.options_json))


@router.post("/login/finish", response_model=TokenResponse)
def login_finish(
    payload: AuthenticationFinishRequest,
    db: Annotated[DBSession, Depends(get_db)],
) -> TokenResponse:
    """Verifiziere die Authentication-Response, gib Token aus."""
    operator = db.get(Operator, payload.operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator unknown")

    try:
        result = webauthn_service.finish_authentication(
            operator_id=operator.id,
            client_response=payload.credential,
            stored_credentials=operator.webauthn_credentials or [],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # sign_count nachhalten — wichtig gegen Klon-Angriffe
    creds = list(operator.webauthn_credentials or [])
    for c in creds:
        if c["credential_id"] == result.credential_id:
            c["sign_count"] = result.new_sign_count
            break
    operator.webauthn_credentials = creds
    db.add(operator)
    db.flush()

    org = db.get(Organization, operator.org_id) if operator.org_id else None
    token = jwt_service.issue_token(
        operator_id=operator.id,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
        org_timezone=org.timezone if org else None,
    )

    return TokenResponse(
        token=token,
        role=operator.role,
        edition=operator.edition,
        operator_id=operator.id,
        display_name=operator.display_name,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    operator: Annotated[Operator, Depends(get_current_operator)],
    db: Annotated[DBSession, Depends(get_db)],
) -> TokenResponse:
    """Neuer Token mit verlängerter Lifetime."""
    org = db.get(Organization, operator.org_id) if operator.org_id else None
    token = jwt_service.issue_token(
        operator_id=operator.id,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
        org_timezone=org.timezone if org else None,
    )
    return TokenResponse(
        token=token,
        role=operator.role,
        edition=operator.edition,
        operator_id=operator.id,
        display_name=operator.display_name,
    )


@router.get("/me", response_model=MeResponse)
def me(
    operator: Annotated[Operator, Depends(get_current_operator)],
) -> MeResponse:
    """Wer bin ich?"""
    return MeResponse(
        operator_id=operator.id,
        display_name=operator.display_name,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
        org_name=operator.organization.name if operator.organization else None,
        email=operator.email,
    )


@router.post("/email-code", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def email_code_notausgang():
    """E-Mail-OTP-Notausgang — Phase 2, nicht in Phase 1 implementiert."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="E-Mail-OTP-Notausgang ist erst in Phase 2 implementiert. "
               "In Phase 1: nutze Passkey-Login.",
    )

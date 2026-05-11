"""WebAuthn-Service — Passkey-Registration + Authentication.

Uses py_webauthn (https://github.com/duo-labs/py_webauthn). Wraps registration
and authentication ceremonies for the Presence-Switch UI.

Challenges are stored in-memory short-term (5 min) keyed by operator_id +
ceremony-type. In Phase 2: move challenges to Redis/DB if multi-instance.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..settings import get_settings


# ===================================================================
# In-Memory Challenge-Store (Phase 1 — single-instance OK)
# Format: {(operator_id, ceremony): (challenge_b64, expires_at)}
# ===================================================================

_CHALLENGE_TTL_SEC = 300  # 5 Minuten
_challenges: dict[tuple[str, str], tuple[bytes, float]] = {}


def _store_challenge(operator_id: str, ceremony: str, challenge: bytes) -> None:
    _challenges[(operator_id, ceremony)] = (challenge, time.time() + _CHALLENGE_TTL_SEC)
    _cleanup_expired()


def _retrieve_challenge(operator_id: str, ceremony: str) -> bytes | None:
    key = (operator_id, ceremony)
    if key not in _challenges:
        return None
    challenge, expires_at = _challenges[key]
    if time.time() > expires_at:
        del _challenges[key]
        return None
    return challenge


def _consume_challenge(operator_id: str, ceremony: str) -> bytes | None:
    """Get and delete in one step (challenges are one-time use)."""
    result = _retrieve_challenge(operator_id, ceremony)
    if result is not None:
        _challenges.pop((operator_id, ceremony), None)
    return result


def _cleanup_expired() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _challenges.items() if now > exp]
    for k in expired:
        _challenges.pop(k, None)


# ===================================================================
# Registration Ceremony
# ===================================================================

@dataclass
class RegistrationStart:
    options_json: str  # JSON the browser passes to navigator.credentials.create()


def start_registration(
    operator_id: str,
    operator_display_name: str,
    existing_credential_ids: list[str] | None = None,
) -> RegistrationStart:
    """Beginnt Passkey-Registrierung. Browser bekommt PublicKeyCredentialCreationOptions."""
    settings = get_settings()

    exclude = [
        PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(cid + "==" * (4 - len(cid) % 4)))
        for cid in (existing_credential_ids or [])
    ]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=operator_id.encode("utf-8"),
        user_name=operator_id,
        user_display_name=operator_display_name,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
        timeout=60_000,
    )

    _store_challenge(operator_id, "registration", options.challenge)
    return RegistrationStart(options_json=options_to_json(options))


@dataclass
class StoredCredential:
    """What we persist in operators.webauthn_credentials."""
    credential_id: str    # base64url-encoded
    public_key: str       # base64url-encoded
    sign_count: int
    transports: list[str]
    registered_at: str


def finish_registration(
    operator_id: str,
    client_response: dict[str, Any],
) -> StoredCredential:
    """Schließt Passkey-Registrierung ab. Gibt das zu persistierende Credential zurück."""
    settings = get_settings()
    challenge = _consume_challenge(operator_id, "registration")
    if challenge is None:
        raise ValueError("No active registration challenge for this operator")

    verification = verify_registration_response(
        credential=client_response,
        expected_challenge=challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
        require_user_verification=False,
    )

    transports = client_response.get("response", {}).get("transports", [])

    return StoredCredential(
        credential_id=base64.urlsafe_b64encode(verification.credential_id).decode("ascii").rstrip("="),
        public_key=base64.urlsafe_b64encode(verification.credential_public_key).decode("ascii").rstrip("="),
        sign_count=verification.sign_count,
        transports=transports if isinstance(transports, list) else [],
        registered_at=__import__("datetime").datetime.utcnow().isoformat() + "Z",
    )


# ===================================================================
# Authentication Ceremony
# ===================================================================

@dataclass
class AuthenticationStart:
    options_json: str


def start_authentication(
    operator_id: str,
    stored_credentials: list[dict[str, Any]],
) -> AuthenticationStart:
    """Beginnt Passkey-Login. Browser bekommt PublicKeyCredentialRequestOptions."""
    settings = get_settings()

    allow = [
        PublicKeyCredentialDescriptor(
            id=_b64u_decode(cred["credential_id"]),
            transports=cred.get("transports", []) or None,
        )
        for cred in stored_credentials
    ]

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
        timeout=60_000,
    )

    _store_challenge(operator_id, "authentication", options.challenge)
    return AuthenticationStart(options_json=options_to_json(options))


@dataclass
class AuthenticationResult:
    credential_id: str
    new_sign_count: int


def finish_authentication(
    operator_id: str,
    client_response: dict[str, Any],
    stored_credentials: list[dict[str, Any]],
) -> AuthenticationResult:
    """Verifiziert die Authentication-Response, gibt neuen sign_count zurück."""
    settings = get_settings()
    challenge = _consume_challenge(operator_id, "authentication")
    if challenge is None:
        raise ValueError("No active authentication challenge for this operator")

    # Welches Credential wurde benutzt?
    used_cred_id_b64 = client_response.get("id")
    used_cred = next(
        (c for c in stored_credentials if c["credential_id"] == used_cred_id_b64),
        None,
    )
    if used_cred is None:
        raise ValueError("Credential not registered for this operator")

    verification = verify_authentication_response(
        credential=client_response,
        expected_challenge=challenge,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
        credential_public_key=_b64u_decode(used_cred["public_key"]),
        credential_current_sign_count=used_cred.get("sign_count", 0),
        require_user_verification=False,
    )

    return AuthenticationResult(
        credential_id=used_cred_id_b64,
        new_sign_count=verification.new_sign_count,
    )


# ===================================================================
# Helpers
# ===================================================================

def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def generate_setup_token() -> str:
    """One-time-Token für die initiale Passkey-Registrierung beim Onboarding.

    Wird in der URL übergeben, Backend wandelt ihn in eine kurze Auth-Session
    für die Passkey-Registration.
    """
    return secrets.token_urlsafe(32)

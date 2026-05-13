"""JWT-Service — issue, verify, refresh."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from ..settings import get_settings


class TokenError(Exception):
    """Token-related errors (expired, invalid, missing claims, ...)."""


def issue_token(
    *,
    operator_id: str,
    role: str,
    edition: str,
    org_id: str | None = None,
    org_timezone: str | None = None,
    extra_claims: dict[str, Any] | None = None,
    lifetime_days: int | None = None,
) -> str:
    """Issue a signed JWT for an Operator.

    org_timezone wird als Claim mit-signiert, damit TZ-aware Frontends
    (Calendar, Anwesenheit) ohne Extra-Roundtrip rendern können.
    Default 'Europe/Berlin' für Operatoren ohne org-Anker (z.B. Developer).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=lifetime_days or settings.jwt_lifetime_days)

    payload: dict[str, Any] = {
        "sub":           operator_id,
        "role":          role,
        "edition":       edition,
        "org_id":        org_id,
        "org_timezone": org_timezone or "Europe/Berlin",
        "iat":           int(now.timestamp()),
        "exp":           int(exp.timestamp()),
        "iss":           "shiksha-engine",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT. Raises TokenError on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
        return payload
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}") from e


def refresh_token(token: str) -> str:
    """Issue a fresh token from an existing valid one."""
    payload = verify_token(token)
    return issue_token(
        operator_id=payload["sub"],
        role=payload.get("role", "operator"),
        edition=payload.get("edition", ""),
        org_id=payload.get("org_id"),
        org_timezone=payload.get("org_timezone"),
    )

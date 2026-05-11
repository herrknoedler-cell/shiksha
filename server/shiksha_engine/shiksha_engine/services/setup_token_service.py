"""Setup-Token-Service — One-Time-Tokens für Phone-Onboarding.

Flow:
  1. Developer (oder seed-Script) generiert via POST /api/v1/dev/setup-tokens
     einen Token für einen Operator.
  2. Token lebt 10 Minuten in-memory.
  3. URL https://shiksha.world/presence_switch.html?setup=<TOKEN>
     wird an die Operator-Person geschickt (QR oder Link).
  4. Operator öffnet URL auf Phone.
  5. Frontend: Token + operator_id → /api/v1/auth/register/begin/<operator>
     (offen für Setup-Token-Inhaber).
  6. WebAuthn-Register-Ceremony, Token wird beim register/finish konsumiert.

In Phase 1: in-memory Store. Phase 2+: redis o.ä. wenn Multi-Worker.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


_TOKEN_TTL_SEC = 600  # 10 Minuten


@dataclass
class SetupTokenEntry:
    operator_id: str
    expires_at:  float
    consumed:    bool = False


_tokens: dict[str, SetupTokenEntry] = {}


def issue(operator_id: str) -> tuple[str, float]:
    """Generiert einen neuen Setup-Token für einen Operator.

    Gibt (token, expires_at_unix) zurück.
    """
    _cleanup()
    token = secrets.token_urlsafe(32)
    expires = time.time() + _TOKEN_TTL_SEC
    _tokens[token] = SetupTokenEntry(operator_id=operator_id, expires_at=expires)
    return token, expires


def verify(token: str, operator_id: str | None = None) -> str | None:
    """Prüft Token. Wenn gültig: gibt operator_id zurück.

    Wenn operator_id angegeben: muss zum Token passen.
    """
    _cleanup()
    entry = _tokens.get(token)
    if entry is None:
        return None
    if entry.consumed:
        return None
    if time.time() > entry.expires_at:
        return None
    if operator_id and entry.operator_id != operator_id:
        return None
    return entry.operator_id


def consume(token: str) -> str | None:
    """Verifizieren und sofort als verbraucht markieren.

    Wird beim register/finish aufgerufen — danach kann der Token nicht
    nochmal genutzt werden.
    """
    entry = _tokens.get(token)
    if entry is None or entry.consumed:
        return None
    if time.time() > entry.expires_at:
        return None
    entry.consumed = True
    return entry.operator_id


def revoke(token: str) -> bool:
    """Manuelles Revoken (z.B. Developer kann zurückziehen)."""
    return _tokens.pop(token, None) is not None


def list_active() -> list[dict]:
    """Alle aktiven (nicht verbrauchten + nicht abgelaufenen) Tokens listen."""
    _cleanup()
    now = time.time()
    return [
        {
            "token_prefix": tok[:12] + "…",
            "operator_id": entry.operator_id,
            "expires_in":  int(entry.expires_at - now),
            "consumed":    entry.consumed,
        }
        for tok, entry in _tokens.items()
        if not entry.consumed and entry.expires_at > now
    ]


def _cleanup() -> None:
    """Entferne abgelaufene oder verbrauchte Tokens."""
    now = time.time()
    expired = [
        tok for tok, entry in _tokens.items()
        if entry.consumed or now > entry.expires_at
    ]
    for tok in expired:
        _tokens.pop(tok, None)

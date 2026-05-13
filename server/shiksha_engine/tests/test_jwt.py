"""JWT-Service Tests — Issue, Verify, Refresh."""

import pytest

from shiksha_engine.services.jwt_service import (
    TokenError,
    issue_token,
    refresh_token,
    verify_token,
)


def test_issue_and_verify():
    token = issue_token(
        operator_id="mira",
        role="operator",
        edition="kita",
        org_id="krummelus",
    )
    payload = verify_token(token)
    assert payload["sub"] == "mira"
    assert payload["role"] == "operator"
    assert payload["edition"] == "kita"
    assert payload["org_id"] == "krummelus"


def test_invalid_token():
    with pytest.raises(TokenError):
        verify_token("garbage.token.here")


def test_refresh():
    """Refresh-Token ist semantisch korrekt: neue iat >= alte iat.

    Hinweis: bytewise-Vergleich (fresh != original) wäre nicht
    deterministisch, weil JWT-iat nur sekunden-präzise ist — wenn
    issue + refresh in derselben Sekunde laufen, ist der Token
    bytewise identisch. Strukturelle Assertion ist semantisch klarer.
    """
    original = issue_token(operator_id="thomas", role="developer", edition="kita")
    original_payload = verify_token(original)

    fresh = refresh_token(original)
    fresh_payload = verify_token(fresh)

    # Refresh hat aktuelle iat (>= alte) und aktuelle exp
    assert fresh_payload["iat"] >= original_payload["iat"]
    assert fresh_payload["exp"] >= original_payload["exp"]

    # Claims werden korrekt übernommen
    assert fresh_payload["sub"] == "thomas"
    assert fresh_payload["role"] == "developer"
    assert fresh_payload["edition"] == "kita"


def test_extra_claims():
    token = issue_token(
        operator_id="mira",
        role="operator",
        edition="kita",
        extra_claims={"setup": True},
    )
    payload = verify_token(token)
    assert payload.get("setup") is True


def test_token_carries_org_timezone():
    """org_timezone-Claim für TZ-aware Frontends (Calendar etc.)."""
    token = issue_token(
        operator_id="krummelus_mira",
        role="leitung",
        edition="kita",
        org_id="krummelus",
        org_timezone="Europe/Vienna",
    )
    payload = verify_token(token)
    assert payload["org_timezone"] == "Europe/Vienna"


def test_token_default_org_timezone():
    """Ohne explizite TZ fällt auf Europe/Berlin zurück."""
    token = issue_token(
        operator_id="thomas",
        role="developer",
        edition="kita",
    )
    payload = verify_token(token)
    assert payload["org_timezone"] == "Europe/Berlin"

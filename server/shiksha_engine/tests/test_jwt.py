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
    original = issue_token(operator_id="thomas", role="developer", edition="kita")
    fresh = refresh_token(original)
    assert fresh != original  # neuer iat/exp
    payload = verify_token(fresh)
    assert payload["sub"] == "thomas"
    assert payload["role"] == "developer"


def test_extra_claims():
    token = issue_token(
        operator_id="mira",
        role="operator",
        edition="kita",
        extra_claims={"setup": True},
    )
    payload = verify_token(token)
    assert payload.get("setup") is True

"""Rate-Limit Tests — Counter, 429, Developer-Bypass."""

from datetime import date
from unittest.mock import patch

import pytest

from shiksha_engine.middleware.rate_limit import _increment_bucket
from shiksha_engine.models import RateLimitBucket
from shiksha_engine.services.jwt_service import issue_token


def test_increment_bucket(db, mira):
    today = date.today()
    c1 = _increment_bucket(mira.id, today)
    assert c1 == 1

    c2 = _increment_bucket(mira.id, today)
    assert c2 == 2

    c3 = _increment_bucket(mira.id, today)
    assert c3 == 3

    # Bucket-Eintrag existiert?
    bucket = db.get(RateLimitBucket, (mira.id, today))
    assert bucket is not None
    assert bucket.count == 3


def test_no_rate_limit_on_unauthed_endpoints(client):
    """Auth-Endpoints sind nie rate-limitiert."""
    for _ in range(10):
        r = client.get("/health")
        assert r.status_code == 200


def test_429_after_exceeded(client, mira):
    """Mit Limit auf 3 — beim 4. Call gibt's 429."""
    token = issue_token(operator_id=mira.id, role=mira.role, edition=mira.edition, org_id=mira.org_id)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with patch("shiksha_engine.middleware.rate_limit.get_settings") as mock_settings:
        # Limit = 3 für diesen Test
        mock_settings.return_value.rate_limit_per_operator_per_day = 3

        # Erste 3 Calls — gehen durch (auch wenn /tools-Endpoints 4xx liefern, das ist egal)
        for i in range(3):
            r = client.post(
                "/api/v1/tools/add_memory",
                json={"text": f"Eintrag #{i}"},
                headers=headers,
            )
            # Status egal, Rate-Limit ist OK
            assert "X-RateLimit-Limit" in r.headers
            assert r.headers["X-RateLimit-Limit"] == "3"

        # 4. Call → 429
        r = client.post(
            "/api/v1/tools/add_memory",
            json={"text": "über Limit"},
            headers=headers,
        )
        assert r.status_code == 429
        body = r.json()
        assert body["limit"] == 3
        assert "reset_at" in body
        assert r.headers["X-RateLimit-Remaining"] == "0"


def test_developer_bypasses_rate_limit(client, thomas):
    """Developer hat kein Limit — auch nach vielen Calls keine 429."""
    token = issue_token(operator_id=thomas.id, role=thomas.role, edition=thomas.edition, org_id=thomas.org_id)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with patch("shiksha_engine.middleware.rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.rate_limit_per_operator_per_day = 2

        for _ in range(5):
            r = client.post(
                "/api/v1/tools/add_memory",
                json={"text": "developer call"},
                headers=headers,
            )
            assert r.status_code != 429

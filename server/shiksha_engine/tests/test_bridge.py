"""Bridge-Router-Tests — Whitelist, Auth, Proxy-Verhalten, Audit.

httpx.AsyncClient wird via monkeypatch durch einen MockTransport ersetzt.
Damit testen wir den Proxy ohne echte Outbound-Calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from shiksha_engine.models import AuditLog


# ===================================================================
# JWT-Helpers
# ===================================================================

def _auth_for(operator):
    from shiksha_engine.services import jwt_service
    token = jwt_service.issue_token(
        operator_id=operator.id,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
    )
    return {"Authorization": f"Bearer {token}"}


# ===================================================================
# httpx-Mock
# ===================================================================

class _BridgeMock:
    """Speichert die letzte Request, liefert konfigurierte Response.

    Verwendung:
        mock = _BridgeMock()
        mock.set_response(200, b'{"hello":"world"}', {"content-type": "application/json"})
        with mock.activate():
            ...

    Danach:
        mock.last_request.method, mock.last_request.url, ...
    """

    def __init__(self):
        self.last_request: httpx.Request | None = None
        self._status = 200
        self._body = b""
        self._headers = {"content-type": "application/json"}
        self._raises = None

    def set_response(self, status: int, body: bytes, headers: dict | None = None):
        self._status = status
        self._body = body
        self._headers = headers or {"content-type": "application/json"}
        self._raises = None

    def set_raises(self, exc: Exception):
        self._raises = exc

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last_request = request
        if self._raises:
            raise self._raises
        return httpx.Response(
            self._status,
            content=self._body,
            headers=self._headers,
        )

    def patch_async_client(self):
        """Liefert ein patch()-Objekt, das httpx.AsyncClient durch einen
        Client mit MockTransport ersetzt."""
        transport = httpx.MockTransport(self.handler)
        original = httpx.AsyncClient

        def _patched(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        return patch("shiksha_engine.routers.bridge.httpx.AsyncClient", side_effect=_patched)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def bridge_configured(monkeypatch):
    """Setzt BRIDGE_OLD_BASE_URL für die Test-Dauer."""
    from shiksha_engine.settings import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "bridge_old_base_url", "http://127.0.0.1:8002")
    return settings


# ===================================================================
# Auth-Wand
# ===================================================================

def test_bridge_unauthorized_returns_401(client, bridge_configured):
    res = client.get("/api/v1/bridge/kita/calendar")
    assert res.status_code == 401


# ===================================================================
# Whitelist
# ===================================================================

def test_bridge_unknown_path_returns_404(client, bridge_configured, mira_leitung):
    res = client.get(
        "/api/v1/bridge/admin/secret",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 404
    assert "Whitelist" in res.json()["detail"] or "whitelist" in res.json()["detail"].lower()


def test_bridge_allowed_path_proxies(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_response(200, b'{"count":18}')
    with mock.patch_async_client():
        res = client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
        )
    assert res.status_code == 200
    assert res.json() == {"count": 18}


# ===================================================================
# Konfig-Check
# ===================================================================

def test_bridge_without_config_returns_503(client, mira_leitung, monkeypatch):
    from shiksha_engine.settings import get_settings
    monkeypatch.setattr(get_settings(), "bridge_old_base_url", "")

    res = client.get(
        "/api/v1/bridge/kita/calendar",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 503


# ===================================================================
# Proxy-Verhalten
# ===================================================================

def test_bridge_forwards_query_params(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_response(200, b'{"ok":true}')
    with mock.patch_async_client():
        client.get(
            "/api/v1/bridge/kita/calendar?group_id=2&active=true",
            headers=_auth_for(mira_leitung),
        )
    assert mock.last_request is not None
    assert "group_id=2" in str(mock.last_request.url)
    assert "active=true" in str(mock.last_request.url)


def test_bridge_strips_authorization_header(client, bridge_configured, mira_leitung):
    """Authorization-Header darf NICHT an die alte Welt durchgereicht werden."""
    mock = _BridgeMock()
    mock.set_response(200, b"{}")
    with mock.patch_async_client():
        client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
        )
    assert mock.last_request is not None
    assert "authorization" not in {k.lower() for k in mock.last_request.headers.keys()}


def test_bridge_forwards_method_and_body(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_response(201, b'{"id":42}')
    with mock.patch_async_client():
        res = client.post(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
            json={"name": "Neue Person"},
        )
    assert res.status_code == 201
    assert mock.last_request.method == "POST"
    body = json.loads(mock.last_request.content.decode())
    assert body == {"name": "Neue Person"}


def test_bridge_returns_upstream_status_code(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_response(404, b'{"error":"not found"}')
    with mock.patch_async_client():
        res = client.get(
            "/api/v1/bridge/kita/calendar/999",
            headers=_auth_for(mira_leitung),
        )
    assert res.status_code == 404


# ===================================================================
# Fehler-Verhalten
# ===================================================================

def test_bridge_timeout_returns_504(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_raises(httpx.TimeoutException("simulated timeout"))
    with mock.patch_async_client():
        res = client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
        )
    assert res.status_code == 504


def test_bridge_connection_error_returns_502(client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_raises(httpx.ConnectError("simulated connection refused"))
    with mock.patch_async_client():
        res = client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
        )
    assert res.status_code == 502


# ===================================================================
# Audit
# ===================================================================

def test_bridge_writes_audit_on_success(db, client, bridge_configured, mira_leitung):
    mock = _BridgeMock()
    mock.set_response(200, b"{}")
    with mock.patch_async_client():
        client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(mira_leitung),
        )
    db.expire_all()
    logs = db.query(AuditLog).filter(
        AuditLog.action == "bridge.get.ok"
    ).all()
    assert len(logs) >= 1
    log = logs[-1]
    assert log.actor_id == mira_leitung.id
    assert log.target_id == "/kita/calendar"


def test_bridge_writes_audit_on_whitelist_reject(db, client, bridge_configured, mira_leitung):
    client.get(
        "/api/v1/bridge/admin/secret",
        headers=_auth_for(mira_leitung),
    )
    db.expire_all()
    logs = db.query(AuditLog).filter(
        AuditLog.action == "bridge.get.fail"
    ).all()
    assert len(logs) >= 1


# ===================================================================
# Klient-Rollen dürfen bridgen (kein Rollen-Filter im Bridge selbst)
# ===================================================================

def test_bridge_works_for_klient_role(client, bridge_configured, vater):
    """Eltern dürfen Bridge nutzen (in Phase 1.5 alle authentifizierten)."""
    mock = _BridgeMock()
    mock.set_response(200, b"{}")
    with mock.patch_async_client():
        res = client.get(
            "/api/v1/bridge/kita/calendar",
            headers=_auth_for(vater),
        )
    assert res.status_code == 200

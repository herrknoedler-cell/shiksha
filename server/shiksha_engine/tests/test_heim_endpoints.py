"""Heim-Endpoint-Tests — /api/v1/heim und /api/v1/heim/config.

E2E via TestClient + JWT-Auth.
"""

from __future__ import annotations

import pytest


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
# GET /api/v1/heim — Hauptseite
# ===================================================================

def test_heim_unauthorized_returns_401(client):
    res = client.get("/api/v1/heim")
    assert res.status_code == 401


def test_heim_for_leitung(client, mira_leitung):
    res = client.get("/api/v1/heim", headers=_auth_for(mira_leitung))
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "leitung"
    assert body["tenant"] == "krummelus_v2"
    assert "Mira" in body["greeting"]
    assert len(body["cards"]) >= 2


def test_heim_for_padagoge(client, pedagogin):
    res = client.get("/api/v1/heim", headers=_auth_for(pedagogin))
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "padagoge"
    card_ids = {c["id"] for c in body["cards"]}
    # Pädagogin sieht Abholer-prüfen, nicht Personal-heute (das ist leitung-only)
    assert "abholer_pruefen" in card_ids
    assert "personal_heute" not in card_ids


def test_heim_for_eltern_shows_stub(client, vater):
    res = client.get("/api/v1/heim", headers=_auth_for(vater))
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "eltern"
    card_ids = {c["id"] for c in body["cards"]}
    assert "stub_klienten_demnaechst" in card_ids
    # Eltern sehen keine Staff-Karten
    assert "anwesenheit_today" not in card_ids


def test_heim_for_legacy_operator_still_works(client, mira):
    """Bestehende Mira mit role='operator' (Legacy) bekommt auch ein Heim."""
    res = client.get("/api/v1/heim", headers=_auth_for(mira))
    assert res.status_code == 200
    body = res.json()
    # core.yaml hat 'operator' im role_scope für Tagesausklang
    card_ids = {c["id"] for c in body["cards"]}
    assert "tagesausklang" in card_ids


# ===================================================================
# GET /api/v1/heim/config — Karten-Pool für eine Rolle
# ===================================================================

def test_config_list_requires_leitung(client, pedagogin):
    """Pädagogin darf nicht in die Konfig."""
    res = client.get("/api/v1/heim/config?role=padagoge", headers=_auth_for(pedagogin))
    assert res.status_code == 403


def test_config_list_requires_leitung_eltern_denied(client, vater):
    res = client.get("/api/v1/heim/config?role=eltern", headers=_auth_for(vater))
    assert res.status_code == 403


def test_config_list_for_leitung_returns_pool(client, mira_leitung):
    res = client.get(
        "/api/v1/heim/config?role=padagoge",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 200
    cards = res.json()
    card_ids = {c["card_id"] for c in cards}
    assert "abholer_pruefen" in card_ids
    # Leitung-only Karten NICHT im Pädagogen-Pool
    assert "personal_heute" not in card_ids

    # Alle ohne Override stehen auf enabled=True, is_overridden=False
    for c in cards:
        if c["card_id"] == "abholer_pruefen":
            assert c["enabled"] is True
            assert c["is_overridden"] is False


def test_config_list_unknown_role_400(client, mira_leitung):
    res = client.get(
        "/api/v1/heim/config?role=zauberer",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 400


# ===================================================================
# PATCH /api/v1/heim/config/{role}/{card_id}
# ===================================================================

def test_patch_disable_card_takes_effect(client, mira_leitung, pedagogin):
    """Leitung deaktiviert eine Karte für Pädagogen — Pädagogin sieht sie nicht mehr."""
    # Vorher: Pädagogin sieht Abholer-prüfen
    res_before = client.get("/api/v1/heim", headers=_auth_for(pedagogin))
    ids_before = {c["id"] for c in res_before.json()["cards"]}
    assert "abholer_pruefen" in ids_before

    # Leitung deaktiviert die Karte für padagoge
    patch_res = client.patch(
        "/api/v1/heim/config/padagoge/abholer_pruefen",
        json={"enabled": False},
        headers=_auth_for(mira_leitung),
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["enabled"] is False

    # Danach: Pädagogin sieht Karte nicht mehr
    res_after = client.get("/api/v1/heim", headers=_auth_for(pedagogin))
    ids_after = {c["id"] for c in res_after.json()["cards"]}
    assert "abholer_pruefen" not in ids_after


def test_patch_custom_title_takes_effect(client, mira_leitung):
    """Leitung überschreibt den Titel einer Karte."""
    patch_res = client.patch(
        "/api/v1/heim/config/leitung/tagesausklang",
        json={"custom_title": "Tagesabschluss"},
        headers=_auth_for(mira_leitung),
    )
    assert patch_res.status_code == 200

    res = client.get("/api/v1/heim", headers=_auth_for(mira_leitung))
    cards = res.json()["cards"]
    tagesausklang = next(c for c in cards if c["id"] == "tagesausklang")
    assert tagesausklang["title"] == "Tagesabschluss"


def test_patch_unknown_card_returns_404(client, mira_leitung):
    res = client.patch(
        "/api/v1/heim/config/leitung/unbekannte_karte",
        json={"enabled": False},
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 404


def test_patch_unknown_role_returns_400(client, mira_leitung):
    res = client.patch(
        "/api/v1/heim/config/zauberer/tagesausklang",
        json={"enabled": False},
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 400


def test_patch_denied_for_padagoge(client, pedagogin):
    """Pädagogin darf keine Heim-Config ändern."""
    res = client.patch(
        "/api/v1/heim/config/padagoge/abholer_pruefen",
        json={"enabled": False},
        headers=_auth_for(pedagogin),
    )
    assert res.status_code == 403


def test_patch_idempotent_update(client, mira_leitung):
    """Zweimal PATCH derselben Karte: zweite überschreibt erste."""
    # Erstes PATCH: deaktivieren
    client.patch(
        "/api/v1/heim/config/leitung/tagesausklang",
        json={"enabled": False},
        headers=_auth_for(mira_leitung),
    )
    # Zweites PATCH: wieder aktivieren
    res = client.patch(
        "/api/v1/heim/config/leitung/tagesausklang",
        json={"enabled": True},
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True


def test_patch_partial_update_keeps_other_fields(client, mira_leitung):
    """custom_title setzen, dann nur enabled patchen — title bleibt."""
    client.patch(
        "/api/v1/heim/config/leitung/tagesausklang",
        json={"custom_title": "Mein Titel"},
        headers=_auth_for(mira_leitung),
    )
    res = client.patch(
        "/api/v1/heim/config/leitung/tagesausklang",
        json={"enabled": False},
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False
    assert body["custom_title"] == "Mein Titel"

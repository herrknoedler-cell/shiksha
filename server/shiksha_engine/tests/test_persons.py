"""Persons-Router-Tests — CRUD, Filter, Tenant-Isolation, Auth-Rollen."""

from __future__ import annotations

from datetime import date

import pytest

from shiksha_engine.models import Organization, Person


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
# Test-Daten
# ===================================================================

@pytest.fixture
def krummelus_persons(db, mira_leitung):
    """Drei Personen-Stammdaten in Krummelus."""
    p1 = Person(
        tenant_org_id=mira_leitung.org_id,
        kind="kind", given_name="Amelie", family_name="K.",
        birth_date=date(2023, 4, 15), gender="w", group_id=2,
    )
    p2 = Person(
        tenant_org_id=mira_leitung.org_id,
        kind="kind", given_name="Tobias", family_name="M.",
        birth_date=date(2022, 8, 3), gender="m", group_id=2,
    )
    p3 = Person(
        tenant_org_id=mira_leitung.org_id,
        kind="staff", given_name="Anna", family_name="W.",
        birth_date=date(1989, 6, 12),
        metadata_={"qualification": "Pädagogin"},
    )
    for p in (p1, p2, p3):
        db.add(p)
    db.commit()
    return [p1, p2, p3]


# ===================================================================
# Auth
# ===================================================================

def test_persons_unauthorized_returns_401(client):
    res = client.get("/api/v1/persons")
    assert res.status_code == 401


def test_persons_klient_role_denied(client, vater):
    """Eltern dürfen Persons-API nicht ansprechen (Phase 1.5)."""
    res = client.get("/api/v1/persons", headers=_auth_for(vater))
    assert res.status_code == 403


def test_persons_staff_role_allowed(client, mira_leitung, krummelus_persons):
    res = client.get("/api/v1/persons", headers=_auth_for(mira_leitung))
    assert res.status_code == 200


# ===================================================================
# GET — Liste + Filter
# ===================================================================

def test_list_returns_all_active(client, mira_leitung, krummelus_persons):
    res = client.get("/api/v1/persons", headers=_auth_for(mira_leitung))
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 3


def test_list_filter_by_kind(client, mira_leitung, krummelus_persons):
    res = client.get(
        "/api/v1/persons?kind=kind",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert all(p["kind"] == "kind" for p in items)


def test_list_filter_by_search(client, mira_leitung, krummelus_persons):
    res = client.get(
        "/api/v1/persons?q=amel",
        headers=_auth_for(mira_leitung),
    )
    items = res.json()
    assert len(items) == 1
    assert items[0]["given_name"] == "Amelie"


def test_list_active_only_default(client, db, mira_leitung, krummelus_persons):
    # Eine Person deaktivieren
    p = krummelus_persons[0]
    p.active = False
    db.add(p)
    db.commit()

    res = client.get("/api/v1/persons", headers=_auth_for(mira_leitung))
    items = res.json()
    assert len(items) == 2  # Amelie raus


def test_list_active_false_shows_inactive(client, db, mira_leitung, krummelus_persons):
    p = krummelus_persons[0]
    p.active = False
    db.add(p)
    db.commit()

    res = client.get(
        "/api/v1/persons?active_only=false",
        headers=_auth_for(mira_leitung),
    )
    items = res.json()
    assert len(items) == 3


# ===================================================================
# GET — Stats
# ===================================================================

def test_stats_aggregation(client, mira_leitung, krummelus_persons):
    res = client.get("/api/v1/persons/stats", headers=_auth_for(mira_leitung))
    assert res.status_code == 200
    stats = res.json()
    assert stats["total"] == 3
    assert stats["kind_count"] == 2
    assert stats["staff_count"] == 1
    assert stats["eltern_count"] == 0
    assert stats["inactive_count"] == 0


def test_stats_counts_inactive(client, db, mira_leitung, krummelus_persons):
    krummelus_persons[0].active = False
    db.add(krummelus_persons[0])
    db.commit()

    res = client.get("/api/v1/persons/stats", headers=_auth_for(mira_leitung))
    stats = res.json()
    assert stats["inactive_count"] == 1
    assert stats["kind_count"] == 1  # Amelie raus


# ===================================================================
# GET /{id} — Detail
# ===================================================================

def test_detail_returns_person(client, mira_leitung, krummelus_persons):
    p = krummelus_persons[0]
    res = client.get(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["given_name"] == "Amelie"
    assert body["family_name"] == "K."
    assert body["kind"] == "kind"


def test_detail_404_for_unknown(client, mira_leitung):
    res = client.get("/api/v1/persons/99999", headers=_auth_for(mira_leitung))
    assert res.status_code == 404


def test_detail_404_for_deleted(client, db, mira_leitung, krummelus_persons):
    from datetime import datetime, timezone
    p = krummelus_persons[0]
    p.deleted_at = datetime.now(timezone.utc)
    db.add(p)
    db.commit()

    res = client.get(f"/api/v1/persons/{p.id}", headers=_auth_for(mira_leitung))
    assert res.status_code == 404


# ===================================================================
# POST — Anlegen
# ===================================================================

def test_create_kind(client, mira_leitung):
    res = client.post(
        "/api/v1/persons",
        headers=_auth_for(mira_leitung),
        json={
            "kind": "kind",
            "given_name": "Lukas",
            "family_name": "B.",
            "birth_date": "2024-01-10",
            "gender": "m",
            "group_id": 1,
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["id"] is not None
    assert body["tenant_org_id"] == mira_leitung.org_id
    assert body["given_name"] == "Lukas"


def test_create_invalid_kind_rejected(client, mira_leitung):
    res = client.post(
        "/api/v1/persons",
        headers=_auth_for(mira_leitung),
        json={"kind": "alien", "given_name": "Zorblax"},
    )
    assert res.status_code == 422  # Pydantic-Validierung


def test_create_denied_for_padagoge(client, pedagogin):
    """Pädagogin darf KEINE Person anlegen (nur Leitung+Developer)."""
    res = client.post(
        "/api/v1/persons",
        headers=_auth_for(pedagogin),
        json={"kind": "kind", "given_name": "X"},
    )
    assert res.status_code == 403


def test_padagoge_can_read_but_not_write(client, mira_leitung, pedagogin, krummelus_persons):
    """Pädagogin darf GET, aber kein POST/PATCH/DELETE."""
    p = krummelus_persons[0]
    res_get = client.get(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(pedagogin),
    )
    assert res_get.status_code == 200

    res_patch = client.patch(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(pedagogin),
        json={"notes": "Test"},
    )
    assert res_patch.status_code == 403


# ===================================================================
# PATCH — Bearbeiten
# ===================================================================

def test_patch_updates_field(client, mira_leitung, krummelus_persons):
    p = krummelus_persons[0]
    res = client.patch(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
        json={"notes": "Vegetarisch"},
    )
    assert res.status_code == 200
    assert res.json()["notes"] == "Vegetarisch"


def test_patch_only_updates_provided_fields(client, mira_leitung, krummelus_persons):
    """Family_name nicht im Patch → bleibt unverändert."""
    p = krummelus_persons[0]
    res = client.patch(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
        json={"given_name": "Amelie-Sophie"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["given_name"] == "Amelie-Sophie"
    assert body["family_name"] == "K."  # unverändert


def test_patch_metadata(client, mira_leitung, krummelus_persons):
    """Metadata-Dict kann gesetzt werden."""
    p = krummelus_persons[2]  # Anna W. (Staff)
    res = client.patch(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
        json={"metadata": {"qualification": "Leitung", "contract_type": "unbefristet"}},
    )
    assert res.status_code == 200
    assert res.json()["metadata"]["contract_type"] == "unbefristet"


# ===================================================================
# DELETE — Soft-Delete
# ===================================================================

def test_delete_is_soft(client, db, mira_leitung, krummelus_persons):
    p = krummelus_persons[0]
    res = client.delete(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
    )
    assert res.status_code == 204

    db.expire_all()
    refreshed = db.get(Person, p.id)
    assert refreshed.deleted_at is not None
    assert refreshed.active is False


def test_delete_removes_from_list(client, mira_leitung, krummelus_persons):
    p = krummelus_persons[0]
    client.delete(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(mira_leitung),
    )
    res = client.get("/api/v1/persons", headers=_auth_for(mira_leitung))
    items = res.json()
    assert len(items) == 2
    assert all(item["id"] != p.id for item in items)


# ===================================================================
# Tenant-Isolation
# ===================================================================

def test_cross_tenant_access_denied(client, db, mira_leitung, krummelus_persons):
    # Eine andere Organisation + Operator anlegen
    other_org = Organization(
        id="other_kita", edition="kita", name="Andere KITA",
        legal_name="Andere KITA gGmbH", region="Wien, AT",
        metadata_={},
    )
    from shiksha_engine.models import Operator
    other_op = Operator(
        id="other_leitung",
        org_id="other_kita", edition="kita",
        display_name="Other-Mira",
        kind="staff", role="leitung",
        email="other@kita.example",
        metadata_={},
    )
    db.add(other_org)
    db.add(other_op)
    db.commit()

    # Other-Leitung versucht, Krummelus-Person zu sehen
    p = krummelus_persons[0]
    res = client.get(
        f"/api/v1/persons/{p.id}",
        headers=_auth_for(other_op),
    )
    assert res.status_code == 403


def test_list_filters_by_tenant(client, db, mira_leitung, krummelus_persons):
    """Other-Leitung sieht ihre eigenen Personen, nicht die Krummelus-Personen."""
    other_org = Organization(
        id="other_kita_2", edition="kita", name="Andere KITA 2",
        legal_name="Andere KITA 2 gGmbH", region="Berlin, DE",
        metadata_={},
    )
    from shiksha_engine.models import Operator
    other_op = Operator(
        id="other_leitung_2",
        org_id="other_kita_2", edition="kita",
        display_name="Other-Mira-2",
        kind="staff", role="leitung",
        email="other2@kita.example",
        metadata_={},
    )
    db.add(other_org)
    db.add(other_op)
    # Eine Person für die andere KITA
    other_person = Person(
        tenant_org_id="other_kita_2",
        kind="kind", given_name="Fremd", family_name="Kind",
    )
    db.add(other_person)
    db.commit()

    res = client.get("/api/v1/persons", headers=_auth_for(other_op))
    items = res.json()
    assert len(items) == 1
    assert items[0]["given_name"] == "Fremd"


# ===================================================================
# Developer-Bypass (sieht Cross-Tenant für Debugging)
# ===================================================================

def test_developer_sees_all_tenants(client, db, mira_leitung, thomas, krummelus_persons):
    """Developer (kind=system) ist tenant-übergreifend."""
    res = client.get("/api/v1/persons", headers=_auth_for(thomas))
    assert res.status_code == 200
    # Sollte mindestens die Krummelus-Personen sehen (3)
    items = res.json()
    assert len(items) >= 3

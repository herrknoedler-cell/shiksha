"""Memory-Router Tests."""

import pytest

from shiksha_engine.models import MemoryEntry
from shiksha_engine.services.jwt_service import issue_token


def _auth_header(operator):
    token = issue_token(
        operator_id=operator.id,
        role=operator.role,
        edition=operator.edition,
        org_id=operator.org_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_memory(client, mira, db):
    headers = _auth_header(mira)

    # POST
    r = client.post("/api/v1/memory", json={"text": "Mira mag keine Wochenend-Anrufe."}, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["text"] == "Mira mag keine Wochenend-Anrufe."
    assert body["operator_id"] == mira.id
    mem_id = body["id"]

    # LIST
    r = client.get("/api/v1/memory", headers=headers)
    assert r.status_code == 200
    entries = r.json()
    assert any(e["id"] == mem_id for e in entries)


def test_patch_memory(client, mira):
    headers = _auth_header(mira)
    r = client.post("/api/v1/memory", json={"text": "Original-Text"}, headers=headers)
    mem_id = r.json()["id"]

    r = client.patch(f"/api/v1/memory/{mem_id}", json={"text": "Korrigierter Text"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["text"] == "Korrigierter Text"


def test_delete_memory(client, mira):
    headers = _auth_header(mira)
    r = client.post("/api/v1/memory", json={"text": "Wird gleich gelöscht"}, headers=headers)
    mem_id = r.json()["id"]

    r = client.delete(f"/api/v1/memory/{mem_id}", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/api/v1/memory", headers=headers)
    assert all(e["id"] != mem_id for e in r.json())


def test_operator_cannot_see_others(client, mira, thomas, db):
    # Thomas legt für Mira einen Eintrag an (er ist developer)
    th_headers = _auth_header(thomas)
    r = client.post(
        "/api/v1/memory",
        json={"text": "Von Thomas für Mira", "operator_id": mira.id},
        headers=th_headers,
    )
    assert r.status_code == 201

    # Mira sieht eigene
    mira_headers = _auth_header(mira)
    r = client.get("/api/v1/memory", headers=mira_headers)
    mira_entries = r.json()
    assert any("Von Thomas für Mira" in e["text"] for e in mira_entries)

    # Mira darf NICHT cross-operator querieren
    r = client.get(f"/api/v1/memory?target_operator_id={thomas.id}", headers=mira_headers)
    assert r.status_code == 403


def test_developer_can_see_others(client, mira, thomas):
    th_headers = _auth_header(thomas)
    # Erst Mira's Memory anreichern
    mira_headers = _auth_header(mira)
    client.post("/api/v1/memory", json={"text": "Mira's eigenes"}, headers=mira_headers)

    # Thomas cross-queriet
    r = client.get(f"/api/v1/memory?target_operator_id={mira.id}", headers=th_headers)
    assert r.status_code == 200
    entries = r.json()
    assert any("Mira's eigenes" in e["text"] for e in entries)

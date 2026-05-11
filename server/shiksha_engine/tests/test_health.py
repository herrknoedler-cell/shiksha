"""Sanity-Check — /health läuft."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "SHIKSHA Engine"

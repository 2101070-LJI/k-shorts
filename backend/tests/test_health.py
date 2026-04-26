from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "ollama" in body
    assert "current_weights" in body


def test_templates_list():
    r = client.get("/templates")
    assert r.status_code == 200
    ids = {t["id"] for t in r.json()}
    assert ids == {"clean", "soft", "bold", "split"}


def test_template_one():
    r = client.get("/templates/clean")
    assert r.status_code == 200
    assert r.json()["layout"]["type"] == "face_track"


def test_template_missing():
    r = client.get("/templates/nope")
    assert r.status_code == 404

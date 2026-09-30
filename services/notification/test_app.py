from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_notify_accepted():
    r = client.post("/notify", json={"to": "a@example.com", "subject": "Hi", "body": "Hello"})
    assert r.status_code == 202
    assert client.get("/notifications").json()[-1]["subject"] == "Hi"


def test_health():
    assert client.get("/healthz").status_code == 200

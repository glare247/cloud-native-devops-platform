from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_list_items():
    items = client.get("/items").json()
    assert any(i["sku"] == "sku-100" for i in items)


def test_reserve_success():
    r = client.post("/reserve", json={"sku": "sku-100", "quantity": 2})
    assert r.status_code == 200
    assert r.json()["reserved"] == 2


def test_reserve_out_of_stock():
    r = client.post("/reserve", json={"sku": "sku-300", "quantity": 1})
    assert r.status_code == 409


def test_unknown_sku():
    assert client.get("/items/nope").status_code == 404


def test_metrics_exposed():
    assert client.get("/metrics").status_code == 200

import httpx
import respx
from fastapi.testclient import TestClient

import app as fe

client = TestClient(fe.app)


@respx.mock
def test_home_lists_items():
    respx.get(f"{fe.INVENTORY_URL}/items").mock(return_value=httpx.Response(
        200, json=[{"sku": "sku-100", "name": "Laptop", "price": 1200.0, "stock": 5}]))
    r = client.get("/")
    assert r.status_code == 200
    assert "Laptop" in r.text


@respx.mock
def test_home_degrades_gracefully():
    respx.get(f"{fe.INVENTORY_URL}/items").mock(side_effect=httpx.ConnectError("down"))
    r = client.get("/")
    assert r.status_code == 200
    assert "unavailable" in r.text

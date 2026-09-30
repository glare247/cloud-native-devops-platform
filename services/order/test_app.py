"""Unit tests mock the downstream services, so they run without a cluster."""
import httpx
import respx
from fastapi.testclient import TestClient

import app as order_app

client = TestClient(order_app.app)


@respx.mock
def test_create_order_success():
    respx.post(f"{order_app.INVENTORY_URL}/reserve").mock(
        return_value=httpx.Response(200, json={"sku": "sku-100", "reserved": 2, "remaining": 48, "unit_price": 10.0})
    )
    respx.post(f"{order_app.NOTIFICATION_URL}/notify").mock(return_value=httpx.Response(202))

    r = client.post("/orders", json={"sku": "sku-100", "quantity": 2, "customer_email": "a@example.com"})
    assert r.status_code == 201
    assert r.json()["total"] == 20.0
    assert r.json()["status"] == "CONFIRMED"


@respx.mock
def test_create_order_out_of_stock():
    respx.post(f"{order_app.INVENTORY_URL}/reserve").mock(
        return_value=httpx.Response(409, json={"detail": "Insufficient stock"})
    )
    r = client.post("/orders", json={"sku": "sku-300", "quantity": 1, "customer_email": "a@example.com"})
    assert r.status_code == 409


@respx.mock
def test_order_survives_notification_outage():
    respx.post(f"{order_app.INVENTORY_URL}/reserve").mock(
        return_value=httpx.Response(200, json={"sku": "sku-100", "reserved": 1, "remaining": 1, "unit_price": 5.0})
    )
    respx.post(f"{order_app.NOTIFICATION_URL}/notify").mock(side_effect=httpx.ConnectError("down"))
    r = client.post("/orders", json={"sku": "sku-100", "quantity": 1, "customer_email": "a@example.com"})
    assert r.status_code == 201


def test_invalid_email_rejected():
    r = client.post("/orders", json={"sku": "sku-100", "quantity": 1, "customer_email": "not-an-email"})
    assert r.status_code == 422

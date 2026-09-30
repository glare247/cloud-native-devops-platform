"""Order Service - creates orders.

Flow for POST /orders:
  1. call Inventory Service  -> reserve stock
  2. store the order
  3. call Notification Service -> tell the customer (best-effort, never blocks the order)
"""
import logging
import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, EmailStr

SERVICE = "order"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"' + SERVICE + '","msg":"%(message)s"}',
)
log = logging.getLogger(SERVICE)

# Service discovery via Kubernetes DNS names (overridable for local docker-compose)
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:8000")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification:8000")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "3"))

app = FastAPI(title="Order Service", version=os.getenv("APP_VERSION", "dev"))
Instrumentator().instrument(app).expose(app)

# Business metric -> great for a Grafana panel
ORDERS_TOTAL = Counter("orders_created_total", "Orders created", ["status"])

ORDERS: dict[str, dict] = {}


class OrderRequest(BaseModel):
    sku: str
    quantity: int
    customer_email: EmailStr


@app.get("/healthz")
def liveness():
    return {"status": "ok"}


@app.get("/readyz")
def readiness():
    # Ready only if the dependency we can't work without is reachable
    try:
        httpx.get(f"{INVENTORY_URL}/healthz", timeout=1).raise_for_status()
        return {"status": "ready"}
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="inventory unavailable")


@app.get("/orders")
def list_orders():
    return list(ORDERS.values())


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    return ORDERS[order_id]


@app.post("/orders", status_code=201)
def create_order(req: OrderRequest):
    # 1. Reserve stock
    try:
        res = httpx.post(
            f"{INVENTORY_URL}/reserve",
            json={"sku": req.sku, "quantity": req.quantity},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        ORDERS_TOTAL.labels(status="failed").inc()
        log.error("inventory call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Inventory service unreachable")

    if res.status_code != 200:
        ORDERS_TOTAL.labels(status="rejected").inc()
        raise HTTPException(status_code=res.status_code, detail=res.json().get("detail"))

    reservation = res.json()

    # 2. Save order
    order_id = str(uuid.uuid4())
    order = {
        "id": order_id,
        "sku": req.sku,
        "quantity": req.quantity,
        "total": round(reservation["unit_price"] * req.quantity, 2),
        "customer_email": req.customer_email,
        "status": "CONFIRMED",
    }
    ORDERS[order_id] = order
    ORDERS_TOTAL.labels(status="confirmed").inc()
    log.info("order created id=%s sku=%s qty=%s", order_id, req.sku, req.quantity)

    # 3. Notify (best-effort)
    try:
        httpx.post(
            f"{NOTIFICATION_URL}/notify",
            json={"to": req.customer_email, "subject": "Order confirmed",
                  "body": f"Your order {order_id} is confirmed."},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        log.warning("notification failed (order still created): %s", exc)

    return order

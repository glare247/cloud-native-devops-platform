"""Inventory Service - owns product stock levels.

Endpoints
  GET  /healthz          liveness probe
  GET  /readyz           readiness probe
  GET  /metrics          Prometheus metrics
  GET  /items            list all items
  GET  /items/{sku}      one item
  POST /reserve          reserve stock (called by Order Service)
"""
import logging
import os

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "inventory"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"' + SERVICE + '","msg":"%(message)s"}',
)
log = logging.getLogger(SERVICE)

app = FastAPI(title="Inventory Service", version=os.getenv("APP_VERSION", "dev"))
Instrumentator().instrument(app).expose(app)  # /metrics for Prometheus

# In-memory store keeps the demo self-contained.
# In production, replace with PostgreSQL (e.g. AWS RDS) via DATABASE_URL.
STOCK: dict[str, dict] = {
    "sku-100": {"name": "Laptop", "price": 1200.0, "stock": 50},
    "sku-200": {"name": "Headphones", "price": 150.0, "stock": 10},
    "sku-300": {"name": "Keyboard", "price": 80.0, "stock": 0},
}


class Reservation(BaseModel):
    sku: str
    quantity: int


@app.get("/healthz")
def liveness():
    return {"status": "ok"}


@app.get("/readyz")
def readiness():
    return {"status": "ready"}


@app.get("/items")
def list_items():
    return [{"sku": sku, **data} for sku, data in STOCK.items()]


@app.get("/items/{sku}")
def get_item(sku: str):
    if sku not in STOCK:
        raise HTTPException(status_code=404, detail="SKU not found")
    return {"sku": sku, **STOCK[sku]}


@app.post("/reserve")
def reserve(r: Reservation):
    item = STOCK.get(r.sku)
    if item is None:
        raise HTTPException(status_code=404, detail="SKU not found")
    if r.quantity <= 0 or item["stock"] < r.quantity:
        log.warning("reservation rejected sku=%s qty=%s", r.sku, r.quantity)
        raise HTTPException(status_code=409, detail="Insufficient stock")
    item["stock"] -= r.quantity
    log.info("reserved sku=%s qty=%s remaining=%s", r.sku, r.quantity, item["stock"])
    return {"sku": r.sku, "reserved": r.quantity, "remaining": item["stock"], "unit_price": item["price"]}

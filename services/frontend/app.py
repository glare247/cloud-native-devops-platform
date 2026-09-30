"""Web Frontend - server-rendered page that talks to Inventory and Order services."""
import logging
import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from prometheus_fastapi_instrumentator import Instrumentator

SERVICE = "frontend"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"' + SERVICE + '","msg":"%(message)s"}',
)
log = logging.getLogger(SERVICE)

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:8000")
ORDER_URL = os.getenv("ORDER_URL", "http://order:8000")

app = FastAPI(title="Web Frontend", version=os.getenv("APP_VERSION", "dev"))
Instrumentator().instrument(app).expose(app)

PAGE = """<!doctype html><html><head><title>DevOps Shop</title>
<style>body{{font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:.5rem;border-bottom:1px solid #ddd;text-align:left}}
.msg{{padding:.75rem;background:#eef;margin:1rem 0}}</style></head><body>
<h1>DevOps Shop</h1><p>Version: {version}</p>{msg}
<table><tr><th>SKU</th><th>Item</th><th>Price</th><th>Stock</th><th>Order</th></tr>{rows}</table>
</body></html>"""

ROW = """<tr><td>{sku}</td><td>{name}</td><td>${price}</td><td>{stock}</td><td>
<form method="post" action="/order"><input type="hidden" name="sku" value="{sku}">
<input name="email" type="email" placeholder="you@example.com" required>
<button {disabled}>Buy 1</button></form></td></tr>"""


@app.get("/healthz")
def liveness():
    return {"status": "ok"}


@app.get("/readyz")
def readiness():
    return {"status": "ready"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, msg: str = ""):
    try:
        items = httpx.get(f"{INVENTORY_URL}/items", timeout=3).json()
    except httpx.HTTPError:
        items, msg = [], "Inventory service is unavailable right now."
    rows = "".join(
        ROW.format(**i, disabled="disabled" if i["stock"] == 0 else "") for i in items
    )
    banner = f'<div class="msg">{msg}</div>' if msg else ""
    return PAGE.format(version=app.version, msg=banner, rows=rows)


@app.post("/order")
def order(sku: str = Form(...), email: str = Form(...)):
    try:
        r = httpx.post(f"{ORDER_URL}/orders",
                       json={"sku": sku, "quantity": 1, "customer_email": email}, timeout=5)
        msg = f"Order {r.json()['id']} confirmed!" if r.status_code == 201 else f"Order failed: {r.json().get('detail')}"
    except httpx.HTTPError:
        msg = "Order service is unavailable right now."
    return RedirectResponse(url=f"/?msg={msg}", status_code=303)

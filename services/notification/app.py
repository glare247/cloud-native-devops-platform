"""Notification Service - sends customer notifications.

For the demo it logs the message (visible in Loki/Grafana). Swap `send()` for
AWS SES, SendGrid or an SNS topic in a real deployment.
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "notification"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"' + SERVICE + '","msg":"%(message)s"}',
)
log = logging.getLogger(SERVICE)

app = FastAPI(title="Notification Service", version=os.getenv("APP_VERSION", "dev"))
Instrumentator().instrument(app).expose(app)

SENT_TOTAL = Counter("notifications_sent_total", "Notifications sent", ["channel"])
OUTBOX: list[dict] = []


class Notification(BaseModel):
    to: str
    subject: str
    body: str
    channel: str = "email"


def send(n: Notification) -> None:
    log.info("sending %s to=%s subject=%s", n.channel, n.to, n.subject)


@app.get("/healthz")
def liveness():
    return {"status": "ok"}


@app.get("/readyz")
def readiness():
    return {"status": "ready"}


@app.post("/notify", status_code=202)
def notify(n: Notification):
    send(n)
    record = {**n.model_dump(), "sent_at": datetime.now(timezone.utc).isoformat()}
    OUTBOX.append(record)
    SENT_TOTAL.labels(channel=n.channel).inc()
    return {"accepted": True}


@app.get("/notifications")
def list_notifications():
    return OUTBOX[-50:]

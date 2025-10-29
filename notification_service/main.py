import json, threading
from fastapi import FastAPI
import redis
from common.kafka import get_consumer, TOPIC_PAYMENT_EVENTS
from common.settings import settings

app = FastAPI(title="Notification Service")

r = redis.from_url(settings.redis_url)

def was_sent(event_id: str) -> bool:
    # Returns True if already sent
    return r.setnx(f"notif:{event_id}", 1) == 0

def consume():
    c = get_consumer("notification-service", [TOPIC_PAYMENT_EVENTS])
    while True:
        msg = c.poll(1.0)
        if not msg or msg.error():
            continue
        evt = json.loads(msg.value())
        event_id = f"{evt.get('type')}:{evt.get('payment_id')}"
        if was_sent(event_id):
            c.commit(); continue
        if evt.get("type") == "PaymentCommitted":
            print(f"[NOTIFY] Payment {evt['payment_id']} committed for user {evt['user_id']}")
        elif evt.get("type") == "PaymentFailed":
            print(f"[NOTIFY] Payment {evt['payment_id']} failed: {evt.get('reason')}")
        c.commit()

threading.Thread(target=consume, daemon=True).start()

@app.get("/health")
async def health():
    return {"ok": True}

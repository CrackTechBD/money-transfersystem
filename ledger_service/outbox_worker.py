import json, time
from sqlalchemy import select, update
from confluent_kafka import KafkaException
from common.kafka import producer, TOPIC_PAYMENT_EVENTS
from db import SessionLocal
from models import Outbox

POLL_INTERVAL = 0.5

def run():
    while True:
        try:
            with SessionLocal() as db:
                rows = db.execute(select(Outbox).where(Outbox.status=="new").limit(50)).scalars().all()
                for row in rows:
                    try:
                        producer.produce(TOPIC_PAYMENT_EVENTS, value=row.payload.encode("utf-8"))
                        producer.flush()
                        db.execute(update(Outbox).where(Outbox.id==row.id).values(status="sent"))
                        db.commit()
                    except KafkaException:
                        db.execute(update(Outbox).where(Outbox.id==row.id).values(status="failed"))
                        db.commit()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

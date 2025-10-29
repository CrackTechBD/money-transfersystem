from confluent_kafka import Producer, Consumer
import json
from common.settings import settings

producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "enable.idempotence": True})

def get_consumer(group_id: str, topics: list[str]):
    c = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe(topics)
    return c

TOPIC_PAYMENT_COMMANDS = "payment_commands"
TOPIC_PAYMENT_EVENTS   = "payment_events"
TOPIC_FRAUD_EVENTS     = "fraud_events"

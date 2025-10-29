import json, threading, time
from fastapi import FastAPI, Depends, Header, HTTPException
from cassandra.cluster import Cluster
from cassandra.cluster import NoHostAvailable
from common.kafka import get_consumer, producer, TOPIC_PAYMENT_EVENTS, TOPIC_FRAUD_EVENTS
from common.schemas import FraudDecision, InitiatePayment, PaymentEvent
from common.security import verify_token, mint_internal_jwt
from common.settings import settings
import requests

app = FastAPI(title="Fraud Service")

# Initialize Cassandra with retry logic
def connect_to_cassandra(max_retries=30, retry_delay=2):
    """Connect to Cassandra with retry logic"""
    for attempt in range(max_retries):
        try:
            cluster = Cluster([settings.cassandra_host])
            session = cluster.connect()
            session.set_keyspace(settings.cassandra_keyspace)
            print(f"✅ Connected to Cassandra on attempt {attempt + 1}")
            return cluster, session
        except (NoHostAvailable, Exception) as e:
            print(f"❌ Cassandra connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise e

cluster, session = connect_to_cassandra()

# Very naive risk function (demo only)
def risk_score(evt) -> float:
    amt = evt.get("amount", 0)
    return min(1.0, amt / 10000.0)

def consume():
    print("🔍 Starting Kafka consumer for fraud service...")
    c = get_consumer("fraud-service", [TOPIC_PAYMENT_EVENTS])
    print(f"🔍 Consumer created for topic: {TOPIC_PAYMENT_EVENTS}")
    while True:
        msg = c.poll(1.0)
        if not msg or msg.error():
            continue
        print(f"🔍 Received message: {msg.value()}")
        evt = json.loads(msg.value())
        print(f"🔍 Parsed event: {evt}")
        if evt.get("type") != "PaymentInitiated":
            print(f"🔍 Skipping event type: {evt.get('type')}")
            c.commit()
            continue
        score = risk_score(evt)
        decision = "allow" if score < 0.7 else "review"
        print(f"🔍 Fraud score: {score}, decision: {decision}")
        # Write features for analysis
        session.execute(
            "INSERT INTO features (payment_id, user_id, amount, score) VALUES (%s,%s,%s,%s)",
            (evt["payment_id"], evt["user_id"], evt["amount"], score),
        )
        print(f"🔍 Stored fraud features for payment_id: {evt['payment_id']}")
        fd = FraudDecision(payment_id=evt["payment_id"], decision=decision, score=score)
        producer.produce(TOPIC_FRAUD_EVENTS, value=fd.model_dump_json().encode("utf-8"))
        producer.flush()
        c.commit()
        print(f"🔍 Published fraud decision for payment_id: {evt['payment_id']}")

print("🚀 Starting fraud consumer thread...")
threading.Thread(target=consume, daemon=True).start()

@app.get("/health")
async def health():
    return {"ok": True}

# User auth dependency
async def user_auth(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")

@app.post("/evaluate")
async def evaluate_payment(payment: InitiatePayment, user=Depends(user_auth)):
    """
    Evaluate a payment for fraud and initiate the payment flow.
    This is the main entry point for payment processing.
    """
    try:
        # Step 1: Perform fraud check
        score = risk_score(payment.model_dump())
        decision = "allow" if score < 0.5 else ("review" if score < 0.8 else "block")
        
        # Store fraud decision
        session.execute(
            "INSERT INTO features (payment_id, user_id, amount, score) VALUES (%s,%s,%s,%s)",
            (payment.payment_id, payment.user_id, payment.amount, score)
        )
        
        # Publish fraud decision
        fd = FraudDecision(payment_id=payment.payment_id, decision=decision, score=score)
        producer.produce(TOPIC_FRAUD_EVENTS, value=fd.model_dump_json().encode("utf-8"))
        producer.flush()
        
        if decision == "block":
            # Create payment failed event
            pe = PaymentEvent(
                type="PaymentFailed", 
                **payment.model_dump(), 
                reason="fraud_blocked"
            )
            producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
            producer.flush()
            
            return {
                "status": "blocked",
                "payment_id": payment.payment_id,
                "reason": "fraud_blocked",
                "fraud_score": score
            }
        
        elif decision == "review":
            # Create payment under review
            pe = PaymentEvent(
                type="PaymentFailed", 
                **payment.model_dump(), 
                reason="under_review"
            )
            producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
            producer.flush()
            
            return {
                "status": "under_review",
                "payment_id": payment.payment_id,
                "reason": "manual_review_required",
                "fraud_score": score
            }
        
        # Step 2: If allowed, initiate payment
        pe_initiated = PaymentEvent(
            type="PaymentInitiated",
            **payment.model_dump()
        )
        producer.produce(TOPIC_PAYMENT_EVENTS, value=pe_initiated.model_dump_json().encode("utf-8"))
        producer.flush()
        
        # Step 3: Call shard manager service to process payment
        try:
            # Convert amount from cents to dollars (shard_manager expects dollars)
            amount_dollars = payment.amount / 100
            
            shard_response = requests.post(
                f"http://shard_manager_service:8000/transfer/{payment.user_id}/{payment.merchant_id}/{amount_dollars}",
                timeout=10
            )
            
            if shard_response.status_code == 200:
                shard_result = shard_response.json()
                
                # Send success event to Kafka
                pe_success = PaymentEvent(type="PaymentCommitted", **payment.model_dump())
                producer.produce(TOPIC_PAYMENT_EVENTS, value=pe_success.model_dump_json().encode("utf-8"))
                producer.flush()
                
                return {
                    "status": "completed" if shard_result.get("success") else "failed",
                    "payment_id": payment.payment_id,
                    "fraud_score": score,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "transfer_details": shard_result
                }
            else:
                # Send failure event to Kafka
                pe_fail = PaymentEvent(
                    type="PaymentFailed", 
                    **payment.model_dump(), 
                    reason="transfer_failed"
                )
                producer.produce(TOPIC_PAYMENT_EVENTS, value=pe_fail.model_dump_json().encode("utf-8"))
                producer.flush()
                
                return {
                    "status": "failed",
                    "payment_id": payment.payment_id,
                    "reason": "shard_manager_error",
                    "fraud_score": score,
                    "http_status": shard_response.status_code
                }
                
        except Exception as e:
            # Send failure event to Kafka
            try:
                pe_fail = PaymentEvent(
                    type="PaymentFailed", 
                    **payment.model_dump(), 
                    reason="service_timeout"
                )
                producer.produce(TOPIC_PAYMENT_EVENTS, value=pe_fail.model_dump_json().encode("utf-8"))
                producer.flush()
            except:
                pass  # Don't let Kafka errors block the response
                
            return {
                "status": "failed",
                "payment_id": payment.payment_id,
                "reason": "shard_manager_timeout",
                "error": str(e),
                "fraud_score": score
            }
            
    except Exception as e:
        return {
            "status": "error",
            "payment_id": payment.payment_id,
            "error": str(e)
        }

import json, threading
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from common.schemas import InitiatePayment, PaymentEvent
from common.kafka import TOPIC_PAYMENT_EVENTS, producer
from common.security import verify_token, mint_internal_jwt
from db import SessionLocal, engine
from models import Base, Account, LedgerEntry, Outbox

app = FastAPI(title="Ledger Service")
Base.metadata.create_all(bind=engine)

print("🚀 Ledger service starting with direct Kafka publishing...")

# Simple dependency to check internal auth (down-scoped token)
async def internal_auth(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ",1)[1]
    try:
        verify_token(token, audience="ledger")
    except Exception as e:
        raise HTTPException(401, f"invalid internal token: {e}")

# For demo, create accounts quickly
@app.post("/accounts/{account_id}/seed/{balance}")
async def seed(account_id: str, balance: int):
    with SessionLocal() as db:
        acc = db.get(Account, account_id)
        if not acc:
            acc = Account(id=account_id, balance=balance)
            db.add(acc)
        else:
            acc.balance = balance
        db.commit()
    return {"ok": True}

@app.post("/commit", dependencies=[Depends(internal_auth)])
async def commit(payment: InitiatePayment):
    """ACID money move: debit user, credit merchant; send events directly."""
    print(f"💰 Processing payment commit: {payment.payment_id[:8]}... for ₹{payment.amount/100:.2f}")
    
    with SessionLocal() as db:
        user = db.get(Account, payment.user_id)
        merch = db.get(Account, payment.merchant_id)
        if not user or not merch:
            print(f"❌ Account not found: user={user is not None}, merchant={merch is not None}")
            raise HTTPException(400, "account not found")
        if user.balance < payment.amount:
            print(f"❌ Insufficient funds: balance={user.balance}, required={payment.amount}")
            pe = PaymentEvent(type="PaymentFailed", **payment.model_dump(), reason="insufficient_funds")
            # Send directly to Kafka instead of outbox
            try:
                producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
                producer.flush()
                print(f"📤 Sent PaymentFailed event for {payment.payment_id[:8]}...")
            except Exception as e:
                print(f"❌ Failed to send PaymentFailed event: {e}")
            return {"status": "failed", "reason": "insufficient_funds"}

        print(f"✅ Sufficient funds. User balance: {user.balance}, Payment: {payment.amount}")
        
        # Atomic posting
        user.balance -= payment.amount
        merch.balance += payment.amount
        db.add(LedgerEntry(payment_id=payment.payment_id, account_id=user.id, amount=payment.amount, direction="debit"))
        db.add(LedgerEntry(payment_id=payment.payment_id, account_id=merch.id, amount=payment.amount, direction="credit"))

        # Commit database changes first
        db.commit()
        print(f"💾 Database committed. New balances - User: {user.balance}, Merchant: {merch.balance}")

        # Send success event directly to Kafka
        pe = PaymentEvent(type="PaymentCommitted", **payment.model_dump())
        try:
            print(f"📤 Publishing PaymentCommitted event to Kafka...")
            producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
            producer.flush()
            print(f"✅ Successfully sent PaymentCommitted event for {payment.payment_id[:8]}...")
        except Exception as e:
            print(f"❌ Failed to send PaymentCommitted event: {e}")
            # Note: Transaction is already committed to DB, this is just event publishing

    return {"status": "committed"}

@app.get("/health")
async def health():
    return {"ok": True, "service": "ledger"}

# Helper for other services to get an internal token (in real life, gateway issues this)
@app.get("/mint-internal-token")
async def mint():
    return {"token": mint_internal_jwt(aud="ledger")}

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

@app.post("/payment/transfer")
async def transfer_money(payment_data: dict):
    """Simple transfer endpoint for user-to-user payments with sharding support"""
    import hashlib
    import mysql.connector
    import uuid
    from datetime import datetime
    
    try:
        from_user = payment_data.get("from_user_id")
        to_user = payment_data.get("to_user_id")
        amount = float(payment_data.get("amount", 0))
        
        if not from_user or not to_user or amount <= 0:
            raise HTTPException(400, "Invalid payment data")
        
        # Convert to cents
        amount_cents = int(amount * 100)
        payment_id = str(uuid.uuid4())
        
        # Calculate shards for both users
        from_shard = int(hashlib.md5(from_user.encode()).hexdigest(), 16) % 4
        to_shard = int(hashlib.md5(to_user.encode()).hexdigest(), 16) % 4
        
        print(f"💳 Transfer: {from_user}(shard {from_shard}) -> {to_user}(shard {to_shard}), ${amount}")
        
        # Get shard connections
        def get_shard_conn(shard_id):
            import os
            host = os.environ.get(f'SHARD_{shard_id}_HOST', f'mysql-shard-{shard_id}')
            return mysql.connector.connect(
                host=host, port=3306, user='root',
                password='rootpassword', database='paytm_shard'
            )
        
        # Connect to shards
        from_conn = get_shard_conn(from_shard)
        to_conn = get_shard_conn(to_shard) if to_shard != from_shard else from_conn
        
        try:
            # Start transactions
            from_cursor = from_conn.cursor(dictionary=True)
            to_cursor = to_conn.cursor(dictionary=True) if to_conn != from_conn else from_cursor
            
            # Check sender balance
            from_cursor.execute("SELECT balance FROM accounts WHERE user_id = %s FOR UPDATE", (from_user,))
            from_account = from_cursor.fetchone()
            
            if not from_account:
                raise HTTPException(400, f"Sender account not found: {from_user}")
            
            if from_account['balance'] < amount_cents:
                raise HTTPException(400, f"Insufficient balance: have ${from_account['balance']/100:.2f}, need ${amount:.2f}")
            
            # Check recipient exists
            to_cursor.execute("SELECT balance FROM accounts WHERE user_id = %s FOR UPDATE", (to_user,))
            to_account = to_cursor.fetchone()
            
            if not to_account:
                raise HTTPException(400, f"Recipient account not found: {to_user}")
            
            # Debit sender
            from_cursor.execute(
                "UPDATE accounts SET balance = balance - %s WHERE user_id = %s",
                (amount_cents, from_user)
            )
            from_cursor.execute(
                "INSERT INTO ledger_entries (payment_id, account_id, amount, direction, created_at) VALUES (%s, %s, %s, 'debit', NOW())",
                (payment_id, from_user, amount_cents)
            )
            
            # Credit recipient
            to_cursor.execute(
                "UPDATE accounts SET balance = balance + %s WHERE user_id = %s",
                (amount_cents, to_user)
            )
            to_cursor.execute(
                "INSERT INTO ledger_entries (payment_id, account_id, amount, direction, created_at) VALUES (%s, %s, %s, 'credit', NOW())",
                (payment_id, to_user, amount_cents)
            )
            
            # Commit both transactions
            from_conn.commit()
            if to_conn != from_conn:
                to_conn.commit()
            
            print(f"✅ Transfer complete: {payment_id[:16]}...")
            
            return {
                "status": "success",
                "payment_id": payment_id,
                "from_user": from_user,
                "to_user": to_user,
                "amount": amount,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            from_conn.rollback()
            if to_conn != from_conn:
                to_conn.rollback()
            raise
        finally:
            from_cursor.close()
            if to_conn != from_conn:
                to_cursor.close()
            from_conn.close()
            if to_conn != from_conn:
                to_conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        raise HTTPException(500, f"Transfer failed: {str(e)}")

@app.get("/health")
async def health():
    return {"ok": True, "service": "ledger"}

# Helper for other services to get an internal token (in real life, gateway issues this)
@app.get("/mint-internal-token")
async def mint():
    return {"token": mint_internal_jwt(aud="ledger")}

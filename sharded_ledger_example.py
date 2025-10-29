"""
Modified Ledger Service that understands sharding
This would replace the current ledger_service/main.py
"""

import json, threading
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from common.schemas import InitiatePayment, PaymentEvent
from common.kafka import TOPIC_PAYMENT_EVENTS, producer
from common.security import verify_token, mint_internal_jwt
import hashlib
import os
from typing import Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ledger_service.models import Base, Account, LedgerEntry

app = FastAPI(title="Sharded Ledger Service")

class ShardedLedgerService:
    def __init__(self):
        self.total_shards = int(os.getenv("TOTAL_SHARDS", "4"))
        self.engines = {}
        self.sessions = {}
        
        # Initialize connections to all shards
        for shard_id in range(self.total_shards):
            host = f"mysql-shard-{shard_id}"
            database_url = f"mysql+pymysql://root:rootpassword@{host}:3306/paytm_shard"
            engine = create_engine(database_url)
            Base.metadata.create_all(bind=engine)
            
            self.engines[shard_id] = engine
            self.sessions[shard_id] = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def get_shard_id(self, user_id: str) -> int:
        """Determine which shard contains this user"""
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        return hash_value % self.total_shards
    
    def get_session(self, shard_id: int):
        """Get database session for specific shard"""
        return self.sessions[shard_id]()

# Initialize the sharded ledger service
sharded_ledger = ShardedLedgerService()

# Authentication dependency
async def internal_auth(authorization: str = Header(...)):
    """Verify internal service authentication"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")

@app.post("/commit", dependencies=[Depends(internal_auth)])
async def commit(payment: InitiatePayment):
    """ACID money move across shards"""
    user_shard = sharded_ledger.get_shard_id(payment.user_id)
    merchant_shard = sharded_ledger.get_shard_id(payment.merchant_id)
    
    if user_shard == merchant_shard:
        # Same shard transaction - simpler case
        return await commit_same_shard(payment, user_shard)
    else:
        # Cross-shard transaction - more complex
        return await commit_cross_shard(payment, user_shard, merchant_shard)

async def commit_same_shard(payment: InitiatePayment, shard_id: int):
    """Handle transaction within same shard"""
    with sharded_ledger.get_session(shard_id) as db:
        user = db.get(Account, payment.user_id)
        merchant = db.get(Account, payment.merchant_id)
        
        if not user or not merchant:
            raise HTTPException(400, "account not found")
        if user.balance < payment.amount:
            # Send failure event
            pe = PaymentEvent(type="PaymentFailed", **payment.model_dump(), reason="insufficient_funds")
            producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
            producer.flush()
            return {"status": "failed", "reason": "insufficient_funds"}
        
        # Execute transaction
        user.balance -= payment.amount
        merchant.balance += payment.amount
        db.add(LedgerEntry(payment_id=payment.payment_id, account_id=user.id, amount=payment.amount, direction="debit"))
        db.add(LedgerEntry(payment_id=payment.payment_id, account_id=merchant.id, amount=payment.amount, direction="credit"))
        db.commit()
        
        # Send success event
        pe = PaymentEvent(type="PaymentCommitted", **payment.model_dump())
        producer.produce(TOPIC_PAYMENT_EVENTS, value=pe.model_dump_json().encode("utf-8"))
        producer.flush()
        
    return {"status": "committed"}

async def commit_cross_shard(payment: InitiatePayment, user_shard: int, merchant_shard: int):
    """Handle cross-shard transaction using 2PC pattern"""
    # This would require implementing 2-phase commit for ACID guarantees
    # For now, delegate to shard_manager_service which already handles this
    raise HTTPException(501, "Cross-shard transactions should use shard_manager_service")
#!/usr/bin/env python3
"""
Fraud Action Service
Listens to fraud decisions and takes appropriate actions:
- Auto-reverse suspicious transactions
- Freeze high-risk accounts
- Send alerts to admins
- Manage manual review queue
"""

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from cassandra.cluster import Cluster, NoHostAvailable
from common.kafka import get_consumer, producer, TOPIC_FRAUD_EVENTS, TOPIC_PAYMENT_EVENTS
from common.redis_client import redis_client
from common.security import verify_token, mint_internal_jwt
from common.settings import settings
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fraud Action Service", version="1.0.0")

# Initialize Cassandra
def connect_to_cassandra(max_retries=30, retry_delay=2):
    """Connect to Cassandra with retry logic"""
    for attempt in range(max_retries):
        try:
            cluster = Cluster([settings.cassandra_host])
            session = cluster.connect()
            session.set_keyspace(settings.cassandra_keyspace)
            logger.info(f"✅ Connected to Cassandra on attempt {attempt + 1}")
            return cluster, session
        except (NoHostAvailable, Exception) as e:
            logger.error(f"❌ Cassandra connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise e

cluster, session = connect_to_cassandra()

# Create fraud action tables
def setup_fraud_tables():
    """Create necessary tables for fraud action management"""
    try:
        # Table for tracking fraud actions taken
        session.execute("""
            CREATE TABLE IF NOT EXISTS fraud_actions (
                payment_id UUID PRIMARY KEY,
                action_type TEXT,
                reason TEXT,
                fraud_score FLOAT,
                original_decision TEXT,
                action_timestamp TIMESTAMP,
                user_id TEXT,
                amount BIGINT,
                status TEXT,
                reversed_payment_id UUID,
                admin_notes TEXT
            )
        """)
        
        # Table for account status tracking
        session.execute("""
            CREATE TABLE IF NOT EXISTS account_status (
                user_id TEXT PRIMARY KEY,
                status TEXT,
                reason TEXT,
                frozen_at TIMESTAMP,
                frozen_by TEXT,
                last_updated TIMESTAMP
            )
        """)
        
        # Table for manual review queue
        session.execute("""
            CREATE TABLE IF NOT EXISTS review_queue (
                payment_id UUID PRIMARY KEY,
                user_id TEXT,
                amount BIGINT,
                fraud_score FLOAT,
                reason TEXT,
                created_at TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by TEXT,
                review_decision TEXT,
                review_notes TEXT
            )
        """)
        
        # Table for fraud alerts
        session.execute("""
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                alert_id UUID PRIMARY KEY,
                alert_type TEXT,
                payment_id UUID,
                user_id TEXT,
                message TEXT,
                severity TEXT,
                created_at TIMESTAMP,
                acknowledged_at TIMESTAMP,
                acknowledged_by TEXT
            )
        """)
        
        logger.info("✅ Fraud action tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to create fraud tables: {e}")

setup_fraud_tables()

class FraudActionManager:
    """Manages fraud actions and responses"""
    
    def __init__(self):
        self.shard_manager_url = "http://shard_manager_service:8000"
        self.internal_token = None
        
    def get_internal_token(self) -> str:
        """Get internal service token for API calls"""
        if not self.internal_token:
            self.internal_token = mint_internal_jwt("fraud_action_service", expires_in=3600)
        return self.internal_token
    
    async def reverse_payment(self, payment_id: str, original_amount: int, from_user: str, to_user: str, reason: str) -> Dict:
        """Reverse a fraudulent payment by creating a counter-transaction"""
        try:
            # Generate reverse payment ID
            reverse_payment_id = str(uuid.uuid4())
            
            # Create reverse transfer (from to_user back to from_user)
            reverse_url = f"{self.shard_manager_url}/transfer/{to_user}/{from_user}/{original_amount/100}"
            headers = {"Authorization": f"Bearer {self.get_internal_token()}"}
            
            response = requests.post(reverse_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                reverse_result = response.json()
                
                # Record the fraud action
                session.execute("""
                    INSERT INTO fraud_actions (
                        payment_id, action_type, reason, action_timestamp, 
                        user_id, amount, status, reversed_payment_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.UUID(payment_id), "REVERSE", reason, datetime.now(),
                    from_user, original_amount, "COMPLETED", uuid.UUID(reverse_payment_id)
                ))
                
                # Create alert
                await self.create_alert(
                    "PAYMENT_REVERSED", payment_id, from_user,
                    f"Payment {payment_id} reversed due to: {reason}",
                    "HIGH"
                )
                
                logger.info(f"✅ Successfully reversed payment {payment_id} with reverse payment {reverse_payment_id}")
                return {
                    "success": True,
                    "reverse_payment_id": reverse_payment_id,
                    "original_payment_id": payment_id,
                    "action": "REVERSED"
                }
            else:
                logger.error(f"❌ Failed to reverse payment {payment_id}: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error reversing payment {payment_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def freeze_account(self, user_id: str, reason: str, payment_id: str = None) -> Dict:
        """Freeze a user account"""
        try:
            # Update account status
            session.execute("""
                INSERT INTO account_status (
                    user_id, status, reason, frozen_at, frozen_by, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, "FROZEN", reason, datetime.now(), "fraud_action_service", datetime.now()))
            
            # Cache the frozen status in Redis for fast lookups
            redis_client.redis.setex(f"account_status:{user_id}", 3600, "FROZEN")
            
            # Create alert
            await self.create_alert(
                "ACCOUNT_FROZEN", payment_id, user_id,
                f"Account {user_id} frozen due to: {reason}",
                "CRITICAL"
            )
            
            logger.info(f"✅ Successfully froze account {user_id}")
            return {"success": True, "user_id": user_id, "action": "FROZEN"}
            
        except Exception as e:
            logger.error(f"❌ Error freezing account {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_to_review_queue(self, payment_id: str, user_id: str, amount: int, fraud_score: float, reason: str) -> Dict:
        """Add a transaction to manual review queue"""
        try:
            session.execute("""
                INSERT INTO review_queue (
                    payment_id, user_id, amount, fraud_score, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (uuid.UUID(payment_id), user_id, amount, fraud_score, reason, datetime.now()))
            
            # Create alert for review queue
            await self.create_alert(
                "REVIEW_REQUIRED", payment_id, user_id,
                f"Payment {payment_id} requires manual review (score: {fraud_score})",
                "MEDIUM"
            )
            
            logger.info(f"✅ Added payment {payment_id} to review queue")
            return {"success": True, "payment_id": payment_id, "action": "QUEUED_FOR_REVIEW"}
            
        except Exception as e:
            logger.error(f"❌ Error adding to review queue: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_alert(self, alert_type: str, payment_id: str, user_id: str, message: str, severity: str) -> Dict:
        """Create a fraud alert"""
        try:
            alert_id = uuid.uuid4()
            session.execute("""
                INSERT INTO fraud_alerts (
                    alert_id, alert_type, payment_id, user_id, message, severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (alert_id, alert_type, uuid.UUID(payment_id) if payment_id else None, user_id, message, severity, datetime.now()))
            
            # Also cache in Redis for real-time alerts
            alert_data = {
                "alert_id": str(alert_id),
                "type": alert_type,
                "payment_id": payment_id,
                "user_id": user_id,
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            }
            redis_client.redis.lpush("fraud_alerts", json.dumps(alert_data))
            redis_client.redis.ltrim("fraud_alerts", 0, 999)  # Keep only latest 1000 alerts
            
            logger.info(f"✅ Created {severity} alert: {message}")
            return {"success": True, "alert_id": str(alert_id)}
            
        except Exception as e:
            logger.error(f"❌ Error creating alert: {e}")
            return {"success": False, "error": str(e)}

fraud_action_manager = FraudActionManager()

def consume_fraud_decisions():
    """Consumer for fraud decisions from fraud service"""
    logger.info("🔍 Starting Kafka consumer for fraud decisions...")
    consumer = get_consumer("fraud-action-service", [TOPIC_FRAUD_EVENTS])
    
    while True:
        try:
            msg = consumer.poll(1.0)
            if not msg or msg.error():
                continue
                
            logger.info(f"🔍 Received fraud decision: {msg.value()}")
            fraud_decision = json.loads(msg.value())
            
            payment_id = fraud_decision.get("payment_id")
            decision = fraud_decision.get("decision")
            score = fraud_decision.get("score", 0.0)
            
            # Get original payment details from features table
            payment_details = session.execute(
                "SELECT user_id, amount FROM features WHERE payment_id = ? LIMIT 1",
                (uuid.UUID(payment_id),)
            ).one()
            
            if not payment_details:
                logger.warning(f"⚠️ No payment details found for {payment_id}")
                consumer.commit()
                continue
            
            user_id = payment_details.user_id
            amount = payment_details.amount
            
            # Take action based on fraud decision (synchronous for Kafka consumer)
            if decision == "block" and score >= 0.8:
                # High-risk: Record actions for async processing
                logger.info(f"🚨 HIGH RISK: Scheduling reversal for payment {payment_id}")
                
                # Store action in database for async processing
                session.execute("""
                    INSERT INTO fraud_actions (
                        payment_id, action_type, reason, action_timestamp, 
                        user_id, amount, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.UUID(payment_id), "REVERSE_PENDING", f"High fraud score: {score}", 
                    datetime.now(), user_id, amount, "PENDING"
                ))
                
                # Create immediate alert
                alert_id = uuid.uuid4()
                session.execute("""
                    INSERT INTO fraud_alerts (
                        alert_id, alert_type, payment_id, user_id, message, severity, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (alert_id, "HIGH_RISK_DETECTED", uuid.UUID(payment_id), user_id, 
                      f"High-risk payment {payment_id} detected (score: {score})", "CRITICAL", datetime.now()))
                
                logger.info(f"✅ Scheduled high-risk actions for {payment_id}")
                
            elif decision == "review" or (decision == "block" and score < 0.8):
                # Medium-risk: Add to review queue
                logger.info(f"⚠️ MEDIUM RISK: Adding payment {payment_id} to review queue")
                
                session.execute("""
                    INSERT INTO review_queue (
                        payment_id, user_id, amount, fraud_score, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (uuid.UUID(payment_id), user_id, amount, score, f"Fraud score: {score}", datetime.now()))
                
                # Create review alert
                alert_id = uuid.uuid4()
                session.execute("""
                    INSERT INTO fraud_alerts (
                        alert_id, alert_type, payment_id, user_id, message, severity, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (alert_id, "REVIEW_REQUIRED", uuid.UUID(payment_id), user_id,
                      f"Payment {payment_id} requires review (score: {score})", "MEDIUM", datetime.now()))
                
                logger.info(f"✅ Added {payment_id} to review queue")
                
            elif decision == "allow":
                # Low-risk: Just log for monitoring
                logger.info(f"✅ LOW RISK: Payment {payment_id} allowed (score: {score})")
                
                # Create monitoring alert
                alert_id = uuid.uuid4()
                session.execute("""
                    INSERT INTO fraud_alerts (
                        alert_id, alert_type, payment_id, user_id, message, severity, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (alert_id, "PAYMENT_ALLOWED", uuid.UUID(payment_id), user_id,
                      f"Payment processed normally (score: {score})", "LOW", datetime.now()))
            
            consumer.commit()
            
        except Exception as e:
            logger.error(f"❌ Error processing fraud decision: {e}")
            consumer.commit()  # Skip problematic message

# Start fraud decision consumer
logger.info("🚀 Starting fraud decision consumer thread...")
threading.Thread(target=consume_fraud_decisions, daemon=True).start()

# Authentication dependency
async def get_current_user(authorization: str = Header(..., description="Bearer token")):
    """Extract and validate JWT token from Authorization header"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header format")
    
    token = authorization.split(" ", 1)[1]
    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")

@app.get("/health")
async def health():
    """Health check"""
    return {"ok": True, "service": "fraud_action_service"}

@app.get("/alerts")
async def get_alerts(limit: int = 50, user_data: dict = Depends(get_current_user)):
    """Get recent fraud alerts"""
    try:
        # Get alerts from Redis for real-time data
        alerts = redis_client.redis.lrange("fraud_alerts", 0, limit - 1)
        alert_list = [json.loads(alert) for alert in alerts]
        
        return {
            "alerts": alert_list,
            "total": len(alert_list),
            "source": "redis_cache"
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return {"alerts": [], "error": str(e)}

@app.get("/review-queue")
async def get_review_queue(user_data: dict = Depends(get_current_user)):
    """Get manual review queue"""
    try:
        rows = session.execute("""
            SELECT payment_id, user_id, amount, fraud_score, reason, created_at, review_decision
            FROM review_queue 
            WHERE reviewed_at IS NULL 
            ORDER BY created_at DESC 
            LIMIT 100
        """)
        
        queue_items = []
        for row in rows:
            queue_items.append({
                "payment_id": str(row.payment_id),
                "user_id": row.user_id,
                "amount": row.amount / 100,  # Convert to dollars
                "fraud_score": row.fraud_score,
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "status": "PENDING"
            })
        
        return {
            "queue": queue_items,
            "total": len(queue_items)
        }
    except Exception as e:
        logger.error(f"Error getting review queue: {e}")
        return {"queue": [], "error": str(e)}

@app.post("/review/{payment_id}/approve")
async def approve_payment(payment_id: str, user_data: dict = Depends(get_current_user)):
    """Approve a payment in review queue"""
    try:
        reviewer = user_data.get("sub", "unknown")
        
        session.execute("""
            UPDATE review_queue 
            SET reviewed_at = ?, reviewed_by = ?, review_decision = ?, review_notes = ?
            WHERE payment_id = ?
        """, (datetime.now(), reviewer, "APPROVED", "Manually approved by admin", uuid.UUID(payment_id)))
        
        # Create approval alert
        await fraud_action_manager.create_alert(
            "PAYMENT_APPROVED", payment_id, None,
            f"Payment {payment_id} manually approved by {reviewer}",
            "LOW"
        )
        
        return {"success": True, "payment_id": payment_id, "action": "APPROVED"}
        
    except Exception as e:
        logger.error(f"Error approving payment: {e}")
        raise HTTPException(500, f"Failed to approve payment: {str(e)}")

@app.post("/review/{payment_id}/reject")
async def reject_payment(payment_id: str, reason: str = "Manually rejected", user_data: dict = Depends(get_current_user)):
    """Reject a payment in review queue and reverse it"""
    try:
        reviewer = user_data.get("sub", "unknown")
        
        # Get payment details
        payment_details = session.execute(
            "SELECT user_id, amount FROM features WHERE payment_id = ? LIMIT 1",
            (uuid.UUID(payment_id),)
        ).one()
        
        if payment_details:
            # Reverse the payment
            reverse_result = await fraud_action_manager.reverse_payment(
                payment_id, payment_details.amount, payment_details.user_id, "jekopaul2", reason
            )
            
        # Update review queue
        session.execute("""
            UPDATE review_queue 
            SET reviewed_at = ?, reviewed_by = ?, review_decision = ?, review_notes = ?
            WHERE payment_id = ?
        """, (datetime.now(), reviewer, "REJECTED", reason, uuid.UUID(payment_id)))
        
        return {"success": True, "payment_id": payment_id, "action": "REJECTED"}
        
    except Exception as e:
        logger.error(f"Error rejecting payment: {e}")
        raise HTTPException(500, f"Failed to reject payment: {str(e)}")

@app.post("/account/{user_id}/unfreeze")
async def unfreeze_account(user_id: str, reason: str = "Manually unfrozen", user_data: dict = Depends(get_current_user)):
    """Unfreeze a user account"""
    try:
        admin = user_data.get("sub", "unknown")
        
        # Update account status
        session.execute("""
            INSERT INTO account_status (
                user_id, status, reason, frozen_by, last_updated
            ) VALUES (?, ?, ?, ?, ?)
        """, (user_id, "ACTIVE", reason, admin, datetime.now()))
        
        # Remove from Redis cache
        redis_client.redis.delete(f"account_status:{user_id}")
        
        # Create alert
        await fraud_action_manager.create_alert(
            "ACCOUNT_UNFROZEN", None, user_id,
            f"Account {user_id} unfrozen by {admin}: {reason}",
            "LOW"
        )
        
        return {"success": True, "user_id": user_id, "action": "UNFROZEN"}
        
    except Exception as e:
        logger.error(f"Error unfreezing account: {e}")
        raise HTTPException(500, f"Failed to unfreeze account: {str(e)}")

@app.get("/account/{user_id}/status")
async def get_account_status(user_id: str, user_data: dict = Depends(get_current_user)):
    """Get account status"""
    try:
        # Check Redis cache first
        cached_status = redis_client.redis.get(f"account_status:{user_id}")
        if cached_status:
            return {"user_id": user_id, "status": cached_status.decode(), "source": "cache"}
        
        # Query database
        result = session.execute(
            "SELECT status, reason, frozen_at, frozen_by FROM account_status WHERE user_id = ? LIMIT 1",
            (user_id,)
        ).one()
        
        if result:
            return {
                "user_id": user_id,
                "status": result.status,
                "reason": result.reason,
                "frozen_at": result.frozen_at.isoformat() if result.frozen_at else None,
                "frozen_by": result.frozen_by,
                "source": "database"
            }
        else:
            return {"user_id": user_id, "status": "ACTIVE", "source": "default"}
            
    except Exception as e:
        logger.error(f"Error getting account status: {e}")
        return {"user_id": user_id, "status": "UNKNOWN", "error": str(e)}

@app.get("/stats")
async def get_fraud_stats(user_data: dict = Depends(get_current_user)):
    """Get fraud action statistics"""
    try:
        # Get action counts
        action_stats = session.execute("""
            SELECT action_type, COUNT(*) as count 
            FROM fraud_actions 
            WHERE action_timestamp > ? 
            GROUP BY action_type
        """, (datetime.now() - timedelta(days=7),))
        
        actions = {row.action_type: row.count for row in action_stats}
        
        # Get review queue size
        queue_size = session.execute(
            "SELECT COUNT(*) FROM review_queue WHERE reviewed_at IS NULL"
        ).one()[0]
        
        # Get frozen accounts
        frozen_accounts = session.execute(
            "SELECT COUNT(*) FROM account_status WHERE status = 'FROZEN'"
        ).one()[0]
        
        return {
            "fraud_actions_last_7_days": actions,
            "pending_reviews": queue_size,
            "frozen_accounts": frozen_accounts,
            "total_alerts": redis_client.redis.llen("fraud_alerts")
        }
        
    except Exception as e:
        logger.error(f"Error getting fraud stats: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
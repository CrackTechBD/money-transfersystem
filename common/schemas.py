from pydantic import BaseModel
from typing import Literal, Optional

class InitiatePayment(BaseModel):
    payment_id: str
    user_id: str
    amount: int
    currency: str = "INR"
    merchant_id: str
    idempotency_key: str

class PaymentEvent(BaseModel):
    type: Literal["PaymentInitiated", "PaymentCommitted", "PaymentFailed"]
    payment_id: str
    user_id: str
    amount: int
    currency: str
    merchant_id: str
    reason: Optional[str] = None

class FraudDecision(BaseModel):
    payment_id: str
    decision: Literal["allow", "review", "block"]
    score: float = 0.0

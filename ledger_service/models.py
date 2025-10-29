from sqlalchemy import Column, Integer, String, BigInteger, DateTime, func, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"
    id = Column(String(64), primary_key=True)
    balance = Column(BigInteger, nullable=False, default=0)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    payment_id = Column(String(64), index=True)
    account_id = Column(String(64), ForeignKey("accounts.id"))
    amount = Column(BigInteger, nullable=False)
    direction = Column(String(8))  # 'debit' or 'credit'
    created_at = Column(DateTime, server_default=func.now())

class Outbox(Base):
    __tablename__ = "outbox"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic = Column(String(64), nullable=False)
    payload = Column(String(4000), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(16), default="new")  # new|sent|failed

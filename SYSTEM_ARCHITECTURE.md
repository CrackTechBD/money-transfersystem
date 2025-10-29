# Paytm-Style Sharded Payment System Architecture

## 🏗️ System Overview

This is a horizontally sharded payment system demonstrating modern microservices architecture with event-driven design patterns. The system processes payments across multiple database shards with real-time fraud detection and analytics.

---

## 📊 **Data Layer Components**

### 🗄️ **MySQL Shards (4 Instances)**
**Ports:** 3306, 3307, 3308, 3309  
**Purpose:** Primary data storage with horizontal sharding

**What it does:**
- Stores user accounts and balances across 4 shards
- Implements double-entry bookkeeping with `ledger_entries` table
- Provides ACID transactions for payment processing
- Distributes users across shards using consistent hashing

**Schema per shard:**
```sql
-- User account balances (stored in cents for precision)
accounts (id, user_id, balance, currency, created_at, updated_at)

-- Transaction audit trail  
transactions (id, transaction_id, from_user_id, to_user_id, amount, status)

-- Double-entry ledger for financial accuracy
ledger_entries (id, payment_id, account_id, amount, direction, created_at)

-- Event sourcing outbox pattern
outbox_events (id, event_id, event_type, aggregate_id, event_data)
```

**Sharding Strategy:**
- **Shard 0** (port 3306): Users with hash(user_id) % 4 == 0
- **Shard 1** (port 3307): Users with hash(user_id) % 4 == 1  
- **Shard 2** (port 3308): Users with hash(user_id) % 4 == 2
- **Shard 3** (port 3309): Users with hash(user_id) % 4 == 3

---

### 🏪 **Cassandra Cluster**
**Port:** 9042  
**Keyspace:** `paytm_style`  
**Purpose:** NoSQL storage for fraud detection and analytics

**What it does:**
- Stores real-time fraud detection features and scores
- Maintains denormalized analytics events for fast queries
- Provides high-availability storage for non-transactional data
- Supports time-series data for fraud pattern analysis

**Schema:**
```cql
-- Fraud detection features
features (payment_id PRIMARY KEY, user_id, amount, score)

-- Analytics events (denormalized for performance)
events (payment_id, type, body, PRIMARY KEY (payment_id, type))
```

**Use Cases:**
- ✅ Real-time fraud scoring storage
- ✅ Analytics event denormalization
- ✅ Machine learning feature storage
- ✅ Audit trail for fraud decisions

---

### 🔄 **Redis Cache**
**Port:** 6379  
**Purpose:** High-performance caching layer

**What it does:**
- Caches frequently accessed user data
- Stores session information for authentication
- Implements rate limiting for API endpoints
- Provides fast lookup for shard routing decisions

**Typical Usage:**
```redis
# User session cache
user:session:{token} -> {user_id, permissions, expiry}

# Shard routing cache  
shard:route:{user_id} -> {shard_id}

# Rate limiting
rate_limit:{user_id}:{endpoint} -> {count, window_start}

# Fraud detection cache
fraud:score:{user_id} -> {last_score, timestamp}
```

---

## 🎯 **Application Services**

### 🛡️ **Shard Manager Service**
**Port:** 8006  
**Purpose:** Core sharding logic and cross-shard transaction orchestration

**What it does:**
- **User Distribution**: Routes users to appropriate shards using consistent hashing
- **Cross-Shard Transactions**: Handles payments between users on different shards
- **Balance Management**: Maintains account balances with double-entry bookkeeping
- **Shard Health Monitoring**: Tracks shard availability and performance
- **Event Publishing**: Publishes payment events to Kafka for downstream processing

**Key Endpoints:**
```http
POST /transfer/{from_user}/{to_user}/{amount}  # Cross-shard money transfer
POST /create_account/{user_id}/{balance}       # Create new user account
GET  /analytics                                # Real-time shard analytics
GET  /health                                   # Service and shard health
```

**Database Connections:**
- Connects to all 4 MySQL shards simultaneously
- Manages connection pools for optimal performance
- Handles transaction rollbacks across multiple shards

---

### 🔒 **Authentication Service**
**Port:** 8001  
**Purpose:** User authentication and authorization

**What it does:**
- **JWT Token Generation**: Creates secure authentication tokens
- **User Login/Registration**: Manages user credentials
- **Permission Management**: Controls API access levels
- **Session Management**: Tracks active user sessions in Redis

**Security Features:**
- ✅ Password hashing with salt
- ✅ JWT token expiration
- ✅ Rate limiting on login attempts
- ✅ Session invalidation

---

### 🚨 **Fraud Service**
**Port:** 8003  
**Purpose:** Real-time fraud detection and risk assessment

**What it does:**
- **Real-time Scoring**: Analyzes transactions for fraud patterns
- **Risk Assessment**: Calculates fraud probability scores (0.0 - 1.0)
- **Decision Engine**: Automatically approves/reviews/blocks transactions
- **Feature Storage**: Stores fraud indicators in Cassandra
- **Event Processing**: Consumes payment events from Kafka

**Fraud Detection Logic:**
```python
def risk_score(transaction):
    amount = transaction.amount
    # Simple demo: higher amounts = higher risk
    return min(1.0, amount / 10000.0)

# Decision thresholds
if score < 0.7: decision = "allow"
else: decision = "review"
```

**Data Flow:**
1. Listens to Kafka `payment_events` topic
2. Calculates fraud score for each transaction
3. Stores features in Cassandra `features` table
4. Publishes decision to Kafka `fraud_events` topic

---

### 📊 **Analytics Service**
**Port:** 8005  
**Purpose:** Real-time analytics and business intelligence

**What it does:**
- **Real-time Dashboards**: Provides live system metrics
- **Shard Analytics**: Monitors individual shard performance
- **Transaction Analytics**: Tracks payment patterns and volumes
- **System Health**: Aggregates health data across all services
- **HTML Dashboards**: Web-based analytics interfaces

**Key Metrics:**
- Total accounts and balances across all shards
- Transaction success rates and volumes
- Cross-shard vs same-shard transaction ratios
- Daily/hourly transaction patterns
- Fraud detection statistics

**Data Sources:**
- Direct MySQL shard queries for real-time data
- Cassandra events for analytics history
- Service health endpoints for system status

---

### 📧 **Notification Service**
**Port:** 8004  
**Purpose:** Event-driven notifications and alerts

**What it does:**
- **Transaction Notifications**: Sends payment confirmations
- **Fraud Alerts**: Notifies on suspicious activities
- **System Alerts**: Monitors service health and failures
- **Multi-channel Support**: Email, SMS, push notifications

---

## 🔄 **Event Streaming & Messaging**

### 📨 **Apache Kafka**
**Port:** 9092  
**Purpose:** Event streaming backbone for microservices communication

**What it does:**
- **Event Sourcing**: Captures all payment events for audit trail
- **Microservice Decoupling**: Enables loose coupling between services
- **Real-time Processing**: Streams events for immediate processing
- **Fault Tolerance**: Provides message durability and replay capability

**Topic Structure:**
```
payment_events:
- PaymentInitiated
- PaymentCompleted  
- PaymentFailed
- PaymentCancelled

fraud_events:
- FraudScoreCalculated
- TransactionBlocked
- ManualReviewRequired

notification_events:
- EmailSent
- SMSSent
- PushNotificationSent

analytics_events:
- UserCreated
- BalanceUpdated
- SystemHealthCheck
```

**Event Flow:**
```
Shard Manager → payment_events → Fraud Service
                               → Analytics Service
                               → Notification Service

Fraud Service → fraud_events → Notification Service
                             → Analytics Service

Services → analytics_events → Analytics Service
```

---

### 🔧 **Apache Zookeeper**
**Port:** 2181  
**Purpose:** Coordination service for Kafka cluster

**What it does:**
- **Kafka Cluster Management**: Manages Kafka brokers and topics
- **Leader Election**: Coordinates partition leadership
- **Configuration Management**: Stores Kafka cluster metadata
- **Service Discovery**: Helps services find Kafka brokers

---

## 📈 **Data Flow Architecture**

### 💰 **Payment Processing Flow**
```
1. User initiates payment → Shard Manager Service
2. Shard Manager validates accounts across shards
3. Cross-shard transaction executed with rollback capability
4. Payment event published to Kafka
5. Fraud Service consumes event → calculates risk score
6. Fraud decision stored in Cassandra
7. Analytics Service updates real-time metrics
8. Notification Service sends confirmation
```

### 📊 **Analytics Data Pipeline**
```
MySQL Shards → Real-time queries → Analytics Service → Dashboard
Cassandra → Historical events → Analytics Service → Reports
Kafka → Event stream → Analytics Service → Metrics
```

### 🛡️ **Fraud Detection Pipeline**
```
Payment Event → Kafka → Fraud Service → Feature Extraction
                                     → Risk Scoring
                                     → Decision Engine
                                     → Cassandra Storage
                                     → Response to Shard Manager
```

---

## 🔧 **Technology Stack Summary**

| Component | Technology | Purpose | Port |
|-----------|------------|---------|------|
| **Sharding** | MySQL 8.0 | Primary data storage | 3306-3309 |
| **Fraud Detection** | Cassandra 4.1 | NoSQL feature storage | 9042 |
| **Caching** | Redis 7 | High-speed cache | 6379 |
| **Messaging** | Kafka 7.4 | Event streaming | 9092 |
| **Coordination** | Zookeeper 7.4 | Kafka management | 2181 |
| **API Gateway** | FastAPI | REST APIs | 8001-8006 |
| **Container** | Docker Compose | Orchestration | - |

---

## 🎯 **Key System Benefits**

### ⚡ **Performance**
- **Horizontal Scaling**: Add more shards as user base grows
- **Load Distribution**: Users distributed evenly across shards
- **Cache Layer**: Redis reduces database load
- **Async Processing**: Kafka enables non-blocking operations

### 🛡️ **Reliability**
- **ACID Transactions**: Consistent financial data across shards
- **Event Sourcing**: Complete audit trail of all operations
- **Fault Tolerance**: Services can restart without data loss
- **Health Monitoring**: Real-time system health tracking

### 🔒 **Security**
- **Fraud Detection**: Real-time transaction risk assessment
- **Authentication**: JWT-based secure API access
- **Audit Trail**: Complete transaction history
- **Data Isolation**: Sharded data provides natural isolation

### 📈 **Observability**
- **Real-time Analytics**: Live system metrics and dashboards
- **Business Intelligence**: Transaction pattern analysis
- **System Monitoring**: Service health and performance tracking
- **Event Tracing**: End-to-end transaction visibility

---

## 🚀 **Deployment Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                   │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  │  Auth   │ │ Fraud   │ │Analytics│ │Notification│ │Shard   ││
│  │ :8001   │ │ :8003   │ │ :8005   │ │  :8004   │ │Manager ││
│  │         │ │         │ │         │ │          │ │ :8006  ││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
├─────────────────────────────────────────────────────────────┤
│  Event Streaming Layer                                      │
│  ┌─────────────┐              ┌─────────────┐               │
│  │   Kafka     │              │ Zookeeper   │               │
│  │   :9092     │              │   :2181     │               │
│  └─────────────┘              └─────────────┘               │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  │MySQL    │ │MySQL    │ │MySQL    │ │MySQL    │ │Cassandra││
│  │Shard 0  │ │Shard 1  │ │Shard 2  │ │Shard 3  │ │ :9042   ││
│  │ :3306   │ │ :3307   │ │ :3308   │ │ :3309   │ │         ││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
│                                      ┌─────────┐             │
│                                      │  Redis  │             │
│                                      │ :6379   │             │
│                                      └─────────┘             │
└─────────────────────────────────────────────────────────────┘
```

This architecture demonstrates enterprise-grade patterns including sharding, event sourcing, CQRS, and microservices - all essential for building scalable financial systems! 🏦
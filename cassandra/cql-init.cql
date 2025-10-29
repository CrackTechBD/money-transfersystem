CREATE KEYSPACE IF NOT EXISTS paytm_style WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};
USE paytm_style;

-- Fraud features store (very small demo)
CREATE TABLE IF NOT EXISTS features (
  payment_id text PRIMARY KEY,
  user_id text,
  amount bigint,
  score double
);

-- Analytics denormalized events
CREATE TABLE IF NOT EXISTS events (
  payment_id text,
  type text,
  body text,
  PRIMARY KEY (payment_id, type)
);

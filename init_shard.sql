-- MySQL Shard Initialization Script
-- Creates the necessary tables for the sharded payment system

CREATE DATABASE IF NOT EXISTS paytm_shard;
USE paytm_shard;

-- Accounts table for storing user balances
CREATE TABLE IF NOT EXISTS accounts (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0,  -- Store as cents for precision
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_balance (balance),
    INDEX idx_created_at (created_at)
);

-- Transactions table for audit trail
CREATE TABLE IF NOT EXISTS transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(255) UNIQUE NOT NULL,
    from_user_id VARCHAR(255),
    to_user_id VARCHAR(255),
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    transaction_type ENUM('TRANSFER', 'DEPOSIT', 'WITHDRAWAL') NOT NULL,
    status ENUM('PENDING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    metadata JSON,
    INDEX idx_from_user (from_user_id),
    INDEX idx_to_user (to_user_id),
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
);

-- Outbox pattern for event publishing
CREATE TABLE IF NOT EXISTS outbox_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    event_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL,
    INDEX idx_event_id (event_id),
    INDEX idx_processed_at (processed_at),
    INDEX idx_created_at (created_at)
);

-- Ledger entries table for double-entry bookkeeping
CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGINT NOT NULL AUTO_INCREMENT,
    payment_id VARCHAR(64),
    account_id VARCHAR(64),
    amount BIGINT NOT NULL,
    direction VARCHAR(8),
    created_at DATETIME DEFAULT now(),
    PRIMARY KEY (id),
    FOREIGN KEY(account_id) REFERENCES accounts (id),
    INDEX idx_payment_id (payment_id),
    INDEX idx_account_id (account_id),
    INDEX idx_created_at (created_at)
);

-- Insert some demo data for testing
INSERT IGNORE INTO accounts (id, user_id, balance, currency) VALUES 
('demo_user_000', 'demo_user_000', 10000, 'USD'),  -- $100.00 in cents
('demo_user_001', 'demo_user_001', 20000, 'USD'),  -- $200.00 in cents
('demo_user_002', 'demo_user_002', 30000, 'USD');  -- $300.00 in cents

-- Grant permissions
GRANT ALL PRIVILEGES ON paytm_shard.* TO 'root'@'%';
FLUSH PRIVILEGES;
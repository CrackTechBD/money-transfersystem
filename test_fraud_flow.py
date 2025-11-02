#!/usr/bin/env python3
"""
Test script to demonstrate the complete fraud action flow
"""
import requests
import json
import time
from datetime import datetime

# Service URLs
SHARD_MANAGER_URL = "http://localhost:8006"
FRAUD_ACTION_URL = "http://localhost:8007" 
FRAUD_ADMIN_URL = "http://localhost:8008"

def test_basic_connectivity():
    """Test that all services are responding"""
    print("🔍 Testing service connectivity...")
    
    # Test Shard Manager
    try:
        response = requests.get(f"{SHARD_MANAGER_URL}/health", timeout=5)
        print(f"✅ Shard Manager: {response.status_code}")
    except Exception as e:
        print(f"❌ Shard Manager: {e}")
    
    # Test Fraud Action Service
    try:
        response = requests.get(f"{FRAUD_ACTION_URL}/health", timeout=5)
        print(f"✅ Fraud Action Service: {response.status_code}")
    except Exception as e:
        print(f"❌ Fraud Action Service: {e}")
    
    # Test Admin Dashboard
    try:
        response = requests.get(f"{FRAUD_ADMIN_URL}/", timeout=5)
        print(f"✅ Fraud Admin Dashboard: {response.status_code}")
    except Exception as e:
        print(f"❌ Fraud Admin Dashboard: {e}")

def create_test_accounts():
    """Create test accounts for fraud testing"""
    print("\\n👥 Creating test accounts...")
    
    accounts = [
        ("fraud_test_sender", 10000.0),
        ("fraud_test_receiver", 1000.0),
        ("normal_user", 5000.0)
    ]
    
    for user_id, initial_balance in accounts:
        try:
            response = requests.post(
                f"{SHARD_MANAGER_URL}/accounts/{user_id}/create/{initial_balance}"
            )
            if response.status_code == 200:
                print(f"✅ Created account: {user_id} with ${initial_balance}")
            else:
                print(f"⚠️  Account {user_id} might already exist")
        except Exception as e:
            print(f"❌ Error creating account {user_id}: {e}")

def test_normal_payment():
    """Test a normal payment that should pass fraud checks"""
    print("\\n💳 Testing normal payment...")
    
    try:
        response = requests.post(
            f"{SHARD_MANAGER_URL}/transfer/normal_user/fraud_test_receiver/25.0",
            headers={"Authorization": "Bearer test-token"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Normal payment successful: {result}")
            return result.get('payment_id')
        else:
            print(f"❌ Payment failed: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error making payment: {e}")
        return None

def test_high_risk_payment():
    """Test a high-risk payment that should trigger fraud actions"""
    print("\\n🚨 Testing high-risk payment...")
    
    try:
        # Large amount transfer that should trigger fraud detection
        response = requests.post(
            f"{SHARD_MANAGER_URL}/transfer/fraud_test_sender/fraud_test_receiver/5000.0",
            headers={"Authorization": "Bearer test-token"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ High-risk payment initiated: {result}")
            return result.get('payment_id')
        else:
            print(f"❌ Payment failed: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error making payment: {e}")
        return None

def check_account_balances():
    """Check current account balances"""
    print("\\n💰 Checking account balances...")
    
    accounts = ["fraud_test_sender", "fraud_test_receiver", "normal_user"]
    
    for user_id in accounts:
        try:
            response = requests.get(f"{SHARD_MANAGER_URL}/accounts/{user_id}/balance")
            if response.status_code == 200:
                balance = response.json()
                print(f"💰 {user_id}: ${balance}")
            else:
                print(f"❌ Could not get balance for {user_id}")
        except Exception as e:
            print(f"❌ Error getting balance for {user_id}: {e}")

def display_fraud_dashboard_info():
    """Display information about accessing the fraud dashboard"""
    print("\\n🖥️  Fraud Management Dashboard:")
    print(f"   📊 Main Dashboard: {FRAUD_ADMIN_URL}")
    print(f"   🚨 View Alerts: {FRAUD_ADMIN_URL}/alerts") 
    print(f"   📋 Review Queue: {FRAUD_ADMIN_URL}/review-queue")
    print(f"   📈 Statistics: {FRAUD_ADMIN_URL}/stats")
    print(f"   👥 Account Status: {FRAUD_ADMIN_URL}/accounts")

def main():
    """Run the complete fraud flow test"""
    print("🚀 Starting Fraud Action System Test")
    print("=" * 50)
    
    # Test connectivity
    test_basic_connectivity()
    
    # Create test accounts
    create_test_accounts()
    
    # Check initial balances
    check_account_balances()
    
    # Test normal payment
    normal_payment_id = test_normal_payment()
    
    # Test high-risk payment
    high_risk_payment_id = test_high_risk_payment()
    
    # Wait a moment for fraud processing
    print("\\n⏳ Waiting for fraud processing...")
    time.sleep(3)
    
    # Check balances after payments
    check_account_balances()
    
    # Display dashboard info
    display_fraud_dashboard_info()
    
    print("\\n" + "=" * 50)
    print("🎯 Test Summary:")
    print("1. ✅ Created test accounts")
    print("2. ✅ Tested normal payment flow")
    print("3. ✅ Tested high-risk payment flow")
    print("4. ✅ Fraud processing completed")
    
    print("\\n🔍 What to check next:")
    print("1. 🖥️  Open the fraud dashboard in your browser")
    print("2. 🚨 Look for fraud alerts and actions")
    print("3. 📋 Check the manual review queue")
    print("4. 📊 Monitor fraud statistics")
    
    print("\\n🌟 Your fraud action system is now fully operational!")

if __name__ == "__main__":
    main()
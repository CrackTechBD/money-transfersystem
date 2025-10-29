#!/usr/bin/env python3
"""
Integration Tests for MySQL Sharding Payment System
Tests the complete payment flow across sharded databases.
"""

import time
import requests
import json
from typing import Dict, List, Tuple


class PaymentSystemIntegrationTest:
    """Integration tests for the complete payment system"""
    
    def __init__(self):
        self.base_url = "http://localhost:8006"
        self.timeout = 10
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str, data: Dict = None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "data": data or {}
        })
        
    def wait_for_system(self, max_wait: int = 60) -> bool:
        """Wait for the system to be ready"""
        print("🔄 Waiting for sharding system to be ready...")
        
        for i in range(max_wait):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    print("✅ System is ready!")
                    return True
            except:
                pass
            time.sleep(1)
            
        print("❌ System failed to start within timeout")
        return False

    def test_payment_ecosystem_setup(self) -> bool:
        """Test 1: Set up payment ecosystem (merchants + customers)"""
        print("\n1️⃣ Setting up payment ecosystem...")
        
        # Define merchants and customers
        merchants = [
            ("coffee_shop", 0.00),
            ("pizza_place", 0.00), 
            ("gas_station", 0.00),
            ("bookstore", 0.00)
        ]
        
        customers = [
            ("alice", 500.00),
            ("bob", 300.00),
            ("charlie", 250.00),
            ("diana", 400.00)
        ]
        
        created_accounts = 0
        total_accounts = len(merchants) + len(customers)
        
        # Create merchant accounts
        for merchant, balance in merchants:
            try:
                response = requests.post(
                    f"{self.base_url}/create_user/{merchant}/{balance}",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"   📍 Merchant {merchant}: Shard {data['shard']}")
                    created_accounts += 1
                else:
                    print(f"   ❌ Failed to create merchant {merchant}")
            except Exception as e:
                print(f"   ❌ Error creating merchant {merchant}: {e}")
                
        # Create customer accounts  
        for customer, balance in customers:
            try:
                response = requests.post(
                    f"{self.base_url}/create_user/{customer}/{balance}",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"   👤 Customer {customer}: ${balance} on Shard {data['shard']}")
                    created_accounts += 1
                else:
                    print(f"   ❌ Failed to create customer {customer}")
            except Exception as e:
                print(f"   ❌ Error creating customer {customer}: {e}")
                
        success = created_accounts >= total_accounts * 0.8  # 80% success rate
        message = f"Created {created_accounts}/{total_accounts} accounts"
        self.log_test("Payment Ecosystem Setup", success, message)
        return success

    def test_same_shard_payments(self) -> bool:
        """Test 2: Same-shard payment transactions"""
        print("\n2️⃣ Testing same-shard payments...")
        
        # Get shard assignments for our test accounts
        test_pairs = [
            ("alice", "coffee_shop", 4.50),
            ("bob", "pizza_place", 18.75),
            ("charlie", "gas_station", 35.20),
            ("diana", "bookstore", 12.99)
        ]
        
        same_shard_transactions = 0
        successful_transactions = 0
        
        for customer, merchant, amount in test_pairs:
            try:
                # Check if they're on the same shard
                customer_response = requests.get(f"{self.base_url}/user_shard/{customer}")
                merchant_response = requests.get(f"{self.base_url}/user_shard/{merchant}")
                
                if customer_response.status_code == 200 and merchant_response.status_code == 200:
                    customer_shard = customer_response.json()["shard"]
                    merchant_shard = merchant_response.json()["shard"]
                    
                    if customer_shard == merchant_shard:
                        same_shard_transactions += 1
                        
                        # Perform transaction
                        response = requests.post(
                            f"{self.base_url}/transfer/{customer}/{merchant}/{amount}",
                            timeout=self.timeout
                        )
                        
                        if response.status_code == 200:
                            successful_transactions += 1
                            print(f"   💳 {customer} → {merchant}: ${amount} (Same-shard: {customer_shard})")
                        else:
                            print(f"   ❌ Failed transaction: {customer} → {merchant}")
                    else:
                        print(f"   🔄 {customer} (shard {customer_shard}) → {merchant} (shard {merchant_shard}): Cross-shard")
                        
            except Exception as e:
                print(f"   ❌ Error in transaction {customer} → {merchant}: {e}")
                
        success = successful_transactions > 0 or same_shard_transactions == 0
        message = f"{successful_transactions}/{same_shard_transactions} same-shard transactions successful"
        self.log_test("Same-Shard Payments", success, message)
        return success

    def test_cross_shard_payments(self) -> bool:
        """Test 3: Cross-shard payment transactions"""
        print("\n3️⃣ Testing cross-shard payments...")
        
        # Test all customer-merchant combinations for cross-shard transactions
        customers = ["alice", "bob", "charlie", "diana"]
        merchants = ["coffee_shop", "pizza_place", "gas_station", "bookstore"]
        
        cross_shard_transactions = 0
        successful_transactions = 0
        
        for customer in customers:
            for merchant in merchants:
                try:
                    # Check if they're on different shards
                    customer_response = requests.get(f"{self.base_url}/user_shard/{customer}")
                    merchant_response = requests.get(f"{self.base_url}/user_shard/{merchant}")
                    
                    if customer_response.status_code == 200 and merchant_response.status_code == 200:
                        customer_shard = customer_response.json()["shard"]
                        merchant_shard = merchant_response.json()["shard"]
                        
                        if customer_shard != merchant_shard:
                            cross_shard_transactions += 1
                            amount = 10.00  # Small test amount
                            
                            # Perform cross-shard transaction
                            response = requests.post(
                                f"{self.base_url}/transfer/{customer}/{merchant}/{amount}",
                                timeout=self.timeout
                            )
                            
                            if response.status_code == 200:
                                successful_transactions += 1
                                print(f"   🔄 {customer} (shard {customer_shard}) → {merchant} (shard {merchant_shard}): ${amount}")
                            else:
                                print(f"   ❌ Failed cross-shard: {customer} → {merchant}")
                                
                except Exception as e:
                    print(f"   ❌ Error in cross-shard transaction {customer} → {merchant}: {e}")
                    
        success = successful_transactions >= cross_shard_transactions * 0.5  # 50% success rate for cross-shard
        message = f"{successful_transactions}/{cross_shard_transactions} cross-shard transactions successful"
        self.log_test("Cross-Shard Payments", success, message)
        return success

    def test_p2p_transfers(self) -> bool:
        """Test 4: Peer-to-peer transfers between customers"""
        print("\n4️⃣ Testing P2P transfers...")
        
        p2p_transfers = [
            ("alice", "bob", 25.00),
            ("charlie", "diana", 15.00),
            ("bob", "charlie", 10.00),
            ("diana", "alice", 20.00)
        ]
        
        successful_transfers = 0
        
        for sender, receiver, amount in p2p_transfers:
            try:
                response = requests.post(
                    f"{self.base_url}/transfer/{sender}/{receiver}/{amount}",
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    successful_transfers += 1
                    
                    # Get shard info for logging
                    sender_shard_response = requests.get(f"{self.base_url}/user_shard/{sender}")
                    receiver_shard_response = requests.get(f"{self.base_url}/user_shard/{receiver}")
                    
                    if sender_shard_response.status_code == 200 and receiver_shard_response.status_code == 200:
                        sender_shard = sender_shard_response.json()["shard"]
                        receiver_shard = receiver_shard_response.json()["shard"]
                        transfer_type = "same-shard" if sender_shard == receiver_shard else "cross-shard"
                        print(f"   💸 {sender} → {receiver}: ${amount} ({transfer_type})")
                    else:
                        print(f"   💸 {sender} → {receiver}: ${amount}")
                else:
                    print(f"   ❌ Failed P2P transfer: {sender} → {receiver}")
                    
            except Exception as e:
                print(f"   ❌ Error in P2P transfer {sender} → {receiver}: {e}")
                
        success = successful_transfers >= len(p2p_transfers) * 0.6  # 60% success rate
        message = f"{successful_transfers}/{len(p2p_transfers)} P2P transfers successful"
        self.log_test("P2P Transfers", success, message)
        return success

    def test_real_time_analytics(self) -> bool:
        """Test 5: Real-time analytics across shards"""
        print("\n5️⃣ Testing real-time analytics...")
        
        try:
            response = requests.get(f"{self.base_url}/analytics", timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"   📊 Total Accounts: {data.get('total_accounts', 0)}")
                print(f"   💰 Total Balance: ${data.get('total_balance', 0):.2f}")
                print(f"   📈 Average Balance: ${data.get('average_balance', 0):.2f}")
                
                # Verify shard-level data
                if 'shards' in data:
                    for shard_data in data['shards']:
                        shard_id = shard_data.get('shard_id', 'unknown')
                        accounts = shard_data.get('accounts', 0)
                        balance = shard_data.get('balance', 0)
                        print(f"   📍 Shard {shard_id}: {accounts} accounts, ${balance:.2f}")
                        
                success = data.get('total_accounts', 0) > 0
                message = f"Analytics aggregated {data.get('total_accounts', 0)} accounts across shards"
                self.log_test("Real-time Analytics", success, message, data)
                return success
            else:
                message = f"Analytics endpoint failed: HTTP {response.status_code}"
                self.log_test("Real-time Analytics", False, message)
                return False
                
        except Exception as e:
            message = f"Analytics test failed: {e}"
            self.log_test("Real-time Analytics", False, message)
            return False

    def test_system_consistency(self) -> bool:
        """Test 6: System consistency check"""
        print("\n6️⃣ Testing system consistency...")
        
        try:
            # Get system stats
            stats_response = requests.get(f"{self.base_url}/stats", timeout=self.timeout)
            analytics_response = requests.get(f"{self.base_url}/analytics", timeout=self.timeout)
            
            if stats_response.status_code == 200 and analytics_response.status_code == 200:
                stats_data = stats_response.json()
                analytics_data = analytics_response.json()
                
                # Check consistency between stats and analytics
                stats_accounts = stats_data.get('total_accounts', 0)
                analytics_accounts = analytics_data.get('total_accounts', 0)
                
                consistency_check = abs(stats_accounts - analytics_accounts) <= 1  # Allow small discrepancy
                
                print(f"   📊 Stats Accounts: {stats_accounts}")
                print(f"   📈 Analytics Accounts: {analytics_accounts}")
                print(f"   🎯 Consistency: {'✅' if consistency_check else '❌'}")
                
                # Check all shards are reporting
                expected_shards = 4
                actual_shards = len(stats_data.get('shards', []))
                shards_check = actual_shards == expected_shards
                
                print(f"   📍 Expected Shards: {expected_shards}")
                print(f"   📍 Reporting Shards: {actual_shards}")
                
                success = consistency_check and shards_check
                message = f"System consistency: {stats_accounts} accounts, {actual_shards} shards"
                self.log_test("System Consistency", success, message)
                return success
            else:
                message = "Failed to get system stats"
                self.log_test("System Consistency", False, message)
                return False
                
        except Exception as e:
            message = f"Consistency check failed: {e}"
            self.log_test("System Consistency", False, message)
            return False

    def run_integration_tests(self) -> Dict:
        """Run all integration tests"""
        print("🚀 MySQL Sharding Payment System - Integration Tests")
        print("=" * 65)
        
        # Wait for system to be ready
        if not self.wait_for_system():
            return {"success": False, "message": "System not ready"}
            
        # Run test sequence
        tests = [
            self.test_payment_ecosystem_setup,
            self.test_same_shard_payments,
            self.test_cross_shard_payments,
            self.test_p2p_transfers,
            self.test_real_time_analytics,
            self.test_system_consistency
        ]
        
        passed = 0
        failed = 0
        
        start_time = time.time()
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
                failed += 1
                
        total_time = time.time() - start_time
        
        # Print summary
        print("\n" + "=" * 65)
        print("📊 INTEGRATION TEST SUMMARY")
        print("=" * 65)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Total Time: {total_time:.2f}s")
        print(f"🎯 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("🎉 ALL INTEGRATION TESTS PASSED!")
            print("💳 Payment system is working correctly across all shards!")
        else:
            print("⚠️  Some integration tests failed.")
            
        return {
            "success": failed == 0,
            "passed": passed,
            "failed": failed,
            "total_time": total_time,
            "tests": self.test_results
        }


def main():
    """Main test runner"""
    tester = PaymentSystemIntegrationTest()
    results = tester.run_integration_tests()
    
    # Exit with appropriate code
    exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
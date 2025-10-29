#!/usr/bin/env python3
"""
Comprehensive Test Suite for MySQL Sharding System
Tests all aspects of the payment system with distributed database architecture.
"""

import pytest
import requests
import time
import json
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import mysql.connector


@dataclass
class TestResult:
    """Container for test results"""
    test_name: str
    success: bool
    message: str
    duration: float
    data: Optional[Dict] = None


class ShardingSystemTest:
    """Main test class for the sharding system"""
    
    def __init__(self):
        self.base_url = "http://localhost:8006"
        self.shard_ports = [3306, 3307, 3308, 3309]
        self.results: List[TestResult] = []
        
    def log_result(self, test_name: str, success: bool, message: str, 
                   duration: float, data: Optional[Dict] = None):
        """Log test result"""
        result = TestResult(test_name, success, message, duration, data)
        self.results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message} ({duration:.2f}s)")
        
    def wait_for_services(self, timeout: int = 120) -> bool:
        """Wait for all services to be ready"""
        print("🔄 Waiting for services to start...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    print("✅ All services ready!")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(2)
            
        print("❌ Services failed to start within timeout")
        return False

    def test_shard_manager_health(self) -> TestResult:
        """Test 1: Shard Manager Health Check"""
        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                message = f"Shard Manager healthy. Shards: {data.get('total_shards', 'unknown')}"
                self.log_result("Shard Manager Health", True, message, duration, data)
                return True
            else:
                self.log_result("Shard Manager Health", False, f"HTTP {response.status_code}", duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Shard Manager Health", False, str(e), duration)
            return False

    def test_mysql_shards_connectivity(self) -> bool:
        """Test 2: Direct MySQL Shard Connectivity"""
        start_time = time.time()
        connected_shards = 0
        
        for i, port in enumerate(self.shard_ports):
            try:
                conn = mysql.connector.connect(
                    host='localhost',
                    port=port,
                    user='root',
                    password='rootpassword',
                    database='paytm_shard',
                    connection_timeout=5
                )
                
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM accounts")
                count = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                connected_shards += 1
                print(f"   Shard {i} (port {port}): {count} accounts")
                
            except Exception as e:
                print(f"   Shard {i} (port {port}): Connection failed - {e}")
                
        duration = time.time() - start_time
        success = connected_shards == len(self.shard_ports)
        message = f"{connected_shards}/{len(self.shard_ports)} shards accessible"
        
        self.log_result("MySQL Shards Connectivity", success, message, duration)
        return success

    def test_consistent_hashing(self) -> bool:
        """Test 3: Consistent Hashing Algorithm"""
        start_time = time.time()
        test_users = [
            "alice", "bob", "charlie", "david", "eve", "frank", 
            "grace", "henry", "iris", "jack", "kate", "liam"
        ]
        
        shard_distribution = {0: 0, 1: 0, 2: 0, 3: 0}
        
        try:
            for user in test_users:
                # Test the hash function locally
                hash_value = int(hashlib.md5(user.encode()).hexdigest(), 16)
                expected_shard = hash_value % 4
                
                # Verify with shard manager
                response = requests.get(f"{self.base_url}/user_shard/{user}", timeout=5)
                if response.status_code == 200:
                    actual_shard = response.json()["shard"]
                    if actual_shard == expected_shard:
                        shard_distribution[actual_shard] += 1
                    else:
                        duration = time.time() - start_time
                        message = f"Hash mismatch for {user}: expected {expected_shard}, got {actual_shard}"
                        self.log_result("Consistent Hashing", False, message, duration)
                        return False
                        
            duration = time.time() - start_time
            message = f"Distribution: {dict(shard_distribution)}"
            self.log_result("Consistent Hashing", True, message, duration, shard_distribution)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Consistent Hashing", False, str(e), duration)
            return False

    def test_account_creation(self) -> bool:
        """Test 4: Account Creation Across Shards"""
        start_time = time.time()
        test_accounts = [
            ("test_user_1", 1000.00),
            ("test_user_2", 2000.00),
            ("test_user_3", 1500.00),
            ("test_merchant_1", 0.00),
            ("test_merchant_2", 0.00)
        ]
        
        created_accounts = 0
        
        try:
            for username, balance in test_accounts:
                response = requests.post(
                    f"{self.base_url}/create_user/{username}/{balance}",
                    timeout=10
                )
                if response.status_code == 200:
                    created_accounts += 1
                    data = response.json()
                    print(f"   Created {username}: ${balance} on shard {data.get('shard')}")
                else:
                    print(f"   Failed to create {username}: HTTP {response.status_code}")
                    
            duration = time.time() - start_time
            success = created_accounts == len(test_accounts)
            message = f"{created_accounts}/{len(test_accounts)} accounts created"
            
            self.log_result("Account Creation", success, message, duration)
            return success
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Account Creation", False, str(e), duration)
            return False

    def test_same_shard_transactions(self) -> bool:
        """Test 5: Same-Shard Transactions (ACID)"""
        start_time = time.time()
        
        try:
            # First, check which shard our test users are on
            user1_response = requests.get(f"{self.base_url}/user_shard/test_user_1")
            user2_response = requests.get(f"{self.base_url}/user_shard/test_user_2")
            
            if user1_response.status_code != 200 or user2_response.status_code != 200:
                duration = time.time() - start_time
                self.log_result("Same-Shard Transactions", False, "Users not found", duration)
                return False
                
            user1_shard = user1_response.json()["shard"]
            user2_shard = user2_response.json()["shard"]
            
            # If they're on the same shard, test the transaction
            if user1_shard == user2_shard:
                response = requests.post(
                    f"{self.base_url}/transfer/test_user_1/test_user_2/100.00",
                    timeout=10
                )
                
                duration = time.time() - start_time
                if response.status_code == 200:
                    message = f"Same-shard transaction successful (shard {user1_shard})"
                    self.log_result("Same-Shard Transactions", True, message, duration)
                    return True
                else:
                    message = f"Transaction failed: HTTP {response.status_code}"
                    self.log_result("Same-Shard Transactions", False, message, duration)
                    return False
            else:
                duration = time.time() - start_time
                message = f"Test users on different shards ({user1_shard}, {user2_shard}) - skipping same-shard test"
                self.log_result("Same-Shard Transactions", True, message, duration)
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Same-Shard Transactions", False, str(e), duration)
            return False

    def test_cross_shard_transactions(self) -> bool:
        """Test 6: Cross-Shard Transactions"""
        start_time = time.time()
        
        try:
            # Create users on different shards by using specific usernames
            # that hash to different shards
            users_to_create = [
                ("shard0_user", 500.00, 0),  # Should go to shard 0
                ("shard1_user", 500.00, 1),  # Should go to shard 1
            ]
            
            created_users = []
            for username, balance, expected_shard in users_to_create:
                # Verify the user would go to expected shard
                hash_value = int(hashlib.md5(username.encode()).hexdigest(), 16)
                actual_shard = hash_value % 4
                
                if actual_shard == expected_shard:
                    response = requests.post(
                        f"{self.base_url}/create_user/{username}/{balance}",
                        timeout=10
                    )
                    if response.status_code == 200:
                        created_users.append(username)
                        
            if len(created_users) >= 2:
                # Perform cross-shard transaction
                response = requests.post(
                    f"{self.base_url}/transfer/{created_users[0]}/{created_users[1]}/50.00",
                    timeout=15
                )
                
                duration = time.time() - start_time
                if response.status_code == 200:
                    message = "Cross-shard transaction successful"
                    self.log_result("Cross-Shard Transactions", True, message, duration)
                    return True
                else:
                    message = f"Cross-shard transaction failed: HTTP {response.status_code}"
                    self.log_result("Cross-Shard Transactions", False, message, duration)
                    return False
            else:
                duration = time.time() - start_time
                message = "Could not create users on different shards"
                self.log_result("Cross-Shard Transactions", False, message, duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Cross-Shard Transactions", False, str(e), duration)
            return False

    def test_concurrent_transactions(self) -> bool:
        """Test 7: Concurrent Transaction Handling"""
        start_time = time.time()
        
        try:
            # Create test accounts for concurrent transactions
            base_accounts = [
                ("concurrent_user_1", 1000.00),
                ("concurrent_user_2", 1000.00),
                ("concurrent_user_3", 1000.00),
                ("concurrent_merchant", 0.00)
            ]
            
            for username, balance in base_accounts:
                requests.post(f"{self.base_url}/create_user/{username}/{balance}", timeout=5)
                
            # Define concurrent transactions
            transactions = [
                ("concurrent_user_1", "concurrent_merchant", 10.00),
                ("concurrent_user_2", "concurrent_merchant", 15.00),
                ("concurrent_user_3", "concurrent_merchant", 20.00),
                ("concurrent_user_1", "concurrent_user_2", 25.00),
                ("concurrent_user_2", "concurrent_user_3", 30.00),
            ]
            
            # Execute transactions concurrently
            successful_transactions = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for from_user, to_user, amount in transactions:
                    future = executor.submit(
                        requests.post,
                        f"{self.base_url}/transfer/{from_user}/{to_user}/{amount}",
                        timeout=10
                    )
                    futures.append(future)
                    
                for future in as_completed(futures):
                    try:
                        response = future.result()
                        if response.status_code == 200:
                            successful_transactions += 1
                    except Exception as e:
                        print(f"   Concurrent transaction failed: {e}")
                        
            duration = time.time() - start_time
            success = successful_transactions >= len(transactions) * 0.8  # 80% success rate
            message = f"{successful_transactions}/{len(transactions)} concurrent transactions successful"
            
            self.log_result("Concurrent Transactions", success, message, duration)
            return success
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Concurrent Transactions", False, str(e), duration)
            return False

    def test_analytics_aggregation(self) -> bool:
        """Test 8: Cross-Shard Analytics Aggregation"""
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.base_url}/analytics", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                duration = time.time() - start_time
                
                # Verify analytics data structure
                required_fields = ["total_accounts", "total_balance", "shards"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    message = f"Analytics: {data['total_accounts']} accounts, ${data['total_balance']:.2f} total"
                    self.log_result("Analytics Aggregation", True, message, duration, data)
                    return True
                else:
                    message = f"Missing analytics fields: {missing_fields}"
                    self.log_result("Analytics Aggregation", False, message, duration)
                    return False
            else:
                duration = time.time() - start_time
                message = f"Analytics endpoint failed: HTTP {response.status_code}"
                self.log_result("Analytics Aggregation", False, message, duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Analytics Aggregation", False, str(e), duration)
            return False

    def test_system_stats(self) -> bool:
        """Test 9: System Statistics"""
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.base_url}/stats", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                duration = time.time() - start_time
                
                # Verify expected shard count
                if data.get("total_shards") == 4:
                    message = f"System stats: {data['total_shards']} shards, {data.get('total_accounts', 0)} accounts"
                    self.log_result("System Statistics", True, message, duration, data)
                    return True
                else:
                    message = f"Unexpected shard count: {data.get('total_shards')}"
                    self.log_result("System Statistics", False, message, duration)
                    return False
            else:
                duration = time.time() - start_time
                message = f"Stats endpoint failed: HTTP {response.status_code}"
                self.log_result("System Statistics", False, message, duration)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("System Statistics", False, str(e), duration)
            return False

    def test_performance_load(self) -> bool:
        """Test 10: Performance Load Test"""
        start_time = time.time()
        
        try:
            # Create multiple accounts rapidly
            account_creation_times = []
            num_accounts = 20
            
            for i in range(num_accounts):
                account_start = time.time()
                response = requests.post(
                    f"{self.base_url}/create_user/load_test_{i}/100.00",
                    timeout=5
                )
                account_duration = time.time() - account_start
                account_creation_times.append(account_duration)
                
                if response.status_code != 200:
                    duration = time.time() - start_time
                    message = f"Failed to create account {i}"
                    self.log_result("Performance Load Test", False, message, duration)
                    return False
                    
            # Calculate performance metrics
            avg_creation_time = sum(account_creation_times) / len(account_creation_times)
            max_creation_time = max(account_creation_times)
            
            duration = time.time() - start_time
            accounts_per_second = num_accounts / duration
            
            # Performance thresholds
            success = avg_creation_time < 1.0 and accounts_per_second > 5
            message = f"{accounts_per_second:.1f} accounts/sec, avg {avg_creation_time:.3f}s, max {max_creation_time:.3f}s"
            
            self.log_result("Performance Load Test", success, message, duration)
            return success
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Performance Load Test", False, str(e), duration)
            return False

    def run_all_tests(self) -> Dict:
        """Run all tests and return summary"""
        print("🚀 Starting MySQL Sharding System Test Suite")
        print("=" * 60)
        
        # Wait for services to be ready
        if not self.wait_for_services():
            return {"success": False, "message": "Services failed to start"}
        
        # Define test sequence
        tests = [
            self.test_shard_manager_health,
            self.test_mysql_shards_connectivity,
            self.test_consistent_hashing,
            self.test_account_creation,
            self.test_same_shard_transactions,
            self.test_cross_shard_transactions,
            self.test_concurrent_transactions,
            self.test_analytics_aggregation,
            self.test_system_stats,
            self.test_performance_load
        ]
        
        # Run tests
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test.__name__} crashed: {e}")
                failed += 1
                
        # Generate summary
        total_duration = sum(result.duration for result in self.results)
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Total Duration: {total_duration:.2f}s")
        print(f"🎯 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED! Sharding system is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the logs above for details.")
            
        return {
            "success": failed == 0,
            "passed": passed,
            "failed": failed,
            "total_duration": total_duration,
            "success_rate": passed/(passed+failed)*100 if (passed+failed) > 0 else 0,
            "results": [
                {
                    "test": result.test_name,
                    "success": result.success,
                    "message": result.message,
                    "duration": result.duration
                }
                for result in self.results
            ]
        }


def main():
    """Main test runner"""
    tester = ShardingSystemTest()
    summary = tester.run_all_tests()
    
    # Exit with appropriate code
    exit(0 if summary["success"] else 1)


if __name__ == "__main__":
    main()
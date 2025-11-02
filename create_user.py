#!/usr/bin/env python3
"""
Script to create new users in the payment system
Usage: python create_user.py <user_id> <initial_balance>
Example: python create_user.py john_doe 500.00
"""

import sys
import hashlib
import mysql.connector
from datetime import datetime

def get_shard_id(user_id: str) -> int:
    """Determine which shard this user belongs to"""
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return hash_value % 4

def create_user(user_id: str, initial_balance: float = 1000.0):
    """Create a new user account"""
    
    # Determine shard
    shard_id = get_shard_id(user_id)
    
    # Shard configurations
    shard_configs = {
        0: ("mysql-shard-0", 3306),
        1: ("mysql-shard-1", 3306),
        2: ("mysql-shard-2", 3306),
        3: ("mysql-shard-3", 3306)
    }
    
    host, port = shard_configs[shard_id]
    
    try:
        # Connect to the appropriate shard
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user='root',
            password='rootpassword',
            database='paytm_shard',
            connection_timeout=10
        )
        
        cursor = connection.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT user_id FROM accounts WHERE user_id = %s", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"❌ User '{user_id}' already exists in shard {shard_id}")
            cursor.close()
            connection.close()
            return False
        
        # Convert balance to cents (integer)
        balance_cents = int(initial_balance * 100)
        
        # Insert new user
        insert_query = """
        INSERT INTO accounts (user_id, balance, created_at)
        VALUES (%s, %s, %s)
        """
        
        cursor.execute(insert_query, (user_id, balance_cents, datetime.now()))
        connection.commit()
        
        print(f"✅ Successfully created user!")
        print(f"   User ID: {user_id}")
        print(f"   Shard: {shard_id}")
        print(f"   Initial Balance: ${initial_balance:.2f}")
        print(f"   Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n🔗 Login URL: http://localhost:8005/user/login")
        
        cursor.close()
        connection.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_user.py <user_id> [initial_balance]")
        print("Example: python create_user.py john_doe 500.00")
        sys.exit(1)
    
    user_id = sys.argv[1]
    initial_balance = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    
    print(f"🚀 Creating new user...")
    create_user(user_id, initial_balance)

if __name__ == "__main__":
    main()

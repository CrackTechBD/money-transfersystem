#!/usr/bin/env python3
"""
Simple user creation script that runs inside Docker container
Usage: 
  docker exec paytm-style-analytics_service-1 python3 create_user_simple.py <user_id> [balance]
  
Example:
  docker exec paytm-style-analytics_service-1 python3 create_user_simple.py bob_jones 750.00
"""

import sys
import hashlib
import uuid
import mysql.connector
from datetime import datetime

def create_user(user_id, initial_balance=1000.00):
    # Calculate shard using same logic as payment service
    shard_id = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 4
    balance_cents = int(initial_balance * 100)
    
    # Generate unique ID
    account_id = str(uuid.uuid4())
    
    try:
        # Connect to appropriate shard
        conn = mysql.connector.connect(
            host=f'mysql-shard-{shard_id}',
            port=3306,
            user='root',
            password='rootpassword',
            database='paytm_shard'
        )
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT user_id FROM accounts WHERE user_id = %s', (user_id,))
        if cursor.fetchone():
            print(f'❌ User "{user_id}" already exists in shard {shard_id}')
            return False
        
        # Insert new user
        cursor.execute('''
            INSERT INTO accounts (id, user_id, balance, currency, created_at, updated_at)
            VALUES (%s, %s, %s, 'USD', NOW(), NOW())
        ''', (account_id, user_id, balance_cents))
        
        conn.commit()
        
        # Get the created user
        cursor.execute('SELECT user_id, balance/100 as balance, created_at FROM accounts WHERE user_id = %s', (user_id,))
        user = cursor.fetchone()
        
        print('✅ Successfully created user!')
        print('')
        print('📊 User Details:')
        print(f'   User ID: {user[0]}')
        print(f'   Balance: ${user[1]:.2f}')
        print(f'   Shard: {shard_id}')
        print(f'   Created: {user[2]}')
        print('')
        print('🔗 Login URL: http://localhost:8005/user/login')
        print(f'   Enter User ID: {user_id}')
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f'❌ Error creating user: {e}')
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 create_user_simple.py <user_id> [initial_balance]')
        print('Example: python3 create_user_simple.py john_doe 500.00')
        sys.exit(1)
    
    user_id = sys.argv[1]
    initial_balance = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.00
    
    create_user(user_id, initial_balance)

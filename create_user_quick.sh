#!/bin/bash
# Quick user creation script
# Usage: ./create_user_quick.sh <user_id> <balance>

if [ -z "$1" ]; then
    echo "Usage: ./create_user_quick.sh <user_id> <balance>"
    echo "Example: ./create_user_quick.sh john_doe 500"
    exit 1
fi

USER_ID=$1
BALANCE=${2:-1000}

docker exec paytm-style-analytics_service-1 python3 -c "
import hashlib, uuid, mysql.connector

user_id, balance = '$USER_ID', float($BALANCE)
shard = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 4
balance_cents = int(balance * 100)

conn = mysql.connector.connect(host=f'mysql-shard-{shard}', port=3306, user='root', password='rootpassword', database='paytm_shard')
c = conn.cursor()
c.execute('SELECT user_id FROM accounts WHERE user_id=%s', (user_id,))
if c.fetchone():
    print(f'❌ User {user_id} already exists in shard {shard}')
else:
    c.execute('INSERT INTO accounts (id, user_id, balance, currency) VALUES (%s, %s, %s, \"USD\")', (str(uuid.uuid4()), user_id, balance_cents))
    conn.commit()
    print(f'✅ Successfully created user!')
    print(f'   User ID: {user_id}')
    print(f'   Balance: \${balance:.2f}')
    print(f'   Shard: {shard}')
    print(f'🔗 Login: http://localhost:8005/user/login')
c.close()
conn.close()
"

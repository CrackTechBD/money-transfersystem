#!/bin/bash
# Script to create new users in the payment system
# Usage: ./create_user.sh <user_id> [initial_balance]
# Example: ./create_user.sh john_doe 500.00

USER_ID=$1
INITIAL_BALANCE=${2:-1000.00}

if [ -z "$USER_ID" ]; then
    echo "❌ Error: User ID is required"
    echo "Usage: ./create_user.sh <user_id> [initial_balance]"
    echo "Example: ./create_user.sh john_doe 500.00"
    exit 1
fi

# Calculate shard ID using MD5 hash (compatible with macOS)
if command -v md5 &> /dev/null; then
    # macOS
    MD5_HASH=$(echo -n "$USER_ID" | md5)
else
    # Linux
    MD5_HASH=$(echo -n "$USER_ID" | md5sum | awk '{print $1}')
fi
# Take first 8 characters and convert to decimal, then modulo 4
SHARD_ID=$(echo "ibase=16; ${MD5_HASH:0:8}" | bc | awk '{print $1 % 4}')

# Convert balance to cents (integer)
BALANCE_CENTS=$(echo "$INITIAL_BALANCE * 100" | bc | cut -d. -f1)

# Determine which shard container to use
SHARD_CONTAINER="paytm-style-mysql-shard-${SHARD_ID}-1"

echo "🚀 Creating new user..."
echo "   User ID: $USER_ID"
echo "   Shard: $SHARD_ID"
echo "   Initial Balance: \$$INITIAL_BALANCE"
echo ""

# Check if user already exists
EXISTING=$(docker exec $SHARD_CONTAINER mysql -uroot -prootpassword paytm_shard \
  -e "SELECT user_id FROM accounts WHERE user_id='$USER_ID';" -sN 2>/dev/null)

if [ ! -z "$EXISTING" ]; then
    echo "❌ User '$USER_ID' already exists in shard $SHARD_ID"
    exit 1
fi

# Create the user
docker exec $SHARD_CONTAINER mysql -uroot -prootpassword paytm_shard \
  -e "INSERT INTO accounts (user_id, balance, created_at) VALUES ('$USER_ID', $BALANCE_CENTS, NOW());" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Successfully created user!"
    echo ""
    echo "📊 User Details:"
    docker exec $SHARD_CONTAINER mysql -uroot -prootpassword paytm_shard \
      -e "SELECT user_id as 'User ID', balance/100 as 'Balance (\$)', created_at as 'Created At' FROM accounts WHERE user_id='$USER_ID';" 2>/dev/null
    echo ""
    echo "🔗 Login URL: http://localhost:8005/user/login"
    echo "   Enter User ID: $USER_ID"
else
    echo "❌ Failed to create user"
    exit 1
fi

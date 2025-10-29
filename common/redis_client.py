"""
Redis client utilities for caching and session management
"""
import json
import redis
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from .settings import settings
import hashlib

class RedisClient:
    """Redis client wrapper with utility methods"""
    
    def __init__(self):
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    
    def ping(self) -> bool:
        """Check Redis connectivity"""
        try:
            return self.client.ping()
        except:
            return False
    
    # Session Management
    def set_session(self, token: str, user_data: Dict[str, Any], ttl_seconds: int = 3600) -> bool:
        """Store user session data"""
        try:
            key = f"session:{token}"
            value = json.dumps(user_data)
            return self.client.setex(key, ttl_seconds, value)
        except Exception as e:
            print(f"Failed to set session: {e}")
            return False
    
    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve user session data"""
        try:
            key = f"session:{token}"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Failed to get session: {e}")
            return None
    
    def delete_session(self, token: str) -> bool:
        """Delete user session"""
        try:
            key = f"session:{token}"
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"Failed to delete session: {e}")
            return False
    
    # Shard Routing Cache
    def cache_shard_route(self, user_id: str, shard_id: int, ttl_seconds: int = 3600) -> bool:
        """Cache user's shard assignment"""
        try:
            key = f"shard_route:{user_id}"
            return self.client.setex(key, ttl_seconds, str(shard_id))
        except Exception as e:
            print(f"Failed to cache shard route: {e}")
            return False
    
    def get_shard_route(self, user_id: str) -> Optional[int]:
        """Get cached shard assignment"""
        try:
            key = f"shard_route:{user_id}"
            value = self.client.get(key)
            if value:
                return int(value)
            return None
        except Exception as e:
            print(f"Failed to get shard route: {e}")
            return None
    
    # Rate Limiting
    def check_rate_limit(self, user_id: str, endpoint: str, max_requests: int, window_seconds: int) -> Dict[str, Any]:
        """Check and update rate limit for user/endpoint combination"""
        try:
            key = f"rate_limit:{user_id}:{endpoint}"
            current_time = datetime.now()
            window_start = int(current_time.timestamp()) // window_seconds * window_seconds
            current_key = f"{key}:{window_start}"
            
            # Get current count first
            current_count = self.client.get(current_key)
            current_count = int(current_count) if current_count else 0
            
            # Check if we would exceed the limit
            if current_count >= max_requests:
                reset_time = window_start + window_seconds
                return {
                    "allowed": False,
                    "count": current_count,
                    "remaining": 0,
                    "reset_time": reset_time,
                    "retry_after": reset_time - int(current_time.timestamp())
                }
            
            # Increment the counter atomically
            pipe = self.client.pipeline()
            pipe.incr(current_key)
            pipe.expire(current_key, window_seconds)
            results = pipe.execute()
            new_count = results[0]
            
            # Calculate remaining requests and reset time
            remaining = max(0, max_requests - new_count)
            reset_time = window_start + window_seconds
            
            print(f"Rate limit check for {user_id}:{endpoint} - count: {new_count}/{max_requests}")
            
            return {
                "allowed": new_count <= max_requests,
                "count": new_count,
                "remaining": remaining,
                "reset_time": reset_time,
                "retry_after": reset_time - int(current_time.timestamp()) if new_count > max_requests else 0
            }
            
        except Exception as e:
            print(f"🚨 Rate limit check failed: {e}")
            import traceback
            traceback.print_exc()
            # Fail open - allow request if Redis is down
            return {
                "allowed": True,
                "count": 0,
                "remaining": max_requests,
                "reset_time": 0,
                "retry_after": 0
            }
    
    # User Data Caching
    def cache_user_balance(self, user_id: str, balance: int, ttl_seconds: int = 300) -> bool:
        """Cache user balance (short TTL for financial data)"""
        try:
            key = f"balance:{user_id}"
            return self.client.setex(key, ttl_seconds, str(balance))
        except Exception as e:
            print(f"Failed to cache balance: {e}")
            return False
    
    def get_cached_balance(self, user_id: str) -> Optional[int]:
        """Get cached user balance"""
        try:
            key = f"balance:{user_id}"
            value = self.client.get(key)
            if value:
                return int(value)
            return None
        except Exception as e:
            print(f"Failed to get cached balance: {e}")
            return None
    
    def invalidate_user_cache(self, user_id: str) -> bool:
        """Invalidate all cached data for a user"""
        try:
            keys_to_delete = []
            # Find all keys related to this user
            patterns = [
                f"balance:{user_id}",
                f"shard_route:{user_id}",
                f"rate_limit:{user_id}:*"
            ]
            
            for pattern in patterns:
                if "*" in pattern:
                    keys_to_delete.extend(self.client.keys(pattern))
                else:
                    keys_to_delete.append(pattern)
            
            if keys_to_delete:
                return bool(self.client.delete(*keys_to_delete))
            return True
            
        except Exception as e:
            print(f"Failed to invalidate user cache: {e}")
            return False
    
    # Fraud Detection Cache
    def cache_fraud_score(self, user_id: str, score: float, ttl_seconds: int = 1800) -> bool:
        """Cache user's latest fraud score"""
        try:
            key = f"fraud_score:{user_id}"
            data = {
                "score": score,
                "timestamp": datetime.now().isoformat()
            }
            return self.client.setex(key, ttl_seconds, json.dumps(data))
        except Exception as e:
            print(f"Failed to cache fraud score: {e}")
            return False
    
    def get_fraud_score(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached fraud score"""
        try:
            key = f"fraud_score:{user_id}"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Failed to get fraud score: {e}")
            return None
    
    # System Health Caching
    def cache_system_health(self, health_data: Dict[str, Any], ttl_seconds: int = 60) -> bool:
        """Cache system health status"""
        try:
            key = "system:health"
            value = json.dumps(health_data)
            return self.client.setex(key, ttl_seconds, value)
        except Exception as e:
            print(f"Failed to cache system health: {e}")
            return False
    
    def get_system_health(self) -> Optional[Dict[str, Any]]:
        """Get cached system health"""
        try:
            key = "system:health"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Failed to get system health: {e}")
            return None
    
    # Statistics
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        try:
            info = self.client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_ratio": round(
                    info.get("keyspace_hits", 0) / 
                    max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)) * 100, 2
                )
            }
        except Exception as e:
            print(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}

# Global Redis client instance
redis_client = RedisClient()
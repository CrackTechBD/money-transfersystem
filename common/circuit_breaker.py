"""
Circuit Breaker pattern implementation for preventing cascade failures
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, failing fast
    HALF_OPEN = "HALF_OPEN"  # Trying to recover

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures before opening
    reset_timeout: float = 60.0  # Seconds to wait before trying half-open
    success_threshold: int = 3   # Successes needed to close from half-open
    timeout: float = 10.0        # Operation timeout
    
class CircuitBreakerException(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_state_change = time.time()
        
    def _should_attempt_reset(self) -> bool:
        """Check if we should try to reset the circuit"""
        return (self.state == CircuitState.OPEN and 
                time.time() - self.last_failure_time >= self.config.reset_timeout)
    
    def _record_success(self):
        """Record a successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = time.time()
                logger.info(f"Circuit breaker {self.name} closed after successful recovery")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset failure count on success
    
    def _record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.last_state_change = time.time()
            logger.warning(f"Circuit breaker {self.name} re-opened during half-open state")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            self.last_state_change = time.time()
            logger.info(f"Circuit breaker {self.name} entering half-open state")
        
        # Fail fast if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerException(f"Circuit breaker {self.name} is open")
        
        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs),
                    timeout=self.config.timeout
                )
            
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure()
            raise e
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "uptime_since_last_change": time.time() - self.last_state_change
        }

# Global circuit breakers for different services
MYSQL_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    reset_timeout=30.0,
    success_threshold=2,
    timeout=5.0
)

REDIS_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    reset_timeout=15.0,
    success_threshold=2,
    timeout=2.0
)

KAFKA_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    reset_timeout=45.0,
    success_threshold=2,
    timeout=10.0
)

# Circuit breaker instances
mysql_circuit_breaker = CircuitBreaker("mysql", MYSQL_CB_CONFIG)
redis_circuit_breaker = CircuitBreaker("redis", REDIS_CB_CONFIG)
kafka_circuit_breaker = CircuitBreaker("kafka", KAFKA_CB_CONFIG)

def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers"""
    return {
        "mysql": mysql_circuit_breaker.get_state(),
        "redis": redis_circuit_breaker.get_state(),
        "kafka": kafka_circuit_breaker.get_state()
    }
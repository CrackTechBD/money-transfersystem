"""
Retry utilities for handling transient failures
"""
import asyncio
import random
from typing import Callable, Any, Optional, List
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[type]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]

def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for exponential backoff with jitter"""
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # Add jitter to avoid thundering herd
        delay *= (0.5 + random.random() * 0.5)
    
    return delay

async def retry_async(func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
    """Async retry wrapper with exponential backoff"""
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if exception is retryable
            if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                logger.warning(f"Non-retryable exception: {e}")
                raise e
            
            if attempt == config.max_attempts:
                logger.error(f"Max retry attempts ({config.max_attempts}) reached for {func.__name__}")
                break
            
            delay = calculate_delay(attempt, config)
            logger.warning(f"Attempt {attempt}/{config.max_attempts} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
            await asyncio.sleep(delay)
    
    # All attempts failed
    raise last_exception

def retry_decorator(config: RetryConfig):
    """Decorator for automatic retry with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, config, *args, **kwargs)
        return wrapper
    return decorator

# Common retry configurations
MYSQL_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=[
        # MySQL connection errors
        Exception,  # For now, retry all exceptions
    ]
)

REDIS_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.1,
    max_delay=2.0,
    retryable_exceptions=[Exception]
)

KAFKA_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=15.0,
    retryable_exceptions=[Exception]
)

PAYMENT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=[Exception]
)
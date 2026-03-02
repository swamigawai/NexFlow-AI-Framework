import time
import functools
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def exponential_backoff(max_retries: int = 3, base_delay: float = 2.0, backoff_factor: float = 2.0):
    """
    Decorator for retrying a function with exponential backoff.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            delay = base_delay
            
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {str(e)}")
                        raise e
                    
                    logger.warning(
                        f"Attempt {retries} failed for {func.__name__}. "
                        f"Retrying in {delay}s... Error: {str(e)}"
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
            
            return None # Should not reach here
        return wrapper
    return decorator

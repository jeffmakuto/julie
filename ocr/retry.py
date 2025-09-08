import time
import random
import logging
from typing import Tuple, Type

logger = logging.getLogger("ocr")

def retry_on_exception(
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    max_attempts: int = 5,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    jitter: float = 0.1,
):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = initial_delay
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.exception(f"Max retry attempts reached for {func.__name__}")
                        raise
                    to_sleep = delay * (1 + (random.random() - 0.5) * 2 * jitter)
                    logger.warning(f"Retrying {func.__name__} attempt {attempt}/{max_attempts}: {e}; sleeping {to_sleep:.2f}s")
                    time.sleep(to_sleep)
                    delay *= backoff_factor
        return wrapper
    return decorator

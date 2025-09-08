import time, random
from typing import Callable, Any
from .logger import get_logger

log = get_logger()

def with_retries(func: Callable, *args, retries: int = 3, **kwargs) -> Any:
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                log.exception("LLM call failed permanently.")
                raise
            wait = (2 ** attempt) + random.random()
            log.warning("Retrying LLM call after error: %s (sleep %.2fs)", e, wait)
            time.sleep(wait)

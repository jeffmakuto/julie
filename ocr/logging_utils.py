import logging
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def log_struct(msg: str, **kwargs):
    logger.info(f"{msg} -- {json.dumps(kwargs, default=str)}" if kwargs else msg)

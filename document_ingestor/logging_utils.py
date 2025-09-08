import logging, os

logger = logging.getLogger("document_ingestor")
logger.setLevel(os.getenv("RAG_LOG_LEVEL", "INFO"))
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)
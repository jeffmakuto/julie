from __future__ import annotations
from typing import Optional
from .logging_utils import logger
from .s3_ingestor import S3DocumentIngestor

# Scheduler optional (APScheduler)
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    APSCHED_AVAILABLE = True
except Exception:
    BackgroundScheduler = None
    APSCHED_AVAILABLE = False

def preload_knowledge_base(rag_runner, bucket: str, **ingest_opts):
    """
    Preload all documents from an S3 bucket into the RAG index.
    """
    ingestor = S3DocumentIngestor(rag_runner, bucket=bucket, **ingest_opts)
    results = ingestor.ingest_bucket()
    logger.info("Preloaded S3 knowledge base: %s", results)
    return ingestor

def schedule_periodic_reindex(ingestor, interval_minutes: Optional[int] = None):
    if not APSCHED_AVAILABLE or BackgroundScheduler is None:
        logger.warning("APScheduler not installed; skipping scheduled reindex")
        return None

    scheduler = BackgroundScheduler()

    def job():
        logger.info("Running scheduled S3 reindex")
        try:
            ingestor.ingest_bucket()
        except Exception:
            logger.exception("Scheduled reindex failed")

    if interval_minutes is not None:
        scheduler.add_job(job, "interval", minutes=interval_minutes, id="reindex_s3")
    else:
        raise ValueError("interval_minutes must be provided")

    scheduler.start()
    logger.info("Started scheduler for S3 ingestion")
    return scheduler

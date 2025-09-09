import os
import logging
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from orchestrator.email_poller import EmailPollingService
from rag.rag_client import RAGRunner
from document_ingestor.scheduler import schedule_periodic_reindex, preload_knowledge_base
from orchestrator.rpa_reply_service import RPAReplyService
from bedrock_llms.client import BedrockLLMClient
from stores.redis import AsyncRedisCache

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EmailPollingAppS3:
    """
    FastAPI app with background email polling, RPA replies, and S3-based RAG ingestion.
    """

    def __init__(
        self,
        s3_bucket: str,
        reindex_interval_minutes: int | None = 60,
        work_dir: str = ".rag_ingest"
    ):
        self.app = FastAPI(lifespan=self.lifespan)
        self.polling_service: EmailPollingService | None = None
        self.rpa_reply_service: RPAReplyService | None = None
        self.s3_bucket = s3_bucket
        self.reindex_interval_minutes = reindex_interval_minutes
        self.work_dir = work_dir
        self.scheduler = None

        # Health check route
        self.app.get("/")(self.read_root)

    async def read_root(self) -> dict[str, str]:
        return {"message": "Email polling and RPA reply service running with S3 ingestion."}

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Startup: RAG runner + S3 KB preload + async email polling + RPA reply service.
        """
        try:
            # --- RAG / S3 setup ---
            logger.info("Initializing RAG runner...")
            rag_runner = RAGRunner()

            logger.info("Preloading knowledge base from S3...")
            ingestor = preload_knowledge_base(
                rag_runner,
                bucket=self.s3_bucket,
                work_dir=self.work_dir
            )

            # Schedule periodic S3 reindex
            if self.reindex_interval_minutes:
                self.scheduler = schedule_periodic_reindex(
                    ingestor,
                    interval_minutes=self.reindex_interval_minutes
                )

            # --- Email polling setup ---
            logger.info("Starting EmailPollingService...")
            self.polling_service = EmailPollingService()
            self.polling_service.pipeline.rag = rag_runner
            asyncio.create_task(self.polling_service.run())

            # --- RPA reply service setup ---
            logger.info("Starting RPAReplyService...")
            llm_client = BedrockLLMClient()  # configure as needed
            redis_client = AsyncRedisCache()  # configure as needed
            # For email sending via Graph
            from orchestrator.email_poller import GraphEmailClient
            graph_email_client = GraphEmailClient(
                tenant_id=os.environ["AZURE_TENANT_ID"],
                client_id=os.environ["AZURE_CLIENT_ID"],
                client_secret=os.environ["AZURE_CLIENT_SECRET"],
                user_email=os.environ["GRAPH_USER_EMAIL"]
            )

            self.rpa_reply_service = RPAReplyService(
                llm=llm_client,
                email_client=graph_email_client,
                redis_client=redis_client,
                poll_interval=30
            )
            asyncio.create_task(self.rpa_reply_service.run())

            logger.info("Background services started successfully.")
            yield

        finally:
            logger.info("Shutting down services...")
            if self.scheduler:
                self.scheduler.shutdown(wait=False)

# Use environment variable for S3 bucket
s3_bucket_env = os.environ.get("S3_BUCKET_KB")
if not s3_bucket_env:
    raise RuntimeError("Environment variable S3_BUCKET_KB must be set")

# Instantiate FastAPI app
email_app_s3 = EmailPollingAppS3(
    s3_bucket=s3_bucket_env,
    reindex_interval_minutes=60
)

app = email_app_s3.app
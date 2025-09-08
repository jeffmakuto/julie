from typing import List, Optional, Dict, Any
import logging
import uuid
from extractors.base import Extractor
from extractors.claim_extractor import ClaimExtractor
from ocr.processor import OCRDispatcher, OCRProcessor
from rag.rag_client import RAGRunner, RAGConfig
from orchestrator.payload_stream import PayloadPusherService
from orchestrator.rpa_client import RPAClient

logger = logging.getLogger(__name__)


class ClaimPipeline:
    """
    Orchestrates:
      1) OCR
      2) (Optional) RAG retrieval
      3) LLM extraction
      4) Payload construction and push
      5) RPA queue submission

    Depends only on the abstract Extractor.
    """

    def __init__(
        self,
        ocr_bucket: str,
        *,
        llm_client=None,
        extractor: Optional[Extractor] = None,
        rag_runner: Optional[RAGRunner] = None,
        rag_top_k: int = 5,
    ):
        self.ocr = OCRProcessor(bucket_name=ocr_bucket, ocr_dispatcher=OCRDispatcher())
        self.extractor: Extractor = extractor or ClaimExtractor(llm_client=llm_client)
        self.payload_service = PayloadPusherService()
        self.rpa = RPAClient()
        self.rag = rag_runner or RAGRunner(llm_client=llm_client, config=RAGConfig(k=rag_top_k))
        self.rag_top_k = rag_top_k

    def run(
        self,
        subject: str,
        body: str,
        attachment_keys: List[str],
        sender: Optional[str] = None,
        received_time=None,
        email_id: Optional[str] = None
    ) -> Dict[str, Any]:
        diagnostics = {"errors": []}

        # 1) OCR
        text = self.ocr.ocr_attachments(attachment_keys)
        combined_text = f"{text}\n\n{body}"

        # 2) RAG retrieval
        retrieved_docs = []
        try:
            retrieved = self.rag.retrieve(combined_text, k=self.rag_top_k)
            if retrieved:
                for i, r in enumerate(retrieved, 1):
                    logger.info(
                        "[RAG] Retrieved chunk %d/%d:\n%s\n--- metadata=%s",
                        i, self.rag_top_k,
                        r["content"][:300].replace("\n", " "),
                        r.get("metadata", {}),
                    )
                retrieved_docs = retrieved
            retrieved_context = "\n\n".join([r["content"] for r in retrieved]) if retrieved else ""
            augmented_text = f"{retrieved_context}\n\n{text}" if retrieved_context else text
        except Exception as e:
            logger.warning("RAG retrieval failed, continuing without retrieval: %s", e)
            augmented_text = text

        # 3) LLM Extraction
        struct = self.extractor.extract(subject, body, augmented_text, sender=sender)

        # 4) Correlation ID
        correlation_id = str(uuid.uuid4())

        # 5) Full Payload (for DB, analytics, etc.)
        payload = self.payload_service.push(struct, subject, body, text, received_time)
        payload["CorrelationID"] = correlation_id
        if email_id:
            payload["EmailID"] = email_id

        # 6) RPA Payload (minimal fields)
        try:
            rpa_payload = self.payload_service.build_payload(
                struct, subject, body, text, received_time, fields_file="rpa_fields.txt"
            )
            rpa_payload["CorrelationID"] = correlation_id
            if email_id:
                rpa_payload["EmailID"] = email_id
            rpa_resp = self.rpa.post_queue_item(rpa_payload)
        except Exception as e:
            diagnostics["errors"].append(str(e))
            rpa_resp = None

        return {
            "structured_result": struct,
            "payload": payload,
            "rpa_response": rpa_resp,
            "diagnostics": diagnostics,
            "retrieved_docs": retrieved_docs,
        }

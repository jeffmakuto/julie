from __future__ import annotations
import time
from typing import Optional
from abc import ABC, abstractmethod
from .s3_client import S3ClientManager
from .config import USE_REKOGNITION_S3_OBJECT, OCR_TIMEOUT, OCR_POLL_INTERVAL
from .retry import retry_on_exception


class OCRBackend(ABC):
    @abstractmethod
    def extract_text(self, image_bytes: bytes, bucket: Optional[str] = None, key: Optional[str] = None) -> str:
        pass


# --------------------- Textract OCR ---------------------
class TextractOCR(OCRBackend):
    @retry_on_exception(max_attempts=4)
    def extract_text(self, image_bytes: bytes, bucket: Optional[str] = None, key: Optional[str] = None) -> str:
        _, textract, _ = S3ClientManager.clients()
        resp = textract.detect_document_text(Document={"Bytes": image_bytes})
        lines = [b.get("DetectedText", "") for b in resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return "\n".join(lines)

    @retry_on_exception(max_attempts=4)
    def extract_text_pdf(self, bucket: str, key: str, timeout: int = OCR_TIMEOUT, poll_interval: float = OCR_POLL_INTERVAL) -> str:
        _, textract, _ = S3ClientManager.clients()
        resp = textract.start_document_text_detection(DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}})
        job_id = resp.get("JobId")
        if not job_id:
            raise RuntimeError("Textract did not return JobId")

        # Poll for completion
        start = time.monotonic()
        delay = poll_interval
        while True:
            job_resp = textract.get_document_text_detection(JobId=job_id)
            status = job_resp.get("JobStatus")
            if status in ("SUCCEEDED", "FAILED"):
                break
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Textract async job {job_id} timed out")
            time.sleep(delay)
            delay = min(delay * 2, 20)

        if status == "FAILED":
            raise RuntimeError(f"Textract async job {job_id} failed")

        lines = [b.get("Text", "") for b in job_resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return "\n".join(lines)


# --------------------- Rekognition OCR ---------------------
class RekognitionOCR(OCRBackend):
    @retry_on_exception(max_attempts=3)
    def extract_text(self, image_bytes: bytes, bucket: Optional[str] = None, key: Optional[str] = None) -> str:
        _, _, rek = S3ClientManager.clients()

        if USE_REKOGNITION_S3_OBJECT:
            if not bucket or not key:
                raise ValueError("Rekognition S3Object mode requires bucket/key")
            resp = rek.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": key}})
        else:
            if len(image_bytes) <= 5 * 1024 * 1024:
                resp = rek.detect_text(Image={"Bytes": image_bytes})
            elif bucket and key:
                resp = rek.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": key}})
            else:
                raise ValueError("Image too large for Rekognition Bytes mode without S3 reference")

        lines = [t.get("DetectedText", "") for t in resp.get("TextDetections", []) if t.get("Type") == "LINE"]
        return "\n".join(lines)

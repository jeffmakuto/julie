import threading
from typing import Any, Dict, Optional, Tuple
import boto3
from botocore.config import Config
from .logging_utils import logger
from .config import AWS_REGION, AWS_MAX_RETRIES, S3_STREAM_THRESHOLD_BYTES


class S3ClientManager:
    _thread_local = threading.local()
    _boto_cfg = Config(
        region_name=AWS_REGION,
        retries={"max_attempts": AWS_MAX_RETRIES, "mode": "standard"},
        read_timeout=70,
        connect_timeout=20,
    )

    @classmethod
    def clients(cls) -> Tuple[Any, Any, Any]:
        if not getattr(cls._thread_local, "session", None):
            cls._thread_local.session = boto3.Session()
            cls._thread_local.s3 = cls._thread_local.session.client("s3", config=cls._boto_cfg)
            cls._thread_local.textract = cls._thread_local.session.client("textract", config=cls._boto_cfg)
            cls._thread_local.rekognition = cls._thread_local.session.client("rekognition", config=cls._boto_cfg)
        return cls._thread_local.s3, cls._thread_local.textract, cls._thread_local.rekognition

    @classmethod
    def safe_head_object(cls, bucket: str, key: str) -> Optional[Dict[str, Any]]:
        s3, *_ = cls.clients()
        try:
            return s3.head_object(Bucket=bucket, Key=key)
        except Exception as e:
            logger.debug(f"Could not head_object {bucket}/{key}: {e}")
            return None

    @classmethod
    def fetch_bytes(cls, bucket: str, key: str, max_bytes: int = 0) -> bytes:
        s3, *_ = cls.clients()
        head = cls.safe_head_object(bucket, key)
        size = (head or {}).get("ContentLength", 0)

        if max_bytes > 0:
            with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
                chunks = []
                remaining = max_bytes
                while remaining > 0:
                    chunk = body.read(min(65536, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                return b"".join(chunks)

        if size >= S3_STREAM_THRESHOLD_BYTES:
            chunks = []
            part_size = 8 * 1024 * 1024
            with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
                while True:
                    data = body.read(part_size)
                    if not data:
                        break
                    chunks.append(data)
            return b"".join(chunks)

        with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
            return body.read()

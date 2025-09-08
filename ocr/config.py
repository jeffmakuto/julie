import os
from dotenv import load_dotenv
load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_MAX_RETRIES = int(os.environ.get("AWS_MAX_RETRIES", "10"))
OCR_POLL_INTERVAL = float(os.environ.get("OCR_POLL_INTERVAL", "2.0"))
OCR_TIMEOUT = int(os.environ.get("OCR_TIMEOUT", "300"))
OCR_MAX_WORKERS = int(os.environ.get("OCR_MAX_WORKERS", "5"))
USE_REKOGNITION_S3_OBJECT = os.environ.get("USE_REK_S3OBJECT", "false").lower() in ("1", "true", "yes")
S3_READ_MAX_BYTES = int(os.environ.get("S3_READ_MAX_BYTES", "0"))
S3_STREAM_THRESHOLD_BYTES = int(os.environ.get("S3_STREAM_THRESHOLD_BYTES", str(64*1024*1024)))

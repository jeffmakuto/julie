from __future__ import annotations
from typing import List
from .logging_utils import logger
from typing import Optional
from .filetype import FileTypeDetector
from .preprocess import ImagePreprocessor
from .backends import RekognitionOCR, TextractOCR
from .s3_client import S3ClientManager
from .config import S3_READ_MAX_BYTES
from .logging_utils import logger, log_struct
from .preprocess import PDFRasterFallback


class OCRDispatcher:
    def __init__(self, preprocessor: Optional[ImagePreprocessor] = None):
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.rekognition = RekognitionOCR()
        self.textract = TextractOCR()

    def ocr_from_s3(self, bucket: str, key: str) -> str:
        file_type = FileTypeDetector.detect(bucket, key)
        log_struct("File detected", bucket=bucket, key=key, type=file_type)
        data = S3ClientManager.fetch_bytes(bucket, key, max_bytes=S3_READ_MAX_BYTES)

        if file_type == "image":
            data = self.preprocessor.preprocess(data)
            try:
                return self.rekognition.extract_text(data, bucket=bucket, key=key)
            except Exception as e:
                logger.warning(f"Rekognition failed, fallback to Textract: {e}")
                return self.textract.extract_text(data)
        elif file_type == "pdf":
            try:
                return self.textract.extract_text_pdf(bucket, key)
            except Exception as e:
                logger.warning(f"Textract PDF failed, fallback to raster: {e}")
                fallback = PDFRasterFallback(self.rekognition)
                return fallback.extract_text(data)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")


class OCRProcessor:
    def __init__(self, bucket_name: str, ocr_dispatcher: OCRDispatcher):
        self.bucket_name = bucket_name
        self.ocr_dispatcher = ocr_dispatcher

    def ocr_attachments(self, keys: List[str]) -> str:
        texts = []
        for key in keys:
            try:
                texts.append(self.ocr_dispatcher.ocr_from_s3(self.bucket_name, key))
            except Exception as e:
                logger.warning(f"OCR failed for {key}: {e}")
                texts.append("")
        return "\n\n".join(texts)

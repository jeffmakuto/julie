from typing import Optional
from .s3_client import S3ClientManager
try:
    import magic
except Exception:
    magic = None


class FileTypeDetector:
    @staticmethod
    def detect(bucket: str, key: str, data: Optional[bytes] = None) -> str:
        head = S3ClientManager.safe_head_object(bucket, key)
        if head:
            ct = (head.get("ContentType") or "").lower()
            if "pdf" in ct:
                return "pdf"
            if ct.startswith("image/"):
                return "image"
        if data and magic:
            try:
                m = magic.Magic(mime=True)
                ct2 = (m.from_buffer(data) or "").lower()
                if "pdf" in ct2:
                    return "pdf"
                if ct2.startswith("image/"):
                    return "image"
            except Exception:
                pass
        path = key.lower().split("?")[0]
        if path.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")):
            return "image"
        if path.endswith(".pdf"):
            return "pdf"
        return "unknown"

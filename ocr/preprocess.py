from __future__ import annotations
import io
from PIL import Image, ImageOps, ImageFilter
from .backends import OCRBackend

try:
    from pdf2image import convert_from_bytes  # type: ignore
except Exception:
    convert_from_bytes = None


class ImagePreprocessor:
    @staticmethod
    def preprocess(image_bytes: bytes, scale: float = 1.2, sharpen: bool = True) -> bytes:
        with Image.open(io.BytesIO(image_bytes)) as im:
            im = im.convert("L")
            im = ImageOps.autocontrast(im)
            if sharpen:
                im = im.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            if scale != 1.0:
                w, h = im.size
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return buf.getvalue()


class PDFRasterFallback:
    def __init__(self, backend: OCRBackend, dpi: int = 300, max_pages: int = 15):
        self.backend = backend
        self.dpi = dpi
        self.max_pages = max_pages

    def extract_text(self, pdf_bytes: bytes) -> str:
        if not convert_from_bytes:
            raise RuntimeError("pdf2image not installed for PDF fallback")
        images = convert_from_bytes(pdf_bytes, dpi=self.dpi)[: self.max_pages]
        all_text = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            text = self.backend.extract_text(buf.read())
            all_text.append(text)
        return "\n".join(all_text)
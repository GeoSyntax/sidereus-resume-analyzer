"""Optional OCR for scanned / image-only PDFs.

Text-layer PDFs are parsed directly by ``pdf_parser``; that is fast and needs no
model. When a PDF has no selectable text (a scan or exported image), we render
each page to a PNG with PyMuPDF and send the images to a vision-capable model.

PyMuPDF ships as a cp39-abi3 wheel (~20 MB) rather than the ~250 MB that a local
OCR engine like RapidOCR/onnxruntime would add, so the FC package stays small
and OCR stays consistent with the "AI-powered" theme of the project.
"""

import base64

from app.config import settings
from app.services.ai_client import AIClient


class OcrUnavailable(RuntimeError):
    """Raised when OCR is requested but not configured/installed."""


def render_pdf_to_images(pdf_bytes: bytes, dpi: int, max_pages: int) -> list[str]:
    """Render up to ``max_pages`` PDF pages to base64-encoded PNGs.

    Imported lazily so the service still boots when PyMuPDF is absent (e.g. a
    minimal local install); callers treat an empty list as "cannot OCR".
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - depends on deploy package
        raise OcrUnavailable("PyMuPDF (fitz) is not installed.") from exc

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    images: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            if len(images) >= max_pages:
                break
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            images.append(base64.b64encode(pixmap.tobytes("png")).decode("ascii"))
    return images


async def ocr_pdf(pdf_bytes: bytes, ai_client: AIClient | None = None) -> str | None:
    """OCR a scanned PDF and return recognized text, or None if unavailable.

    Returns None (rather than raising) on any failure so the upload endpoint can
    surface a clean "needs OCR" message instead of a 500.
    """
    if not settings.ocr_enabled:
        return None

    try:
        images = render_pdf_to_images(pdf_bytes, settings.ocr_dpi, settings.ocr_max_pages)
    except OcrUnavailable:
        return None
    if not images:
        return None

    client = ai_client or AIClient()
    return await client.ocr_images(images)

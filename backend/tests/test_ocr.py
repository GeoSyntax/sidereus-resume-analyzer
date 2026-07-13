"""OCR service tests.

We do not call a real vision model here. Instead we verify the two things that
must hold without a network: PyMuPDF renders pages to PNG bytes, and ocr_pdf
returns None (never raises) when OCR is disabled, so the upload path can surface
a clean 422 instead of a 500.
"""

import asyncio
import base64

from app.config import settings
from app.services import ocr


def test_ocr_pdf_returns_none_when_disabled(scanned_pdf_bytes, monkeypatch):
    # Force OCR off regardless of the local .env.
    monkeypatch.setattr(settings, "openai_vision_model", None, raising=False)
    monkeypatch.setattr(settings, "openai_api_key", None, raising=False)

    result = asyncio.run(ocr.ocr_pdf(scanned_pdf_bytes))

    assert result is None


def test_render_pdf_to_images_produces_png(scanned_pdf_bytes):
    images = ocr.render_pdf_to_images(scanned_pdf_bytes, dpi=100, max_pages=5)

    assert len(images) == 1
    # Each item is base64; decoding must yield a PNG signature.
    decoded = base64.b64decode(images[0])
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pdf_respects_max_pages(multipage_pdf_bytes):
    images = ocr.render_pdf_to_images(multipage_pdf_bytes, dpi=72, max_pages=1)

    assert len(images) == 1

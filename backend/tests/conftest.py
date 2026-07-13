"""Shared test fixtures.

PDF fixtures are built in-memory with PyMuPDF (already a runtime dependency), so
tests need no binary fixture files and no network. Text-layer PDFs exercise the
normal parse path; a blank page stands in for a scanned/image-only PDF (no
selectable text) to exercise the OCR-fallback branch without calling a model.
"""

import fitz  # PyMuPDF
import pytest


def _pdf_from_pages(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def text_pdf_bytes():
    """A single-page English text-layer PDF."""
    return _pdf_from_pages(
        [
            "Name: John Smith\n"
            "Phone: 13800001234\n"
            "Email: john.smith@example.com\n"
            "Address: Beijing Haidian District\n"
            "Target: Python Backend Intern\n"
            "Skills: Python FastAPI Redis Docker\n"
            "3 years of backend development experience."
        ]
    )


@pytest.fixture
def multipage_pdf_bytes():
    """A two-page PDF; text must be collected across both pages."""
    return _pdf_from_pages(
        [
            "Name: Jane Doe\nPhone: 13900002345\nEmail: jane@example.com",
            "Projects\nBuilt a resume API with FastAPI and Redis.\nSkills: Python SQL Git",
        ]
    )


@pytest.fixture
def scanned_pdf_bytes():
    """A valid PDF whose single page has no text layer (stands in for a scan)."""
    return _pdf_from_pages([""])


@pytest.fixture
def not_a_pdf_bytes():
    return b"this is definitely not a pdf file"

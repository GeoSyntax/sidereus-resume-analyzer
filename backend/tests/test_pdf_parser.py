import pytest

from app.services.pdf_parser import (
    PdfParseError,
    ScannedPdfError,
    extract_pdf_text,
    finalize_text,
    parse_pdf_bytes,
)


def test_extract_text_reads_all_pages(multipage_pdf_bytes):
    raw_text, page_count = extract_pdf_text(multipage_pdf_bytes)

    assert page_count == 2
    # Content from both pages must be present.
    assert "Jane Doe" in raw_text
    assert "FastAPI" in raw_text


def test_parse_text_pdf_returns_cleaned_sections(text_pdf_bytes):
    cleaned, page_count, sections = parse_pdf_bytes(text_pdf_bytes)

    assert page_count == 1
    assert "John Smith" in cleaned
    assert sections


def test_scanned_pdf_raises_scanned_error_with_page_count(scanned_pdf_bytes):
    with pytest.raises(ScannedPdfError) as exc_info:
        extract_pdf_text(scanned_pdf_bytes)

    # Page count is carried on the exception so the OCR path can still report it.
    assert exc_info.value.page_count == 1


def test_invalid_bytes_raise_plain_parse_error(not_a_pdf_bytes):
    with pytest.raises(PdfParseError) as exc_info:
        extract_pdf_text(not_a_pdf_bytes)

    # Must not be classified as "scanned" — this is genuinely invalid input.
    assert not isinstance(exc_info.value, ScannedPdfError)


def test_finalize_text_drops_page_noise_and_splits_sections():
    raw = "Line one\n1 / 3\n\nSecond block here"
    cleaned, sections = finalize_text(raw)

    assert "1 / 3" not in cleaned
    assert len(sections) == 2

from io import BytesIO

from pypdf import PdfReader

from app.services.text_cleaner import clean_text, split_sections


class PdfParseError(ValueError):
    """The uploaded bytes are not a usable PDF at all."""


class ScannedPdfError(PdfParseError):
    """The PDF is valid but has no selectable text layer (needs OCR).

    Carries ``page_count`` so a caller that falls back to OCR can still report
    how many pages the document has.
    """

    def __init__(self, message: str, page_count: int = 0) -> None:
        super().__init__(message)
        self.page_count = page_count


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Return the concatenated text layer and page count of a PDF.

    Raises:
        PdfParseError: the bytes are not a parseable PDF.
        ScannedPdfError: the PDF is valid but has no selectable text (a scan),
            so the caller can decide whether to OCR it.
    """
    if not pdf_bytes.startswith(b"%PDF"):
        raise PdfParseError("Uploaded file is not a valid PDF document.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises several parser-specific exceptions.
        raise PdfParseError("Failed to parse PDF text.") from exc

    raw_text = "\n\n".join(page_text)
    if not raw_text.strip():
        raise ScannedPdfError(
            "No selectable text was found in the PDF. Scanned resumes need OCR.",
            page_count=page_count,
        )
    return raw_text, page_count


def finalize_text(raw_text: str) -> tuple[str, list[str]]:
    """Clean raw text and split it into sections.

    Shared by the text-layer path and the OCR path so both produce identically
    cleaned, sectioned output before extraction.
    """
    cleaned = clean_text(raw_text)
    return cleaned, split_sections(cleaned)


def parse_pdf_bytes(pdf_bytes: bytes) -> tuple[str, int, list[str]]:
    """Convenience wrapper: parse a text-layer PDF into (cleaned_text, page_count, sections)."""
    raw_text, page_count = extract_pdf_text(pdf_bytes)
    cleaned, sections = finalize_text(raw_text)
    return cleaned, page_count, sections

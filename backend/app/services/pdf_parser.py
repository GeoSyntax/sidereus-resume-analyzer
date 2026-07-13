from io import BytesIO

from pypdf import PdfReader

from app.services.text_cleaner import clean_text, split_sections


class PdfParseError(ValueError):
    pass


def parse_pdf_bytes(pdf_bytes: bytes) -> tuple[str, int, list[str]]:
    if not pdf_bytes.startswith(b"%PDF"):
        raise PdfParseError("Uploaded file is not a valid PDF document.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_text = []
        for page in reader.pages:
            page_text.append(page.extract_text() or "")
    except Exception as exc:  # pypdf raises several parser-specific exceptions.
        raise PdfParseError("Failed to parse PDF text.") from exc

    raw_text = "\n\n".join(page_text)
    cleaned = clean_text(raw_text)
    if not cleaned:
        raise PdfParseError("No selectable text was found in the PDF. Scanned resumes need OCR.")

    return cleaned, len(reader.pages), split_sections(cleaned)


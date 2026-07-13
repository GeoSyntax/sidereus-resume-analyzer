"""API tests for the upload, stateless analyze, and error/edge paths.

These run with the rule engine only (no OPENAI_API_KEY in CI), so LLM extraction
and OCR are disabled. That lets us assert the deterministic rule behavior and the
clean 422 a scanned PDF returns when no vision model is configured.
"""

import io

from fastapi.testclient import TestClient

from app.main import app, cache


client = TestClient(app)


def _upload(pdf_bytes: bytes, filename: str = "resume.pdf"):
    return client.post(
        "/api/v1/resumes",
        files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
    )


def test_upload_single_page_text_pdf(text_pdf_bytes):
    response = _upload(text_pdf_bytes)

    assert response.status_code == 201
    payload = response.json()
    assert payload["page_count"] == 1
    assert payload["source"] == "text"
    assert payload["profile"]["basic_info"]["email"] == "john.smith@example.com"
    assert "Python" in payload["profile"]["skills"]


def test_upload_collects_text_across_multiple_pages(multipage_pdf_bytes):
    response = _upload(multipage_pdf_bytes)

    assert response.status_code == 201
    payload = response.json()
    assert payload["page_count"] == 2
    # Second-page content must be present in the cleaned text.
    assert "FastAPI" in payload["cleaned_text"] or "FastAPI" in payload["profile"]["skills"]


def test_upload_is_cached_on_repeat(text_pdf_bytes):
    first = _upload(text_pdf_bytes)
    second = _upload(text_pdf_bytes)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["cached"] is True


def test_scanned_pdf_without_ocr_returns_422(scanned_pdf_bytes, monkeypatch):
    """No text layer + no vision model configured => clear 422, not 500.

    Force OCR off so the outcome does not depend on whether a vision model is
    configured in the local .env; CI has no key and must see the same 422.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None, raising=False)
    monkeypatch.setattr(settings, "openai_vision_model", None, raising=False)

    response = _upload(scanned_pdf_bytes)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "HTTP_ERROR"


def test_non_pdf_extension_is_rejected(text_pdf_bytes):
    response = client.post(
        "/api/v1/resumes",
        files={"file": ("resume.txt", io.BytesIO(text_pdf_bytes), "text/plain")},
    )

    assert response.status_code == 400


def test_corrupt_pdf_returns_422(not_a_pdf_bytes):
    response = _upload(not_a_pdf_bytes)

    assert response.status_code == 422


def test_oversized_upload_is_rejected(text_pdf_bytes):
    from app.config import settings

    padded = text_pdf_bytes + b"0" * (settings.max_upload_bytes + 1)
    response = _upload(padded)

    assert response.status_code == 413


def test_stateless_analyze_parse_only(text_pdf_bytes):
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(text_pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["resume"]["source"] == "text"
    assert payload["match"] is None


def test_stateless_analyze_with_job(text_pdf_bytes):
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(text_pdf_bytes), "application/pdf")},
        data={"job_description": "Python backend intern, FastAPI, Redis, Docker required."},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["match"] is not None
    assert 0 <= payload["match"]["overall_score"] <= 100
    assert "Python" in payload["match"]["matched_keywords"]


def test_get_resume_after_upload_roundtrip(text_pdf_bytes):
    uploaded = _upload(text_pdf_bytes).json()
    resume_id = uploaded["resume_id"]

    fetched = client.get(f"/api/v1/resumes/{resume_id}")

    assert fetched.status_code == 200
    assert fetched.json()["resume_id"] == resume_id


def test_match_missing_resume_returns_404():
    response = client.post(
        "/api/v1/resumes/deadbeefdeadbeef/matches",
        json={"job_description": "Python backend intern with FastAPI experience."},
    )

    assert response.status_code == 404


def test_stateless_analyze_short_job_returns_422(text_pdf_bytes):
    """A non-empty job_description under 10 chars is a client error, not a
    silent parse-only. Regression guard for the Form() field boundary."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(text_pdf_bytes), "application/pdf")},
        data={"job_description": "too short"},
    )

    assert response.status_code == 422


def test_stateless_analyze_blank_job_is_parse_only(text_pdf_bytes):
    """Whitespace-only job_description is treated as "no job": parse succeeds and
    match stays None rather than raising."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(text_pdf_bytes), "application/pdf")},
        data={"job_description": "   \n  "},
    )

    assert response.status_code == 201
    assert response.json()["match"] is None


def test_stateless_analyze_collects_multipage_text(multipage_pdf_bytes):
    """The stateless path must read every page, same as /resumes."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(multipage_pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["resume"]["page_count"] == 2
    assert "FastAPI" in payload["resume"]["cleaned_text"]


def test_stateless_analyze_rejects_non_pdf(not_a_pdf_bytes):
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("resume.pdf", io.BytesIO(not_a_pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 422

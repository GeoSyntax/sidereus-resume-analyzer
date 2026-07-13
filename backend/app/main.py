import hashlib
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    AnalyzeResult,
    JobAnalysis,
    JobAnalysisRequest,
    JobMatchRequest,
    MatchResult,
    ParsedResume,
)
from app.services.cache import CacheClient
from app.services.extractor import ResumeExtractor
from app.services.matcher import ResumeMatcher, analyze_job
from app.services.ocr import ocr_pdf
from app.services.pdf_parser import PdfParseError, ScannedPdfError, extract_pdf_text, finalize_text


app = FastAPI(
    title="AI Resume Analyzer API",
    version="1.1.0",
    description="PDF resume parsing, structured extraction, and job matching service.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = CacheClient()
extractor = ResumeExtractor()
matcher = ResumeMatcher()


@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


def _validate_pdf_upload(file: UploadFile, content: bytes) -> None:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only single PDF resume upload is supported.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"PDF size exceeds {settings.max_upload_mb} MB.")


async def parse_resume_bytes(content: bytes, file_name: str) -> ParsedResume:
    """Parse PDF bytes into a structured resume, using OCR for scanned files.

    Text-layer PDFs are parsed directly. When no selectable text is found the
    file is treated as a scan: if a vision model is configured we OCR it, then
    run the same cleaning/extraction pipeline; otherwise we raise so the caller
    can return a clear 422.
    """
    file_sha = hashlib.sha256(content).hexdigest()
    resume_id = file_sha[:16]
    cache_key = f"resume:{file_sha}"

    cached = cache.get(cache_key)
    if cached:
        parsed = ParsedResume.model_validate(cached)
        parsed.cached = True
        return parsed

    source = "text"
    try:
        raw_text, page_count = extract_pdf_text(content)
    except ScannedPdfError as exc:
        ocr_text = await ocr_pdf(content)
        if not ocr_text:
            raise HTTPException(
                status_code=422,
                detail="No selectable text found. Scanned resume OCR is not available (configure a vision model).",
            ) from exc
        raw_text = ocr_text
        page_count = exc.page_count
        source = "ocr"
    except PdfParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cleaned_text, sections = finalize_text(raw_text)
    if not cleaned_text:
        raise HTTPException(status_code=422, detail="Resume text was empty after cleaning.")

    profile = await extractor.extract(cleaned_text)
    parsed = ParsedResume(
        resume_id=resume_id,
        file_name=file_name,
        file_sha256=file_sha,
        page_count=page_count,
        cleaned_text=cleaned_text,
        sections=sections,
        profile=profile,
        source=source,
    )
    payload = parsed.model_dump(mode="json")
    cache.set(cache_key, payload)
    cache.set(f"resume:id:{resume_id}", payload)
    return parsed


async def match_resume_to_job(resume: ParsedResume, job_description: str) -> MatchResult:
    """Score a resume against a job description, reusing the match cache."""
    job_hash = hashlib.sha256(job_description.encode("utf-8")).hexdigest()[:16]
    cache_key = f"match:{resume.resume_id}:{job_hash}"

    cached = cache.get(cache_key)
    if cached:
        result = MatchResult.model_validate(cached)
        result.cached = True
        return result

    result = await matcher.match(resume, job_description)
    cache.set(cache_key, result.model_dump(mode="json"))
    return result


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_enabled": settings.llm_enabled,
        "ocr_enabled": settings.ocr_enabled,
        "cache": "redis" if settings.redis_url else "memory",
    }


@app.get("/api/v1/capabilities")
async def capabilities() -> dict[str, object]:
    return {
        "pdf": {"single_upload": True, "multi_page": True, "ocr": settings.ocr_enabled, "max_upload_mb": settings.max_upload_mb},
        "extraction": {"rules": True, "llm_enabled": settings.llm_enabled},
        "matching": {"rules": True, "llm_enhanced": settings.llm_enabled},
        "cache": "redis" if settings.redis_url else "memory",
        "deployment": "FastAPI ASGI, compatible with Aliyun FC custom runtime",
    }


@app.post("/api/v1/resumes", response_model=ParsedResume, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile = File(...)) -> ParsedResume:
    content = await file.read()
    _validate_pdf_upload(file, content)
    return await parse_resume_bytes(content, file.filename)


@app.get("/api/v1/resumes/{resume_id}", response_model=ParsedResume)
async def get_resume(resume_id: str) -> ParsedResume:
    cached = cache.get(f"resume:id:{resume_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Resume not found or cache expired.")
    parsed = ParsedResume.model_validate(cached)
    parsed.cached = True
    return parsed


@app.post("/api/v1/jobs/analyze", response_model=JobAnalysis)
async def analyze_job_description(request: JobAnalysisRequest) -> JobAnalysis:
    return analyze_job(request.job_description)


@app.post("/api/v1/resumes/{resume_id}/matches", response_model=MatchResult)
async def match_resume(resume_id: str, request: JobMatchRequest) -> MatchResult:
    resume_payload = cache.get(f"resume:id:{resume_id}")
    if not resume_payload:
        raise HTTPException(status_code=404, detail="Resume not found or cache expired. Upload it again.")
    resume = ParsedResume.model_validate(resume_payload)
    return await match_resume_to_job(resume, request.job_description)


@app.post("/api/v1/analyze", response_model=AnalyzeResult, status_code=status.HTTP_201_CREATED)
async def analyze(
    file: UploadFile = File(...),
    job_description: str | None = Form(default=None),
) -> AnalyzeResult:
    """Stateless one-shot: parse a PDF and (optionally) match it to a job in one call.

    This does not depend on server-side session state, so it works reliably on
    Serverless platforms where the next request may hit a different instance.
    Caching still applies as a pure optimization, never a correctness requirement.
    """
    content = await file.read()
    _validate_pdf_upload(file, content)
    resume = await parse_resume_bytes(content, file.filename)

    match = None
    if job_description and job_description.strip():
        jd = job_description.strip()
        if len(jd) < 10:
            raise HTTPException(status_code=422, detail="job_description must be at least 10 characters.")
        match = await match_resume_to_job(resume, jd)

    return AnalyzeResult(resume=resume, match=match)

import hashlib
import time
import uuid

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import JobAnalysis, JobAnalysisRequest, JobMatchRequest, MatchResult, ParsedResume
from app.services.cache import CacheClient
from app.services.extractor import ResumeExtractor
from app.services.matcher import ResumeMatcher, analyze_job
from app.services.pdf_parser import PdfParseError, parse_pdf_bytes


app = FastAPI(
    title="AI Resume Analyzer API",
    version="1.0.0",
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


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_enabled": settings.llm_enabled,
        "cache": "redis" if settings.redis_url else "memory",
    }


@app.get("/api/v1/capabilities")
async def capabilities() -> dict[str, object]:
    return {
        "pdf": {"single_upload": True, "multi_page": True, "ocr": False, "max_upload_mb": settings.max_upload_mb},
        "extraction": {"rules": True, "llm_enabled": settings.llm_enabled},
        "matching": {"rules": True, "llm_enhanced": settings.llm_enabled},
        "cache": "redis" if settings.redis_url else "memory",
        "deployment": "FastAPI ASGI, compatible with Aliyun FC custom runtime",
    }


@app.post("/api/v1/resumes", response_model=ParsedResume, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile = File(...)) -> ParsedResume:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only single PDF resume upload is supported.")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"PDF size exceeds {settings.max_upload_mb} MB.")

    file_sha = hashlib.sha256(content).hexdigest()
    resume_id = file_sha[:16]
    cache_key = f"resume:{file_sha}"
    cached = cache.get(cache_key)
    if cached:
        parsed = ParsedResume.model_validate(cached)
        parsed.cached = True
        return parsed

    try:
        cleaned_text, page_count, sections = parse_pdf_bytes(content)
    except PdfParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    profile = await extractor.extract(cleaned_text)
    parsed = ParsedResume(
        resume_id=resume_id,
        file_name=file.filename,
        file_sha256=file_sha,
        page_count=page_count,
        cleaned_text=cleaned_text,
        sections=sections,
        profile=profile,
    )
    payload = parsed.model_dump(mode="json")
    cache.set(cache_key, payload)
    cache.set(f"resume:id:{resume_id}", payload)
    return parsed


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

    job_hash = hashlib.sha256(request.job_description.encode("utf-8")).hexdigest()[:16]
    cache_key = f"match:{resume_id}:{job_hash}"
    cached = cache.get(cache_key)
    if cached:
        result = MatchResult.model_validate(cached)
        result.cached = True
        return result

    resume = ParsedResume.model_validate(resume_payload)
    result = await matcher.match(resume, request.job_description)
    cache.set(cache_key, result.model_dump(mode="json"))
    return result

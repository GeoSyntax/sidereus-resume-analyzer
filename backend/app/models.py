from pydantic import BaseModel, EmailStr, Field


class BasicInfo(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None


class JobIntention(BaseModel):
    target_role: str | None = None
    expected_salary: str | None = None


class ProjectExperience(BaseModel):
    name: str | None = None
    role: str | None = None
    description: str
    technologies: list[str] = Field(default_factory=list)


class BackgroundInfo(BaseModel):
    years_of_experience: float | None = None
    education: list[str] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    job_intention: JobIntention = Field(default_factory=JobIntention)
    background: BackgroundInfo = Field(default_factory=BackgroundInfo)
    skills: list[str] = Field(default_factory=list)
    summary: str | None = None
    extraction_method: str = "rules"


class ParsedResume(BaseModel):
    resume_id: str
    file_name: str
    file_sha256: str
    page_count: int
    cleaned_text: str
    sections: list[str] = Field(default_factory=list)
    profile: ResumeProfile
    cached: bool = False


class JobMatchRequest(BaseModel):
    job_description: str = Field(..., min_length=10, max_length=12000)


class JobAnalysis(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    seniority_hint: str | None = None
    education_hint: str | None = None


class MatchResult(BaseModel):
    resume_id: str
    job_analysis: JobAnalysis
    overall_score: int = Field(..., ge=0, le=100)
    skill_score: int = Field(..., ge=0, le=100)
    experience_score: int = Field(..., ge=0, le=100)
    education_score: int = Field(..., ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    scoring_method: str = "rules"
    cached: bool = False


class ErrorResponse(BaseModel):
    error: dict[str, object]


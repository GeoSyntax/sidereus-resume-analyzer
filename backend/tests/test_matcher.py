from app.models import BackgroundInfo, BasicInfo, ParsedResume, ResumeProfile
from app.services.keywords import extract_keywords
from app.services.matcher import analyze_job, score_by_rules


def test_matcher_scores_skills_and_missing_keywords():
    resume = ParsedResume(
        resume_id="abc123",
        file_name="resume.pdf",
        file_sha256="abc123",
        page_count=1,
        cleaned_text="Python FastAPI Redis React pytest 2年后端开发经验 本科",
        profile=ResumeProfile(
            basic_info=BasicInfo(name="张三"),
            background=BackgroundInfo(years_of_experience=2, education=["本科 计算机科学"], projects=[]),
            skills=["Python", "FastAPI", "Redis", "React", "pytest"],
        ),
    )
    jd = "Python 后端实习生，要求 FastAPI、Redis、Docker、RESTful API，本科，1年经验。"

    result = score_by_rules(resume, jd)

    assert result.overall_score >= 60
    assert "Python" in result.matched_keywords
    assert "Docker" in result.missing_keywords
    assert result.experience_score >= 80


def test_synonyms_collapse_to_single_canonical_keyword():
    """A JD naming 阿里云函数计算/缓存 must not emit both the raw Chinese term
    and its normalized synonym (regression for keyword explosion)."""
    keywords = extract_keywords("熟悉阿里云函数计算，了解 Redis 缓存与云函数部署。")

    assert "Aliyun FC" in keywords
    assert "Cache" in keywords
    # The raw Chinese synonyms must be collapsed, not listed alongside.
    assert "函数计算" not in keywords
    assert "云函数" not in keywords
    assert "缓存" not in keywords


def test_job_analysis_keywords_are_deduplicated():
    analysis = analyze_job("Python 后端，阿里云函数计算 FC，Serverless 部署，Redis 缓存。")

    # No duplicate canonical keywords in the analysis output.
    assert len(analysis.keywords) == len(set(analysis.keywords))
    assert "Aliyun FC" in analysis.keywords


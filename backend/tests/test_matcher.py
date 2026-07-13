from app.models import BackgroundInfo, BasicInfo, ParsedResume, ResumeProfile
from app.services.matcher import score_by_rules


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


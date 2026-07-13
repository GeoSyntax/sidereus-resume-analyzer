import pytest

from app.services.extractor import extract_by_rules


SAMPLE_RESUME = """
张三
电话: 138 0000 1234
邮箱: zhangsan@example.com
地址: 北京市海淀区
求职意向: Python 后端实习生
期望薪资: 150-200元/天

教育经历
北京大学 本科 计算机科学与技术

项目经历
1. 智能简历分析系统
使用 Python、FastAPI、Redis、React 实现 PDF 简历解析和岗位匹配。

技能
Python FastAPI Redis Docker React SQL Git pytest
2年后端开发经验
"""


def test_rule_extractor_gets_required_fields():
    profile = extract_by_rules(SAMPLE_RESUME)

    assert profile.basic_info.name == "张三"
    assert profile.basic_info.phone == "13800001234"
    assert profile.basic_info.email == "zhangsan@example.com"
    assert "北京" in profile.basic_info.address
    assert profile.job_intention.target_role == "Python 后端实习生"
    assert profile.background.years_of_experience == pytest.approx(2)
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert profile.background.projects


def test_project_title_is_not_repeated_in_description():
    """The project title must be a short name, not the full first line, and the
    description must not simply restate the title (the pre-fix redundancy)."""
    profile = extract_by_rules(SAMPLE_RESUME)

    project = profile.background.projects[0]
    assert project.name == "智能简历分析系统"
    assert not project.description.startswith(project.name)
    assert "FastAPI" in project.description


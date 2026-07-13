"""Rule-extractor tests for Chinese resumes and the name cross-line regression.

These exercise ``extract_by_rules`` directly (no model), so they are fast and
deterministic and run in CI without an API key.
"""

from app.services.extractor import extract_by_rules


CHINESE_RESUME = """
姓名：李娜
电话：13900139000
邮箱：lina@example.com
现居：上海市浦东新区
求职意向：后端开发工程师
期望薪资：20k-25k
工作经验：3年
学历：硕士 北京大学 计算机
项目经历
一、电商后台：负责接口设计、数据库优化、缓存设计。
技能：熟悉服务端开发、接口设计、数据库、缓存、部署
"""


def test_chinese_resume_basic_fields():
    profile = extract_by_rules(CHINESE_RESUME)

    assert profile.basic_info.name == "李娜"
    assert profile.basic_info.phone == "13900139000"
    assert profile.basic_info.email == "lina@example.com"
    assert profile.basic_info.address and "上海" in profile.basic_info.address
    assert profile.job_intention.target_role and "后端" in profile.job_intention.target_role
    assert profile.job_intention.expected_salary and "20k" in profile.job_intention.expected_salary
    assert profile.background.years_of_experience == 3.0
    assert profile.background.education


def test_name_label_does_not_swallow_next_line():
    """Regression: the labeled-name regex must stop at the newline.

    Before the fix, ``[...\\s]`` matched the newline and greedily pulled the
    following "电话" line into the captured name ("李娜 电话").
    """
    text = "姓名：李娜\n电话：13900139000\n邮箱：lina@example.com"
    profile = extract_by_rules(text)

    assert profile.basic_info.name == "李娜"


def test_english_name_with_space_is_preserved():
    text = "Name: Zhang Wei\nPhone: 13800001234"
    profile = extract_by_rules(text)

    assert profile.basic_info.name == "Zhang Wei"


def test_missing_fields_do_not_crash():
    """A sparse resume should extract what it can and leave the rest None/empty."""
    profile = extract_by_rules("just some text with no structured fields at all")

    assert profile.basic_info.name is None
    assert profile.basic_info.phone is None
    assert profile.basic_info.email is None
    assert profile.background.years_of_experience is None

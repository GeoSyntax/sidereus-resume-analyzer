import re


TECH_KEYWORDS = {
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "restful": "RESTful",
    "rest": "REST",
    "api": "API",
    "redis": "Redis",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "sql": "SQL",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "serverless": "Serverless",
    "fc": "Aliyun FC",
    "aliyun": "Aliyun",
    "alibaba cloud": "Aliyun",
    "aws": "AWS",
    "linux": "Linux",
    "git": "Git",
    "pytest": "pytest",
    "celery": "Celery",
    "rabbitmq": "RabbitMQ",
    "kafka": "Kafka",
    "nginx": "Nginx",
    "react": "React",
    "vue": "Vue",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "html": "HTML",
    "css": "CSS",
    "openai": "OpenAI",
    "llm": "LLM",
    "rag": "RAG",
    "langchain": "LangChain",
    "nlp": "NLP",
    "pdf": "PDF",
    "pypdf": "pypdf",
    "pandas": "pandas",
    "numpy": "NumPy",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "机器学习": "Machine Learning",
    "深度学习": "Deep Learning",
    "backend": "Backend",
    "back-end": "Backend",
    "fullstack": "Full-stack",
    "full-stack": "Full-stack",
    "后端": "Backend",
    "前端": "Frontend",
    "全栈": "Full-stack",
    "函数计算": "Aliyun FC",
    "阿里云": "Aliyun",
    "缓存": "Cache",
    "简历解析": "Resume Parsing",
}

CHINESE_KEYWORDS = [
    "后端开发",
    "全栈开发",
    "接口设计",
    "数据库",
    "缓存",
    "云函数",
    "函数计算",
    "部署",
    "测试",
    "工程化",
    "数据清洗",
    "文本解析",
    "项目经历",
    "工作流",
    "智能体",
]


def normalize_keyword(keyword: str) -> str:
    key = keyword.strip()
    return TECH_KEYWORDS.get(key.lower(), key)


def extract_keywords(text: str) -> list[str]:
    if not text:
        return []

    lowered = text.lower()
    found: set[str] = set()
    for raw, normalized in TECH_KEYWORDS.items():
        if re.search(rf"(?<![a-z0-9+#.]){re.escape(raw)}(?![a-z0-9+#.])", lowered):
            found.add(normalized)

    for word in CHINESE_KEYWORDS:
        if word in text:
            found.add(word)

    return sorted(found, key=lambda value: value.lower())

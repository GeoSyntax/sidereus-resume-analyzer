# AI Resume Analyzer

AI 赋能的智能简历分析系统，面向 Sidereus AI Python 后端/全栈实习生笔试题实现。项目提供 PDF 简历上传解析、关键信息抽取、岗位关键词分析、匹配度评分、缓存和静态前端页面。

GitHub 仓库：https://github.com/GeoSyntax/sidereus-resume-analyzer

前端演示：https://geosyntax.github.io/sidereus-resume-analyzer/

## 功能

- 上传单个 PDF 简历，解析多页文本并清洗分段
- 抽取姓名、电话、邮箱、地址等必选字段
- 抽取求职意向、期望薪资、工作年限、学历、项目经历和技能关键词
- 根据岗位描述提取关键词并计算匹配度评分
- 支持可选 OpenAI 兼容模型增强抽取与评分；无 API Key 时使用规则引擎降级
- 支持 Redis 缓存；未配置 Redis 时自动使用进程内缓存
- 提供可部署到 GitHub Pages 的静态前端
- 提供阿里云函数计算 FC 自定义运行时部署配置

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic、pypdf、httpx
- 缓存：Redis 可选，内存缓存兜底
- AI：OpenAI Chat Completions 兼容接口可选
- 前端：原生 HTML/CSS/JavaScript，适合 GitHub Pages 静态部署
- 测试：pytest

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── models.py               # 响应与领域模型
│   │   └── services/
│   │       ├── pdf_parser.py        # PDF 文本解析
│   │       ├── text_cleaner.py      # 文本清洗与分段
│   │       ├── extractor.py         # 规则 + LLM 信息抽取
│   │       ├── matcher.py           # 岗位分析与评分
│   │       ├── keywords.py          # 技能关键词词表
│   │       ├── ai_client.py         # OpenAI 兼容调用
│   │       └── cache.py             # Redis/内存缓存
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── bootstrap                   # 阿里云 FC 自定义运行时启动脚本
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── serverless/
│   └── s.yaml                      # Serverless Devs / 阿里云 FC 配置
├── DESIGN.md
└── README.md
```

## 本地运行

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开前端：

```bash
cd frontend
python -m http.server 5173
```

浏览器访问 `http://127.0.0.1:5173`，API Base 使用默认的 `http://127.0.0.1:8000`。

## 环境变量

复制 `backend/.env.example` 为 `backend/.env` 后按需配置：

```bash
APP_ENV=local
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_UPLOAD_MB=8
CACHE_TTL_SECONDS=86400
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
REDIS_URL=
```

说明：

- 不配置 `OPENAI_API_KEY`：系统使用规则抽取和规则评分，可完整演示。
- 配置 `OPENAI_API_KEY`：系统会调用 OpenAI 兼容接口增强简历结构化抽取和匹配评分。
- 不配置 `REDIS_URL`：自动使用内存缓存。

## API

### 健康检查

```http
GET /health
```

### 上传并解析简历

```http
POST /api/v1/resumes
Content-Type: multipart/form-data

file=<resume.pdf>
```

返回字段包含 `resume_id`、`cleaned_text`、`sections`、`profile` 和 `cached`。

### 获取缓存中的简历解析结果

```http
GET /api/v1/resumes/{resume_id}
```

### 岗位匹配评分

```http
POST /api/v1/resumes/{resume_id}/matches
Content-Type: application/json

{
  "job_description": "Python 后端实习生，熟悉 FastAPI、Redis、RESTful API，有 Serverless 部署经验..."
}
```

返回字段包含：

- `overall_score`：综合匹配分
- `skill_score`：技能匹配分
- `experience_score`：经验相关性分
- `education_score`：学历匹配分
- `matched_keywords` / `missing_keywords`
- `recommendations`

## 测试

```bash
pip install -r backend/requirements.txt
pytest
```

## 部署

### 后端部署到阿里云函数计算 FC

1. 安装并配置 Serverless Devs。
2. 根据需要在 `serverless/s.yaml` 中设置 `region`、函数名和环境变量。
3. 确保 `backend/bootstrap` 在 Linux 环境具备执行权限：

```bash
chmod +x backend/bootstrap
```

4. 部署：

```bash
cd serverless
s deploy
```

部署完成后，把函数计算 HTTP 触发器域名填入前端页面的 API Base。

### 前端部署到 GitHub Pages

1. 推送仓库到 GitHub，并确保默认分支为 `main`。
2. 在 GitHub 仓库 Settings -> Pages 中将 Source 设置为 GitHub Actions。
3. `.github/workflows/deploy-frontend.yml` 会把 `frontend/` 发布到 GitHub Pages。
4. 发布后访问 GitHub Pages 地址，在页面右上角 API Base 填入后端服务地址。

## 评分策略

规则评分由三部分加权：

- 技能匹配率：55%，比较岗位关键词与简历技能关键词的交集和缺失项。
- 工作经验相关性：30%，结合岗位要求年限、简历工作年限和项目数量。
- 学历匹配：15%，根据岗位学历要求和简历教育信息估算。

如果启用 LLM，系统会在规则结果基础上请求模型输出结构化 JSON，并通过 Pydantic 校验后再合并，避免模型输出破坏 API 契约。

## 已知限制

- 扫描版 PDF 暂未接入 OCR，当前仅支持可复制文本的 PDF。
- 内存缓存适合本地和单实例演示，生产环境建议配置 Redis。
- LLM 调用会发送简历文本到配置的模型服务，真实生产需要加入用户授权、脱敏和审计。

## 提交信息模板

提交给 Boss 直聘面试官时可使用：

```text
GitHub 仓库地址：https://github.com/GeoSyntax/sidereus-resume-analyzer
线上演示地址：https://geosyntax.github.io/sidereus-resume-analyzer/
姓名与联系方式：<你的姓名 / 手机 / 邮箱>
```

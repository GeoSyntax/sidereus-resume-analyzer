# 评分标准映射

本文档用于面试前快速说明项目如何覆盖笔试评分点。

## 功能完整性 30%

| 要求 | 项目实现 | 说明 |
| --- | --- | --- |
| 单 PDF 上传 | `POST /api/v1/resumes` | 校验扩展名、大小和 PDF magic bytes |
| 多页文本解析 | `pdf_parser.py` | 使用 `pypdf.PdfReader` 遍历 pages |
| 文本清洗分段 | `text_cleaner.py` | 去控制字符、页码噪声、重复空行，按段落切分 |
| 基本信息抽取 | `extractor.py` | 姓名、电话、邮箱、地址规则抽取，LLM 可选增强 |
| 岗位需求分析 | `POST /api/v1/jobs/analyze` | 独立返回岗位关键词、学历和资历提示 |
| 匹配评分 | `POST /api/v1/resumes/{resume_id}/matches` | 技能、经验、学历三项加权 |
| JSON 返回 | `models.py` | Pydantic response model 保证结构 |
| 缓存 | `cache.py` | Redis 可选，内存缓存兜底 |
| 前端页面 | `frontend/` | GitHub Pages 已部署，支持真实 API 和示例模式 |

## 代码质量 25%

- 按职责拆分：API 层、模型层、PDF 解析、清洗、抽取、匹配、缓存、AI client。
- Pydantic 模型约束输入输出，避免接口返回结构漂移。
- `pytest` 覆盖规则抽取、匹配评分、API 能力接口、校验错误格式。
- 前端避免 `innerHTML/eval/document.write`，使用 `textContent` 和 DOM 节点渲染。
- 安全扫描和质量扫描当前通过。

## 工程化实践 20%

- README 包含架构、技术选型、运行、部署、API 和提交信息模板。
- `DESIGN.md` 记录目标、非目标、架构、缓存、AI 安全和已知风险。
- GitHub Actions：
  - `Backend CI`：安装依赖并运行测试。
  - `Deploy frontend to GitHub Pages`：发布 `frontend/`。
- RESTful 路径使用 `/api/v1` 版本前缀。
- 错误响应统一为 `{"error": {"code", "message", "details"}}`。
- 响应头包含 `X-Request-ID` 与 `X-Process-Time-Ms`，便于定位问题。

## 技术深度 15%

| 主题 | 面试说明 |
| --- | --- |
| AI 模型调用 | OpenAI 兼容 Chat Completions，使用 JSON output，Pydantic 校验，失败自动规则降级 |
| Prompt 安全 | 简历/JD 被明确声明为 untrusted data，避免执行文档中的 prompt injection |
| 缓存设计 | Cache-aside，`resume:{sha256}` 避免重复 PDF 解析，`match:{resume_id}:{job_hash}` 避免重复评分 |
| 性能 | PDF 解析结果按 SHA256 复用；匹配按 JD hash 复用；大文件限制默认 8 MB |
| Serverless | FastAPI ASGI + custom runtime `bootstrap`，适配阿里云 FC HTTP 触发器 |
| 可扩展 | 后续可替换 OCR、向量召回、可配置技能词表、异步任务队列 |

## 加分项 10%

- 求职意向、期望薪资、工作年限、学历、项目经历抽取。
- Redis 缓存可选。
- LLM 增强抽取与评分可选。
- GitHub Pages 已部署。
- 前端公开示例模式降低评审验收门槛。
- 技术面试文档已准备，能解释架构、权衡和扩展方案。

## 当前已知边界

- 扫描版 PDF 需要 OCR，当前只处理可复制文本 PDF。
- 规则词表有限，生产环境应引入可配置词表或向量检索。
- 在线 GitHub Pages 只托管前端，完整线上演示还需部署后端 API 到阿里云 FC。


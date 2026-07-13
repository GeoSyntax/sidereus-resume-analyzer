# DESIGN

## 目标

实现一个可在 24 小时笔试周期内完成、可运行、可解释、可部署的智能简历分析系统。系统优先保证必选功能完整：PDF 上传解析、关键信息抽取、岗位匹配评分、JSON 返回、缓存和前端页面。

## 非目标

- 不实现用户账号、权限系统和候选人数据库。
- 不处理批量简历上传。
- 不对扫描版 PDF 做 OCR。
- 不把 LLM 作为唯一依赖，避免没有 API Key 时无法验收。

## 架构

```text
Browser
  |
  | static HTML/CSS/JS
  v
FastAPI REST API
  |
  +-- PDF Parser      pypdf extracts selectable text
  +-- Text Cleaner    normalizes whitespace and sections
  +-- Extractor       rules first, optional LLM enhancement
  +-- Matcher         keyword scoring, optional LLM review
  +-- Cache           Redis if configured, memory fallback
```

## 核心组件

- `app.main`：API 编排层，负责上传校验、缓存读写、错误响应和 CORS。
- `pdf_parser`：解析 PDF 字节流，返回清洗文本、页数和分段。
- `extractor`：用正则和关键词规则抽取必选字段，并可调用 LLM 补全。
- `matcher`：分析岗位关键词，计算技能、经验、学历和综合评分。
- `cache`：实现 cache-aside 模式，Redis 不可用时回退到本地内存。
- `frontend`：静态页面，支持切换 API Base，适合部署到 GitHub Pages。

## 关键设计决策

| 决策 | 理由 | 取舍 |
| --- | --- | --- |
| FastAPI | OpenAPI 自动文档、类型校验强、实现 RESTful API 快 | 需要 ASGI 运行时 |
| 规则引擎作为基础能力 | 无模型密钥也能演示，面试可解释 | 准确率低于领域微调模型 |
| LLM 作为增强能力 | 满足 AI 加分项，可提升复杂简历抽取效果 | 需要 API Key，存在调用成本 |
| Redis 可选 | 符合缓存加分项，同时降低本地运行门槛 | 内存缓存不适合多实例 |
| 静态前端 | 部署简单，GitHub Pages 即可验收 | 不适合复杂状态管理 |

## API 设计

资源路径采用 `/api/v1` 前缀：

- `POST /api/v1/resumes`：创建简历解析结果。
- `GET /api/v1/resumes/{resume_id}`：读取缓存中的解析结果。
- `POST /api/v1/resumes/{resume_id}/matches`：基于已解析简历创建岗位匹配结果。

错误响应统一为：

```json
{
  "error": {
    "code": "HTTP_ERROR",
    "message": "Only single PDF resume upload is supported."
  }
}
```

## 缓存设计

缓存键：

- `resume:{sha256}`：避免重复解析相同 PDF。
- `resume:id:{resume_id}`：支持后续按 ID 查询。
- `match:{resume_id}:{job_hash}`：避免重复计算相同岗位描述。

缓存策略：

- 采用 cache-aside。
- TTL 默认 86400 秒。
- Redis 异常时自动降级为内存缓存。

## AI 安全与可靠性

- 简历和岗位描述在 prompt 中明确标记为不可信输入。
- 要求模型返回 JSON，并使用 Pydantic 进行结构校验。
- LLM 失败时回退到规则结果，不影响接口可用性。
- README 明确说明生产环境需要用户授权、脱敏和审计。

## 已知风险

- PDF 解析依赖文本层，扫描件需要 OCR 扩展。
- 关键词词表有限，后续可改为可配置词表或向量召回。
- 当前评分权重是启发式规则，生产场景需要结合人工标注数据评估。


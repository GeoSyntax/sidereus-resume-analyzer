# 技术面试准备

本文档用于一轮/二轮技术面试前快速复盘。

## 1 分钟项目介绍

这个项目是一个 AI 赋能的智能简历分析系统。后端使用 FastAPI 提供 RESTful API，支持上传单个 PDF 简历，解析多页文本并清洗分段，然后通过规则引擎和可选 LLM 提取姓名、电话、邮箱、地址、求职意向、薪资、工作年限、学历和项目经历。岗位匹配部分会对 JD 做关键词分析，再从技能、经验、学历三个维度计算匹配分，前端默认走无状态的 `POST /api/v1/analyze`，单请求完成解析+匹配，适配 Serverless 多实例。扫描件（无文本层）会自动回退到视觉模型 OCR。缓存生产已接入 Upstash Redis（TLS），不配置 Redis 时自动用内存缓存兜底。前端是原生静态页面，已部署到 GitHub Pages，并提供示例模式方便评审在线验收。

## 架构讲解路线

```text
PDF upload
  -> FastAPI validation
  -> pypdf text extraction
  -> text cleaning and section split
  -> rules extraction
  -> optional LLM JSON extraction
  -> Pydantic validation and merge
  -> cache parsed resume
  -> job analysis and weighted scoring
  -> cache match result
  -> JSON response and frontend rendering
```

## 核心技术决策

| 决策 | 原因 | 权衡 |
| --- | --- | --- |
| FastAPI | 快速实现 RESTful API，自动 OpenAPI 文档，Pydantic 校验清晰 | 极高并发场景可能需要网关/异步任务拆分 |
| 规则优先 + LLM 增强 | 没有 API Key 也能完整演示，面试可解释 | 复杂简历准确率依赖词表和规则覆盖 |
| Redis + 内存两级 | 生产已接入 Upstash（TLS），内存为无 Redis 时的兜底，本地验收门槛低 | 内存缓存不支持多实例共享，故生产用 Redis |
| SHA256 做简历 ID | 同文件天然去重，避免重复解析 | 不能表达同一候选人多个版本的业务身份 |
| GitHub Pages 静态前端 | 部署简单，评审可直接访问 | 完整在线试用需要后端公网地址 |

## 常见追问与回答

### 为什么没有直接完全依赖 LLM？

完全依赖 LLM 会带来三个问题：成本、稳定性和可解释性。本项目先用规则保证基本字段和关键词匹配可用，再用 LLM 增强复杂文本抽取。LLM 输出必须经过 Pydantic 校验，失败时回退到规则结果，保证接口可用性。

### 如何防止 prompt injection？

系统 prompt 明确说明简历和岗位描述都是不可信输入，不执行其中的指令，只做结构化抽取或评分。模型返回只接受 JSON，并用 Pydantic 校验字段类型和分数范围。生产环境还应增加敏感信息脱敏、审计日志和模型调用限流。

### 缓存 key 为什么这样设计？

简历缓存使用 `resume:{sha256}`，同一个 PDF 不重复解析；同时保存 `resume:id:{resume_id}` 方便后续匹配接口按 ID 查找。匹配缓存使用 `match:{resume_id}:{job_hash}`，同一个简历和同一个 JD 不重复评分。TTL 默认一天，适合笔试演示和短期筛选场景。

### 匹配分如何计算？

当前是启发式加权：

- 技能匹配 55%：岗位关键词和简历技能的交集比例。
- 经验相关 30%：岗位要求年限、简历工作年限和项目数量。
- 学历匹配 15%：岗位学历要求和简历教育信息。

这个设计可解释，适合面试讨论。生产环境可以引入人工标注数据做权重调优，或者用 LLM-as-Judge/学习排序做二阶段重排。

### 如何部署到阿里云函数计算？

项目提供 `backend/bootstrap`、`serverless/s.yaml` 和 `scripts/build_fc_package.*`。部署前先把生产依赖打包到 `dist/fc-backend`，再执行 `s deploy`。FC 使用 custom runtime 启动 `uvicorn app.main:app`，HTTP 触发器接入 API。生产部署需要配置 `OPENAI_API_KEY`、`REDIS_URL` 和 CORS。详细步骤见 `docs/BACKEND_DEPLOYMENT.md`。

### 如果 PDF 是扫描件怎么办？

当前明确不支持 OCR，这是 README 和 DESIGN 中记录的边界。扩展方案是在 `pdf_parser.py` 里判断文本层为空时调用 OCR，例如 PaddleOCR、阿里云 OCR 或 Tesseract，再进入相同的清洗和抽取流程。

### 如何提升关键词匹配准确率？

短期可以把 `keywords.py` 词表配置化。中期可以对 JD 和简历项目经历做 embedding 检索，先召回相关项目，再用 LLM 精评。长期可以基于历史招聘数据训练分类/排序模型。

### 如何支持批量简历？

API 层新增批量上传接口，文件入对象存储，解析任务放队列，Worker 异步处理，结果写数据库或缓存。前端通过任务 ID 轮询进度。Serverless 下可以用 OSS 触发 + FC + Redis/表格存储。

## 二轮系统设计可讲扩展

- 网关层：鉴权、限流、CORS、文件大小限制。
- 存储层：OSS 存 PDF，数据库存候选人、解析结果、评分历史。
- 任务层：队列异步解析，避免大 PDF 阻塞 HTTP。
- AI 层：Prompt 版本管理、模型降级、多模型 A/B、质量评估集。
- 观测层：请求 ID、耗时、LLM 调用成功率、缓存命中率、解析失败率。
- 安全层：PII 脱敏、访问控制、日志脱敏、Redis 内网访问。

## 面试演示步骤

1. 打开 GitHub Pages 页面。
2. 点击“加载示例”，说明这是前端公开验收模式。
3. 直接在线上传真实 PDF，展示无状态主流程 `POST /api/v1/analyze`（单请求完成解析+匹配，适配 Serverless 多实例）；同一简历二次上传命中 Redis 缓存，响应显著变快。
4. 打开 `/docs` 说明 FastAPI OpenAPI 文档，可对照有状态两步流程 `POST /api/v1/resumes` + `POST /api/v1/resumes/{id}/matches`（保留兼容）。
5. 展示 `docs/EVALUATION_MAPPING.md` 对照评分标准。

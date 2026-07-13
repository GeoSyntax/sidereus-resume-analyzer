# 后端部署到阿里云函数计算 FC

本文档给出两种部署方式：

- 本地手动部署：适合第一次部署和调试。
- GitHub Actions 手动触发部署：适合后续一键发布。

官方参考：

- Serverless Devs 安装与配置：https://help.aliyun.com/zh/functioncompute/fc/developer-reference/install-serverless-devs-and-docker
- 自定义运行时 HTTP Server 端口要求：https://help.aliyun.com/zh/functioncompute/fc/user-guide/principles-1
- 自定义运行时排错 FAQ：https://help.aliyun.com/zh/functioncompute/fc/troubleshooting-2
- FC 环境变量配置：https://help.aliyun.com/zh/functioncompute/fc/environment-variables

## 部署原理

本项目使用 FastAPI + Uvicorn。阿里云 FC Custom Runtime 会在代码包根目录寻找 `bootstrap` 启动脚本。`backend/bootstrap` 会执行：

```bash
export PATH="/var/fc/lang/python3.10/bin:${PATH}"
exec python3.10 -m uvicorn app.main:app --host 0.0.0.0 --port "${FC_SERVER_PORT:-9000}"
```

关键点：

- 必须监听 `0.0.0.0`，不能监听 `127.0.0.1`。
- Custom Runtime 默认端口是 `9000`。
- 依赖需要和代码一起打包到 `dist/fc-backend`。
- `serverless/s.yaml` 的 `code` 指向 `../dist/fc-backend`。

### 运行时 Python 版本（重要）

`custom.debian10` 内置 **Python 3.10**（位于 `/var/fc/lang/python3.10/bin`），而镜像默认的 `python` 指向 Python 2.7。因此 `bootstrap` 必须显式调用 `python3.10`，直接写 `python` 会启动到 2.7 并崩溃。

由此带来两个必须满足的约束：

- **依赖 wheel 必须是 cp310/manylinux 版本**。`pydantic-core`、`httptools`、`watchfiles`、`websockets`、`PyYAML` 等是编译型扩展，ABI 与解释器版本绑定，用 3.11/3.12 编译的包在 3.10 运行时无法 `import`。
- **在非 3.10 宿主上构建时，需要手动补齐 `python_version < "3.11"` 的 backport 依赖**（如 `exceptiongroup`、`async-timeout`）。pip 交叉下载会按宿主 Python 版本求值环境标记，从而漏掉这些包。`scripts/build_fc_package.ps1` 已处理这一情况；在真实 Linux 3.10 环境（GitHub Actions）构建则会自动包含。

### s.yaml 关键字段

新版 fc3 组件要求显式声明以下字段，否则部署报错：

- `cpu`：vCPU 数，需与 `memorySize` 匹配（内存/CPU 比例在 1024~4096 MB/vCPU 之间）。本项目为 `512MB` + `0.35 vCPU`。
- `internetAccess: true`：开启公网访问，否则报 `no public network configed`。

## 方式一：本地手动部署

### 1. 安装 Serverless Devs

```bash
npm install -g @serverless-devs/s
s --version
```

当前这台机器还没有安装 `s` 命令，所以需要先执行上面的安装。

### 2. 配置阿里云凭证

```bash
s config add
```

按提示选择 Alibaba Cloud，并填写：

- AccessKey ID
- AccessKey Secret
- alias：建议使用 `default`

建议使用 RAM 子账号并只授予函数计算、日志服务、相关资源的最小权限，不要直接使用主账号 AK。

### 3. 构建 FC 代码包

阿里云 FC `custom.debian10` 运行时内置的是 **CPython 3.10**（位于 `/var/fc/lang/python3.10`，镜像默认 `python` 是 Python 2.7）。Python 依赖中包含 `pydantic-core`、`httptools`、`watchfiles` 等平台相关的编译 wheel，其 ABI 与解释器版本绑定，所以部署包里的原生扩展**必须是 cp310 的 Linux wheel**，否则函数实例启动时会 `ModuleNotFoundError` 或加载 `.so` 失败。

三种构建方式都会产出正确的 cp310 包：

GitHub Actions 或 Linux（在 Python 3.10 环境下原生安装）：

```bash
bash scripts/build_fc_package.sh
```

Windows（用 pip 交叉下载 cp310 manylinux wheel，无需本地装 Python 3.10）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_fc_package.ps1
```

`build_fc_package.ps1` 使用 `pip --python-version 3.10 --abi cp310 --platform manylinux... --only-binary=:all:` 交叉下载目标平台 wheel。注意：pip 会按**宿主机 Python 版本**求值依赖的环境标记（如 `exceptiongroup; python_version < "3.11"`），因此脚本会显式补装这些 <3.11 才需要的 backport 包。

Windows 使用 Docker 构建 Linux 依赖（注意镜像必须是 `python:3.10`，不能用 3.11）：

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.10 bash scripts/build_fc_package.sh
```

生成目录：

```text
dist/fc-backend/
├── app/
├── bootstrap
├── requirements-prod.txt
└── site-packages dependencies...
```

### 4. 部署

```bash
cd serverless
s deploy -y
```

部署完成后，在输出日志或阿里云 FC 控制台里找到 HTTP 触发器公网地址。

### 5. 验证

本项目已部署，公网地址为 `https://resume-yzer-api-qfiqdkwrkd.cn-hangzhou.fcapp.run`：

```bash
curl https://resume-yzer-api-qfiqdkwrkd.cn-hangzhou.fcapp.run/health
curl https://resume-yzer-api-qfiqdkwrkd.cn-hangzhou.fcapp.run/api/v1/capabilities
```

`/health` 正常返回（生产已启用 LLM、OCR 和 Redis 缓存）：

```json
{"status":"ok","llm_enabled":true,"ocr_enabled":true,"cache":"redis"}
```

其中 `cache` 反映**真实连接状态**：仅当 Redis 连接建立且 `ping()` 成功才报 `redis`，否则回退内存并如实报 `memory`。

然后打开 GitHub Pages：

```text
https://geosyntax.github.io/sidereus-resume-analyzer/
```

前端会在 GitHub Pages 域名下自动把 `API Base` 指向上面的 FC 地址，直接上传 PDF 即可测试。本地开发时默认回落到 `http://127.0.0.1:8000`。

## 方式二：GitHub Actions 部署

项目已添加 `.github/workflows/deploy-backend-fc.yml`。它是手动触发的 workflow，不会在每次 push 自动部署。

### 1. 配置 GitHub Secrets

在 GitHub 仓库：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

添加：

```text
ALIYUN_ACCOUNT_ID
ALIYUN_ACCESS_KEY_ID
ALIYUN_ACCESS_KEY_SECRET
```

### 2. 手动触发

在 GitHub 仓库：

```text
Actions -> Deploy backend to Aliyun FC -> Run workflow
```

workflow 会执行：

1. 安装 Python。
2. 安装 Serverless Devs。
3. 构建 `dist/fc-backend`。
4. 写入阿里云凭证。
5. 执行 `s deploy -y`。

## 环境变量

`serverless/s.yaml` 已配置基础变量：

```yaml
APP_ENV: production
MAX_UPLOAD_MB: "8"
CACHE_TTL_SECONDS: "86400"
CORS_ORIGINS: "https://geosyntax.github.io,http://localhost:5173,http://127.0.0.1:5173"
OPENAI_BASE_URL: https://api.openai.com/v1
OPENAI_MODEL: gpt-4o-mini
```

可选变量建议在 FC 控制台配置，不要写入 Git：

```text
OPENAI_API_KEY
REDIS_URL
```

## 常见问题

### `s` 命令不存在

说明未安装 Serverless Devs：

```bash
npm install -g @serverless-devs/s
```

### 函数实例启动失败，提示 bootstrap 不存在

先确认执行过构建脚本，并且 `dist/fc-backend/bootstrap` 存在。Linux/macOS 下还需要：

```bash
chmod +x dist/fc-backend/bootstrap
```

### 健康检查失败

确认服务监听：

- host：`0.0.0.0`
- port：`9000` 或平台注入的 `FC_SERVER_PORT`

本项目的 `bootstrap` 已按这个要求配置。

### GitHub Pages 调用 FC 报 CORS

确认 `CORS_ORIGINS` 包含：

```text
https://geosyntax.github.io
```

修改后重新部署 FC。

### LLM 不生效

确认 FC 环境变量中配置了：

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
```

不配置 `OPENAI_API_KEY` 时，系统会自动使用规则抽取和规则评分，不影响基础功能。

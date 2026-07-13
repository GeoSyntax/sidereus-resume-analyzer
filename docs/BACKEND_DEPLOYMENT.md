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
python -m uvicorn app.main:app --host 0.0.0.0 --port "${FC_SERVER_PORT:-9000}"
```

关键点：

- 必须监听 `0.0.0.0`，不能监听 `127.0.0.1`。
- Custom Runtime 默认端口是 `9000`。
- 依赖需要和代码一起打包到 `dist/fc-backend`。
- `serverless/s.yaml` 的 `code` 指向 `../dist/fc-backend`。

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

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_fc_package.ps1
```

macOS/Linux/Git Bash：

```bash
bash scripts/build_fc_package.sh
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

假设公网地址是 `https://xxx.cn-hangzhou.fcapp.run`：

```bash
curl https://xxx.cn-hangzhou.fcapp.run/health
curl https://xxx.cn-hangzhou.fcapp.run/api/v1/capabilities
```

然后打开 GitHub Pages：

```text
https://geosyntax.github.io/sidereus-resume-analyzer/
```

把页面右上角 `API Base` 改成 FC 公网地址，再上传 PDF 测试。

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


# CoreKB 知核

CoreKB 是一个轻量企业内部知识库平台，聚焦知识库管理、权限控制、文档异步索引、语义检索、RAG 问答和基础运维能力。不包含 Agent、Workflow、插件市场、计费、多租户 SaaS 或复杂 BI 大屏。

## 技术栈

- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, JWT, Pydantic v2, Celery, pytest
- Vector DB: Qdrant
- Queue: Redis + Celery worker
- Frontend: React, Vite, TypeScript
- Parsing: PyMuPDF, python-docx, Markdown/TXT，Excel/CSV 表格解析
- LLM: OpenAI-compatible API
- Observability: request log, health check, Prometheus metrics, audit logs

## 检索评估

CoreKB 已提供真实生产资料模拟测试集和检索质量评估框架，用于对比 Search、RAG、后续 Rerank 与 Metadata filter 的效果变化。详见 [docs/EVALUATION.md](docs/EVALUATION.md)。

## 岗位助手

CoreKB 已提供四类最小岗位助手：维修助手、质量助手、SOP 助手、物料 / 参数助手。它们是固定 prompt 和检索参数的业务包装，不是 Agent 或 Workflow。详见 [docs/ASSISTANTS.md](docs/ASSISTANTS.md)。

## 启动

```bash
cp .env.example .env
docker compose up --build
```

服务地址：

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`
- Qdrant: `http://localhost:6333/dashboard`
- Flower: `http://localhost:5555`

Flower 默认只绑定 `127.0.0.1:5555`，不要直接暴露公网。生产环境建议只通过内网、VPN 或受保护的反向代理访问，并配置 `FLOWER_BASIC_AUTH`。

创建管理员：

```bash
docker compose run --rm \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=ChangeMe123! \
  -e ADMIN_EMAIL=admin@example.com \
  backend python -m app.scripts.create_admin
```

本地开发：

```bash
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload
```

```bash
cd backend
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO
```

```bash
cd frontend
npm install
npm run dev
```

## 关键环境变量

- `SECRET_KEY`: JWT 签名密钥，生产必须替换。
- `DATABASE_URL`: PostgreSQL 连接串。
- `UPLOAD_DIR`: 原始文件目录。
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`: Qdrant 配置。
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHAT_MODEL`, `LLM_EMBEDDING_MODEL`: OpenAI-compatible 模型配置。
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: Redis/Celery 配置。
- `FLOWER_BASIC_AUTH`: Flower basic auth，例如 `admin:ChangeMe123!`。
- `RATE_LIMIT_ENABLED`: 是否启用限流，测试环境可关闭。
- `RATE_LIMIT_LOGIN_PER_5M`: 登录每 IP 每 5 分钟限制。
- `RATE_LIMIT_CHAT_PER_MINUTE`: Chat 每用户每分钟限制。
- `RATE_LIMIT_SEARCH_PER_MINUTE`: Search 每用户每分钟限制。
- `RATE_LIMIT_UPLOAD_PER_MINUTE`: 上传每用户每分钟限制。
- `RATE_LIMIT_INDEX_OPS_PER_10M`: reindex/retry/pause/resume/cancel 每用户每 10 分钟限制。

## Chat 流式输出

非流式接口保持不变：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"A100 的通信协议是什么？\",\"knowledge_base_ids\":[\"{kb_id}\"]}"
```

新增 SSE 流式接口：

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"A100 的通信协议是什么？\",\"knowledge_base_ids\":[\"{kb_id}\"]}"
```

事件类型：

- `retrieval_started`
- `retrieval_completed`
- `token`
- `citations`
- `done`
- `error`

流式接口仍然先做权限校验和知识库检索。如果检索不到可靠依据，会直接返回 `当前知识库未找到可靠依据。`，不会绕过 RAG 约束。

## 审计日志

新增 `audit_logs` 表，记录关键写操作、search/chat、索引运维动作。审计 metadata 会截断长文本并脱敏 `password/api_key/secret/token` 等字段，不保存 API Key、密码或完整文档内容。

查询接口：

```bash
curl "http://localhost:8000/api/audit-logs?action=chat.ask&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

权限：

- admin 可查看全部。
- owner 可查看自己知识库相关日志。
- viewer 不可查看。

前端提供“审计日志”页面，支持按 action、resource、knowledge_base、actor、时间筛选。

## 健康检查与 Metrics

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready
curl http://localhost:8000/metrics
```

`/api/health` 返回 API、PostgreSQL、Redis、Qdrant、Celery 状态。`/api/health/ready` 可作为 readiness check，核心依赖不可用时返回 503。

Prometheus 指标包括：

- `http_requests_total`
- `http_request_duration_seconds`
- `chat_requests_total`
- `search_requests_total`
- `document_uploads_total`
- `index_jobs_total`
- `index_job_failures_total`
- `active_index_jobs`
- `failed_index_jobs_total`

## 限流

使用 Redis 作为限流存储。Redis 短暂不可用时采用 fail-open，避免误伤核心业务。

默认策略：

- 登录：每 IP 每 5 分钟 20 次
- Chat：每用户每分钟 30 次
- Search：每用户每分钟 60 次
- 文档上传：每用户每分钟 10 次
- reindex/retry/pause/resume/cancel：每用户每 10 分钟 10 次

超过限制返回 HTTP 429 和明确错误信息。

## 集中日志

后端 API 和 Celery worker 默认输出结构化 JSON 日志。每条日志至少包含：

- `timestamp`
- `level`
- `request_id`
- `user_id`
- `module`
- `message`
- `error`

请求日志会额外包含 `method`、`path`、`status_code`、`duration_ms`、`ip`。日志 formatter 会对 `password`、`api_key`、`secret`、`token`、`authorization` 等字段做脱敏，并截断过长文本。不要在业务日志中主动记录完整文档内容、模型 API Key 或用户密码。

外部日志平台模板位于 `deploy/logging/`：

- `docker-compose.loki.example.yml`
- `loki-promtail.example.yml`
- `filebeat.elk.example.yml`
- `fluentbit-opensearch.example.conf`

选择建议：

- Loki + Promtail：适合轻量自部署，和 Grafana 配合查看 JSON 日志。
- ELK / Elasticsearch + Filebeat：适合企业已有 Elastic/Kibana 体系。
- OpenSearch + Fluent Bit：适合使用 OpenSearch 或希望采集器更轻量的环境。

这些模板不会接入主 `docker-compose.yml`。采集时只采 backend、worker、beat、nginx/reverse proxy 等运行日志，不要采集 `.env`、API Key、备份包、数据库 dump 或上传原始文件内容。

## OpenTelemetry Tracing

CoreKB 支持最小可用 OpenTelemetry tracing。关闭时系统照常运行；开启后 FastAPI 请求会生成 trace_id，Celery 任务会继承调用链 trace_id 或生成新的 trace_id，JSON 日志会同时包含 `request_id` 和 `trace_id`。

`.env` 配置：

```env
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=corekb-api
OTEL_WORKER_SERVICE_NAME=corekb-worker
```

启动最小可用 Collector 示例：

```bash
cd deploy/otel
docker compose -f docker-compose.otel.example.yml up -d
```

API 会使用 `OTEL_SERVICE_NAME=corekb-api` 上报 trace。`docker-compose.yml` 中 worker/beat 会覆盖为 `OTEL_WORKER_SERVICE_NAME`，默认是 `corekb-worker`。

查看 collector logging exporter 输出：

```bash
docker logs -f otel-otel-collector-1
```

已打 span 的路径：

- FastAPI HTTP request
- Chat：`chat.ask` / `chat.stream`
- Search：`search.query`
- 文档索引：`document.indexing`
- Celery：`celery.process_document` / `celery.process_reindex_job`
- 备份：`backup.job` 和 `celery.backup_*`

Tracing span 只记录资源 id、任务类型、数量等 metadata，不采集 API Key、密码或文档全文。

生产环境可以在 `deploy/otel/otel-collector-config.yml` 中接入 Jaeger、Tempo、Datadog、OpenSearch APM 等 exporter。本项目示例只启用 logging exporter 和 Prometheus exporter 占位，不接真实云厂商。

## Jaeger APM 示例

CoreKB 提供一个可实际运行的 Jaeger all-in-one 示例，用于开发、内网试运行和链路排障。默认不并入主 `docker-compose.yml`。

启动 Jaeger：

```bash
cd deploy/apm/jaeger
docker compose -f docker-compose.jaeger.example.yml up -d
```

Jaeger UI:

```text
http://localhost:16686
```

推荐链路：

```text
CoreKB API / Worker -> OTEL Collector -> Jaeger
```

CoreKB 配置：

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=corekb-api
OTEL_WORKER_SERVICE_NAME=corekb-worker
APM_ENABLED=true
JAEGER_URL=http://localhost:16686
```

在 Jaeger 中按 `trace_id` 查询：

1. 从 CoreKB JSON 日志中复制 `trace_id`。
2. 打开 Jaeger UI。
3. 选择 `corekb-api` 或 `corekb-worker`。
4. 使用 trace id 查询对应请求链路。

可追踪链路包括：

- Chat 普通问答和流式问答
- Search 语义检索
- Document indexing 文档解析、切片、向量入库
- Batch reindex 批量重建索引
- Backup job 自动备份任务

Datadog、Tempo、OpenSearch APM 本轮暂不做真实接入，原因是这些后端通常需要额外账号、存储、认证、保留策略和部署治理。当前阶段以 Jaeger all-in-one 作为最小可用 APM 示例。

## Loki / Promtail

CoreKB 提供真实 Loki / Promtail 可选接入，但默认不启动。Loki 只绑定 `127.0.0.1:3100`，建议仅内网、VPN 或本机访问。

启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d loki promtail
```

配置文件：

- `deploy/logging/loki/loki-config.yml`
- `deploy/logging/loki/promtail-config.yml`
- `deploy/logging/loki/README.md`

按 trace_id 查询日志：

```logql
{trace_id="TRACE_ID_HERE"}
{service="backend", trace_id="TRACE_ID_HERE"}
{service="worker", trace_id="TRACE_ID_HERE"}
```

ELK / OpenSearch 本轮不做真实部署接入，只保留 `deploy/logging/` 下的 Filebeat / Fluent Bit 模板。原因是 CoreKB 当前目标是轻量自部署，Loki + JSON stdout 已经覆盖最小可用集中日志；ELK/OpenSearch 通常需要更重的集群、索引生命周期和权限治理。

## 告警

CoreKB 先提供轻量 webhook 告警，不引入复杂告警平台。告警会先写入 `alert_events` 表，再尝试发送 webhook；webhook 失败不会中断主流程。

`.env` 配置：

```env
ALERT_ENABLED=false
ALERT_WEBHOOK_URL=
ALERT_FAILED_JOB_THRESHOLD=5
ALERT_BACKUP_FAILED_ENABLED=true
```

触发条件：

- 索引任务进入 `failed` 或 `partial_failed`
- 失败索引任务数量达到 `ALERT_FAILED_JOB_THRESHOLD`
- 备份任务失败
- `/api/health` 检测到 PostgreSQL、Redis 或 Qdrant 不可用

`alert_events.status`:

- `open`
- `resolved`
- `ignored`

告警 API：

```bash
curl http://localhost:8000/api/alerts -H "Authorization: Bearer $ADMIN_TOKEN"
curl -X PATCH http://localhost:8000/api/alerts/{alert_id}/resolve -H "Authorization: Bearer $ADMIN_TOKEN"
curl -X PATCH http://localhost:8000/api/alerts/{alert_id}/ignore -H "Authorization: Bearer $ADMIN_TOKEN"
```

webhook payload：

```json
{
  "alert_type": "backup_failed",
  "severity": "critical",
  "message": "pg_dump failed",
  "resource_id": "backup-job-id",
  "created_at": "2026-06-16T02:00:00Z"
}
```

## 文档与表格索引

上传接口立即返回 `uploaded`，worker 后台执行：

`uploaded -> parsing -> chunking -> embedding -> indexed / failed`

支持 PDF、DOCX、MD、TXT、XLSX、XLS、CSV。Excel/CSV 会保留表头、sheet、行范围等 metadata。表格 citation 显示为：

```text
产品参数表.xlsx / Sheet: 产品A / Rows 2-15
```

## 索引任务运维

批量重建：

```bash
curl -X POST http://localhost:8000/api/kb/{kb_id}/reindex \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"force\":true}"
```

失败项批量重试：

```bash
curl -X POST http://localhost:8000/api/index-jobs/{job_id}/retry-failed \
  -H "Authorization: Bearer $TOKEN"
```

暂停 / 恢复 / 取消：

```bash
curl -X POST http://localhost:8000/api/index-jobs/{job_id}/pause -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/index-jobs/{job_id}/resume -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/index-jobs/{job_id}/cancel -H "Authorization: Bearer $TOKEN"
```

pause/resume/cancel 都是 cooperative 模式：不会强杀正在处理的 item，worker 会在下一个 item 前检查 job 状态。

`index_jobs.status`:

- `pending`
- `running`
- `paused`
- `completed`
- `partial_failed`
- `failed`
- `cancelled`

## 备份与恢复

新增脚本目录：`scripts/`

- `scripts/backup_postgres.sh`
- `scripts/restore_postgres.sh`
- `scripts/backup_qdrant.sh`
- `scripts/backup_uploads.sh`
- `scripts/backup_all.sh`

示例：

```bash
BACKUP_DIR=./backups/$(date +%Y%m%d_%H%M%S) sh scripts/backup_all.sh
```

恢复 PostgreSQL：

```bash
BACKUP_FILE=./backups/20260616_120000/postgres/corekb.dump sh scripts/restore_postgres.sh
```

备份目录建议：

```text
backups/
  20260616_120000/
    postgres/corekb.dump
    uploads/uploads.tgz
    qdrant/qdrant_storage.tgz
    config/docker-compose.yml
    config/.env.example
```

不要把真实 `.env` secrets 打包进备份。生产建议至少每日备份 PostgreSQL 和 uploads，Qdrant 使用快照、对象存储、NAS 或云盘快照；恢复时先恢复 PostgreSQL，再恢复上传文件和 Qdrant 数据。

## 自动备份调度

Celery Beat 根据 `.env` 中的 `BACKUP_CRON` 定时提交 `backup_all`，默认每天凌晨 2 点执行。

```env
BACKUP_ENABLED=false
BACKUP_CRON=0 2 * * *
BACKUP_DIR=/app/storage/backups
BACKUP_RETENTION_DAYS=14
QDRANT_STORAGE_DIR=/qdrant/storage
```

Docker Compose 中新增 `beat` 服务：

```bash
docker compose up --build -d postgres redis qdrant backend worker beat
```

备份任务：

- `backup_postgres`: 使用 `pg_dump` 生成 PostgreSQL dump。
- `backup_qdrant`: 如果配置了 `QDRANT_STORAGE_DIR`，打包 Qdrant storage；生产更建议使用 Qdrant snapshot 或 volume 快照。
- `backup_uploads`: 打包上传文件目录。
- `backup_all`: 聚合 PostgreSQL、Qdrant、uploads 和安全配置示例，不包含真实 `.env` secrets。

每次备份会写入 `backup_jobs`，记录 `status`、`backup_path`、`file_size`、`checksum`、`started_at`、`finished_at` 和错误信息。备份完成后计算 sha256 checksum；失败时 `status=failed` 并触发告警。

备份历史：

```bash
curl http://localhost:8000/api/backups -H "Authorization: Bearer $ADMIN_TOKEN"
```

校验备份完整性：

```bash
curl -X POST http://localhost:8000/api/backups/{backup_id}/verify \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

恢复流程提醒：

1. 先停止写入流量和 worker。
2. 恢复 PostgreSQL dump。
3. 恢复 uploads 原始文件目录。
4. 恢复 Qdrant snapshot 或 volume。
5. 启动服务后运行 `/api/health/ready`。
6. 抽样执行 search/chat，确认引用来源和向量检索正常。

## 备份恢复演练

新增恢复演练脚本：

```bash
./scripts/dr_restore_check.sh /path/to/backup_all.tgz
```

脚本会：

1. 创建临时恢复目录。
2. 解压指定 `backup_all` 文件。
3. 计算 sha256；如果存在同名 `.sha256` 文件，则进行比对。
4. 使用 `createdb` / `pg_restore` 恢复 PostgreSQL dump 到临时测试库。
5. 检查 uploads 备份是否可解压。
6. 检查 Qdrant 备份文件是否存在。
7. 输出 `restore_check_result.json`。

脚本不会覆盖生产数据库；默认创建 `corekb_restore_check_<timestamp>` 临时库，结束后删除。失败会返回非 0 exit code。生产建议每月至少执行一次恢复演练，并把结果归档到运维记录。

## 生产部署建议

- 全站启用 HTTPS，JWT、管理员登录和文件上传接口不得通过明文 HTTP 暴露。
- 管理后台、系统状态页、审计日志页和索引任务运维页建议只允许内网或 VPN 访问。
- Flower 只用于 Celery 运维排障，必须配置 `FLOWER_BASIC_AUTH`，不要暴露公网。
- PostgreSQL 做定期备份，建议至少每日一次，并保留多代备份。
- uploads 原始文件目录需要定期备份，生产环境建议使用对象存储、NAS 或云盘快照。
- Qdrant 建议定期做 snapshot 或 volume 备份，恢复演练时要同时验证向量检索可用。
- Redis 只作为 broker、缓存和限流存储，不作为永久数据源。
- `.env` secrets 不进入 Git；`SECRET_KEY`、模型 `API_KEY`、数据库密码必须由部署环境注入。
- API Key、密码、原始文档正文不得写入请求日志、错误日志或审计日志。
- 审计日志建议设置保留周期，例如 180 天或 365 天，并按企业合规要求归档。
- 限流默认开启；测试环境可关闭，生产环境不建议关闭。
- 定期测试恢复流程，至少覆盖 PostgreSQL、uploads、Qdrant 三类数据的联合恢复。

pause/resume/cancel 的区别：

- `pause`: cooperative 暂停。当前正在处理的 item 不会被强制中断，worker 会在下一个 item 前退出，剩余 item 保持 `pending`。
- `resume`: 只继续处理 `pending` item；已经 `failed` 的 item 仍通过 `retry-failed` 创建新任务处理。
- `cancel`: cooperative 取消。pending item 会标记为 `cancelled`，正在执行的 item 不强杀。

## 测试

```bash
cd backend
python -m pytest app/tests -q
```

```bash
cd frontend
npm install
npm run build
```

真实 PostgreSQL/Qdrant/Redis 集成测试默认跳过：

```powershell
docker compose up --build -d
cd backend
$env:RUN_INTEGRATION_TESTS="1"
$env:INTEGRATION_DATABASE_URL="postgresql+psycopg://corekb:corekb@localhost:5432/corekb"
$env:QDRANT_URL="http://localhost:6333"
$env:REDIS_URL="redis://localhost:6379/0"
python -m pytest tests\integration -q
```

## 已完成

- Chat SSE 流式输出
- 审计日志和审计日志页面
- Redis 基础限流
- JSON 请求日志、request_id、健康检查、Prometheus metrics
- 告警事件持久化与 webhook 告警
- Flower 接入
- 索引任务 pause/resume/cancel cooperative 运维
- 备份脚本与恢复说明
- 自动备份调度与恢复演练脚本
- Loki / ELK / OpenSearch 日志接入模板
- 基础系统状态统计卡片

## 暂未完成

- 任务强杀式暂停/恢复
- 复杂图表监控或 BI 大屏
- 分布式 tracing
- 自研完整告警通知策略和升级规则

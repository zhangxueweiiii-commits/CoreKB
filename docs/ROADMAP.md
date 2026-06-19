# CoreKB Roadmap

CoreKB 当前阶段的重心回到企业知识库主线能力：让真实资料能被稳定解析、检索、评估和问答，并沉淀面向典型岗位的知识助手。

## Current Focus: Core Knowledge Base MVP+

下一阶段优先任务：

1. 真实生产资料测试集
   - 收集脱敏后的 PDF、DOCX、Markdown、TXT、Excel、CSV 样例。
   - 覆盖产品参数表、故障代码表、SOP、质检记录、维修记录、备件清单、FAQ。
   - 建立标准问题集、期望答案和期望引用来源。

2. 检索质量评估
   - 为 search / chat 构建可重复运行的评估集。
   - 记录 recall、precision、MRR、citation hit rate、no-evidence accuracy。
   - 输出错误样例，区分解析问题、切片问题、embedding 问题、权限问题和 prompt 问题。

3. Rerank 接入
   - 在 embedding 检索后增加可配置 rerank service。
   - 支持 OpenAI-compatible / 本地 reranker 的抽象接口。
   - 保持 provider-neutral，不绑定单一模型供应商。

4. Metadata filter
   - 支持按知识库、文档类型、文件名、章节、页码、sheet、row range 等 metadata 过滤。
   - Search 和 Chat 都必须继续执行权限过滤。
   - 表格型资料优先支持 sheet_name、row_start、row_end、column_names。

5. 四类岗位助手
   - 维修助手：面向故障现象、故障代码、维修步骤、备件建议。
   - 质量助手：面向检验标准、不良原因、抽检记录、质量判定依据。
   - SOP 助手：面向作业步骤、安全注意事项、岗位操作规范。
   - 物料 / 参数助手：面向产品参数、物料替代、规格对比、选型问答。

## Existing Ops Baseline

当前 CoreKB 已具备的生产运维基础能力：

- JSON 日志
- audit logs
- alerts 与 alert_events 持久化
- backup jobs
- backup verify
- OTEL tracing
- OTEL Collector 示例
- Jaeger 示例
- Loki 示例
- health check
- Prometheus metrics

这些能力已经满足当前 MVP 的基础可观测性、审计、告警和备份验证需求。后续开发默认不继续扩展运维平台，除非主线能力明确需要。

## Enterprise Ops Later

以下事项归档为企业级运维增强，非当前 MVP 必需，当前阶段不实现：

- 强杀式任务控制
- 复杂图表监控 / BI 大屏
- 复杂任务控制增强
- 真实 ELK / OpenSearch 部署接入
- Datadog / Tempo / OpenSearch APM 真实接入

这些能力适合在 CoreKB 主线知识库质量、检索评估和岗位助手稳定之后，再按企业部署规模与合规要求进入单独阶段评估。

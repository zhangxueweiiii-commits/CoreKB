# CoreKB 岗位助手

CoreKB 第一版岗位助手是现有 Search / Chat 能力的业务包装，不是 Agent，也不是 Workflow。它不做多步骤规划、不调用外部工具、不接 ERP / MES / 工单系统，只提供固定助手类型、固定 prompt、默认 metadata filter、默认检索参数和引用来源。

## 四类助手定位

| assistant_type | 名称 | 定位 |
| --- | --- | --- |
| `maintenance` | 维修助手 | 设备故障排查、检查步骤、处理方法和安全注意 |
| `quality` | 质量助手 | 检验项目、判定标准、检验方法和不合格处理 |
| `sop` | SOP 助手 | 工序步骤、关键参数、注意事项和安全要求 |
| `material` | 物料 / 参数助手 | 物料编码、产品型号、规格参数、供应商和替代料 |

## 默认检索范围

每类助手都会追加默认 metadata filter：

```json
{
  "maintenance": { "category": "maintenance" },
  "quality": { "category": "quality" },
  "sop": { "category": "sop" },
  "material": { "category": "material" }
}
```

合并优先级：

```text
preset default metadata < query auto metadata < user explicit metadata_filter
```

也就是说，用户显式传入的 metadata filter 优先级最高。

## 默认回答格式

维修助手：
- 可能原因
- 检查步骤
- 处理方法
- 需要停机 / 安全注意
- 引用来源

质量助手：
- 判定标准
- 检验方法
- 不合格处理
- 引用来源

SOP 助手：
- 工序名称
- 操作步骤
- 关键参数
- 注意事项
- 引用来源

物料 / 参数助手：
- 物料编码 / 产品型号
- 关键规格
- 电气参数 / 通信协议 / 供应商 / 替代料
- 引用来源

## API

查看 preset：

```bash
curl http://localhost:8000/api/assistants/presets \
  -H "Authorization: Bearer $TOKEN"
```

调用助手：

```bash
curl -X POST http://localhost:8000/api/assistants/maintenance/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "A200 设备报 E12 怎么处理？",
    "auto_metadata_filter": true,
    "use_rerank": true,
    "top_k": 5
  }'
```

返回包含：

- `assistant_type`
- `answer`
- `citations`
- `used_metadata_filter`
- `use_rerank`
- `rerank_applied`
- `sources`
- `no_answer_detected`

## 前端使用

登录后进入“岗位助手”页面：

1. 选择维修、质量、SOP 或物料 / 参数助手。
2. 输入岗位问题。
3. 查看回答、引用来源、实际使用的 metadata filter 和 rerank 状态。

## 助手评估

`eval_cases.json` 支持 `assistant_type` 字段。运行助手评估：

```bash
curl -X POST http://localhost:8000/api/evaluation/assistants/run \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

指标按助手类型输出：

- `total_cases`
- `hit_at_1`
- `hit_at_3`
- `hit_at_5`
- `mrr`
- `keyword_match_rate`
- `metadata_match_rate`
- `no_answer_accuracy`
- `citation_rate`

`citation_rate` 表示回答是否返回引用来源。

### 岗位助手评估报告

前端“检索评估”页面中包含“岗位助手评估报告”区域。管理员可以直接运行四类助手评估，并查看：

- overall metrics：四类助手汇总指标。
- per assistant metrics：按 `maintenance` / `quality` / `sop` / `material` 分组的指标。
- failed cases：每类助手失败用例，可展开查看 query、expected document、actual top documents、expected metadata、used metadata filter 和失败原因。

后端接口：

```bash
curl -X POST http://localhost:8000/api/evaluation/assistants/run \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "use_metadata_filter": true,
    "use_rerank": true
  }'
```

最近一次助手评估：

```bash
curl http://localhost:8000/api/evaluation/assistants/latest \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

返回结构包含：

- `overall_metrics`
- `per_assistant_metrics`
- `quality_gate_passed`
- `failed_thresholds`
- `threshold_config`
- `per_assistant_quality_gate`
- `use_metadata_filter`
- `use_rerank`
- `rerank_top_n`
- `created_at`

### 岗位助手质量优化流程

建议每次调整 prompt、metadata、chunking 或 rerank 参数后按固定顺序验证：

1. 导入或更新 evaluation fixtures。
2. 运行 baseline / metadata filter / rerank 三组对比。
3. 查看每类助手 `quality_gate_passed`。
4. 展开 failed cases，按 `failure_reason` 和 `suggested_fix_type` 分类处理。
5. 只在指标和失败原因都改善后，才进入试用。

失败原因字段：

| failure_reason | 含义 |
| --- | --- |
| `document_not_found` | 未找到可引用的期望文档 |
| `wrong_document_retrieved` | 检索到了文档，但不是期望文档 |
| `metadata_mismatch` | 期望 metadata 未命中 |
| `keyword_missing` | 期望关键词未出现在引用片段中 |
| `no_citation` | 回答缺少引用 |
| `hallucinated_answer` | 疑似无依据回答 |
| `no_answer_should_answer` | 应回答但没有可靠回答 |
| `answered_should_no_answer` | 应拒答但回答了 |
| `low_mrr` | 命中文档排序不够靠前 |
| `low_hit_at_k` | Top K 内未命中 |
| `unknown` | 规则未能分类 |

建议修复类型：

| suggested_fix_type | 优先排查方向 |
| --- | --- |
| `prompt` | 收紧回答格式、引用和拒答约束 |
| `metadata_filter` | 优化 query metadata 提取或 filter 合并 |
| `rerank` | 调整 rerank top_n 或 rerank provider |
| `chunking` | 调整切片粒度、表格 chunk 格式或关键词保留 |
| `document_metadata` | 修正文档或 chunk metadata |
| `test_case` | 检查评估用例期望是否正确 |
| `unknown` | 需要人工检查 |

### 质量阈值

第一版每类助手最低阈值如下：

| assistant_type | Hit@3 | MRR | Citation rate | No-answer accuracy | Metadata match rate |
| --- | --- | --- | --- | --- | --- |
| `maintenance` | >= 0.85 | >= 0.75 | >= 0.95 | >= 0.85 | - |
| `quality` | >= 0.85 | >= 0.75 | >= 1.00 | >= 0.90 | - |
| `sop` | >= 0.85 | >= 0.75 | >= 0.95 | >= 0.85 | - |
| `material` | >= 0.85 | >= 0.75 | >= 0.95 | - | >= 0.85 |

`quality_gate_passed=true` 表示该助手达到当前最低试用门槛。阈值是初版建议，需要结合真实企业资料、岗位风险和评估集覆盖度持续调整。

### Baseline / Metadata Filter / Rerank 对比

评估页面提供 `Run assistant comparison`，一次运行三组：

| mode | metadata filter | rerank |
| --- | --- | --- |
| `baseline` | false | false |
| `metadata_filter` | true | false |
| `metadata_filter_rerank` | true | true |

接口：

```bash
curl -X POST http://localhost:8000/api/evaluation/assistants/compare \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

对比结果包含每组 overall/per-assistant metrics，以及 delta：

- `hit_at_1`
- `mrr`
- `citation_rate`
- `no_answer_accuracy`

分析建议：

- `Hit@1` 和 `MRR` 上升，说明首条引用排序更好。
- `metadata_match_rate` 上升，说明助手默认分类和 query metadata 对检索范围有帮助。
- `citation_rate` 下降通常意味着过滤过严或数据集缺引用。
- `no_answer_accuracy` 下降时，需要检查 rerank 是否把无关但相似的 chunk 推到了前面。

当前只做评估报告和表格，不做 BI 大屏；只评估四类固定助手，不评估多步骤任务或外部工具调用。

## 当前限制

- 固定四类助手。
- 不支持用户自定义助手。
- 不支持多步骤 Workflow。
- 不调用外部工具。
- 不接 ERP / MES / OA / 工单系统。
- 不做复杂 Agent 规划。
- 失败原因分析仍是规则判断，不调用 LLM 自动修复 prompt。
- 不自动修改文档 metadata。
- 质量阈值是初版建议，需要根据真实企业资料调整。

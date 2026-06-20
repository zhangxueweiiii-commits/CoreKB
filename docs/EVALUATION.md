# CoreKB Retrieval Evaluation

检索评估用于回答一个很实际的问题：上传真实生产资料后，系统能不能把正确资料、正确片段和正确引用稳定找出来。后续接入 Rerank、Metadata filter 或岗位助手时，都应该用同一套评估集对比指标变化。

## 测试集结构

```text
backend/tests/evaluation/
  fixtures/
    documents/
      maintenance_A200.txt
      quality_standard.csv
      sop_assembly_line.txt
      sop_checklist.docx
      material_parameters.xlsx
    expected/
      eval_cases.json
  test_retrieval_eval.py
```

当前模拟资料覆盖：

- 设备维修资料
- 质量标准资料
- SOP 资料
- 物料 / 产品参数资料

资料均为脱敏模拟数据，不包含真实商业机密。

## 导入 Evaluation Fixtures

评估前需要先把 fixtures 导入一个专用知识库。脚本会创建或复用 `CoreKB Evaluation KB`，复制测试文档到上传目录，为文档写入基础 metadata，并提交现有异步索引任务。

```bash
python backend/scripts/import_evaluation_fixtures.py
```

重复运行时，同名 fixture 文档不会重复创建。重新导入并重建已有文档索引：

```bash
python backend/scripts/import_evaluation_fixtures.py --force
```

清空 Evaluation KB 后重新导入：

```bash
python backend/scripts/import_evaluation_fixtures.py --reset
```

脚本需要数据库中已有一个 active admin 用户，作为 Evaluation KB 的 owner。文档导入后仍由 Celery worker 执行解析、chunk、embedding 和 Qdrant 入库；运行评估前请确认文档状态均为 `indexed`。

相关配置：

```env
EVALUATION_KB_NAME=CoreKB Evaluation KB
EVALUATION_FIXTURES_DIR=backend/tests/evaluation/fixtures/documents
```

## eval_cases.json

每条 case 示例：

```json
{
  "id": "maintenance_001",
  "category": "maintenance",
  "query": "A200 设备报 E12 怎么处理？",
  "expected_document": "A200维修手册",
  "expected_keywords": ["E12", "温度传感器", "检查接线"],
  "expected_metadata": {
    "equipment_model": "A200",
    "fault_code": "E12"
  },
  "expected_answer_type": "troubleshooting_steps",
  "should_have_answer": true
}
```

字段说明：

- `id`: 稳定用例 ID。
- `category`: `maintenance` / `quality` / `sop` / `material`。
- `query`: 用户问题。
- `expected_document`: 期望命中的文档名或文档标题。
- `expected_keywords`: 期望 top chunks 中出现的关键字。
- `expected_metadata`: 期望匹配的 metadata。
- `expected_answer_type`: 期望答案类型，方便后续评估岗位助手。
- `should_have_answer`: 是否应该从知识库中找到可靠依据。

## 运行评估

API：

```bash
curl -X POST http://localhost:8000/api/evaluation/retrieval/run \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

运行前 API 会检查 Evaluation KB 是否存在、`eval_cases.json` 中的 `expected_document` 是否已导入，以及对应文档是否已完成索引。如果未准备好，接口返回 `400`，并给出 `missing_documents`、`unindexed_documents`，提示先运行 `import_evaluation_fixtures.py`。

查看最近一次：

```bash
curl http://localhost:8000/api/evaluation/retrieval/latest \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

前端 admin 用户可在“评估”页面运行并查看结果。

## Metadata Filter

Metadata filter 用于把检索范围收窄到更明确的业务标签，例如设备型号、故障码、物料编码、SOP 编码等。第一版只做 exact match，不做模糊匹配、范围过滤或 LLM 抽取。

当前支持字段：

- `category`
- `doc_type`
- `equipment_model`
- `fault_code`
- `material_code`
- `product_model`
- `process_name`
- `sop_code`
- `version`

Search 手动传入：

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "A200 设备报 E12 怎么处理？",
    "knowledge_base_ids": ["{kb_id}"],
    "top_k": 5,
    "metadata_filter": {
      "equipment_model": "A200",
      "fault_code": "E12"
    }
  }'
```

Chat 可以手动传入 `metadata_filter`，也可以开启规则型自动提取：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "A200 设备报 E12 怎么处理？",
    "knowledge_base_ids": ["{kb_id}"],
    "auto_metadata_filter": true
  }'
```

Chat 返回会包含 `used_metadata_filter`，用于确认实际参与检索的过滤条件。若同时传入显式 `metadata_filter` 和 `auto_metadata_filter=true`，显式字段优先覆盖自动提取结果。

当前规则型 metadata extractor 保持保守，主要识别：

- `equipment_model`: `A200`、`A-200`、`EQ-A200`，其中 `A-200` 会标准化为 `A200`。
- `fault_code`: `E12`、`E-12`、`ERR12`、`Error 12`、`故障码 E12`，统一标准化为 `E12`。
- `material_code`: `MAT-001`、`M001`、`WL-1001`、`物料 MAT-001`。
- `sop_code`: `SOP-001`、`SOP001`、`作业指导书 SOP-001`。
- `product_model`: `P100`、`PX-200`。

普通年份、页码、数量不会被识别为业务编码。

运行带 metadata filter 的检索评估：

```bash
curl -X POST http://localhost:8000/api/evaluation/retrieval/run \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"use_metadata_filter": true}'
```

评估时每条 case 优先使用 `expected_metadata` 作为 filter；没有 `expected_metadata` 时才使用规则型 query metadata extractor。对比启用前后的指标时，重点看：

- `metadata_match_rate` 是否提升。
- Hit@1 / Hit@3 / Hit@5 是否提升。
- MRR 是否提升。
- `no_answer_accuracy` 是否提升或下降。
- 是否因为 filter 太严格导致召回下降。

## 新增测试文档

1. 将脱敏后的模拟资料放入 `backend/tests/evaluation/fixtures/documents/`。
2. 在 `backend/scripts/import_evaluation_fixtures.py` 的 `EVALUATION_FIXTURE_METADATA` 中为文档补充业务 metadata。
3. 在 `eval_cases.json` 中新增对应 case。
4. 运行 `python backend/scripts/import_evaluation_fixtures.py --force` 重建索引。
5. 再运行检索评估，对比指标变化。

## 新增 Eval Cases

新增 case 时优先覆盖真实岗位问题，而不是只写关键词搜索。推荐每条 case 至少包含 `category`、`query`、`expected_document`、`expected_keywords`、`expected_metadata`、`expected_answer_type` 和 `should_have_answer`。

## 指标说明

- `hit_at_1`: 正确文档是否出现在 Top 1。
- `hit_at_3`: 正确文档是否出现在 Top 3。
- `hit_at_5`: 正确文档是否出现在 Top 5。
- `mrr`: Mean Reciprocal Rank，正确文档越靠前越高。
- `keyword_match_rate`: 期望关键字在检索 chunk 中的覆盖率。
- `metadata_match_rate`: 期望 metadata 在检索结果中的匹配率。
- `no_answer_accuracy`: 对无依据问题，系统是否没有返回高置信检索结果。

## 对比 Rerank / Metadata Filter

后续接入 Rerank 或 Metadata filter 时，应保留同一份 eval cases，并记录改动前后的：

- Hit@1 / Hit@3 / Hit@5
- MRR
- keyword match rate
- metadata match rate
- no-answer accuracy
- failed cases 差异

如果 Rerank 提升 Hit@1 但降低 no-answer accuracy，需要继续调整 score threshold 或 no-answer 策略。

Metadata filter 和 Rerank 接入后，不要更换评估集。使用同一批 fixtures 和 eval cases 连续运行，才能看出改动是否真正提升了检索质量。

## Failed Cases 分析

岗位助手评估会为 failed cases 输出规则型失败原因：

- `failure_reason`: 失败分类，例如 `wrong_document_retrieved`、`metadata_mismatch`、`keyword_missing`、`no_citation`。
- `failure_detail`: 可读的失败细节。
- `suggested_fix_type`: 建议优先处理方向，例如 `prompt`、`metadata_filter`、`rerank`、`chunking`、`document_metadata`、`test_case`。

排查建议：

- `wrong_document_retrieved`: 先看 metadata filter 是否过宽，再看 rerank 排序。
- `metadata_mismatch`: 先检查 fixture metadata、文档 metadata 和 query extractor。
- `keyword_missing`: 优先检查 chunking 是否切碎了关键字段，或 rerank 是否把包含关键词的 chunk 排低。
- `no_citation`: 优先收紧 prompt，要求必须引用来源。
- `answered_should_no_answer`: 优先加强拒答约束和 no-answer 测试集。

这些分析只用规则，不调用 LLM，也不会自动修改 prompt 或文档 metadata。

## 评估闭环

评估闭环把 failed cases 汇总成可执行的 improvement items，帮助团队判断下一轮优化重点来自 prompt、metadata filter、rerank、chunking、document metadata 还是测试用例本身。

流程：

1. 运行岗位助手评估。
2. 在前端“岗位助手评估报告”下点击 `Generate improvement items`。
3. 查看 summary cards 和改进清单表格。
4. 按 `fix_type` 处理问题。
5. 将改进项标记为 `in_progress`、`resolved` 或 `ignored`。
6. 修复后重新运行同一批 eval cases，对比指标和 failed cases 是否减少。

生成接口：

```bash
curl -X POST http://localhost:8000/api/evaluation/improvements/generate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_run_id": "{assistant_evaluation_run_id}"
  }'
```

同一个 evaluation run 默认不会重复生成。需要重建时：

```bash
curl -X POST http://localhost:8000/api/evaluation/improvements/generate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_run_id": "{assistant_evaluation_run_id}",
    "force": true
  }'
```

查询和更新：

```bash
curl http://localhost:8000/api/evaluation/improvements \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl http://localhost:8000/api/evaluation/improvements/summary \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl -X PATCH http://localhost:8000/api/evaluation/improvements/{item_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'
```

Improvement item 字段：

- `assistant_type`: 受影响助手。
- `fix_type`: `prompt` / `metadata_filter` / `rerank` / `chunking` / `document_metadata` / `test_case` / `unknown`。
- `priority`: `high` / `medium` / `low`。
- `failed_case_count`: 该组失败用例数量。
- `affected_case_ids`: 受影响 case id。
- `main_failure_reasons`: 主要失败原因。
- `suggested_action`: 规则生成的建议动作。
- `status`: `open` / `in_progress` / `resolved` / `ignored`。

Priority 初版规则：

- `high`: 同组失败数 >= 3，或出现 `hallucinated_answer` / `answered_should_no_answer`。
- `medium`: 同组失败数 >= 2，或出现 `no_citation` / `metadata_mismatch` / `wrong_document_retrieved`。
- `low`: 单个低风险失败。

处理建议：

- `prompt`: 强化必须引用、资料不足拒答、不得编造标准/参数/故障原因。
- `metadata_filter`: 检查 query metadata extractor、Qdrant payload、filter 合并和字段标准化。
- `rerank`: 调整 `rerank_top_n`，检查 rerank score，并对比 rerank 前后排序。
- `chunking`: 检查 chunk 是否切断表格、步骤或关键字段，必要时使用结构化 chunk。
- `document_metadata`: 补全文档 metadata，标准化设备型号、故障码、物料编码、SOP 编码。
- `test_case`: 修正 `eval_cases.json`，确认 expected document、keywords、metadata 是否合理。

当前限制：

- 改进建议仍基于规则。
- 不调用 LLM 自动生成修复方案。
- 不自动修改 prompt。
- 不自动修改文档 metadata。
- 不自动调整 chunking 或 rerank 参数。

## 改进效果追踪

改进效果追踪用于把已修复的 improvement items 和后续 assistant evaluation run 关联起来，形成质量回归记录。它回答三个问题：

1. 哪些改进项被修复。
2. 修复前后指标是否改善。
3. 这些改进项关联的 failed cases 是否仍然失败。

推荐流程：

1. 运行一次助手评估，生成 improvement items。
2. 人工处理 prompt / metadata / rerank / chunking / test case 等问题。
3. 再次运行同一批 eval cases，得到 after evaluation run。
4. 在前端“改进效果追踪”中选择 before run、after run 和相关 improvement items。
5. 创建 regression，查看 `regression_passed`、`delta_metrics`、`resolved_case_ids` 和 `still_failed_case_ids`。

创建接口：

```bash
curl -X POST http://localhost:8000/api/evaluation/regressions/create \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "before_evaluation_run_id": "{before_run_id}",
    "after_evaluation_run_id": "{after_run_id}",
    "improvement_item_ids": ["{item_id}"],
    "notes": "优化维修助手 prompt 和 E12 metadata 标准化后回归"
  }'
```

查询：

```bash
curl http://localhost:8000/api/evaluation/regressions \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl http://localhost:8000/api/evaluation/regressions/summary \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Regression 记录字段：

- `before_evaluation_run_id`: 修复前评估 run。
- `after_evaluation_run_id`: 修复后评估 run。
- `improvement_item_ids`: 关联改进项。
- `assistant_type`: 单一助手类型或 `mixed`。
- `fix_type`: 单一修复类型或 `mixed`。
- `before_metrics` / `after_metrics`: 修复前后指标。
- `delta_metrics`: after - before。
- `affected_case_ids`: 改进项影响的 case。
- `resolved_case_ids`: 修复后不再失败的 case。
- `still_failed_case_ids`: 修复后仍失败的 case。
- `regression_passed`: 是否通过回归验证。

`delta_metrics` 重点看：

- `hit_at_1`
- `hit_at_3`
- `mrr`
- `citation_rate`
- `no_answer_accuracy`
- `metadata_match_rate`

`regression_passed=true` 的初版规则：

- `affected_case_ids` 中至少有一个 case 从 failed 变为 passed。
- `citation_rate` 不允许下降。
- `no_answer_accuracy` 下降不能超过 `0.05`。
- `hit_at_1`、`hit_at_3`、`mrr`、`metadata_match_rate` 单项下降不能超过 `0.03`。

创建 regression 后，相关 improvement item 会更新：

- `resolved_evaluation_run_id = after_evaluation_run_id`
- `regression_status = passed / failed`
- `related_regression_id = regression.id`

当前限制：

- 只做规则判断。
- 不自动判断真实业务正确性。
- 不自动修改修复项状态以外的业务配置。
- 不做复杂 BI 大屏。
- 指标阈值后续需要用真实企业资料校准。

## 评估趋势记录

评估趋势记录用于按时间查看同一助手的质量变化。趋势数据直接来自已有 `evaluation_runs` 和 `evaluation_regressions`，不会重复存储大量评估明细。

可以查看的核心指标：

- `hit_at_1`
- `hit_at_3`
- `hit_at_5`
- `mrr`
- `keyword_match_rate`
- `metadata_match_rate`
- `no_answer_accuracy`
- `citation_rate`
- `quality_gate_passed`
- `regression_pass_rate`

助手趋势接口：

```bash
curl 'http://localhost:8000/api/evaluation/trends/assistants?assistant_type=maintenance&use_metadata_filter=true&use_rerank=true&limit=20' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

整体趋势接口：

```bash
curl 'http://localhost:8000/api/evaluation/trends/overall?limit=20' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

回归趋势接口：

```bash
curl 'http://localhost:8000/api/evaluation/trends/regressions?limit=20' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

`delta_from_previous` 表示最新一条趋势记录相对上一条记录的变化，计算方式为：

```text
current_metric - previous_metric
```

`regression_warnings` 用于提示质量退化。第一版规则：

- `hit_at_1` 下降超过 `0.05`。
- `hit_at_3` 下降超过 `0.05`。
- `mrr` 下降超过 `0.05`。
- `citation_rate` 下降。
- `no_answer_accuracy` 下降超过 `0.05`。
- `quality_gate_passed` 从 `true` 变为 `false`。

前端“评估趋势”区域支持：

- 选择助手类型：All / maintenance / quality / sop / material。
- 选择模式：baseline / metadata filter / metadata filter + rerank。
- 查看最近 N 次评估表格。
- 查看每条记录的 regression warnings。

“改进回归趋势”区域展示：

- Regression id
- Created at
- Assistant
- Fix type
- Before run
- After run
- Regression passed
- Resolved cases
- Still failed cases

使用趋势判断质量退化时，建议优先关注：

- `quality_gate_passed` 是否从 Pass 变 Fail。
- `citation_rate` 是否下降。
- `no_answer_accuracy` 是否明显下降。
- `Hit@1` 与 `MRR` 是否连续下降。
- regression pass rate 是否持续偏低。

当前限制：

- 只做轻量表格。
- 不做 BI 大屏。
- 不做自动告警。
- 不做定时评估。
- 不做自定义指标编辑器。
- 趋势数据来自已有 evaluation runs 和 regressions。

## 评估运行标记 / 版本备注

每次 assistant evaluation run 都可以记录运行标签、变更类型、变更说明和操作者备注。这样在趋势表中看到 Hit@1、MRR、citation rate 或 no-answer accuracy 波动时，可以快速判断这次评估对应的是 prompt 修改、metadata 修正、chunking 调整、rerank 参数实验，还是 eval case / parser 变更。

支持字段：

- `run_label`: 本次评估的短标签，便于在趋势表中识别。
- `change_type`: 本次评估对应的变更类型。
- `change_summary`: 本次变更的简短说明。
- `operator_notes`: 操作者备注，可记录关注指标、验证假设或异常现象。
- `config_snapshot`: 后端自动记录的关键评估配置。

`change_type` 允许值：

- `baseline`
- `prompt`
- `metadata`
- `chunking`
- `rerank`
- `eval_case`
- `parser`
- `mixed`
- `unknown`

推荐 `run_label` 命名示例：

- `baseline_v1`
- `maintenance_prompt_v2`
- `metadata_a200_e12_fix`
- `rerank_topn_20_test`
- `sop_chunking_v2`
- `material_eval_case_update`

运行助手评估时可以直接传入备注：

```bash
curl -X POST http://localhost:8000/api/evaluation/assistants/run \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "run_label": "maintenance_prompt_v2",
    "change_type": "prompt",
    "change_summary": "强化维修助手资料不足时拒答，并要求输出安全注意",
    "operator_notes": "本轮主要验证 no-answer accuracy 和 citation_rate",
    "use_metadata_filter": true,
    "use_rerank": true
  }'
```

评估完成后也可以补充或修正备注：

```bash
curl -X PATCH http://localhost:8000/api/evaluation/runs/{run_id}/metadata \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "run_label": "metadata_a200_e12_fix",
    "change_type": "metadata",
    "change_summary": "补齐 A200 / E12 的文档 metadata",
    "operator_notes": "观察 metadata_match_rate 和 Hit@3"
  }'
```

查询评估 run 列表：

```bash
curl 'http://localhost:8000/api/evaluation/runs?eval_type=assistant&change_type=prompt&limit=20' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

`config_snapshot` 当前记录：

```json
{
  "eval_type": "assistant",
  "use_metadata_filter": true,
  "use_rerank": true,
  "rerank_top_n": 20,
  "assistant_types": ["maintenance", "quality", "sop", "material"],
  "mode": "single",
  "evaluation_case_set_signature": "sha256...",
  "evaluation_case_ids": ["maintenance_001", "quality_001"]
}
```

趋势 API 和前端趋势表会展示 `run_label`、`change_type`、`change_summary`、`operator_notes` 和 `config_snapshot`。回归详情会额外返回 before / after run 的 label、change type 和 change summary，便于判断一次回归验证比较的到底是哪两轮变更。

为了让趋势表和回归对比更容易阅读，后端会为每条 evaluation run 生成统一展示字段：

- `display_label`: 用于下拉选择器和趋势表的主标签。
- `mode_summary`: 用于描述本轮评估模式。
- `metrics_summary`: 用于快速展示核心指标。

`display_label` 规则：

1. `run_label` 有值时：`{run_label} · Run #{id}`。
2. `run_label` 为空但 `change_type` 有值时：`{change_type} · Run #{id}`。
3. 二者都为空时：`Run #{id}`。

`mode_summary` 规则：

- `use_metadata_filter=false` 且 `use_rerank=false`: `Baseline`
- `use_metadata_filter=true` 且 `use_rerank=false`: `Metadata filter`
- `use_metadata_filter=true` 且 `use_rerank=true`: `Metadata filter + Rerank`
- `use_metadata_filter=false` 且 `use_rerank=true`: `Rerank only`

`metrics_summary` 当前包含：

- `hit_at_1`
- `hit_at_3`
- `mrr`
- `citation_rate`
- `no_answer_accuracy`
- `quality_gate_passed`

在前端“改进效果追踪”区域创建 regression 时，before / after run 选择器默认只展示 assistant evaluation runs，并支持：

- 按 `run_label` / `display_label` / `change_summary` 搜索。
- 按 `change_type` 过滤。
- 按 `assistant_type` 过滤。
- 查看每个 run 的模式摘要、创建时间、变更说明和关键指标。

Regression detail 会同时展示：

- Before run 的 `display_label`、`change_type`、`change_summary`、`mode_summary` 和关键指标。
- After run 的 `display_label`、`change_type`、`change_summary`、`mode_summary` 和关键指标。
- 中间的 `delta_metrics`、`resolved_case_ids`、`still_failed_case_ids` 和 `regression_passed`。

阅读趋势表时，建议先看 `Run` 和 `Change type`，确认某次指标波动是否对应 prompt、metadata、chunking、rerank、eval case 或 parser 修改；再看 `Mode`，确认这次评估是否启用了 metadata filter / rerank；最后结合 Hit@1、MRR、citation rate、no-answer accuracy 和 quality gate 判断质量变化。

使用建议：

- `baseline`: 首次建立基准或重建测试集后的基础评估。
- `prompt`: 只改助手 prompt 或回答格式约束。
- `metadata`: 修改文档 metadata、fixture metadata 或 metadata 标准化规则。
- `chunking`: 修改 chunk size、overlap 或结构化 chunk 策略。
- `rerank`: 修改 rerank provider、开关或 top_n 参数。
- `eval_case`: 修改 eval cases、expected document、keywords 或 expected metadata。
- `parser`: 修改 PDF / DOCX / TXT / 表格解析逻辑。
- `mixed`: 多类改动同时发生，适合临时记录，但正式质量回归建议拆分验证。
- `unknown`: 旧数据或暂未分类的评估。

当前限制：

- 不关联 Git commit。
- 不自动读取 git diff。
- 不自动分析代码或资料变更。
- 不自动判断 change type。
- 不自动生成 change summary。
- 不做复杂版本管理系统或 BI 大屏。

## 任意两次评估运行对比

管理员可以选择任意两个 evaluation runs 做按需对比，用于回答：

- 指标是否改善。
- 哪些 failed cases 被解决。
- 哪些问题是新引入的。
- 哪些问题仍然失败。
- 两次评估是否具备可比性。

接口：

```bash
curl 'http://localhost:8000/api/evaluation/runs/compare?before_run_id={before_run_id}&after_run_id={after_run_id}' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

返回核心结构：

```json
{
  "before_run": {
    "id": "...",
    "display_label": "maintenance_prompt_v2 · Run #12",
    "change_type": "prompt",
    "change_summary": "...",
    "mode_summary": "Metadata filter + Rerank",
    "metrics_summary": {}
  },
  "after_run": {
    "id": "...",
    "display_label": "metadata_a200_e12_fix · Run #19",
    "change_type": "metadata",
    "change_summary": "...",
    "mode_summary": "Metadata filter + Rerank",
    "metrics_summary": {}
  },
  "comparable": true,
  "comparability_warnings": [],
  "metric_deltas": {
    "hit_at_1": 0.08,
    "hit_at_3": 0.04,
    "mrr": 0.06,
    "citation_rate": 0.0,
    "no_answer_accuracy": -0.02
  },
  "failed_case_diff": {
    "resolved_cases": [],
    "introduced_failures": [],
    "still_failed_cases": [],
    "unchanged_passed_count": 0,
    "before_failed_count": 0,
    "after_failed_count": 0
  }
}
```

`comparable` 表示两次评估是否在关键前提上可直接比较。以下情况会产生 `comparability_warnings`：

- `eval_type` 不一致。
- `assistant_types` 不一致。
- `evaluation_case_set_signature` 不一致。
- `use_metadata_filter` 不一致。
- `use_rerank` 不一致。
- `rerank_top_n` 不一致。

其中评估集不同通常不应直接比较，因为 case 数量、问题类型或 expected document 变了，指标变化可能来自测试集本身，而不是 prompt、metadata、chunking 或 rerank 的优化。检索配置不同不一定禁止比较，但系统会提示：指标变化可能来自 metadata filter 或 rerank，而非单一 prompt 或资料修改。

`evaluation_case_set_signature` 由评估用例的稳定字段计算：

- case id
- assistant_type
- expected_document
- should_have_answer

不关联 Git，不读取 git diff。

failed case diff 含义：

- `resolved_cases`: before failed，after passed。
- `introduced_failures`: before passed，after failed。
- `still_failed_cases`: 两次都 failed。
- `unchanged_passed_count`: 两次都 passed 的用例数量。
- `before_failed_count`: before run 的失败用例数。
- `after_failed_count`: after run 的失败用例数。

每个 failed case diff item 会包含：

- case id
- assistant type
- query
- failure reason
- suggested fix type
- before / after actual top documents
- before / after used metadata filter

解读建议：

- Hit@1、Hit@3、MRR 上升，说明正确资料或片段排序更靠前。
- citation_rate 上升，说明回答引用更稳定。
- no_answer_accuracy 下降，需要重点检查是否出现资料不足仍回答的问题。
- resolved cases 增多且 introduced failures 很少，通常说明优化有效。
- introduced failures 增多时，需要检查本轮变更是否过度收紧 prompt、metadata filter 或 rerank 参数。

当前限制：

- 不关联 Git commit。
- 不读取 git diff。
- 变更信息仍由操作者手工填写。
- 不自动判断真实业务正确性。
- 不做图表平台或复杂版本管理。

## Failed Case Drill-down

Failed case drill-down 用于从任意两次 evaluation runs 的对比结果中，打开单个 case，查看 before / after 的完整评估快照。它帮助判断问题更可能来自：

- prompt
- metadata filter
- rerank
- chunking
- document metadata
- evaluation case

重要原则：drill-down 只读取 evaluation run 当时保存的快照，不会重新执行 Search、Chat、Rerank 或 LLM 调用。这样可以保证排查时看到的是当时真实评估证据，而不是当前系统状态重新计算出来的结果。

每次 evaluation run 会为所有 cases 保存 `evaluation_case_results`，不只保存 failed cases。快照包含：

- case 基本信息：case id、assistant type、query、expected document、expected keywords、expected metadata、should_have_answer。
- 评估结果：passed、failure_reason、suggested_fix_type。
- 检索配置：used_metadata_filter、use_rerank、rerank_applied。
- 回答证据：answer_excerpt、citations。
- 检索证据：retrieved_results。

`retrieved_results` 每条记录包含：

- `rank`
- `document_id`
- `document_name`
- `chunk_id`
- `chunk_excerpt`
- `chunk_metadata`
- `vector_score`
- `rerank_score`
- `final_score`
- `citation`

`chunk_excerpt` 最多保存约 1200 字符，不保存完整原始文档，不保存 API Key、认证信息或敏感配置。

接口：

```bash
curl http://localhost:8000/api/evaluation/cases/{case_result_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

对比某个 case 的 before / after 快照：

```bash
curl 'http://localhost:8000/api/evaluation/runs/compare/cases/maintenance_001?before_run_id={before_run_id}&after_run_id={after_run_id}' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

返回中的 `comparison.status` 支持：

- `resolved`: before failed，after passed。
- `introduced_failure`: before passed，after failed。
- `still_failed`: 两次都 failed。
- `unchanged_passed`: 两次都 passed。
- `unavailable`: 至少一侧没有保存 case 快照。

Drill-down 页面阅读顺序建议：

1. 先看 Case 基本信息，确认 query、expected document 和 expected metadata 是否合理。
2. 再看 Before / After 的 used metadata filter 和 rerank 状态，判断检索配置是否变化。
3. 看 retrieved results 中 expected document 是否进入 Top 1 / Top 3 / Top 5。
4. 对比 vector score、rerank score、final score，判断是召回问题还是排序问题。
5. 查看 citations 和 answer excerpt，判断检索正确但回答没有引用，还是回答约束不足。

规则型诊断提示：

- After Top 1 命中 expected document，但 Before 未进入 Top 5：检索召回明显改善，优先检查 metadata filter、document metadata 或向量检索配置。
- 两次 expected document 都进入 Top 5，但 After 排名更高：排序改善，优先检查 rerank 或 chunk 相关性。
- expected document 命中但 expected keywords 仍缺失：可能是 chunk 切片、表格解析或文档内容覆盖不足。
- 检索结果正确但没有 citation：优先检查 prompt 或 citation 输出逻辑。
- `should_have_answer=false` 但有明确回答：优先检查 no-answer prompt 约束和置信度阈值。

历史运行限制：

- 在引入 `evaluation_case_results` 之前创建的历史 run 没有详细快照。
- 对这类 run 进行 drill-down 时会返回 `unavailable`。
- 系统不会为了补齐历史详情而重新执行检索、rerank 或 LLM。

当前限制：

- 不关联 Git commit。
- 不读取 git diff。
- 不自动判断真实业务正确性。
- 诊断提示只使用规则。
- 不自动修改 prompt、metadata、chunking 或 rerank。
- 不做图表平台或复杂版本管理。

## Case 级人工标注

Case 级人工标注用于在 failed case drill-down 页面中记录管理员对单个 evaluation case 的人工复核结论。它用于沉淀企业内部评估经验，帮助区分问题到底来自 prompt、metadata filter、document metadata、chunking、rerank、parser、source document、evaluation case 还是业务规则本身。

人工标注不会覆盖系统自动判断。以下系统字段仍然保留原样：

- `failure_reason`
- `suggested_fix_type`
- `passed`
- `retrieved_results`
- `citations`
- `used_metadata_filter`

人工标注会单独保存到 `evaluation_case_annotations`，字段包括：

- `human_judgement`
- `human_root_cause`
- `human_fix_type`
- `handling_status`
- `handling_notes`
- `annotated_by`
- `annotated_at`
- `updated_at`

`human_judgement` 表示管理员认为系统自动判断是否正确：

- `system_correct`
- `system_partially_correct`
- `system_incorrect`
- `business_expected_answer_wrong`
- `insufficient_documentation`
- `needs_expert_review`

`human_root_cause` 表示人工确认的根因：

- `prompt`
- `metadata_filter`
- `document_metadata`
- `chunking`
- `rerank`
- `parser`
- `source_document`
- `evaluation_case`
- `business_rule`
- `unknown`

`human_fix_type` 表示建议处理动作：

- `update_prompt`
- `update_metadata`
- `update_chunking`
- `tune_rerank`
- `improve_parser`
- `supplement_document`
- `revise_eval_case`
- `confirm_business_rule`
- `no_action`

`handling_status` 表示当前处理状态：

- `open`
- `investigating`
- `planned`
- `resolved`
- `ignored`

API 示例：

```bash
curl http://localhost:8000/api/evaluation/cases/{case_result_id}/annotation \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

```bash
curl -X POST http://localhost:8000/api/evaluation/cases/{case_result_id}/annotation \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "human_judgement": "system_partially_correct",
    "human_root_cause": "document_metadata",
    "human_fix_type": "update_metadata",
    "handling_status": "planned",
    "handling_notes": "A200 维修手册缺少 fault_code=E12，需补充并重建索引。"
  }'
```

查询标注列表：

```bash
curl 'http://localhost:8000/api/evaluation/case-annotations?handling_status=planned' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

人工标注如何影响 improvement items：

1. 如果 failed case 有人工标注，生成改进清单时优先使用 `human_root_cause` 和 `human_fix_type` 归因。
2. 如果没有人工标注，继续使用系统的 `suggested_fix_type` 和规则判断。
3. `evaluation_improvement_items.source` 会标记来源：
   - `human_annotation`
   - `system_rule`
4. `evaluation_improvement_items.annotation_count` 会记录该改进项包含多少个人工标注 case。

人工标注不会自动把 improvement item 标记为 resolved，也不会自动修改 prompt、metadata、chunking 或 rerank 参数。它只提供更可靠的归因依据。

当前限制：

- 人工标注不自动修改 prompt、metadata、chunking 或 rerank。
- 人工标注不自动训练模型。
- 系统不自动判断真实业务正确性。
- 不做多人审批、评论流、附件上传或复杂历史版本。
- 不做 BI 大屏或复杂协作流。

## 人工标注统计视图

人工标注统计视图用于汇总 `evaluation_case_annotations`，帮助团队判断当前知识库质量问题主要集中在哪一类。它只统计管理员已经人工复核过的 case，不会调用 LLM，也不会自动修改 prompt、metadata、chunking 或 rerank 参数。

接口：

```bash
curl 'http://localhost:8000/api/evaluation/annotations/summary' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

支持筛选：

- `evaluation_run_id`
- `assistant_type`
- `handling_status`
- `date_from`
- `date_to`

示例：

```bash
curl 'http://localhost:8000/api/evaluation/annotations/summary?assistant_type=maintenance&handling_status=open' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

返回内容包括：

- `total_annotations`: 当前筛选范围内的人工标注总数。
- `by_root_cause`: 按 `human_root_cause` 汇总，用于判断主要根因。
- `by_fix_type`: 按 `human_fix_type` 汇总，用于判断下一轮主要修复动作。
- `by_handling_status`: 按处理状态汇总，区分 open、investigating、planned、resolved、ignored。
- `by_assistant_type`: 按助手类型汇总，判断问题集中在哪类岗位助手。
- `open_priority_items`: 对未解决标注按 root cause + fix type + assistant type 聚合并按数量排序。

推荐动作仍然是规则型建议，不是自动修复指令：

- `document_metadata` 或 `metadata_filter` 占比最高：建议进入 metadata 半自动标注与审核流程。
- `chunking` 占比最高：建议检查 SOP 步骤、Excel 表格、设备手册是否被错误切分。
- `prompt` 占比最高：建议检查引用强制、资料不足拒答、安全提示等岗位助手约束。
- `rerank` 占比最高：建议检查 rerank_top_n、候选召回数量和排序效果。
- `source_document` 占比最高：建议补充或更新源文件，而不是继续调模型参数。
- `evaluation_case` 占比最高：建议复核评估问题、标准答案和 expected metadata。

如何用统计结果确定下一轮优化优先级：

1. 先看 `by_root_cause` 的最高项，确认问题是资料、元数据、切片、提示词还是排序。
2. 再看 `open_priority_items`，优先处理未解决数量最多的助手 + 根因 + 修复方式组合。
3. 处理后重新运行同一批 evaluation cases，观察 trends、regression 和 failed case drill-down。
4. 如果问题集中在 `evaluation_case`，优先修正测试集，避免用错误评估结论指导系统优化。

当前限制：

- 仅统计人工标注。
- 不调用 LLM 自动分析。
- 不自动判断真实业务正确性。
- 不自动修改系统参数或资料。
- 不做图表平台、自动告警或复杂流程管理。

## 人工标注列表筛选页

人工标注列表页用于从统计结果进一步下钻到具体 annotations。它仍然是轻量表格，不做审批流、评论流、任务分派或 BI 图表。

入口：

- 在 Evaluation 页面“人工复核问题分布”中点击 root cause、fix type、handling status、assistant type 或 open priority item。
- 或直接访问 `/evaluation/annotations?...`。

列表接口：

```bash
curl 'http://localhost:8000/api/evaluation/case-annotations?human_root_cause=document_metadata&page=1&page_size=20' \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

支持筛选参数：

- `human_root_cause`
- `human_fix_type`
- `handling_status`
- `assistant_type`
- `evaluation_run_id`
- `date_from`
- `date_to`
- `keyword`
- `page`
- `page_size`
- `order_by`
- `order_direction`

默认排序：

- `order_by=annotated_at`
- `order_direction=desc`
- `page_size=20`

`keyword` 第一版匹配：

- `case_id`
- `query`
- `handling_notes`

每条 annotation 返回：

- `annotation_id`
- `evaluation_case_result_id`
- `evaluation_run_id`
- `case_id`
- `assistant_type`
- `query`
- `human_judgement`
- `human_root_cause`
- `human_fix_type`
- `handling_status`
- `handling_notes`
- `annotated_by`
- `annotated_at`
- `system_failure_reason`
- `system_suggested_fix_type`
- `evaluation_run_display_label`
- `evaluation_run_change_type`
- `evaluation_run_mode_summary`
- `case_passed`

统计项跳转示例：

```text
/evaluation/annotations?human_root_cause=document_metadata
/evaluation/annotations?handling_status=open
/evaluation/annotations?assistant_type=maintenance
/evaluation/annotations?human_fix_type=update_metadata
```

列表页操作：

- `View drill-down`: 查看该 case result 保存的历史检索、回答、引用、metadata、rerank 快照。
- `Edit annotation`: 更新人工判断、根因、修复方向、处理状态和备注。
- `Mark investigating`
- `Mark resolved`
- `Ignore`

Drill-down 回跳：

- 从列表进入 drill-down 时，页面保留当前筛选条件和分页状态。
- drill-down 中的 `Back to annotations` 返回列表，不重新构造筛选条件。

当前限制：

- 仅做轻量筛选表格。
- 不做图表平台、审批流、评论流或复杂任务分派。
- 不调用 LLM 自动分析。
- 不自动修改 prompt、metadata、chunking 或 rerank。

## Rerank

Rerank 用于对向量检索召回的候选片段重新排序。向量检索负责先找出可能相关的候选，metadata filter 负责按业务标签缩小范围，rerank 再根据 query 与 chunk 内容的相关性重新排序。当前顺序固定为：

```text
query embedding -> Qdrant metadata filter -> candidate chunks -> rerank -> top_k
```

之所以先 metadata filter 再 rerank，是为了避免把明显不属于同一设备、故障码、物料或 SOP 的片段交给 rerank，降低误召回和不必要的 rerank 成本。

Rerank 默认关闭：

```env
RERANK_ENABLED=false
RERANK_PROVIDER=openai_compatible
RERANK_BASE_URL=
RERANK_API_KEY=
RERANK_MODEL=
RERANK_TOP_N=20
```

Search 开启 rerank：

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "A200 设备报 E12 怎么处理？",
    "knowledge_base_ids": ["{kb_id}"],
    "top_k": 5,
    "metadata_filter": {
      "equipment_model": "A200",
      "fault_code": "E12"
    },
    "use_rerank": true,
    "rerank_top_n": 20
  }'
```

Chat 开启 rerank：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "A200 设备报 E12 怎么处理？",
    "knowledge_base_ids": ["{kb_id}"],
    "auto_metadata_filter": true,
    "use_rerank": true,
    "rerank_top_n": 20
  }'
```

当 `RERANK_ENABLED=false` 但请求 `use_rerank=true` 时，系统会明确返回 `rerank_error`，并 fallback 到原始向量检索结果；不会静默假装 rerank 已生效。

三组评估对比：

```bash
curl -X POST http://localhost:8000/api/evaluation/retrieval/compare \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rerank_top_n": 20}'
```

返回包含：

- `baseline`: 无 metadata filter，无 rerank。
- `metadata_filter`: 启用 metadata filter。
- `metadata_filter_rerank`: 启用 metadata filter + rerank。
- `delta`: 三组之间的 Hit@1、Hit@3、MRR、metadata_match_rate、no_answer_accuracy 差异。

解读建议：

- Hit@1 / MRR 上升：正确片段排序更靠前。
- metadata_match_rate 上升：业务标签命中更稳定。
- no_answer_accuracy 下降：可能是 rerank 或 filter 让无依据问题也出现高置信结果，需要调整阈值或过滤策略。
- Hit@K 下降：filter 可能过严，或 rerank provider 对企业术语理解不足。

当前限制：

- 只支持一个 rerank provider 配置。
- 暂不做多模型管理。
- 暂不接本地 rerank 模型。
- rerank 失败会 fallback 原始向量结果，并返回 `rerank_error`。
## 人工标注与 Improvement Item 联动筛选

本阶段为人工标注和改进项增加显式关联表：

```text
evaluation_improvement_item_case_results
```

字段：

- `id`
- `improvement_item_id`
- `evaluation_case_result_id`
- `relation_source`
- `created_at`

约束：

- `improvement_item_id + evaluation_case_result_id` 唯一。
- 一个 improvement item 可以关联多个 case result。
- 一个 case result 可以关联多个 improvement item。
- `evaluation_improvement_items.affected_case_ids` 保留为历史摘要和兼容字段，不再作为唯一关联来源。

`relation_source` 含义：

- `system_rule`: 由系统 failure reason / suggested fix type 规则生成。
- `human_annotation`: 由管理员人工标注的 root cause / fix type 生成。
- `manual_link`: 预留给后续手工关联能力，本阶段不提供复杂任务管理。

生成 improvement items 时：

1. 读取 evaluation run 的 failed cases。
2. 如果 case result 已有人为标注，优先使用 `human_root_cause` / `human_fix_type` 归因。
3. 如果没有人为标注，继续使用系统 `failure_reason` / `suggested_fix_type`。
4. 创建 improvement item 后，同时写入 `evaluation_improvement_item_case_results`。

Annotation List 新增筛选：

- `improvement_item_id`
- `improvement_status`
- `regression_status`

每条 annotation 返回 `related_improvement_items`，用于从人工标注反查相关改进项。

新增 API：

```http
GET /api/evaluation/improvements/{item_id}
GET /api/evaluation/improvements/{item_id}/annotations
```

`GET /api/evaluation/improvements/{item_id}` 返回：

- improvement item 基本信息
- `related_case_results`
- `related_annotations`

前端跳转：

- Annotation List -> 点击 related improvement item -> Improvement Item Detail。
- Improvement Item Detail -> 点击 related annotation -> Case drill-down。
- Case drill-down -> Back to improvement item 或 Back to annotations。

当前限制：

- 不做自动任务分派、审批、评论、附件或复杂项目管理。
- 不自动修改 prompt、metadata、chunking 或 rerank。
- 不调用 LLM 自动分析。
- 不自动判断真实业务正确性。

## Evaluation Runner Baseline

`make eval` now runs a deterministic read-only baseline over `backend/tests/evaluation/fixtures/expected/eval_cases.json`:

```bash
make eval
```

Equivalent direct command:

```bash
python scripts/run_evaluation_baseline.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json
```

This baseline validates fixture readiness before live retrieval or assistant evaluation. It reports:

- total case count
- answerable and no-answer case counts
- category coverage
- assistant type coverage
- expected metadata field coverage
- duplicate case ids
- missing required fields
- invalid category or assistant type values

The command is intentionally read-only. It does not connect to PostgreSQL, Qdrant, Redis, Celery, rerank providers, embedding services, or LLMs. It does not upload documents, create evaluation runs, create suggestions, mutate `documents.metadata`, or trigger reindexing.

A successful baseline means the fixture file is structurally ready for a later live evaluation workflow. It does not prove retrieval quality, answer quality, citation correctness, or rerank effectiveness. Those still require the existing API-backed retrieval and assistant evaluation paths after fixtures have been imported and indexed.

If the baseline exits non-zero, fix duplicate case ids, missing required fields, or unsupported category / assistant type values before running live evaluation.

## Retrieval Evaluation Smoke Test

`make eval-smoke` runs a deterministic smoke test through the existing retrieval evaluation service logic:

```bash
make eval-smoke
```

Equivalent direct command:

```bash
python scripts/run_retrieval_evaluation_smoke.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json
```

The smoke runner loads `eval_cases.json`, builds deterministic fake retrieval results for answerable cases, returns no results for no-answer cases, and exercises `EvaluationService.evaluate_case()` plus `calculate_metrics()`. It verifies that Hit@K, MRR, keyword match, metadata match, and no-answer accuracy can be calculated end to end without live infrastructure.

This is still a read-only tooling check. It does not connect to PostgreSQL, Qdrant, Redis, Celery, embedding providers, rerank providers, or LLMs. It does not create `evaluation_runs`, persist `evaluation_case_results`, upload documents, create suggestions, mutate `documents.metadata`, or trigger reindexing.

Use this smoke test after `make eval` passes and before running the heavier API-backed retrieval evaluation. Passing smoke results mean the evaluation code path is structurally healthy with deterministic retrieval, not that production retrieval quality is good.

## Real Retrieval Evaluation Harness

`make eval-real` runs the real retrieval evaluation harness against an already running CoreKB API:

```bash
COREKB_ADMIN_TOKEN=... COREKB_API_BASE_URL=http://localhost:8000 make eval-real
```

Equivalent direct command:

```bash
COREKB_ADMIN_TOKEN=... python scripts/run_real_retrieval_evaluation.py \
  --api-base-url http://localhost:8000 \
  --confirm-persist
```

The harness calls existing API endpoints only:

- `POST /api/evaluation/retrieval/run` for a single retrieval evaluation run.
- `POST /api/evaluation/retrieval/compare` when `--mode compare` is used.

The harness requires an admin bearer token via `COREKB_ADMIN_TOKEN` or `--token`. It also requires `--confirm-persist` because the existing API creates `evaluation_runs` and `evaluation_case_results` records. This confirmation prevents accidental writes during local experimentation.

Useful options:

```bash
python scripts/run_real_retrieval_evaluation.py --confirm-persist --use-metadata-filter
python scripts/run_real_retrieval_evaluation.py --confirm-persist --use-metadata-filter --use-rerank --rerank-top-n 20
python scripts/run_real_retrieval_evaluation.py --confirm-persist --mode compare --rerank-top-n 20
```

Use the commands in this order when validating a CoreKB environment:

1. `make eval`: validate fixture shape and coverage.
2. `make eval-smoke`: exercise evaluation logic with deterministic fake retrieval.
3. `make eval-real`: call the live API after the Evaluation KB has been imported and indexed.

`eval-real` does not import backend services directly and does not connect directly to PostgreSQL, Qdrant, Redis, Celery, embedding providers, rerank providers, or LLMs. Those dependencies are reached only through the already running CoreKB API. It does not mutate documents, metadata, suggestions, or source files, but it does create evaluation records through the API by design.

## Evaluation Result Dashboard

The frontend includes an admin-only `Eval Dashboard` page for a read-only overview of recent evaluation results. It reuses existing evaluation APIs and does not create evaluation runs or modify evaluation data.

The dashboard shows:

- latest retrieval Hit@3, MRR, and no-answer accuracy
- latest assistant quality gate and citation rate
- open improvement item count
- open annotation count
- regression pass rate
- recent retrieval and assistant evaluation runs
- assistant trend warnings
- recent regression records

Use the dashboard for quick status checks. Use the full `Evaluation` workbench when you need to run evaluations, compare runs, inspect failed cases, generate improvement items, or manage annotations.

The dashboard intentionally uses cards and tables only. It does not add charts, BI features, new backend APIs, or write actions.

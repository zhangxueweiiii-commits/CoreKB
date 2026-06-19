import { useEffect, useState } from "react";
import {
  evaluationApi,
  type AnnotationSummary,
  type AnnotationSummaryBucket,
  type AssistantEvaluationCompareResult,
  type AssistantEvaluationMetrics,
  type AssistantEvaluationResult,
  type AssistantTrendResponse,
  type CaseAnnotation,
  type CaseAnnotationPayload,
  type EvalCaseResult,
  type EvaluationRegression,
  type EvaluationCaseCompareResult,
  type EvaluationRunCompareResult,
  type EvaluationRun,
  type EvaluationRunListItem,
  type FailedCaseDiffItem,
  type ImprovementItem,
  type ImprovementSummary,
  type RegressionSummary,
  type RegressionTrendResponse,
  type RetrievalEvaluationCompareResult,
  type RetrievalEvaluationResult,
} from "../api/evaluation";

function percent(value?: number | null) {
  if (value === undefined || value === null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function numericMetric(value: number | boolean | undefined): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function failedCasesFromRun(run: EvaluationRun | null): EvalCaseResult[] {
  return run?.failed_cases ?? [];
}

const CHANGE_TYPE_OPTIONS = [
  "baseline",
  "prompt",
  "metadata",
  "chunking",
  "rerank",
  "eval_case",
  "parser",
  "mixed",
  "unknown",
];

const CHANGE_TYPE_LABELS: Record<string, string> = {
  baseline: "基线",
  prompt: "提示词",
  metadata: "元数据",
  chunking: "切片",
  rerank: "重排",
  eval_case: "评估用例",
  parser: "解析器",
  mixed: "混合修改",
  unknown: "未标注",
};

const HUMAN_JUDGEMENT_OPTIONS = [
  "system_correct",
  "system_partially_correct",
  "system_incorrect",
  "business_expected_answer_wrong",
  "insufficient_documentation",
  "needs_expert_review",
] as const;

const HUMAN_ROOT_CAUSE_OPTIONS = [
  "prompt",
  "metadata_filter",
  "document_metadata",
  "chunking",
  "rerank",
  "parser",
  "source_document",
  "evaluation_case",
  "business_rule",
  "unknown",
] as const;

const HUMAN_FIX_TYPE_OPTIONS = [
  "update_prompt",
  "update_metadata",
  "update_chunking",
  "tune_rerank",
  "improve_parser",
  "supplement_document",
  "revise_eval_case",
  "confirm_business_rule",
  "no_action",
] as const;

const HANDLING_STATUS_OPTIONS = ["open", "investigating", "planned", "resolved", "ignored"] as const;

const DEFAULT_ANNOTATION_DRAFT: CaseAnnotationPayload = {
  human_judgement: "system_partially_correct",
  human_root_cause: "unknown",
  human_fix_type: "no_action",
  handling_status: "open",
  handling_notes: "",
};

function changeTypeLabel(value?: string | null) {
  return CHANGE_TYPE_LABELS[value || "unknown"] ?? value ?? "未标注";
}

function truncateText(value?: string | null, length = 36) {
  if (!value) return "-";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function runOptionText(run: EvaluationRunListItem) {
  return `${run.display_label} | ${changeTypeLabel(run.change_type)} | ${run.mode_summary} | ${new Date(run.created_at).toLocaleString()}`;
}

function metricInterpretation(delta: number) {
  if (delta > 0) return "Improved";
  if (delta < 0) return "Degraded";
  return "Unchanged";
}

function metricDisplay(value: unknown, metric?: string) {
  if (typeof value === "boolean") return value ? "Pass" : "Fail";
  if (typeof value !== "number") return "-";
  if (metric === "mrr") return value.toFixed(3);
  return value <= 1 && value >= -1 ? percent(value) : value.toFixed(3);
}

function bucketCount(summary: AnnotationSummary | null, group: keyof AnnotationSummary, key: string) {
  const value = summary?.[group];
  if (!Array.isArray(value)) return 0;
  return (value as AnnotationSummaryBucket[]).find((item) => item.key === key)?.count ?? 0;
}

function topBucket(items?: AnnotationSummaryBucket[]) {
  return items && items.length > 0 ? items[0] : null;
}

function FailedCaseDiffTable({
  title,
  items,
  onDrillDown,
}: {
  title: string;
  items: FailedCaseDiffItem[];
  onDrillDown: (caseId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="subtle-block">
      <button type="button" onClick={() => setExpanded((value) => !value)}>
        {expanded ? "收起" : "展开"} {title} ({items.length})
      </button>
      {expanded && (
        items.length === 0 ? (
          <p className="muted">暂无记录</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case id</th>
                <th>Assistant</th>
                <th>Query</th>
                <th>Failure reason</th>
                <th>Suggested fix</th>
                <th>Before top docs</th>
                <th>After top docs</th>
                <th>Before filter</th>
                <th>After filter</th>
                <th>Human annotation</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`${title}-${item.case_id}`}>
                  <td>{item.case_id}</td>
                  <td>{item.assistant_type || "-"}</td>
                  <td>{item.query || "-"}</td>
                  <td>{item.failure_reason || "-"}</td>
                  <td>{item.suggested_fix_type || "-"}</td>
                  <td>{item.before_actual_top_documents.join(", ") || "-"}</td>
                  <td>{item.after_actual_top_documents.join(", ") || "-"}</td>
                  <td>{JSON.stringify(item.before_used_metadata_filter)}</td>
                  <td>{JSON.stringify(item.after_used_metadata_filter)}</td>
                  <td>
                    {item.annotation
                      ? `${item.annotation.human_root_cause} / ${item.annotation.handling_status}`
                      : item.annotation_status || "未标注"}
                  </td>
                  <td>
                    <button type="button" onClick={() => onDrillDown(item.case_id)}>
                      Drill-down
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}

function RunSummary({
  run,
}: {
  run?: Pick<
    EvaluationRunListItem,
    "display_label" | "change_type" | "mode_summary" | "created_at" | "change_summary" | "metrics_summary"
  > | null;
}) {
  if (!run) return <p className="muted">未选择评估 run</p>;
  return (
    <div className="subtle-block">
      <strong>{run.display_label}</strong>
      <p className="muted">
        {changeTypeLabel(run.change_type)} · {run.mode_summary} · {new Date(run.created_at).toLocaleString()}
      </p>
      <p title={run.change_summary ?? undefined}>{truncateText(run.change_summary, 80)}</p>
      <div className="metric-grid">
        <span>Hit@1: {percent(run.metrics_summary.hit_at_1 as number | null)}</span>
        <span>Hit@3: {percent(run.metrics_summary.hit_at_3 as number | null)}</span>
        <span>MRR: {typeof run.metrics_summary.mrr === "number" ? run.metrics_summary.mrr.toFixed(3) : "-"}</span>
        <span>Citation: {percent(run.metrics_summary.citation_rate as number | null)}</span>
        <span>No-answer: {percent(run.metrics_summary.no_answer_accuracy as number | null)}</span>
        <span>Gate: {run.metrics_summary.quality_gate_passed === true ? "Pass" : run.metrics_summary.quality_gate_passed === false ? "Fail" : "-"}</span>
      </div>
    </div>
  );
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

function CaseSnapshotPanel({ title, snapshot }: { title: string; snapshot?: Record<string, unknown> | null }) {
  if (!snapshot) {
    return (
      <div className="subtle-block">
        <h4>{title}</h4>
        <p className="muted">该历史运行未保存详细快照。</p>
      </div>
    );
  }
  const retrievedResults = asRecordArray(snapshot.retrieved_results);
  const citations = asRecordArray(snapshot.citations);
  return (
    <div className="subtle-block">
      <h4>{title}: {snapshot.passed ? "Pass" : "Fail"}</h4>
      <div className="metric-grid">
        <span>Failure: {String(snapshot.failure_reason || "-")}</span>
        <span>Suggested fix: {String(snapshot.suggested_fix_type || "-")}</span>
        <span>Rerank: {String(snapshot.use_rerank)} / applied {String(snapshot.rerank_applied)}</span>
        <span>Filter: {JSON.stringify(snapshot.used_metadata_filter || {})}</span>
      </div>
      <p>{String(snapshot.answer_excerpt || "-")}</p>
      <h5>Citations</h5>
      {citations.length === 0 ? (
        <p className="muted">无引用</p>
      ) : (
        <ul>
          {citations.map((citation, index) => (
            <li key={`${title}-citation-${index}`}>
              {String(citation.filename || "-")} · {String(citation.quote || "").slice(0, 160)}
            </li>
          ))}
        </ul>
      )}
      <h5>Retrieved results</h5>
      {retrievedResults.length === 0 ? (
        <p className="muted">无检索快照</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Document</th>
              <th>Chunk excerpt</th>
              <th>Vector</th>
              <th>Rerank</th>
              <th>Final</th>
              <th>Metadata</th>
              <th>Citation</th>
            </tr>
          </thead>
          <tbody>
            {retrievedResults.map((item, index) => (
              <tr key={`${title}-retrieved-${index}`}>
                <td>{String(item.rank ?? "-")}</td>
                <td>{String(item.document_name || "-")}</td>
                <td>{String(item.chunk_excerpt || "-").slice(0, 240)}</td>
                <td>{typeof item.vector_score === "number" ? item.vector_score.toFixed(3) : "-"}</td>
                <td>{typeof item.rerank_score === "number" ? item.rerank_score.toFixed(3) : "-"}</td>
                <td>{typeof item.final_score === "number" ? item.final_score.toFixed(3) : "-"}</td>
                <td>{JSON.stringify(item.chunk_metadata || {})}</td>
                <td>{JSON.stringify(item.citation || {})}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AssistantMetricsRow({ label, metrics }: { label: string; metrics: AssistantEvaluationMetrics }) {
  return (
    <tr>
      <td>{label}</td>
      <td>{metrics.quality_gate_passed ? "Pass" : "Fail"}</td>
      <td>{metrics.total_cases}</td>
      <td>{percent(metrics.hit_at_1)}</td>
      <td>{percent(metrics.hit_at_3)}</td>
      <td>{percent(metrics.hit_at_5)}</td>
      <td>{metrics.mrr.toFixed(3)}</td>
      <td>{percent(metrics.keyword_match_rate)}</td>
      <td>{percent(metrics.metadata_match_rate)}</td>
      <td>{percent(metrics.no_answer_accuracy)}</td>
      <td>{percent(metrics.citation_rate)}</td>
      <td>{metrics.failed_cases.length}</td>
    </tr>
  );
}

export function EvaluationPage({
  onOpenAnnotations,
}: {
  onOpenAnnotations?: (search: string) => void;
}) {
  const [latest, setLatest] = useState<EvaluationRun | null>(null);
  const [lastRun, setLastRun] = useState<RetrievalEvaluationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [useMetadataFilter, setUseMetadataFilter] = useState(false);
  const [useRerank, setUseRerank] = useState(false);
  const [comparison, setComparison] = useState<RetrievalEvaluationCompareResult | null>(null);
  const [assistantLatest, setAssistantLatest] = useState<AssistantEvaluationResult | null>(null);
  const [assistantResult, setAssistantResult] = useState<AssistantEvaluationResult | null>(null);
  const [assistantComparison, setAssistantComparison] = useState<AssistantEvaluationCompareResult | null>(null);
  const [assistantUseMetadataFilter, setAssistantUseMetadataFilter] = useState(true);
  const [assistantUseRerank, setAssistantUseRerank] = useState(true);
  const [runLabel, setRunLabel] = useState("");
  const [changeType, setChangeType] = useState("unknown");
  const [changeSummary, setChangeSummary] = useState("");
  const [operatorNotes, setOperatorNotes] = useState("");
  const [expandedAssistant, setExpandedAssistant] = useState<string | null>(null);
  const [improvementItems, setImprovementItems] = useState<ImprovementItem[]>([]);
  const [improvementSummary, setImprovementSummary] = useState<ImprovementSummary | null>(null);
  const [annotationSummary, setAnnotationSummary] = useState<AnnotationSummary | null>(null);
  const [evaluationRuns, setEvaluationRuns] = useState<EvaluationRunListItem[]>([]);
  const [runSearch, setRunSearch] = useState("");
  const [runChangeTypeFilter, setRunChangeTypeFilter] = useState("");
  const [runAssistantTypeFilter, setRunAssistantTypeFilter] = useState("");
  const [editingRunId, setEditingRunId] = useState<string | null>(null);
  const [editRunLabel, setEditRunLabel] = useState("");
  const [editChangeType, setEditChangeType] = useState("unknown");
  const [editChangeSummary, setEditChangeSummary] = useState("");
  const [editOperatorNotes, setEditOperatorNotes] = useState("");
  const [regressions, setRegressions] = useState<EvaluationRegression[]>([]);
  const [regressionSummary, setRegressionSummary] = useState<RegressionSummary | null>(null);
  const [selectedImprovementIds, setSelectedImprovementIds] = useState<string[]>([]);
  const [beforeRunId, setBeforeRunId] = useState("");
  const [afterRunId, setAfterRunId] = useState("");
  const [compareBeforeRunId, setCompareBeforeRunId] = useState("");
  const [compareAfterRunId, setCompareAfterRunId] = useState("");
  const [runCompareResult, setRunCompareResult] = useState<EvaluationRunCompareResult | null>(null);
  const [caseCompareResult, setCaseCompareResult] = useState<EvaluationCaseCompareResult | null>(null);
  const [annotationDraft, setAnnotationDraft] = useState<CaseAnnotationPayload>(DEFAULT_ANNOTATION_DRAFT);
  const [annotationSaving, setAnnotationSaving] = useState(false);
  const [regressionNotes, setRegressionNotes] = useState("");
  const [lastRegression, setLastRegression] = useState<EvaluationRegression | null>(null);
  const [trendAssistantType, setTrendAssistantType] = useState("all");
  const [trendMode, setTrendMode] = useState("metadata_filter_rerank");
  const [assistantTrends, setAssistantTrends] = useState<AssistantTrendResponse | null>(null);
  const [regressionTrends, setRegressionTrends] = useState<RegressionTrendResponse | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setLatest(await evaluationApi.latestRetrieval());
      setAssistantLatest(await evaluationApi.latestAssistants());
      setImprovementItems(await evaluationApi.listImprovements());
      setImprovementSummary(await evaluationApi.improvementSummary());
      setAnnotationSummary(await evaluationApi.annotationSummary());
      setRegressions(await evaluationApi.listRegressions());
      setRegressionSummary(await evaluationApi.regressionSummary());
      await loadEvaluationRuns();
      await loadTrends();
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载评估结果失败");
    } finally {
      setLoading(false);
    }
  }

  async function run() {
    setRunning(true);
    setError("");
    try {
      const result = await evaluationApi.runRetrieval(useMetadataFilter, useRerank);
      setLastRun(result);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行评估失败");
    } finally {
      setRunning(false);
    }
  }

  async function runComparison() {
    setRunning(true);
    setError("");
    try {
      const result = await evaluationApi.compareRetrieval();
      setComparison(result);
      setLastRun(result.metadata_filter_rerank);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行对比失败");
    } finally {
      setRunning(false);
    }
  }

  async function runAssistantEvaluation() {
    setRunning(true);
    setError("");
    try {
      const result = await evaluationApi.runAssistants(assistantUseMetadataFilter, assistantUseRerank, {
        run_label: runLabel || undefined,
        change_type: changeType,
        change_summary: changeSummary || undefined,
        operator_notes: operatorNotes || undefined,
      });
      setAssistantResult(result);
      setAssistantLatest(result);
      await loadImprovements();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行助手评估失败");
    } finally {
      setRunning(false);
    }
  }

  async function runAssistantComparison() {
    setRunning(true);
    setError("");
    try {
      const result = await evaluationApi.compareAssistants();
      setAssistantComparison(result);
      setAssistantResult(result.metadata_filter_rerank);
      setAssistantLatest(result.metadata_filter_rerank);
      await loadImprovements();
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行助手对比失败");
    } finally {
      setRunning(false);
    }
  }

  async function loadImprovements() {
    setImprovementItems(await evaluationApi.listImprovements());
    setImprovementSummary(await evaluationApi.improvementSummary());
    setAnnotationSummary(await evaluationApi.annotationSummary());
    setRegressions(await evaluationApi.listRegressions());
    setRegressionSummary(await evaluationApi.regressionSummary());
    await loadEvaluationRuns();
    await loadTrends();
  }

  async function loadEvaluationRuns() {
    setEvaluationRuns(
      await evaluationApi.listRuns({
        change_type: runChangeTypeFilter || undefined,
        assistant_type: runAssistantTypeFilter || undefined,
        limit: 100,
      }),
    );
  }

  function trendModeFlags() {
    if (trendMode === "baseline") return { use_metadata_filter: false, use_rerank: false };
    if (trendMode === "metadata_filter") return { use_metadata_filter: true, use_rerank: false };
    return { use_metadata_filter: true, use_rerank: true };
  }

  async function loadTrends() {
    const flags = trendModeFlags();
    setAssistantTrends(
      await evaluationApi.assistantTrends({
        assistant_type: trendAssistantType === "all" ? undefined : trendAssistantType,
        limit: 20,
        ...flags,
      }),
    );
    setRegressionTrends(await evaluationApi.regressionTrends(20));
  }

  async function generateImprovementItems(force = false) {
    if (!assistantReport?.run_id) {
      setError("请先运行或加载一次助手评估，再生成改进清单");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const items = await evaluationApi.generateImprovements(assistantReport.run_id, force);
      setImprovementItems(items);
      setImprovementSummary(await evaluationApi.improvementSummary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成改进清单失败");
    } finally {
      setRunning(false);
    }
  }

  async function updateImprovementStatus(item: ImprovementItem, status: ImprovementItem["status"]) {
    setRunning(true);
    setError("");
    try {
      await evaluationApi.updateImprovement(item.id, { status });
      await loadImprovements();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新改进项失败");
    } finally {
      setRunning(false);
    }
  }

  function toggleImprovementSelection(itemId: string) {
    setSelectedImprovementIds((current) =>
      current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId],
    );
  }

  async function createRegression() {
    if (!beforeRunId || !afterRunId || selectedImprovementIds.length === 0) {
      setError("请选择 before run、after run 和至少一个改进项");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const regression = await evaluationApi.createRegression({
        before_evaluation_run_id: beforeRunId,
        after_evaluation_run_id: afterRunId,
        improvement_item_ids: selectedImprovementIds,
        notes: regressionNotes || undefined,
      });
      setLastRegression(regression);
      await loadImprovements();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建回归记录失败");
    } finally {
      setRunning(false);
    }
  }

  async function compareSelectedRuns() {
    if (!compareBeforeRunId || !compareAfterRunId) {
      setError("请选择用于对比的 before run 和 after run");
      return;
    }
    setRunning(true);
    setError("");
    try {
      setRunCompareResult(await evaluationApi.compareRuns(compareBeforeRunId, compareAfterRunId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "评估运行对比失败");
    } finally {
      setRunning(false);
    }
  }

  async function openCaseDrillDown(caseId: string) {
    if (!compareBeforeRunId || !compareAfterRunId) {
      setError("请选择 before / after run 后再查看 case drill-down");
      return;
    }
    setRunning(true);
    setError("");
    try {
      setCaseCompareResult(await evaluationApi.compareCase(caseId, compareBeforeRunId, compareAfterRunId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 case drill-down 失败");
    } finally {
      setRunning(false);
    }
  }

  function currentAnnotation(): CaseAnnotation | null {
    return caseCompareResult?.after?.annotation || caseCompareResult?.before?.annotation || null;
  }

  function currentCaseResultId(): string | null {
    return caseCompareResult?.after?.case_result_id || caseCompareResult?.before?.case_result_id || null;
  }

  function syncAnnotationDraft(annotation?: CaseAnnotation | null) {
    if (!annotation) {
      setAnnotationDraft(DEFAULT_ANNOTATION_DRAFT);
      return;
    }
    setAnnotationDraft({
      human_judgement: annotation.human_judgement,
      human_root_cause: annotation.human_root_cause,
      human_fix_type: annotation.human_fix_type,
      handling_status: annotation.handling_status,
      handling_notes: annotation.handling_notes ?? "",
    });
  }

  async function saveCaseAnnotation() {
    const caseResultId = currentCaseResultId();
    if (!caseResultId || !caseCompareResult) {
      setError("当前 case 没有可标注的评估快照");
      return;
    }
    setAnnotationSaving(true);
    setError("");
    try {
      await evaluationApi.upsertCaseAnnotation(caseResultId, annotationDraft);
      setCaseCompareResult(await evaluationApi.compareCase(caseCompareResult.case_id, compareBeforeRunId, compareAfterRunId));
      setAnnotationSummary(await evaluationApi.annotationSummary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存人工标注失败");
    } finally {
      setAnnotationSaving(false);
    }
  }

  function openAnnotations(filters: Record<string, string>) {
    const search = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    onOpenAnnotations?.(`?${search.toString()}`);
  }

  function beginEditRun(run: EvaluationRunListItem) {
    setEditingRunId(run.id);
    setEditRunLabel(run.run_label ?? "");
    setEditChangeType(run.change_type ?? "unknown");
    setEditChangeSummary(run.change_summary ?? "");
    setEditOperatorNotes(run.operator_notes ?? "");
  }

  async function saveRunMetadata(runId: string) {
    setRunning(true);
    setError("");
    try {
      await evaluationApi.updateRunMetadata(runId, {
        run_label: editRunLabel,
        change_type: editChangeType,
        change_summary: editChangeSummary,
        operator_notes: editOperatorNotes,
      });
      setEditingRunId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新评估备注失败");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    syncAnnotationDraft(currentAnnotation());
  }, [caseCompareResult]);

  const metrics = lastRun ?? latest?.metrics;
  const failedCases = lastRun?.failed_cases ?? failedCasesFromRun(latest);
  const assistantReport = assistantResult ?? assistantLatest;
  const assistantMetricsEntries = assistantReport ? Object.entries(assistantReport.per_assistant_metrics) : [];
  const metadataIssueCount =
    (improvementSummary?.by_fix_type.metadata_filter ?? 0) +
    (improvementSummary?.by_fix_type.document_metadata ?? 0);
  const normalizedRunSearch = runSearch.trim().toLowerCase();
  const filteredEvaluationRuns = evaluationRuns.filter((run) => {
    if (!normalizedRunSearch) return true;
    return [run.display_label, run.run_label, run.change_type, run.change_summary]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalizedRunSearch));
  });
  const selectedBeforeRun = evaluationRuns.find((run) => run.id === beforeRunId);
  const selectedAfterRun = evaluationRuns.find((run) => run.id === afterRunId);
  const selectedCompareBeforeRun = evaluationRuns.find((run) => run.id === compareBeforeRunId);
  const selectedCompareAfterRun = evaluationRuns.find((run) => run.id === compareAfterRunId);
  const topRootCause = topBucket(annotationSummary?.by_root_cause);
  const topFixType = topBucket(annotationSummary?.by_fix_type);
  const openAnnotationCount =
    bucketCount(annotationSummary, "by_handling_status", "open") +
    bucketCount(annotationSummary, "by_handling_status", "investigating") +
    bucketCount(annotationSummary, "by_handling_status", "planned");
  const resolvedAnnotationCount = bucketCount(annotationSummary, "by_handling_status", "resolved");

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>检索评估</h2>
        <label className="inline-control">
          <input
            type="checkbox"
            checked={useMetadataFilter}
            onChange={(event) => setUseMetadataFilter(event.target.checked)}
          />
          Use metadata filter
        </label>
        <label className="inline-control">
          <input
            type="checkbox"
            checked={useRerank}
            onChange={(event) => setUseRerank(event.target.checked)}
          />
          Use rerank
        </label>
        <button type="button" onClick={run} disabled={running}>
          {running ? "评估中..." : "运行评估"}
        </button>
        <button type="button" onClick={runComparison} disabled={running}>
          Run comparison
        </button>
      </div>
      {loading && <p className="muted">加载中...</p>}
      {error && <p className="error">{error}</p>}
      {latest && <p className="muted">最近一次评估：{new Date(latest.created_at).toLocaleString()}</p>}

      <div className="metric-grid">
        <span>Total: {lastRun?.total_cases ?? latest?.total_cases ?? 0}</span>
        <span>Filter: {String(lastRun?.use_metadata_filter ?? latest?.metrics?.use_metadata_filter ?? false)}</span>
        <span>Rerank: {String(lastRun?.use_rerank ?? latest?.metrics?.use_rerank ?? false)}</span>
        <span>Hit@1: {percent(numericMetric(metrics?.hit_at_1))}</span>
        <span>Hit@3: {percent(numericMetric(metrics?.hit_at_3))}</span>
        <span>Hit@5: {percent(numericMetric(metrics?.hit_at_5))}</span>
        <span>MRR: {numericMetric(metrics?.mrr)?.toFixed(3) ?? "-"}</span>
        <span>Keyword: {percent(numericMetric(metrics?.keyword_match_rate))}</span>
        <span>Metadata: {percent(numericMetric(metrics?.metadata_match_rate))}</span>
        <span>No-answer: {percent(numericMetric(metrics?.no_answer_accuracy))}</span>
      </div>

      {comparison && (
        <div className="subtle-block">
          <h3>三组对比</h3>
          <table>
            <thead>
              <tr>
                <th>模式</th>
                <th>Hit@1</th>
                <th>Hit@3</th>
                <th>Hit@5</th>
                <th>MRR</th>
                <th>Keyword</th>
                <th>Metadata</th>
                <th>No-answer</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["baseline", comparison.baseline],
                ["metadata filter", comparison.metadata_filter],
                ["metadata filter + rerank", comparison.metadata_filter_rerank],
              ].map(([label, item]) => (
                <tr key={label as string}>
                  <td>{label as string}</td>
                  <td>{percent((item as RetrievalEvaluationResult).hit_at_1)}</td>
                  <td>{percent((item as RetrievalEvaluationResult).hit_at_3)}</td>
                  <td>{percent((item as RetrievalEvaluationResult).hit_at_5)}</td>
                  <td>{(item as RetrievalEvaluationResult).mrr.toFixed(3)}</td>
                  <td>{percent((item as RetrievalEvaluationResult).keyword_match_rate)}</td>
                  <td>{percent((item as RetrievalEvaluationResult).metadata_match_rate)}</td>
                  <td>{percent((item as RetrievalEvaluationResult).no_answer_accuracy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="subtle-block">
        <h3>失败用例</h3>
        {failedCases.length === 0 ? (
          <p className="muted">暂无失败用例</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>类别</th>
                <th>问题</th>
                <th>Hit@5</th>
                <th>Keyword</th>
                <th>Metadata</th>
                <th>No-answer</th>
              </tr>
            </thead>
            <tbody>
              {failedCases.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.category}</td>
                  <td>{item.query}</td>
                  <td>{item.hit_at_5 ? "是" : "否"}</td>
                  <td>{percent(item.keyword_match_rate)}</td>
                  <td>{percent(item.metadata_match_rate)}</td>
                  <td>{item.no_answer_correct === null || item.no_answer_correct === undefined ? "-" : item.no_answer_correct ? "正确" : "失败"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="subtle-block">
        <div className="section-heading">
          <h3>岗位助手评估报告</h3>
          <label className="inline-control">
            <input
              type="checkbox"
              checked={assistantUseMetadataFilter}
              onChange={(event) => setAssistantUseMetadataFilter(event.target.checked)}
            />
            Use metadata filter
          </label>
          <label className="inline-control">
            <input
              type="checkbox"
              checked={assistantUseRerank}
              onChange={(event) => setAssistantUseRerank(event.target.checked)}
            />
            Use rerank
          </label>
          <button type="button" onClick={runAssistantEvaluation} disabled={running}>
            运行助手评估
          </button>
          <button type="button" onClick={runAssistantComparison} disabled={running}>
            Run assistant comparison
          </button>
        </div>

        <div className="form-grid">
          <label>
            Run label
            <input
              value={runLabel}
              onChange={(event) => setRunLabel(event.target.value)}
              placeholder="maintenance_prompt_v2"
            />
          </label>
          <label>
            Change type
            <select value={changeType} onChange={(event) => setChangeType(event.target.value)}>
              {CHANGE_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            Change summary
            <input
              value={changeSummary}
              onChange={(event) => setChangeSummary(event.target.value)}
              placeholder="强化资料不足时拒答"
            />
          </label>
          <label>
            Operator notes
            <input
              value={operatorNotes}
              onChange={(event) => setOperatorNotes(event.target.value)}
              placeholder="重点观察 no-answer accuracy 和 citation_rate"
            />
          </label>
        </div>

        {assistantReport?.created_at && (
          <p className="muted">最近一次助手评估：{new Date(assistantReport.created_at).toLocaleString()}</p>
        )}

        {assistantReport ? (
          <>
            <div className="metric-grid">
              <span>Total: {assistantReport.total_cases}</span>
              <span>Filter: {String(assistantReport.use_metadata_filter)}</span>
              <span>Rerank: {String(assistantReport.use_rerank)}</span>
              <span>Hit@1: {percent(assistantReport.overall_metrics.hit_at_1)}</span>
              <span>MRR: {assistantReport.overall_metrics.mrr.toFixed(3)}</span>
              <span>Citation: {percent(assistantReport.overall_metrics.citation_rate)}</span>
              <span>Quality gate: {assistantReport.quality_gate_passed ? "Pass" : "Fail"}</span>
              <span>Run label: {assistantReport.run_label || "-"}</span>
              <span>Change type: {assistantReport.change_type || "unknown"}</span>
            </div>

            <table>
              <thead>
                <tr>
                  <th>助手类型</th>
                  <th>质量门</th>
                  <th>测试用例数</th>
                  <th>Hit@1</th>
                  <th>Hit@3</th>
                  <th>Hit@5</th>
                  <th>MRR</th>
                  <th>Keyword</th>
                  <th>Metadata</th>
                  <th>No-answer</th>
                  <th>Citation</th>
                  <th>Failed</th>
                </tr>
              </thead>
              <tbody>
                <AssistantMetricsRow label="overall" metrics={assistantReport.overall_metrics} />
                {assistantMetricsEntries.map(([assistantType, metrics]) => (
                  <AssistantMetricsRow key={assistantType} label={assistantType} metrics={metrics} />
                ))}
              </tbody>
            </table>

            {assistantMetricsEntries.map(([assistantType, metrics]) => (
              <div key={`${assistantType}-failed`} className="subtle-block">
                <h4>{assistantType} quality gate: {metrics.quality_gate_passed ? "Pass" : "Fail"}</h4>
                {metrics.failed_thresholds.length > 0 && (
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Actual</th>
                        <th>Required</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.failed_thresholds.map((item) => (
                        <tr key={`${assistantType}-${item.metric}`}>
                          <td>{item.metric}</td>
                          <td>{percent(item.actual)}</td>
                          <td>{percent(item.required)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <button
                  type="button"
                  onClick={() => setExpandedAssistant(expandedAssistant === assistantType ? null : assistantType)}
                >
                  {expandedAssistant === assistantType ? "收起" : "展开"} {assistantType} failed cases ({metrics.failed_cases.length})
                </button>
                {expandedAssistant === assistantType && (
                  metrics.failed_cases.length === 0 ? (
                    <p className="muted">暂无失败用例</p>
                  ) : (
                    <table>
                      <thead>
                        <tr>
                          <th>Case</th>
                          <th>Query</th>
                          <th>Expected document</th>
                          <th>Actual top documents</th>
                          <th>Expected metadata</th>
                          <th>Used filter</th>
                          <th>Failure reason</th>
                          <th>Suggested fix</th>
                          <th>Detail</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.failed_cases.map((item) => (
                          <tr key={item.id}>
                            <td>{item.id}</td>
                            <td>{item.query}</td>
                            <td>{item.expected_document ?? "-"}</td>
                            <td>{item.actual_top_documents.join(", ") || "-"}</td>
                            <td>{JSON.stringify(item.expected_metadata)}</td>
                            <td>{JSON.stringify(item.used_metadata_filter)}</td>
                            <td>{item.failure_reason || item.reason || "-"}</td>
                            <td>{item.suggested_fix_type || "-"}</td>
                            <td>{item.failure_detail || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                )}
              </div>
            ))}
          </>
        ) : (
          <p className="muted">暂无助手评估结果</p>
        )}

        {assistantComparison && (
          <div className="subtle-block">
            <h3>助手三组对比</h3>
            <table>
              <thead>
                <tr>
                  <th>模式</th>
                  <th>Hit@1</th>
                  <th>MRR</th>
                  <th>Citation</th>
                  <th>No-answer</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["baseline", assistantComparison.baseline],
                  ["metadata filter", assistantComparison.metadata_filter],
                  ["metadata filter + rerank", assistantComparison.metadata_filter_rerank],
                ].map(([label, item]) => (
                  <tr key={label as string}>
                    <td>{label as string}</td>
                    <td>{percent((item as AssistantEvaluationResult).overall_metrics.hit_at_1)}</td>
                    <td>{(item as AssistantEvaluationResult).overall_metrics.mrr.toFixed(3)}</td>
                    <td>{percent((item as AssistantEvaluationResult).overall_metrics.citation_rate)}</td>
                    <td>{percent((item as AssistantEvaluationResult).overall_metrics.no_answer_accuracy)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="subtle-block">
          <div className="section-heading">
            <h3>改进清单</h3>
            <button
              type="button"
              onClick={() => generateImprovementItems(false)}
              disabled={running || !assistantReport?.run_id}
            >
              Generate improvement items
            </button>
            <button
              type="button"
              onClick={() => generateImprovementItems(true)}
              disabled={running || !assistantReport?.run_id}
            >
              Regenerate with force
            </button>
          </div>
          <p className="muted">
            改进清单用于定位下一轮优化重点。修复后请重新运行同一批 eval cases，对比指标变化。
          </p>
          <div className="metric-grid">
            <span>Open items: {improvementSummary?.total_open ?? 0}</span>
            <span>Prompt issues: {improvementSummary?.by_fix_type.prompt ?? 0}</span>
            <span>Metadata issues: {metadataIssueCount}</span>
            <span>Rerank issues: {improvementSummary?.by_fix_type.rerank ?? 0}</span>
            <span>Chunking issues: {improvementSummary?.by_fix_type.chunking ?? 0}</span>
          </div>
          {improvementItems.length === 0 ? (
            <p className="muted">暂无改进项。运行助手评估后可生成改进清单。</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Select</th>
                  <th>Assistant</th>
                  <th>Fix type</th>
                  <th>Failed cases</th>
                  <th>Source</th>
                  <th>Annotations</th>
                  <th>Main reasons</th>
                  <th>Suggested action</th>
                  <th>Status</th>
                  <th>Regression status</th>
                  <th>Resolved run</th>
                  <th>Related regression</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {improvementItems.map((item) => (
                  <tr key={item.id}>
                    <td>{item.priority}</td>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedImprovementIds.includes(item.id)}
                        onChange={() => toggleImprovementSelection(item.id)}
                      />
                    </td>
                    <td>{item.assistant_type}</td>
                    <td>{item.fix_type}</td>
                    <td>{item.failed_case_count} ({item.affected_case_ids.join(", ")})</td>
                    <td>{item.source}</td>
                    <td>{item.annotation_count}</td>
                    <td>{item.main_failure_reasons.join(", ")}</td>
                    <td>{item.suggested_action}</td>
                    <td>{item.status}</td>
                    <td>{item.regression_status}</td>
                    <td>{item.resolved_evaluation_run_id ?? "-"}</td>
                    <td>{item.related_regression_id ?? "-"}</td>
                    <td>
                      <button
                        type="button"
                        onClick={() => updateImprovementStatus(item, "in_progress")}
                        disabled={running || item.status === "in_progress"}
                      >
                        Mark in progress
                      </button>
                      <button
                        type="button"
                        onClick={() => updateImprovementStatus(item, "resolved")}
                        disabled={running || item.status === "resolved"}
                      >
                        Mark resolved
                      </button>
                      <button
                        type="button"
                        onClick={() => updateImprovementStatus(item, "ignored")}
                        disabled={running || item.status === "ignored"}
                      >
                        Ignore
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="subtle-block">
          <div className="section-heading">
            <h3>人工复核问题分布</h3>
            <button type="button" onClick={() => evaluationApi.annotationSummary().then(setAnnotationSummary)} disabled={running}>
              Refresh annotation stats
            </button>
          </div>
          <p className="muted">
            该区域只统计管理员人工标注，用来判断下一轮优化更应优先处理 prompt、metadata、chunking 还是 rerank。
          </p>
          <div className="metric-grid">
            <span>Total annotations: {annotationSummary?.total_annotations ?? 0}</span>
            <span>Open / active: {openAnnotationCount}</span>
            <span>Resolved: {resolvedAnnotationCount}</span>
            <span>Main root cause: {topRootCause ? `${topRootCause.label} (${topRootCause.count})` : "-"}</span>
            <span>Main fix type: {topFixType ? `${topFixType.label} (${topFixType.count})` : "-"}</span>
          </div>
          {!annotationSummary || annotationSummary.total_annotations === 0 ? (
            <p className="muted">暂无人工标注统计。请先在 case drill-down 中添加人工复核标注。</p>
          ) : (
            <>
              <h4>Root cause</h4>
              <table>
                <thead>
                  <tr>
                    <th>根因</th>
                    <th>数量</th>
                    <th>占比</th>
                    <th>推荐动作</th>
                  </tr>
                </thead>
                <tbody>
                  {annotationSummary.by_root_cause.map((item) => (
                    <tr key={`root-${item.key}`}>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ human_root_cause: item.key })}>
                          {item.label}
                        </button>
                      </td>
                      <td>{item.count}</td>
                      <td>{percent(item.percentage ?? 0)}</td>
                      <td>{item.recommended_action || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Fix type</h4>
              <table>
                <thead>
                  <tr>
                    <th>修复方式</th>
                    <th>数量</th>
                    <th>占比</th>
                    <th>关联助手</th>
                  </tr>
                </thead>
                <tbody>
                  {annotationSummary.by_fix_type.map((item) => (
                    <tr key={`fix-${item.key}`}>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ human_fix_type: item.key })}>
                          {item.label}
                        </button>
                      </td>
                      <td>{item.count}</td>
                      <td>{percent(item.percentage ?? 0)}</td>
                      <td>{item.assistant_types?.map((assistant) => `${assistant.label}(${assistant.count})`).join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Handling status</h4>
              <table>
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>数量</th>
                  </tr>
                </thead>
                <tbody>
                  {annotationSummary.by_handling_status.map((item) => (
                    <tr key={`status-${item.key}`}>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ handling_status: item.key })}>
                          {item.label}
                        </button>
                      </td>
                      <td>{item.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Assistant type</h4>
              <table>
                <thead>
                  <tr>
                    <th>Assistant</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {annotationSummary.by_assistant_type.map((item) => (
                    <tr key={`assistant-${item.key}`}>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ assistant_type: item.key })}>
                          {item.label}
                        </button>
                      </td>
                      <td>{item.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Open priority items</h4>
              <table>
                <thead>
                  <tr>
                    <th>助手</th>
                    <th>根因</th>
                    <th>修复方向</th>
                    <th>未处理数量</th>
                    <th>推荐动作</th>
                  </tr>
                </thead>
                <tbody>
                  {annotationSummary.open_priority_items.map((item) => (
                    <tr key={`${item.assistant_type}-${item.root_cause}-${item.fix_type}`}>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ assistant_type: item.assistant_type })}>
                          {item.assistant_type}
                        </button>
                      </td>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ human_root_cause: item.root_cause })}>
                          {item.root_cause}
                        </button>
                      </td>
                      <td>
                        <button type="button" onClick={() => openAnnotations({ human_fix_type: item.fix_type })}>
                          {item.fix_type}
                        </button>
                      </td>
                      <td>{item.count}</td>
                      <td>{item.recommended_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>

        <div className="subtle-block">
          <h3>改进效果追踪</h3>
          <p className="muted">
            选择一批已修复的改进项，并指定修复前后的助手评估 run，生成质量回归记录。
          </p>
          <div className="metric-grid">
            <span>Total regressions: {regressionSummary?.total_regressions ?? 0}</span>
            <span>Passed: {regressionSummary?.passed_count ?? 0}</span>
            <span>Failed: {regressionSummary?.failed_count ?? 0}</span>
            <span>Pass rate: {percent(regressionSummary?.pass_rate ?? 0)}</span>
          </div>
          <div className="form-grid">
            <label>
              Search runs
              <input
                value={runSearch}
                onChange={(event) => setRunSearch(event.target.value)}
                placeholder="run label / change summary"
              />
            </label>
            <label>
              Change type
              <select value={runChangeTypeFilter} onChange={(event) => setRunChangeTypeFilter(event.target.value)}>
                <option value="">All</option>
                {CHANGE_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {changeTypeLabel(option)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assistant type
              <select value={runAssistantTypeFilter} onChange={(event) => setRunAssistantTypeFilter(event.target.value)}>
                <option value="">All</option>
                <option value="maintenance">maintenance</option>
                <option value="quality">quality</option>
                <option value="sop">sop</option>
                <option value="material">material</option>
              </select>
            </label>
            <label>
              Before evaluation run
              <select value={beforeRunId} onChange={(event) => setBeforeRunId(event.target.value)}>
                <option value="">Select before run</option>
                {filteredEvaluationRuns.map((run) => (
                  <option key={`before-${run.id}`} value={run.id}>
                    {runOptionText(run)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              After evaluation run
              <select value={afterRunId} onChange={(event) => setAfterRunId(event.target.value)}>
                <option value="">Select after run</option>
                {filteredEvaluationRuns.map((run) => (
                  <option key={`after-${run.id}`} value={run.id}>
                    {runOptionText(run)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Notes
              <input value={regressionNotes} onChange={(event) => setRegressionNotes(event.target.value)} />
            </label>
          </div>
          <button type="button" onClick={loadEvaluationRuns} disabled={running}>
            Apply run filters
          </button>
          <div className="form-grid">
            <div>
              <h4>Before</h4>
              <RunSummary run={selectedBeforeRun} />
            </div>
            <div>
              <h4>After</h4>
              <RunSummary run={selectedAfterRun} />
            </div>
          </div>
          <button type="button" onClick={createRegression} disabled={running || selectedImprovementIds.length === 0}>
            Create regression
          </button>

          {lastRegression && (
            <div className="subtle-block">
              <h4>最新回归结果：{lastRegression.regression_passed ? "Passed" : "Failed"}</h4>
              <div className="form-grid">
                <div>
                  <h4>Before</h4>
                  <RunSummary run={lastRegression.before_run ?? lastRegression.before_run_display} />
                </div>
                <div>
                  <h4>After</h4>
                  <RunSummary run={lastRegression.after_run ?? lastRegression.after_run_display} />
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(lastRegression.delta_metrics).map((metric) => (
                    <tr key={metric}>
                      <td>{metric}</td>
                      <td>{percent(lastRegression.before_metrics[metric])}</td>
                      <td>{percent(lastRegression.after_metrics[metric])}</td>
                      <td>{percent(lastRegression.delta_metrics[metric])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p>Resolved cases: {lastRegression.resolved_case_ids.join(", ") || "-"}</p>
              <p>Still failed cases: {lastRegression.still_failed_case_ids.join(", ") || "-"}</p>
              <p>Related improvement items: {lastRegression.improvement_item_ids.join(", ")}</p>
            </div>
          )}

          {regressions.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Assistant</th>
                  <th>Fix type</th>
                  <th>Resolved cases</th>
                  <th>Still failed</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {regressions.map((regression) => (
                  <tr key={regression.id}>
                    <td>{new Date(regression.created_at).toLocaleString()}</td>
                    <td>{regression.regression_passed ? "Passed" : "Failed"}</td>
                    <td>{regression.assistant_type}</td>
                    <td>{regression.fix_type}</td>
                    <td>{regression.resolved_case_ids.join(", ") || "-"}</td>
                    <td>{regression.still_failed_case_ids.join(", ") || "-"}</td>
                    <td>{regression.notes ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="subtle-block">
          <div className="section-heading">
            <h3>评估运行对比</h3>
            <button type="button" onClick={compareSelectedRuns} disabled={running || !compareBeforeRunId || !compareAfterRunId}>
              Compare
            </button>
          </div>
          <p className="muted">
            选择任意两次 assistant evaluation runs，查看指标差异、失败用例变化和可比性提示。
          </p>
          <div className="form-grid">
            <label>
              Before run
              <select value={compareBeforeRunId} onChange={(event) => setCompareBeforeRunId(event.target.value)}>
                <option value="">Select before run</option>
                {filteredEvaluationRuns.map((run) => (
                  <option key={`compare-before-${run.id}`} value={run.id}>
                    {runOptionText(run)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              After run
              <select value={compareAfterRunId} onChange={(event) => setCompareAfterRunId(event.target.value)}>
                <option value="">Select after run</option>
                {filteredEvaluationRuns.map((run) => (
                  <option key={`compare-after-${run.id}`} value={run.id}>
                    {runOptionText(run)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="form-grid">
            <div>
              <h4>Before</h4>
              <RunSummary run={selectedCompareBeforeRun} />
            </div>
            <div>
              <h4>After</h4>
              <RunSummary run={selectedCompareAfterRun} />
            </div>
          </div>

          {runCompareResult && (
            <div className="subtle-block">
              <h4>可比性：{runCompareResult.comparable ? "Comparable" : "Not fully comparable"}</h4>
              {runCompareResult.comparability_warnings.length > 0 ? (
                <ul>
                  {runCompareResult.comparability_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">未发现可比性风险。</p>
              )}
              <div className="form-grid">
                <div>
                  <h4>Before</h4>
                  <RunSummary run={runCompareResult.before_run} />
                </div>
                <div>
                  <h4>After</h4>
                  <RunSummary run={runCompareResult.after_run} />
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Delta</th>
                    <th>Interpretation</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(runCompareResult.metric_deltas).map(([metric, delta]) => (
                    <tr key={metric}>
                      <td>{metric}</td>
                      <td>{metricDisplay(runCompareResult.before_run.metrics_summary[metric], metric)}</td>
                      <td>{metricDisplay(runCompareResult.after_run.metrics_summary[metric], metric)}</td>
                      <td>{delta.toFixed(3)}</td>
                      <td>{metricInterpretation(delta)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="metric-grid">
                <span>Before failed: {runCompareResult.failed_case_diff.before_failed_count}</span>
                <span>After failed: {runCompareResult.failed_case_diff.after_failed_count}</span>
                <span>Resolved: {runCompareResult.failed_case_diff.resolved_cases.length}</span>
                <span>Introduced: {runCompareResult.failed_case_diff.introduced_failures.length}</span>
                <span>Still failed: {runCompareResult.failed_case_diff.still_failed_cases.length}</span>
                <span>Unchanged passed: {runCompareResult.failed_case_diff.unchanged_passed_count}</span>
              </div>
              <FailedCaseDiffTable
                title="Resolved cases"
                items={runCompareResult.failed_case_diff.resolved_cases}
                onDrillDown={openCaseDrillDown}
              />
              <FailedCaseDiffTable
                title="Introduced failures"
                items={runCompareResult.failed_case_diff.introduced_failures}
                onDrillDown={openCaseDrillDown}
              />
              <FailedCaseDiffTable
                title="Still failed cases"
                items={runCompareResult.failed_case_diff.still_failed_cases}
                onDrillDown={openCaseDrillDown}
              />

              {caseCompareResult && (
                <div className="subtle-block">
                  <div className="section-heading">
                    <h4>Case drill-down: {caseCompareResult.case_id}</h4>
                    <button type="button" onClick={() => setCaseCompareResult(null)}>
                      Close
                    </button>
                  </div>
                  <div className="metric-grid">
                    <span>Status: {caseCompareResult.comparison.status}</span>
                    <span>Metadata filter changed: {String(caseCompareResult.comparison.metadata_filter_changed)}</span>
                    <span>Rerank changed: {String(caseCompareResult.comparison.rerank_changed)}</span>
                    <span>Citation changed: {String(caseCompareResult.comparison.citation_changed)}</span>
                    <span>Failure reason changed: {String(caseCompareResult.comparison.failure_reason_changed)}</span>
                  </div>
                  <div className="form-grid">
                    <div>
                      <h4>Before run</h4>
                      <RunSummary run={caseCompareResult.before_run} />
                    </div>
                    <div>
                      <h4>After run</h4>
                      <RunSummary run={caseCompareResult.after_run} />
                    </div>
                  </div>
                  <div className="subtle-block">
                    <h4>Case basic info</h4>
                    <p>Query: {String((caseCompareResult.after || caseCompareResult.before)?.query || "-")}</p>
                    <p>Expected document: {String((caseCompareResult.after || caseCompareResult.before)?.expected_document || "-")}</p>
                    <p>Expected metadata: {JSON.stringify((caseCompareResult.after || caseCompareResult.before)?.expected_metadata || {})}</p>
                    <p>Should have answer: {String((caseCompareResult.after || caseCompareResult.before)?.should_have_answer ?? "-")}</p>
                  </div>
                  <div className="subtle-block">
                    <h4>Automatic diff summary</h4>
                    <p>Ranks: {JSON.stringify(caseCompareResult.comparison.expected_document_ranks || {})}</p>
                    <p>Rank changes: {JSON.stringify(caseCompareResult.comparison.rank_changes || [])}</p>
                    <ul>
                      {caseCompareResult.diagnostic_hints.map((hint) => (
                        <li key={hint}>{hint}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="subtle-block">
                    <div className="section-heading">
                      <h4>人工复核标注</h4>
                      <button type="button" onClick={saveCaseAnnotation} disabled={annotationSaving || !currentCaseResultId()}>
                        {currentAnnotation() ? "编辑人工标注" : "添加人工标注"}
                      </button>
                    </div>
                    <div className="metric-grid">
                      <span>系统 failure_reason: {String((caseCompareResult.after || caseCompareResult.before)?.failure_reason || "-")}</span>
                      <span>系统 suggested_fix_type: {String((caseCompareResult.after || caseCompareResult.before)?.suggested_fix_type || "-")}</span>
                      <span>Annotated by: {currentAnnotation()?.annotated_by || "-"}</span>
                      <span>Annotated at: {currentAnnotation()?.annotated_at ? new Date(currentAnnotation()!.annotated_at).toLocaleString() : "-"}</span>
                    </div>
                    <div className="form-grid">
                      <label>
                        Human judgement
                        <select
                          value={annotationDraft.human_judgement}
                          onChange={(event) =>
                            setAnnotationDraft((current) => ({ ...current, human_judgement: event.target.value as CaseAnnotationPayload["human_judgement"] }))
                          }
                        >
                          {HUMAN_JUDGEMENT_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Root cause
                        <select
                          value={annotationDraft.human_root_cause}
                          onChange={(event) =>
                            setAnnotationDraft((current) => ({ ...current, human_root_cause: event.target.value as CaseAnnotationPayload["human_root_cause"] }))
                          }
                        >
                          {HUMAN_ROOT_CAUSE_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Fix type
                        <select
                          value={annotationDraft.human_fix_type}
                          onChange={(event) =>
                            setAnnotationDraft((current) => ({ ...current, human_fix_type: event.target.value as CaseAnnotationPayload["human_fix_type"] }))
                          }
                        >
                          {HUMAN_FIX_TYPE_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Handling status
                        <select
                          value={annotationDraft.handling_status}
                          onChange={(event) =>
                            setAnnotationDraft((current) => ({ ...current, handling_status: event.target.value as CaseAnnotationPayload["handling_status"] }))
                          }
                        >
                          {HANDLING_STATUS_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      Handling notes
                      <textarea
                        value={annotationDraft.handling_notes ?? ""}
                        onChange={(event) =>
                          setAnnotationDraft((current) => ({ ...current, handling_notes: event.target.value }))
                        }
                        rows={3}
                      />
                    </label>
                  </div>
                  <div className="form-grid">
                    <CaseSnapshotPanel title="Before" snapshot={caseCompareResult.before} />
                    <CaseSnapshotPanel title="After" snapshot={caseCompareResult.after} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="subtle-block">
          <div className="section-heading">
            <h3>评估趋势</h3>
            <label>
              助手类型
              <select value={trendAssistantType} onChange={(event) => setTrendAssistantType(event.target.value)}>
                <option value="all">All</option>
                <option value="maintenance">maintenance</option>
                <option value="quality">quality</option>
                <option value="sop">sop</option>
                <option value="material">material</option>
              </select>
            </label>
            <label>
              模式
              <select value={trendMode} onChange={(event) => setTrendMode(event.target.value)}>
                <option value="baseline">baseline</option>
                <option value="metadata_filter">metadata filter</option>
                <option value="metadata_filter_rerank">metadata filter + rerank</option>
              </select>
            </label>
            <button type="button" onClick={loadTrends} disabled={running}>
              Refresh trends
            </button>
          </div>
          {assistantTrends?.regression_warnings.length ? (
            <p className="error">
              最新趋势存在退化：{assistantTrends.regression_warnings.map((item) => item.metric).join(", ")}
            </p>
          ) : (
            <p className="muted">最近记录未检测到明显退化。</p>
          )}
          {assistantTrends && (
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Change type</th>
                  <th>Change summary</th>
                  <th>Mode</th>
                  <th>Hit@1</th>
                  <th>Hit@3</th>
                  <th>MRR</th>
                  <th>Citation rate</th>
                  <th>No-answer accuracy</th>
                  <th>Quality gate</th>
                  <th>Regression warnings</th>
                </tr>
              </thead>
              <tbody>
                {assistantTrends.items.map((item) => (
                  <tr key={`${item.evaluation_run_id}-${item.assistant_type}`}>
                    <td title={`${item.assistant_type} · ${new Date(item.created_at).toLocaleString()}`}>
                      {item.display_label || item.run_label || item.evaluation_run_id}
                    </td>
                    <td>{changeTypeLabel(item.change_type)}</td>
                    <td title={item.change_summary ?? undefined}>{truncateText(item.change_summary)}</td>
                    <td>{item.mode_summary || item.mode}</td>
                    <td>{percent(item.hit_at_1)}</td>
                    <td>{percent(item.hit_at_3)}</td>
                    <td>{item.mrr.toFixed(3)}</td>
                    <td>{percent(item.citation_rate)}</td>
                    <td>{percent(item.no_answer_accuracy)}</td>
                    <td>{item.quality_gate_passed ? "Pass" : "Fail"}</td>
                    <td>{item.regression_warnings.map((warning) => warning.metric).join(", ") || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="subtle-block">
          <div className="section-heading">
            <h3>Evaluation runs</h3>
            <button type="button" onClick={loadEvaluationRuns} disabled={running}>
              Refresh runs
            </button>
          </div>
          {evaluationRuns.length === 0 ? (
            <p className="muted">暂无助手评估 run 记录。</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Created at</th>
                  <th>Mode</th>
                  <th>Hit@1</th>
                  <th>MRR</th>
                  <th>Change type</th>
                  <th>Change summary</th>
                  <th>Operator notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {evaluationRuns.map((run) => (
                  <tr key={run.id}>
                    <td>{run.display_label}</td>
                    <td>{new Date(run.created_at).toLocaleString()}</td>
                    <td>{run.mode_summary}</td>
                    <td>{percent(run.metrics_summary.hit_at_1 as number | null)}</td>
                    <td>{typeof run.metrics_summary.mrr === "number" ? run.metrics_summary.mrr.toFixed(3) : "-"}</td>
                    <td>
                      {editingRunId === run.id ? (
                        <select value={editChangeType} onChange={(event) => setEditChangeType(event.target.value)}>
                          {CHANGE_TYPE_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {changeTypeLabel(option)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        changeTypeLabel(run.change_type)
                      )}
                    </td>
                    <td>
                      {editingRunId === run.id ? (
                        <div>
                          <input value={editRunLabel} onChange={(event) => setEditRunLabel(event.target.value)} />
                          <input
                            value={editChangeSummary}
                            onChange={(event) => setEditChangeSummary(event.target.value)}
                          />
                        </div>
                      ) : (
                        <span title={run.change_summary ?? undefined}>{truncateText(run.change_summary)}</span>
                      )}
                    </td>
                    <td>
                      {editingRunId === run.id ? (
                        <input
                          value={editOperatorNotes}
                          onChange={(event) => setEditOperatorNotes(event.target.value)}
                        />
                      ) : (
                        run.operator_notes || "-"
                      )}
                    </td>
                    <td>
                      {editingRunId === run.id ? (
                        <>
                          <button type="button" onClick={() => saveRunMetadata(run.id)} disabled={running}>
                            Save
                          </button>
                          <button type="button" onClick={() => setEditingRunId(null)} disabled={running}>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button type="button" onClick={() => beginEditRun(run)} disabled={running}>
                          Edit run metadata
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="subtle-block">
          <h3>改进回归趋势</h3>
          <div className="metric-grid">
            <span>Total regressions: {regressionTrends?.total_regressions ?? 0}</span>
            <span>Passed: {regressionTrends?.passed_count ?? 0}</span>
            <span>Failed: {regressionTrends?.failed_count ?? 0}</span>
            <span>Pass rate: {percent(regressionTrends?.pass_rate ?? 0)}</span>
          </div>
          {regressionTrends?.recent_items.length ? (
            <table>
              <thead>
                <tr>
                  <th>Regression id</th>
                  <th>Created at</th>
                  <th>Assistant</th>
                  <th>Fix type</th>
                  <th>Before run</th>
                  <th>After run</th>
                  <th>Regression passed</th>
                  <th>Resolved cases</th>
                  <th>Still failed cases</th>
                </tr>
              </thead>
              <tbody>
                {regressionTrends.recent_items.map((regression) => (
                  <tr key={regression.id}>
                    <td>{regression.id}</td>
                    <td>{new Date(regression.created_at).toLocaleString()}</td>
                    <td>{regression.assistant_type}</td>
                    <td>{regression.fix_type}</td>
                    <td>{regression.before_run_display?.display_label || regression.before_run_label || regression.before_evaluation_run_id}</td>
                    <td>{regression.after_run_display?.display_label || regression.after_run_label || regression.after_evaluation_run_id}</td>
                    <td>{regression.regression_passed ? "Passed" : "Failed"}</td>
                    <td>{regression.resolved_case_ids.join(", ") || "-"}</td>
                    <td>{regression.still_failed_case_ids.join(", ") || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">暂无回归趋势记录</p>
          )}
        </div>
      </div>
    </section>
  );
}

import { useEffect, useMemo, useState } from "react";
import {
  evaluationApi,
  type CaseAnnotation,
  type CaseAnnotationListItem,
  type CaseAnnotationListResponse,
  type EvaluationCaseResultDetail,
  type EvaluationRunListItem,
} from "../api/evaluation";

const ROOT_CAUSE_OPTIONS = [
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
];

const FIX_TYPE_OPTIONS = [
  "update_prompt",
  "update_metadata",
  "update_chunking",
  "tune_rerank",
  "improve_parser",
  "supplement_document",
  "revise_eval_case",
  "confirm_business_rule",
  "no_action",
];

const STATUS_OPTIONS = ["open", "investigating", "planned", "resolved", "ignored"];
const ASSISTANT_OPTIONS = ["maintenance", "quality", "sop", "material"];

interface AnnotationListPageProps {
  initialSearch?: string;
  onBackToEvaluation?: () => void;
  onOpenImprovementItem?: (itemId: string, fromSearch: string) => void;
}

function initialFilters(search?: string) {
  const params = new URLSearchParams(search || window.location.search);
  return {
    human_root_cause: params.get("human_root_cause") || "",
    human_fix_type: params.get("human_fix_type") || "",
    handling_status: params.get("handling_status") || "",
    assistant_type: params.get("assistant_type") || "",
    evaluation_run_id: params.get("evaluation_run_id") || "",
    improvement_item_id: params.get("improvement_item_id") || "",
    improvement_status: params.get("improvement_status") || "",
    regression_status: params.get("regression_status") || "",
    date_from: params.get("date_from") || "",
    date_to: params.get("date_to") || "",
    keyword: params.get("keyword") || "",
    page: Number(params.get("page") || "1"),
  };
}

function truncate(value?: string | null, length = 96) {
  if (!value) return "-";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

function DetailPanel({
  detail,
  onBack,
}: {
  detail: EvaluationCaseResultDetail;
  onBack: () => void;
}) {
  const retrievedResults = asRecordArray(detail.retrieved_results);
  const citations = asRecordArray(detail.citations);
  return (
    <div className="subtle-block">
      <div className="section-heading">
        <h3>Case drill-down: {detail.case_id}</h3>
        <button type="button" onClick={onBack}>
          Back to annotations
        </button>
      </div>
      <div className="metric-grid">
        <span>Assistant: {detail.assistant_type || "-"}</span>
        <span>Passed: {detail.passed ? "Pass" : "Fail"}</span>
        <span>System reason: {detail.failure_reason || "-"}</span>
        <span>Suggested fix: {detail.suggested_fix_type || "-"}</span>
        <span>Rerank: {String(detail.use_rerank)} / applied {String(detail.rerank_applied)}</span>
        <span>Filter: {JSON.stringify(detail.used_metadata_filter || {})}</span>
      </div>
      <p><strong>Query:</strong> {detail.query}</p>
      <p><strong>Expected document:</strong> {detail.expected_document || "-"}</p>
      <p><strong>Expected metadata:</strong> {JSON.stringify(detail.expected_metadata || {})}</p>
      {detail.annotation && (
        <div className="subtle-block">
          <h4>Human annotation</h4>
          <div className="metric-grid">
            <span>Judgement: {detail.annotation.human_judgement}</span>
            <span>Root cause: {detail.annotation.human_root_cause}</span>
            <span>Fix type: {detail.annotation.human_fix_type}</span>
            <span>Status: {detail.annotation.handling_status}</span>
          </div>
          <p>{detail.annotation.handling_notes || "-"}</p>
        </div>
      )}
      <h4>Answer excerpt</h4>
      <p>{detail.answer_excerpt || "-"}</p>
      <h4>Citations</h4>
      {citations.length === 0 ? (
        <p className="muted">No citations saved.</p>
      ) : (
        <ul>
          {citations.map((citation, index) => (
            <li key={`citation-${index}`}>
              {String(citation.filename || "-")} - {String(citation.quote || "").slice(0, 160)}
            </li>
          ))}
        </ul>
      )}
      <h4>Retrieved results</h4>
      {retrievedResults.length === 0 ? (
        <p className="muted">No retrieval snapshot saved.</p>
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
            </tr>
          </thead>
          <tbody>
            {retrievedResults.map((item, index) => (
              <tr key={`result-${index}`}>
                <td>{String(item.rank ?? "-")}</td>
                <td>{String(item.document_name || "-")}</td>
                <td>{String(item.chunk_excerpt || "-").slice(0, 220)}</td>
                <td>{typeof item.vector_score === "number" ? item.vector_score.toFixed(3) : "-"}</td>
                <td>{typeof item.rerank_score === "number" ? item.rerank_score.toFixed(3) : "-"}</td>
                <td>{typeof item.final_score === "number" ? item.final_score.toFixed(3) : "-"}</td>
                <td>{JSON.stringify(item.chunk_metadata || {})}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function AnnotationListPage({ initialSearch, onBackToEvaluation, onOpenImprovementItem }: AnnotationListPageProps) {
  const [filters, setFilters] = useState(() => initialFilters(initialSearch));
  const [runs, setRuns] = useState<EvaluationRunListItem[]>([]);
  const [result, setResult] = useState<CaseAnnotationListResponse | null>(null);
  const [detail, setDetail] = useState<EvaluationCaseResultDetail | null>(null);
  const [editing, setEditing] = useState<CaseAnnotationListItem | null>(null);
  const [editNotes, setEditNotes] = useState("");
  const [editJudgement, setEditJudgement] = useState<CaseAnnotation["human_judgement"]>("system_partially_correct");
  const [editRootCause, setEditRootCause] = useState<CaseAnnotation["human_root_cause"]>("unknown");
  const [editFixType, setEditFixType] = useState<CaseAnnotation["human_fix_type"]>("no_action");
  const [editStatus, setEditStatus] = useState<CaseAnnotation["handling_status"]>("open");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const queryString = useMemo(() => {
    const search = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== "" && value !== undefined && value !== null) search.set(key, String(value));
    });
    return search.toString();
  }, [filters]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await evaluationApi.listCaseAnnotations({
        ...filters,
        date_from: filters.date_from ? new Date(`${filters.date_from}T00:00:00`).toISOString() : undefined,
        date_to: filters.date_to ? new Date(`${filters.date_to}T23:59:59`).toISOString() : undefined,
        page_size: 20,
        order_by: "annotated_at",
        order_direction: "desc",
      });
      setResult(response);
      window.history.replaceState(null, "", `/evaluation/annotations${queryString ? `?${queryString}` : ""}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载人工标注列表失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadRuns() {
    setRuns(await evaluationApi.listRuns({ eval_type: "assistant", limit: 100 }));
  }

  useEffect(() => {
    loadRuns().catch((err) => setError(err instanceof Error ? err.message : "加载评估 run 失败"));
  }, []);

  useEffect(() => {
    load();
  }, [queryString]);

  function updateFilter(key: keyof typeof filters, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));
  }

  function clearFilters() {
    setFilters({
      human_root_cause: "",
      human_fix_type: "",
      handling_status: "",
      assistant_type: "",
      evaluation_run_id: "",
      improvement_item_id: "",
      improvement_status: "",
      regression_status: "",
      date_from: "",
      date_to: "",
      keyword: "",
      page: 1,
    });
  }

  async function openDrillDown(item: CaseAnnotationListItem) {
    setError("");
    try {
      setDetail(await evaluationApi.getCaseResult(item.evaluation_case_result_id));
      window.history.replaceState(null, "", `/evaluation/annotations?from=annotations&${queryString}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 case drill-down 失败");
    }
  }

  function beginEdit(item: CaseAnnotationListItem) {
    setEditing(item);
    setEditJudgement(item.human_judgement);
    setEditRootCause(item.human_root_cause);
    setEditFixType(item.human_fix_type);
    setEditStatus(item.handling_status);
    setEditNotes(item.handling_notes ?? "");
  }

  async function saveEdit(statusOverride?: CaseAnnotation["handling_status"]) {
    if (!editing) return;
    setError("");
    try {
      await evaluationApi.updateCaseAnnotation(editing.evaluation_case_result_id, {
        human_judgement: editJudgement,
        human_root_cause: editRootCause,
        human_fix_type: editFixType,
        handling_status: statusOverride ?? editStatus,
        handling_notes: editNotes,
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新人工标注失败");
    }
  }

  async function quickStatus(item: CaseAnnotationListItem, status: CaseAnnotation["handling_status"]) {
    setEditing(item);
    setEditJudgement(item.human_judgement);
    setEditRootCause(item.human_root_cause);
    setEditFixType(item.human_fix_type);
    setEditStatus(status);
    setEditNotes(item.handling_notes ?? "");
    await evaluationApi.updateCaseAnnotation(item.evaluation_case_result_id, { handling_status: status });
    await load();
  }

  function openImprovement(itemId: string) {
    if (onOpenImprovementItem) {
      onOpenImprovementItem(itemId, queryString ? `?${queryString}` : "");
      return;
    }
    window.history.pushState(null, "", `/evaluation/improvements/${itemId}`);
  }

  if (detail) {
    return (
      <section className="panel">
        {error && <p className="error">{error}</p>}
        <DetailPanel detail={detail} onBack={() => setDetail(null)} />
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>人工标注列表</h2>
        <div>
          {onBackToEvaluation && (
            <button type="button" onClick={onBackToEvaluation}>
              Back to evaluation
            </button>
          )}
          <button type="button" onClick={clearFilters}>
            Clear filters
          </button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="form-grid">
        <label>
          Assistant type
          <select value={filters.assistant_type} onChange={(event) => updateFilter("assistant_type", event.target.value)}>
            <option value="">All</option>
            {ASSISTANT_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Human root cause
          <select value={filters.human_root_cause} onChange={(event) => updateFilter("human_root_cause", event.target.value)}>
            <option value="">All</option>
            {ROOT_CAUSE_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Human fix type
          <select value={filters.human_fix_type} onChange={(event) => updateFilter("human_fix_type", event.target.value)}>
            <option value="">All</option>
            {FIX_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Handling status
          <select value={filters.handling_status} onChange={(event) => updateFilter("handling_status", event.target.value)}>
            <option value="">All</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Evaluation run
          <select value={filters.evaluation_run_id} onChange={(event) => updateFilter("evaluation_run_id", event.target.value)}>
            <option value="">All</option>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>{run.display_label}</option>
            ))}
          </select>
        </label>
        <label>
          Improvement item
          <input
            value={filters.improvement_item_id}
            placeholder="improvement item id"
            onChange={(event) => updateFilter("improvement_item_id", event.target.value)}
          />
        </label>
        <label>
          Improvement status
          <select value={filters.improvement_status} onChange={(event) => updateFilter("improvement_status", event.target.value)}>
            <option value="">All</option>
            {["open", "in_progress", "resolved", "ignored"].map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Regression status
          <select value={filters.regression_status} onChange={(event) => updateFilter("regression_status", event.target.value)}>
            <option value="">All</option>
            {["unverified", "passed", "failed"].map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label>
          Date from
          <input type="date" value={filters.date_from} onChange={(event) => updateFilter("date_from", event.target.value)} />
        </label>
        <label>
          Date to
          <input type="date" value={filters.date_to} onChange={(event) => updateFilter("date_to", event.target.value)} />
        </label>
        <label>
          Keyword
          <input
            value={filters.keyword}
            placeholder="case id / query / notes"
            onChange={(event) => updateFilter("keyword", event.target.value)}
          />
        </label>
      </div>
      {loading && <p className="muted">加载中...</p>}
      {!loading && result?.items.length === 0 && (
        <div className="subtle-block">
          <p>当前筛选条件下没有人工标注。</p>
          <button type="button" onClick={clearFilters}>清除筛选条件返回全部记录</button>
        </div>
      )}
      {result && result.items.length > 0 && (
        <>
          <p className="muted">
            Total {result.total}, page {result.page} / {result.pages || 1}
          </p>
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Assistant</th>
                <th>Evaluation run</th>
                <th>System reason</th>
                <th>Human root cause</th>
                <th>Human fix type</th>
                <th>Handling status</th>
                <th>Related improvement items</th>
                <th>Annotated at</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((item) => (
                <tr key={item.annotation_id}>
                  <td>
                    <strong>{item.case_id}</strong>
                    <div className="muted" title={item.query}>{truncate(item.query, 72)}</div>
                  </td>
                  <td>{item.assistant_type || "-"}</td>
                  <td>
                    <strong>{item.evaluation_run_display_label}</strong>
                    <div className="muted">{item.evaluation_run_change_type || "unknown"} · {item.evaluation_run_mode_summary}</div>
                  </td>
                  <td>
                    {item.system_failure_reason || "-"}
                    <div className="muted">{item.system_suggested_fix_type || "-"}</div>
                  </td>
                  <td>{item.human_root_cause}</td>
                  <td>{item.human_fix_type}</td>
                  <td>{item.handling_status}</td>
                  <td>
                    {item.related_improvement_items.length === 0 ? (
                      <span className="muted">-</span>
                    ) : (
                      item.related_improvement_items.map((related) => (
                        <button
                          key={related.id}
                          type="button"
                          title={related.suggested_action}
                          onClick={() => openImprovement(related.id)}
                        >
                          #{related.id.slice(0, 8)} {related.fix_type} / {related.priority} / {related.status}
                        </button>
                      ))
                    )}
                  </td>
                  <td>{new Date(item.annotated_at).toLocaleString()}</td>
                  <td>
                    <button type="button" onClick={() => openDrillDown(item)}>View drill-down</button>
                    <button type="button" onClick={() => beginEdit(item)}>Edit annotation</button>
                    <button type="button" onClick={() => quickStatus(item, "investigating")}>Mark investigating</button>
                    <button type="button" onClick={() => quickStatus(item, "resolved")}>Mark resolved</button>
                    <button type="button" onClick={() => quickStatus(item, "ignored")}>Ignore</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="section-heading">
            <button type="button" disabled={filters.page <= 1} onClick={() => updateFilter("page", filters.page - 1)}>
              Previous
            </button>
            <button
              type="button"
              disabled={!result || filters.page >= result.pages}
              onClick={() => updateFilter("page", filters.page + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
      {editing && (
        <div className="subtle-block">
          <div className="section-heading">
            <h3>Edit annotation: {editing.case_id}</h3>
            <button type="button" onClick={() => setEditing(null)}>Close</button>
          </div>
          <div className="form-grid">
            <label>
              Human judgement
              <select value={editJudgement} onChange={(event) => setEditJudgement(event.target.value as CaseAnnotation["human_judgement"])}>
                {["system_correct", "system_partially_correct", "system_incorrect", "business_expected_answer_wrong", "insufficient_documentation", "needs_expert_review"].map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              Root cause
              <select value={editRootCause} onChange={(event) => setEditRootCause(event.target.value as CaseAnnotation["human_root_cause"])}>
                {ROOT_CAUSE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              Fix type
              <select value={editFixType} onChange={(event) => setEditFixType(event.target.value as CaseAnnotation["human_fix_type"])}>
                {FIX_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              Handling status
              <select value={editStatus} onChange={(event) => setEditStatus(event.target.value as CaseAnnotation["handling_status"])}>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Handling notes
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={3} />
          </label>
          <button type="button" onClick={() => saveEdit()}>Save annotation</button>
        </div>
      )}
    </section>
  );
}

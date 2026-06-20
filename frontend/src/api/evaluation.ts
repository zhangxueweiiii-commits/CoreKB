import { request } from "./client";

export interface EvalCaseResult {
  id: string;
  category: string;
  query: string;
  should_have_answer: boolean;
  hit_rank?: number | null;
  hit_at_1: boolean;
  hit_at_3: boolean;
  hit_at_5: boolean;
  reciprocal_rank: number;
  keyword_match_rate: number;
  metadata_match_rate: number;
  no_answer_correct?: boolean | null;
  case_result_id?: string | null;
  used_metadata_filter?: Record<string, unknown>;
  passed: boolean;
  top_results: Array<Record<string, unknown>>;
}

export interface RetrievalEvaluationResult {
  run_id?: string | null;
  evaluation_kb_id?: string | null;
  evaluation_kb_ready: boolean;
  missing_documents: string[];
  unindexed_documents: string[];
  total_cases: number;
  use_metadata_filter: boolean;
  use_rerank: boolean;
  rerank_top_n?: number | null;
  mode: string;
  hit_at_1: number;
  hit_at_3: number;
  hit_at_5: number;
  mrr: number;
  keyword_match_rate: number;
  metadata_match_rate: number;
  no_answer_accuracy: number;
  failed_cases: EvalCaseResult[];
  case_results?: EvalCaseResult[];
}

export interface EvaluationRun {
  id: string;
  eval_type: "retrieval";
  total_cases: number;
  metrics: Record<string, number | boolean>;
  failed_cases: EvalCaseResult[];
  created_by?: string | null;
  created_at: string;
}

export interface RetrievalEvaluationCompareResult {
  baseline: RetrievalEvaluationResult;
  metadata_filter: RetrievalEvaluationResult;
  metadata_filter_rerank: RetrievalEvaluationResult;
  delta: Record<string, Record<string, number>>;
}

export interface AssistantEvaluationCaseResult {
  id: string;
  assistant_type: string;
  category: string;
  query: string;
  passed: boolean;
  citation_present: boolean;
  no_answer_correct?: boolean | null;
  keyword_match_rate: number;
  metadata_match_rate: number;
  hit_at_1: boolean;
  hit_at_3: boolean;
  hit_at_5: boolean;
  expected_document?: string | null;
  actual_top_documents: string[];
  expected_metadata: Record<string, string>;
  used_metadata_filter: Record<string, string>;
  reason?: string | null;
  failure_reason: string;
  failure_detail?: string | null;
  suggested_fix_type: string;
  case_result_id?: string | null;
}

export interface AssistantFailedThreshold {
  assistant_type?: string;
  metric: string;
  actual: number;
  required: number;
}

export interface AssistantEvaluationMetrics {
  assistant_type: string;
  total_cases: number;
  hit_at_1: number;
  hit_at_3: number;
  hit_at_5: number;
  mrr: number;
  keyword_match_rate: number;
  metadata_match_rate: number;
  no_answer_accuracy: number;
  citation_rate: number;
  failed_cases: AssistantEvaluationCaseResult[];
  quality_gate_passed: boolean;
  failed_thresholds: AssistantFailedThreshold[];
  threshold_config: Record<string, number>;
}

export interface AssistantEvaluationResult {
  run_id?: string | null;
  total_cases: number;
  use_metadata_filter: boolean;
  use_rerank: boolean;
  rerank_top_n?: number | null;
  mode: string;
  created_at?: string | null;
  run_label?: string | null;
  change_type?: string | null;
  change_summary?: string | null;
  operator_notes?: string | null;
  config_snapshot?: Record<string, unknown> | null;
  overall_metrics: AssistantEvaluationMetrics;
  per_assistant_metrics: Record<string, AssistantEvaluationMetrics>;
  failed_cases: AssistantEvaluationCaseResult[];
  case_results: AssistantEvaluationCaseResult[];
  quality_gate_passed: boolean;
  failed_thresholds: AssistantFailedThreshold[];
  threshold_config: Record<string, Record<string, number>>;
  per_assistant_quality_gate: Record<string, unknown>;
}

export interface AssistantEvaluationCompareResult {
  baseline: AssistantEvaluationResult;
  metadata_filter: AssistantEvaluationResult;
  metadata_filter_rerank: AssistantEvaluationResult;
  delta: Record<string, Record<string, number>>;
}

export interface ImprovementItem {
  id: string;
  evaluation_run_id: string;
  assistant_type: string;
  fix_type: string;
  priority: "high" | "medium" | "low";
  failed_case_count: number;
  affected_case_ids: string[];
  main_failure_reasons: string[];
  suggested_action: string;
  source: "human_annotation" | "system_rule" | string;
  annotation_count: number;
  status: "open" | "in_progress" | "resolved" | "ignored";
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolved_evaluation_run_id?: string | null;
  regression_status: "unverified" | "passed" | "failed";
  related_regression_id?: string | null;
}

export interface RelatedImprovementItem {
  id: string;
  fix_type: string;
  priority: "high" | "medium" | "low";
  status: "open" | "in_progress" | "resolved" | "ignored";
  regression_status: "unverified" | "passed" | "failed";
  suggested_action: string;
  relation_source: "system_rule" | "human_annotation" | "manual_link" | string;
}

export interface ImprovementCaseResult {
  evaluation_case_result_id: string;
  evaluation_run_id: string;
  case_id: string;
  assistant_type?: string | null;
  query: string;
  system_failure_reason?: string | null;
  system_suggested_fix_type?: string | null;
  evaluation_run_display_label: string;
  evaluation_run_change_type?: string | null;
  evaluation_run_mode_summary: string;
  case_passed: boolean;
  relation_source: string;
}

export interface ImprovementAnnotation {
  annotation_id: string;
  evaluation_case_result_id: string;
  evaluation_run_id: string;
  case_id: string;
  assistant_type?: string | null;
  query: string;
  human_judgement: CaseAnnotation["human_judgement"];
  human_root_cause: CaseAnnotation["human_root_cause"];
  human_fix_type: CaseAnnotation["human_fix_type"];
  handling_status: CaseAnnotation["handling_status"];
  handling_notes?: string | null;
  annotated_by?: string | null;
  annotated_at: string;
  updated_at: string;
  system_failure_reason?: string | null;
  system_suggested_fix_type?: string | null;
  evaluation_run_display_label: string;
  evaluation_run_change_type?: string | null;
  evaluation_run_mode_summary: string;
  case_passed: boolean;
  relation_source: string;
}

export interface ImprovementItemDetail extends ImprovementItem {
  related_case_results: ImprovementCaseResult[];
  related_annotations: ImprovementAnnotation[];
}

export interface ImprovementAnnotationListResponse {
  items: ImprovementAnnotation[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ImprovementSummary {
  total_open: number;
  by_fix_type: Record<string, number>;
  by_assistant_type: Record<string, number>;
  by_priority: Record<string, number>;
  top_failure_reasons: Record<string, number>;
}

export interface EvaluationRegression {
  id: string;
  before_evaluation_run_id: string;
  after_evaluation_run_id: string;
  improvement_item_ids: string[];
  assistant_type: string;
  fix_type: string;
  before_metrics: Record<string, number>;
  after_metrics: Record<string, number>;
  delta_metrics: Record<string, number>;
  affected_case_ids: string[];
  resolved_case_ids: string[];
  still_failed_case_ids: string[];
  regression_passed: boolean;
  notes?: string | null;
  before_run_label?: string | null;
  before_change_type?: string | null;
  before_change_summary?: string | null;
  after_run_label?: string | null;
  after_change_type?: string | null;
  after_change_summary?: string | null;
  before_run_display?: EvaluationRunDisplay | null;
  after_run_display?: EvaluationRunDisplay | null;
  before_metrics_summary?: Record<string, number | boolean | null> | null;
  after_metrics_summary?: Record<string, number | boolean | null> | null;
  before_mode_summary?: string | null;
  after_mode_summary?: string | null;
  before_run?: EvaluationRunDisplay | null;
  after_run?: EvaluationRunDisplay | null;
  created_by?: string | null;
  created_at: string;
}

export interface RegressionSummary {
  total_regressions: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  by_fix_type: Record<string, number>;
  by_assistant_type: Record<string, number>;
  recent_regressions: EvaluationRegression[];
}

export interface TrendWarning {
  metric: string;
  previous: number | boolean;
  current: number | boolean;
  delta?: number | null;
  level: "warning";
}

export interface AssistantTrendItem {
  evaluation_run_id: string;
  created_at: string;
  assistant_type: string;
  mode: string;
  display_label?: string | null;
  metrics_summary?: Record<string, number | boolean | null> | null;
  mode_summary?: string | null;
  use_metadata_filter: boolean;
  use_rerank: boolean;
  hit_at_1: number;
  hit_at_3: number;
  hit_at_5: number;
  mrr: number;
  keyword_match_rate: number;
  metadata_match_rate: number;
  no_answer_accuracy: number;
  citation_rate: number;
  quality_gate_passed: boolean;
  run_label?: string | null;
  change_type?: string | null;
  change_summary?: string | null;
  operator_notes?: string | null;
  config_snapshot?: Record<string, unknown> | null;
  regression_warnings: TrendWarning[];
}

export interface AssistantTrendResponse {
  assistant_type: string;
  items: AssistantTrendItem[];
  delta_from_previous: Record<string, number>;
  regression_warnings: TrendWarning[];
}

export interface EvaluationRunListItem {
  id: string;
  eval_type: "retrieval" | "assistant";
  total_cases: number;
  metrics: Record<string, unknown>;
  display_label: string;
  metrics_summary: Record<string, number | boolean | null>;
  mode_summary: string;
  run_label?: string | null;
  change_type?: string | null;
  change_summary?: string | null;
  operator_notes?: string | null;
  config_snapshot?: Record<string, unknown> | null;
  created_by?: string | null;
  created_at: string;
}

export interface EvaluationRunDisplay {
  id: string;
  display_label: string;
  run_label?: string | null;
  change_type?: string | null;
  change_summary?: string | null;
  operator_notes?: string | null;
  created_at: string;
  created_by?: string | null;
  config_snapshot?: Record<string, unknown> | null;
  metrics_summary: Record<string, number | boolean | null>;
  mode_summary: string;
}

export interface RegressionTrendResponse {
  total_regressions: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  recent_items: EvaluationRegression[];
}

export interface FailedCaseDiffItem {
  case_id: string;
  before_case_result_id?: string | null;
  after_case_result_id?: string | null;
  assistant_type?: string | null;
  query?: string | null;
  failure_reason?: string | null;
  suggested_fix_type?: string | null;
  before_actual_top_documents: string[];
  after_actual_top_documents: string[];
  before_used_metadata_filter: Record<string, unknown>;
  after_used_metadata_filter: Record<string, unknown>;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  annotation_status?: string;
  annotation?: Pick<CaseAnnotation, "id" | "human_root_cause" | "human_fix_type" | "handling_status"> | null;
}

export interface CaseAnnotation {
  id: string;
  evaluation_case_result_id: string;
  human_judgement:
    | "system_correct"
    | "system_partially_correct"
    | "system_incorrect"
    | "business_expected_answer_wrong"
    | "insufficient_documentation"
    | "needs_expert_review";
  human_root_cause:
    | "prompt"
    | "metadata_filter"
    | "document_metadata"
    | "chunking"
    | "rerank"
    | "parser"
    | "source_document"
    | "evaluation_case"
    | "business_rule"
    | "unknown";
  human_fix_type:
    | "update_prompt"
    | "update_metadata"
    | "update_chunking"
    | "tune_rerank"
    | "improve_parser"
    | "supplement_document"
    | "revise_eval_case"
    | "confirm_business_rule"
    | "no_action";
  handling_status: "open" | "investigating" | "planned" | "resolved" | "ignored";
  handling_notes?: string | null;
  annotated_by?: string | null;
  annotated_at: string;
  updated_at: string;
}

export type CaseAnnotationPayload = Omit<
  CaseAnnotation,
  "id" | "evaluation_case_result_id" | "annotated_by" | "annotated_at" | "updated_at"
>;

export interface CaseAnnotationListItem {
  annotation_id: string;
  evaluation_case_result_id: string;
  evaluation_run_id: string;
  case_id: string;
  assistant_type?: string | null;
  query: string;
  human_judgement: CaseAnnotation["human_judgement"];
  human_root_cause: CaseAnnotation["human_root_cause"];
  human_fix_type: CaseAnnotation["human_fix_type"];
  handling_status: CaseAnnotation["handling_status"];
  handling_notes?: string | null;
  annotated_by?: string | null;
  annotated_at: string;
  updated_at: string;
  system_failure_reason?: string | null;
  system_suggested_fix_type?: string | null;
  evaluation_run_display_label: string;
  evaluation_run_change_type?: string | null;
  evaluation_run_mode_summary: string;
  case_passed: boolean;
  related_improvement_items: RelatedImprovementItem[];
}

export interface CaseAnnotationListResponse {
  items: CaseAnnotationListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AnnotationSummaryBucket {
  key: string;
  label: string;
  count: number;
  percentage?: number | null;
  recommended_action?: string | null;
  assistant_types?: Array<{ key: string; label: string; count: number }>;
}

export interface AnnotationOpenPriorityItem {
  root_cause: string;
  fix_type: string;
  assistant_type: string;
  count: number;
  recommended_action: string;
}

export interface AnnotationSummary {
  total_annotations: number;
  by_root_cause: AnnotationSummaryBucket[];
  by_fix_type: AnnotationSummaryBucket[];
  by_handling_status: AnnotationSummaryBucket[];
  by_assistant_type: AnnotationSummaryBucket[];
  open_priority_items: AnnotationOpenPriorityItem[];
}

export interface EvaluationFailureTriageNote {
  id: string;
  evaluation_case_result_id: string;
  triage_status: "open" | "reviewing" | "resolved" | "ignored" | string;
  note?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
  evaluation_run_id?: string;
  case_id?: string;
  assistant_type?: string | null;
  query?: string;
  failure_reason?: string | null;
  suggested_fix_type?: string | null;
  evaluation_run_display_label?: string;
}

export interface EvaluationFailureTriageNotePayload {
  triage_status: string;
  note?: string | null;
}

export interface EvaluationCaseCompareResult {
  case_id: string;
  before_run?: EvaluationRunDisplay | null;
  after_run?: EvaluationRunDisplay | null;
  before?: (Record<string, unknown> & { annotation?: CaseAnnotation | null; case_result_id?: string }) | null;
  after?: (Record<string, unknown> & { annotation?: CaseAnnotation | null; case_result_id?: string }) | null;
  comparison: {
    status: "resolved" | "introduced_failure" | "still_failed" | "unchanged_passed" | "unavailable";
    rank_changes: Array<Record<string, unknown>>;
    metadata_filter_changed: boolean;
    rerank_changed: boolean;
    citation_changed: boolean;
    failure_reason_changed?: boolean;
    expected_document_ranks?: Record<string, number | null>;
  };
  diagnostic_hints: string[];
}

export interface EvaluationCaseResultDetail {
  id: string;
  evaluation_run_id: string;
  case_id: string;
  assistant_type?: string | null;
  query: string;
  expected_document?: string | null;
  expected_keywords: string[];
  expected_metadata: Record<string, unknown>;
  should_have_answer: boolean;
  passed: boolean;
  failure_reason?: string | null;
  suggested_fix_type?: string | null;
  used_metadata_filter: Record<string, unknown>;
  use_rerank: boolean;
  rerank_applied: boolean;
  answer_excerpt?: string | null;
  citations: Array<Record<string, unknown>>;
  retrieved_results: Array<Record<string, unknown>>;
  annotation?: CaseAnnotation | null;
  created_at: string;
}

export interface EvaluationRunCompareResult {
  before_run: EvaluationRunDisplay;
  after_run: EvaluationRunDisplay;
  comparable: boolean;
  comparability_warnings: string[];
  metric_deltas: Record<string, number>;
  failed_case_diff: {
    resolved_cases: FailedCaseDiffItem[];
    introduced_failures: FailedCaseDiffItem[];
    still_failed_cases: FailedCaseDiffItem[];
    unchanged_passed_count: number;
    before_failed_count: number;
    after_failed_count: number;
  };
}

export const evaluationApi = {
  runRetrieval: (useMetadataFilter = false, useRerank = false) =>
    request<RetrievalEvaluationResult>("/evaluation/retrieval/run", {
      method: "POST",
      body: JSON.stringify({ use_metadata_filter: useMetadataFilter, use_rerank: useRerank }),
    }),
  compareRetrieval: () =>
    request<RetrievalEvaluationCompareResult>("/evaluation/retrieval/compare", { method: "POST" }),
  latestRetrieval: () => request<EvaluationRun | null>("/evaluation/retrieval/latest"),
  listFailureTriageNotes: (params: { evaluation_run_id?: string; triage_status?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.evaluation_run_id) search.set("evaluation_run_id", params.evaluation_run_id);
    if (params.triage_status) search.set("triage_status", params.triage_status);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<EvaluationFailureTriageNote[]>(`/evaluation/triage-notes${suffix}`);
  },
  getFailureTriageNote: (caseResultId: string) =>
    request<EvaluationFailureTriageNote | null>(`/evaluation/cases/${caseResultId}/triage-note`),
  upsertFailureTriageNote: (caseResultId: string, payload: EvaluationFailureTriageNotePayload) =>
    request<EvaluationFailureTriageNote>(`/evaluation/cases/${caseResultId}/triage-note`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runAssistants: (
    useMetadataFilter = true,
    useRerank = true,
    metadata: { run_label?: string; change_type?: string; change_summary?: string; operator_notes?: string } = {},
  ) =>
    request<AssistantEvaluationResult>("/evaluation/assistants/run", {
      method: "POST",
      body: JSON.stringify({ use_metadata_filter: useMetadataFilter, use_rerank: useRerank, ...metadata }),
    }),
  compareAssistants: () =>
    request<AssistantEvaluationCompareResult>("/evaluation/assistants/compare", { method: "POST" }),
  latestAssistants: () => request<AssistantEvaluationResult | null>("/evaluation/assistants/latest"),
  listRuns: (params: {
    eval_type?: "retrieval" | "assistant";
    change_type?: string;
    assistant_type?: string;
    limit?: number;
    order_by?: "created_at" | "run_label" | "change_type";
  } = {}) => {
    const search = new URLSearchParams();
    search.set("eval_type", params.eval_type ?? "assistant");
    search.set("limit", String(params.limit ?? 50));
    if (params.change_type) search.set("change_type", params.change_type);
    if (params.assistant_type) search.set("assistant_type", params.assistant_type);
    if (params.order_by) search.set("order_by", params.order_by);
    return request<EvaluationRunListItem[]>(`/evaluation/runs?${search.toString()}`);
  },
  updateRunMetadata: (
    runId: string,
    payload: { run_label?: string; change_type?: string; change_summary?: string; operator_notes?: string },
  ) =>
    request<EvaluationRunListItem>(`/evaluation/runs/${runId}/metadata`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  generateImprovements: (evaluationRunId: string, force = false) =>
    request<ImprovementItem[]>("/evaluation/improvements/generate", {
      method: "POST",
      body: JSON.stringify({ evaluation_run_id: evaluationRunId, force }),
    }),
  listImprovements: () => request<ImprovementItem[]>("/evaluation/improvements"),
  improvementSummary: () => request<ImprovementSummary>("/evaluation/improvements/summary"),
  getImprovement: (itemId: string) => request<ImprovementItemDetail>(`/evaluation/improvements/${itemId}`),
  getImprovementAnnotations: (itemId: string, page = 1, pageSize = 20) =>
    request<ImprovementAnnotationListResponse>(
      `/evaluation/improvements/${itemId}/annotations?page=${page}&page_size=${pageSize}`,
    ),
  updateImprovement: (itemId: string, payload: { status?: string; suggested_action?: string }) =>
    request<ImprovementItem>(`/evaluation/improvements/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createRegression: (payload: {
    before_evaluation_run_id: string;
    after_evaluation_run_id: string;
    improvement_item_ids: string[];
    notes?: string;
  }) =>
    request<EvaluationRegression>("/evaluation/regressions/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listRegressions: () => request<EvaluationRegression[]>("/evaluation/regressions"),
  regressionSummary: () => request<RegressionSummary>("/evaluation/regressions/summary"),
  assistantTrends: (params: {
    assistant_type?: string;
    limit?: number;
    use_metadata_filter?: boolean;
    use_rerank?: boolean;
  } = {}) => {
    const search = new URLSearchParams();
    if (params.assistant_type) search.set("assistant_type", params.assistant_type);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.use_metadata_filter !== undefined) search.set("use_metadata_filter", String(params.use_metadata_filter));
    if (params.use_rerank !== undefined) search.set("use_rerank", String(params.use_rerank));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<AssistantTrendResponse>(`/evaluation/trends/assistants${suffix}`);
  },
  regressionTrends: (limit = 20) =>
    request<RegressionTrendResponse>(`/evaluation/trends/regressions?limit=${limit}`),
  compareRuns: (beforeRunId: string, afterRunId: string) => {
    const search = new URLSearchParams({ before_run_id: beforeRunId, after_run_id: afterRunId });
    return request<EvaluationRunCompareResult>(`/evaluation/runs/compare?${search.toString()}`);
  },
  compareCase: (caseId: string, beforeRunId: string, afterRunId: string) => {
    const search = new URLSearchParams({ before_run_id: beforeRunId, after_run_id: afterRunId });
    return request<EvaluationCaseCompareResult>(`/evaluation/runs/compare/cases/${caseId}?${search.toString()}`);
  },
  getCaseResult: (caseResultId: string) => request<EvaluationCaseResultDetail>(`/evaluation/cases/${caseResultId}`),
  upsertCaseAnnotation: (caseResultId: string, payload: CaseAnnotationPayload) =>
    request<CaseAnnotation>(`/evaluation/cases/${caseResultId}/annotation`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCaseAnnotation: (caseResultId: string, payload: Partial<CaseAnnotationPayload>) =>
    request<CaseAnnotation>(`/evaluation/cases/${caseResultId}/annotation`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  listCaseAnnotations: (params: {
    human_root_cause?: string;
    human_fix_type?: string;
    handling_status?: string;
    assistant_type?: string;
    evaluation_run_id?: string;
    improvement_item_id?: string;
    improvement_status?: string;
    regression_status?: string;
    date_from?: string;
    date_to?: string;
    keyword?: string;
    page?: number;
    page_size?: number;
    order_by?: string;
    order_direction?: "asc" | "desc";
  } = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    });
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<CaseAnnotationListResponse>(`/evaluation/case-annotations${suffix}`);
  },
  annotationSummary: (params: {
    evaluation_run_id?: string;
    assistant_type?: string;
    handling_status?: string;
    date_from?: string;
    date_to?: string;
  } = {}) => {
    const search = new URLSearchParams();
    if (params.evaluation_run_id) search.set("evaluation_run_id", params.evaluation_run_id);
    if (params.assistant_type) search.set("assistant_type", params.assistant_type);
    if (params.handling_status) search.set("handling_status", params.handling_status);
    if (params.date_from) search.set("date_from", params.date_from);
    if (params.date_to) search.set("date_to", params.date_to);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<AnnotationSummary>(`/evaluation/annotations/summary${suffix}`);
  },
};

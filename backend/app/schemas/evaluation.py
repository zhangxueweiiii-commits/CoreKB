from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.evaluation_run import EvaluationType


class EvalCase(BaseModel):
    id: str
    category: str
    assistant_type: str | None = None
    query: str
    expected_document: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)
    expected_metadata: dict[str, str] = Field(default_factory=dict)
    expected_answer_type: str | None = None
    should_have_answer: bool = True


class EvalCaseResult(BaseModel):
    id: str
    category: str
    query: str
    should_have_answer: bool
    hit_rank: int | None = None
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    reciprocal_rank: float = 0.0
    keyword_match_rate: float = 0.0
    metadata_match_rate: float = 0.0
    no_answer_correct: bool | None = None
    passed: bool = False
    used_metadata_filter: dict = Field(default_factory=dict)
    rerank_applied: bool = False
    rerank_error: str | None = None
    case_result_id: UUID | None = None
    top_results: list[dict] = Field(default_factory=list)


class EvaluationMetrics(BaseModel):
    total_cases: int
    use_metadata_filter: bool = False
    use_rerank: bool = False
    rerank_top_n: int | None = None
    mode: str = "single"
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    keyword_match_rate: float
    metadata_match_rate: float
    no_answer_accuracy: float


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    eval_type: EvaluationType
    total_cases: int
    metrics: dict
    failed_cases: list[dict]
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None
    config_snapshot: dict | None = None
    created_by: UUID | None = None
    created_at: datetime


class EvaluationReadiness(BaseModel):
    evaluation_kb_id: UUID | None = None
    evaluation_kb_ready: bool = False
    missing_documents: list[str] = Field(default_factory=list)
    unindexed_documents: list[str] = Field(default_factory=list)


class RetrievalEvaluationRunRequest(BaseModel):
    use_metadata_filter: bool = False
    use_rerank: bool = False
    rerank_top_n: int | None = Field(default=None, ge=1, le=100)


class RetrievalEvaluationResponse(BaseModel):
    run_id: UUID | None = None
    evaluation_kb_id: UUID | None = None
    evaluation_kb_ready: bool = True
    missing_documents: list[str] = Field(default_factory=list)
    unindexed_documents: list[str] = Field(default_factory=list)
    total_cases: int
    use_metadata_filter: bool = False
    use_rerank: bool = False
    rerank_top_n: int | None = None
    mode: str = "single"
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    keyword_match_rate: float
    metadata_match_rate: float
    no_answer_accuracy: float
    failed_cases: list[dict]
    case_results: list[EvalCaseResult] = Field(default_factory=list)


class RetrievalEvaluationCompareResponse(BaseModel):
    baseline: RetrievalEvaluationResponse
    metadata_filter: RetrievalEvaluationResponse
    metadata_filter_rerank: RetrievalEvaluationResponse
    delta: dict[str, dict[str, float]]


class AssistantEvaluationMetrics(BaseModel):
    assistant_type: str = "overall"
    total_cases: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float = 0.0
    mrr: float
    keyword_match_rate: float
    metadata_match_rate: float
    no_answer_accuracy: float
    citation_rate: float
    failed_cases: list[dict] = Field(default_factory=list)
    quality_gate_passed: bool = True
    failed_thresholds: list[dict] = Field(default_factory=list)
    threshold_config: dict = Field(default_factory=dict)


class AssistantEvaluationCaseResult(BaseModel):
    id: str
    assistant_type: str
    category: str
    query: str
    passed: bool
    citation_present: bool
    no_answer_correct: bool | None = None
    keyword_match_rate: float
    metadata_match_rate: float
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool = False
    expected_document: str | None = None
    actual_top_documents: list[str] = Field(default_factory=list)
    expected_metadata: dict = Field(default_factory=dict)
    used_metadata_filter: dict = Field(default_factory=dict)
    use_rerank: bool = False
    rerank_applied: bool = False
    answer_excerpt: str | None = None
    citations: list[dict] = Field(default_factory=list)
    retrieved_results: list[dict] = Field(default_factory=list)
    case_result_id: UUID | None = None
    reason: str | None = None
    failure_reason: str = "unknown"
    failure_detail: str | None = None
    suggested_fix_type: str = "unknown"


class AssistantEvaluationRunRequest(BaseModel):
    use_metadata_filter: bool = True
    use_rerank: bool = True
    rerank_top_n: int | None = Field(default=None, ge=1, le=100)
    run_label: str | None = None
    change_type: str | None = "unknown"
    change_summary: str | None = None
    operator_notes: str | None = None


class AssistantEvaluationResponse(BaseModel):
    run_id: UUID | None = None
    total_cases: int
    use_metadata_filter: bool = True
    use_rerank: bool = True
    rerank_top_n: int | None = None
    mode: str = "single"
    created_at: datetime | None = None
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None
    config_snapshot: dict | None = None
    overall_metrics: AssistantEvaluationMetrics
    per_assistant_metrics: dict[str, AssistantEvaluationMetrics]
    metrics_by_assistant: dict[str, AssistantEvaluationMetrics] = Field(default_factory=dict)
    failed_cases: list[AssistantEvaluationCaseResult]
    case_results: list[AssistantEvaluationCaseResult]
    quality_gate_passed: bool = True
    failed_thresholds: list[dict] = Field(default_factory=list)
    threshold_config: dict = Field(default_factory=dict)
    per_assistant_quality_gate: dict[str, dict] = Field(default_factory=dict)


class AssistantEvaluationCompareResponse(BaseModel):
    baseline: AssistantEvaluationResponse
    metadata_filter: AssistantEvaluationResponse
    metadata_filter_rerank: AssistantEvaluationResponse
    delta: dict[str, dict[str, float]]


class ImprovementGenerateRequest(BaseModel):
    evaluation_run_id: UUID
    force: bool = False


class ImprovementUpdateRequest(BaseModel):
    status: str | None = None
    suggested_action: str | None = None
    resolved_evaluation_run_id: UUID | None = None


class ImprovementItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_run_id: UUID
    assistant_type: str
    fix_type: str
    priority: str
    failed_case_count: int
    affected_case_ids: list[str]
    main_failure_reasons: list[str]
    suggested_action: str
    source: str = "system_rule"
    annotation_count: int = 0
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolved_evaluation_run_id: UUID | None = None
    regression_status: str = "unverified"
    related_regression_id: UUID | None = None


class RelatedImprovementItemRead(BaseModel):
    id: UUID
    fix_type: str
    priority: str
    status: str
    regression_status: str
    suggested_action: str
    relation_source: str


class ImprovementCaseResultRead(BaseModel):
    evaluation_case_result_id: UUID
    evaluation_run_id: UUID
    case_id: str
    assistant_type: str | None = None
    query: str
    system_failure_reason: str | None = None
    system_suggested_fix_type: str | None = None
    evaluation_run_display_label: str
    evaluation_run_change_type: str | None = None
    evaluation_run_mode_summary: str
    case_passed: bool
    relation_source: str


class ImprovementAnnotationRead(BaseModel):
    annotation_id: UUID
    evaluation_case_result_id: UUID
    evaluation_run_id: UUID
    case_id: str
    assistant_type: str | None = None
    query: str
    human_judgement: str
    human_root_cause: str
    human_fix_type: str
    handling_status: str
    handling_notes: str | None = None
    annotated_by: UUID | None = None
    annotated_at: datetime
    updated_at: datetime
    system_failure_reason: str | None = None
    system_suggested_fix_type: str | None = None
    evaluation_run_display_label: str
    evaluation_run_change_type: str | None = None
    evaluation_run_mode_summary: str
    case_passed: bool
    relation_source: str


class ImprovementItemDetailRead(ImprovementItemRead):
    related_case_results: list[ImprovementCaseResultRead] = Field(default_factory=list)
    related_annotations: list[ImprovementAnnotationRead] = Field(default_factory=list)


class ImprovementAnnotationListResponse(BaseModel):
    items: list[ImprovementAnnotationRead] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class ImprovementSummary(BaseModel):
    total_open: int
    by_fix_type: dict[str, int]
    by_assistant_type: dict[str, int]
    by_priority: dict[str, int]
    top_failure_reasons: dict[str, int]


class RegressionCreateRequest(BaseModel):
    before_evaluation_run_id: UUID
    after_evaluation_run_id: UUID
    improvement_item_ids: list[UUID]
    notes: str | None = None


class RegressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    before_evaluation_run_id: UUID
    after_evaluation_run_id: UUID
    improvement_item_ids: list[str]
    assistant_type: str
    fix_type: str
    before_metrics: dict
    after_metrics: dict
    delta_metrics: dict
    affected_case_ids: list[str]
    resolved_case_ids: list[str]
    still_failed_case_ids: list[str]
    regression_passed: bool
    notes: str | None = None
    before_run_label: str | None = None
    before_change_type: str | None = None
    before_change_summary: str | None = None
    after_run_label: str | None = None
    after_change_type: str | None = None
    after_change_summary: str | None = None
    before_run_display: dict | None = None
    after_run_display: dict | None = None
    before_metrics_summary: dict | None = None
    after_metrics_summary: dict | None = None
    before_mode_summary: str | None = None
    after_mode_summary: str | None = None
    before_run: dict | None = None
    after_run: dict | None = None
    created_by: UUID | None = None
    created_at: datetime


class RegressionSummary(BaseModel):
    total_regressions: int
    passed_count: int
    failed_count: int
    pass_rate: float
    by_fix_type: dict[str, int]
    by_assistant_type: dict[str, int]
    recent_regressions: list[RegressionRead]


class RegressionTrendResponse(BaseModel):
    total_regressions: int
    passed_count: int
    failed_count: int
    pass_rate: float
    recent_items: list[RegressionRead]


class TrendWarning(BaseModel):
    metric: str
    previous: float | bool
    current: float | bool
    delta: float | None = None
    level: str = "warning"


class AssistantTrendItem(BaseModel):
    evaluation_run_id: UUID
    created_at: datetime
    assistant_type: str
    mode: str = "single"
    use_metadata_filter: bool = True
    use_rerank: bool = True
    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    mrr: float = 0.0
    keyword_match_rate: float = 0.0
    metadata_match_rate: float = 0.0
    no_answer_accuracy: float = 0.0
    citation_rate: float = 0.0
    quality_gate_passed: bool = True
    display_label: str | None = None
    metrics_summary: dict | None = None
    mode_summary: str | None = None
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None
    config_snapshot: dict | None = None
    regression_warnings: list[TrendWarning] = Field(default_factory=list)


class AssistantTrendResponse(BaseModel):
    assistant_type: str
    items: list[AssistantTrendItem]
    delta_from_previous: dict[str, float] = Field(default_factory=dict)
    regression_warnings: list[TrendWarning] = Field(default_factory=list)


class OverallTrendItem(BaseModel):
    evaluation_run_id: UUID
    created_at: datetime
    mode: str = "single"
    use_metadata_filter: bool = True
    use_rerank: bool = True
    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    mrr: float = 0.0
    keyword_match_rate: float = 0.0
    metadata_match_rate: float = 0.0
    no_answer_accuracy: float = 0.0
    citation_rate: float = 0.0
    quality_gate_passed: bool = True
    display_label: str | None = None
    metrics_summary: dict | None = None
    mode_summary: str | None = None
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None
    config_snapshot: dict | None = None
    regression_warnings: list[TrendWarning] = Field(default_factory=list)


class OverallTrendResponse(BaseModel):
    items: list[OverallTrendItem]
    delta_from_previous: dict[str, float] = Field(default_factory=dict)
    regression_warnings: list[TrendWarning] = Field(default_factory=list)


class EvaluationRunMetadataUpdateRequest(BaseModel):
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None


class EvaluationRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    eval_type: EvaluationType
    total_cases: int
    metrics: dict
    display_label: str
    metrics_summary: dict
    mode_summary: str
    run_label: str | None = None
    change_type: str | None = None
    change_summary: str | None = None
    operator_notes: str | None = None
    config_snapshot: dict | None = None
    created_by: UUID | None = None
    created_at: datetime


class EvaluationRunCompareResponse(BaseModel):
    before_run: dict
    after_run: dict
    comparable: bool
    comparability_warnings: list[str] = Field(default_factory=list)
    metric_deltas: dict[str, float]
    failed_case_diff: dict


class EvaluationCaseAnnotationBase(BaseModel):
    human_judgement: str
    human_root_cause: str
    human_fix_type: str
    handling_status: str = "open"
    handling_notes: str | None = None


class EvaluationCaseAnnotationCreate(EvaluationCaseAnnotationBase):
    pass


class EvaluationCaseAnnotationUpdate(BaseModel):
    human_judgement: str | None = None
    human_root_cause: str | None = None
    human_fix_type: str | None = None
    handling_status: str | None = None
    handling_notes: str | None = None


class EvaluationCaseAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_case_result_id: UUID
    human_judgement: str
    human_root_cause: str
    human_fix_type: str
    handling_status: str
    handling_notes: str | None = None
    annotated_by: UUID | None = None
    annotated_at: datetime
    updated_at: datetime


class EvaluationCaseAnnotationListItem(BaseModel):
    annotation_id: UUID
    evaluation_case_result_id: UUID
    evaluation_run_id: UUID
    case_id: str
    assistant_type: str | None = None
    query: str
    human_judgement: str
    human_root_cause: str
    human_fix_type: str
    handling_status: str
    handling_notes: str | None = None
    annotated_by: UUID | None = None
    annotated_at: datetime
    updated_at: datetime
    system_failure_reason: str | None = None
    system_suggested_fix_type: str | None = None
    evaluation_run_display_label: str
    evaluation_run_change_type: str | None = None
    evaluation_run_mode_summary: str
    case_passed: bool
    related_improvement_items: list[RelatedImprovementItemRead] = Field(default_factory=list)


class EvaluationCaseAnnotationListResponse(BaseModel):
    items: list[EvaluationCaseAnnotationListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class AnnotationSummaryBucket(BaseModel):
    key: str
    label: str
    count: int
    percentage: float | None = None
    recommended_action: str | None = None
    assistant_types: list[dict] = Field(default_factory=list)


class AnnotationOpenPriorityItem(BaseModel):
    root_cause: str
    fix_type: str
    assistant_type: str
    count: int
    recommended_action: str


class AnnotationSummaryResponse(BaseModel):
    total_annotations: int
    by_root_cause: list[AnnotationSummaryBucket] = Field(default_factory=list)
    by_fix_type: list[AnnotationSummaryBucket] = Field(default_factory=list)
    by_handling_status: list[AnnotationSummaryBucket] = Field(default_factory=list)
    by_assistant_type: list[AnnotationSummaryBucket] = Field(default_factory=list)
    open_priority_items: list[AnnotationOpenPriorityItem] = Field(default_factory=list)


class EvaluationCaseResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_run_id: UUID
    case_id: str
    assistant_type: str | None = None
    query: str
    expected_document: str | None = None
    expected_keywords: list = Field(default_factory=list)
    expected_metadata: dict = Field(default_factory=dict)
    should_have_answer: bool
    passed: bool
    failure_reason: str | None = None
    suggested_fix_type: str | None = None
    used_metadata_filter: dict = Field(default_factory=dict)
    use_rerank: bool
    rerank_applied: bool
    answer_excerpt: str | None = None
    citations: list = Field(default_factory=list)
    retrieved_results: list = Field(default_factory=list)
    annotation: EvaluationCaseAnnotationRead | None = None
    created_at: datetime


class EvaluationCaseCompareResponse(BaseModel):
    case_id: str
    before_run: dict | None = None
    after_run: dict | None = None
    before: dict | None = None
    after: dict | None = None
    comparison: dict
    diagnostic_hints: list[str] = Field(default_factory=list)

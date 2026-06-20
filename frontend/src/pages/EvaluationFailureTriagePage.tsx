import { useEffect, useMemo, useState } from "react";
import {
  evaluationApi,
  type AssistantEvaluationCaseResult,
  type AssistantEvaluationResult,
  type EvalCaseResult,
  type EvaluationRun,
} from "../api/evaluation";

interface Props {
  onOpenEvaluation: () => void;
  onOpenAnnotations: (search: string) => void;
}

type TriageSource = "retrieval" | "assistant";

interface TriageCase {
  source: TriageSource;
  id: string;
  category: string;
  assistantType?: string | null;
  query: string;
  shouldHaveAnswer: boolean;
  expectedDocument?: string | null;
  failureReason: string;
  suggestedFixType: string;
  failureDetail?: string | null;
  hitAt1?: boolean;
  hitAt3?: boolean;
  hitAt5?: boolean;
  keywordMatchRate?: number;
  metadataMatchRate?: number;
  noAnswerCorrect?: boolean | null;
  citationPresent?: boolean | null;
  usedMetadataFilter?: Record<string, unknown>;
  topDocuments: string[];
}

function percent(value?: number | null) {
  if (typeof value !== "number") return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function boolText(value?: boolean | null) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "-";
}

function sourceLabel(source: TriageSource) {
  return source === "retrieval" ? "Retrieval" : "Assistant";
}

function statusClass(source: TriageSource) {
  return source === "retrieval" ? "status-info" : "status-warning";
}

function stringifyTopDocument(result: Record<string, unknown>) {
  const candidates = [
    result.document_name,
    result.filename,
    result.document_title,
    result.document_id,
    result.id,
  ];
  const value = candidates.find((candidate) => typeof candidate === "string" && candidate.trim());
  return typeof value === "string" ? value : "Unknown document";
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function inferRetrievalFailureReason(item: EvalCaseResult) {
  if (!item.should_have_answer && item.no_answer_correct === false) return "answered_should_no_answer";
  if (item.should_have_answer && !item.hit_at_5) return "not_retrieved_top5";
  if (item.should_have_answer && !item.hit_at_1) return "low_rank";
  if (item.metadata_match_rate < 1) return "metadata_mismatch";
  if (item.keyword_match_rate < 1) return "keyword_missing";
  if (item.no_answer_correct === false) return "no_answer_incorrect";
  return "retrieval_expectation_failed";
}

function inferRetrievalFixType(reason: string) {
  if (reason === "not_retrieved_top5") return "metadata_filter_or_embedding";
  if (reason === "low_rank") return "rerank";
  if (reason === "metadata_mismatch") return "document_metadata";
  if (reason === "keyword_missing") return "chunking";
  if (reason === "answered_should_no_answer" || reason === "no_answer_incorrect") return "threshold_or_prompt";
  return "unknown";
}

function normalizeRetrievalCase(item: EvalCaseResult): TriageCase {
  const failureReason = inferRetrievalFailureReason(item);
  return {
    source: "retrieval",
    id: item.id,
    category: item.category,
    query: item.query,
    shouldHaveAnswer: item.should_have_answer,
    failureReason,
    suggestedFixType: inferRetrievalFixType(failureReason),
    hitAt1: item.hit_at_1,
    hitAt3: item.hit_at_3,
    hitAt5: item.hit_at_5,
    keywordMatchRate: item.keyword_match_rate,
    metadataMatchRate: item.metadata_match_rate,
    noAnswerCorrect: item.no_answer_correct,
    topDocuments: (item.top_results ?? []).slice(0, 5).map(stringifyTopDocument),
  };
}

function normalizeAssistantCase(item: AssistantEvaluationCaseResult): TriageCase {
  return {
    source: "assistant",
    id: item.id,
    category: item.category,
    assistantType: item.assistant_type,
    query: item.query,
    shouldHaveAnswer: true,
    expectedDocument: item.expected_document,
    failureReason: item.failure_reason || item.reason || "assistant_expectation_failed",
    suggestedFixType: item.suggested_fix_type || "unknown",
    failureDetail: item.failure_detail || item.reason || null,
    hitAt1: item.hit_at_1,
    hitAt3: item.hit_at_3,
    hitAt5: item.hit_at_5,
    keywordMatchRate: item.keyword_match_rate,
    metadataMatchRate: item.metadata_match_rate,
    noAnswerCorrect: item.no_answer_correct,
    citationPresent: item.citation_present,
    usedMetadataFilter: item.used_metadata_filter,
    topDocuments: item.actual_top_documents ?? [],
  };
}

function annotationSearchFor(item: TriageCase) {
  const params = new URLSearchParams({ keyword: item.id });
  if (item.assistantType) params.set("assistant_type", item.assistantType);
  return `?${params.toString()}`;
}

export function EvaluationFailureTriagePage({ onOpenEvaluation, onOpenAnnotations }: Props) {
  const [latestRetrieval, setLatestRetrieval] = useState<EvaluationRun | null>(null);
  const [latestAssistant, setLatestAssistant] = useState<AssistantEvaluationResult | null>(null);
  const [source, setSource] = useState("all");
  const [assistantType, setAssistantType] = useState("all");
  const [failureReason, setFailureReason] = useState("all");
  const [fixType, setFixType] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [retrieval, assistant] = await Promise.all([
        evaluationApi.latestRetrieval(),
        evaluationApi.latestAssistants(),
      ]);
      setLatestRetrieval(retrieval);
      setLatestAssistant(assistant);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation failures");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const cases = useMemo(() => {
    const retrievalCases = (latestRetrieval?.failed_cases ?? []).map(normalizeRetrievalCase);
    const assistantCases = (latestAssistant?.failed_cases ?? []).map(normalizeAssistantCase);
    return [...retrievalCases, ...assistantCases];
  }, [latestRetrieval, latestAssistant]);

  const filteredCases = useMemo(() => {
    const needle = keyword.trim().toLowerCase();
    return cases.filter((item) => {
      if (source !== "all" && item.source !== source) return false;
      if (assistantType !== "all" && item.assistantType !== assistantType) return false;
      if (failureReason !== "all" && item.failureReason !== failureReason) return false;
      if (fixType !== "all" && item.suggestedFixType !== fixType) return false;
      if (!needle) return true;
      return [item.id, item.query, item.expectedDocument, item.failureReason, item.suggestedFixType]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
  }, [assistantType, cases, failureReason, fixType, keyword, source]);

  const reasonOptions = useMemo(() => unique(cases.map((item) => item.failureReason)), [cases]);
  const fixTypeOptions = useMemo(() => unique(cases.map((item) => item.suggestedFixType)), [cases]);
  const assistantTypeOptions = useMemo(
    () => unique(cases.map((item) => item.assistantType || "").filter(Boolean)),
    [cases],
  );

  const noCitationCount = cases.filter(
    (item) => item.failureReason === "no_citation" || item.citationPresent === false,
  ).length;
  const metadataIssueCount = cases.filter(
    (item) => item.failureReason.includes("metadata") || item.suggestedFixType.includes("metadata"),
  ).length;
  const noAnswerIssueCount = cases.filter(
    (item) => item.failureReason.includes("no_answer") || item.failureReason === "answered_should_no_answer",
  ).length;

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Evaluation Failure Triage</h2>
          <p className="muted">
            Read-only triage of the latest retrieval and assistant evaluation failures.
          </p>
        </div>
        <div className="actions">
          <button type="button" onClick={load} disabled={loading}>Refresh</button>
          <button type="button" onClick={onOpenEvaluation}>Open Evaluation Workbench</button>
        </div>
      </div>

      {loading && <p className="muted">Loading failed cases...</p>}
      {error && <p className="error">{error}</p>}

      <div className="metric-grid dashboard-cards">
        <div className="dashboard-card">
          <span className="muted">Total failures</span>
          <strong>{cases.length}</strong>
          <small>{filteredCases.length} visible after filters</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Retrieval failures</span>
          <strong>{cases.filter((item) => item.source === "retrieval").length}</strong>
          <small>Latest retrieval run only</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Assistant failures</span>
          <strong>{cases.filter((item) => item.source === "assistant").length}</strong>
          <small>Latest assistant run only</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Metadata related</span>
          <strong>{metadataIssueCount}</strong>
          <small>Reason or fix type mentions metadata</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Citation issues</span>
          <strong>{noCitationCount}</strong>
          <small>Missing citation signals</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">No-answer issues</span>
          <strong>{noAnswerIssueCount}</strong>
          <small>Refusal or threshold behavior</small>
        </div>
      </div>

      <div className="filters">
        <label>
          Source
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="all">All</option>
            <option value="retrieval">Retrieval</option>
            <option value="assistant">Assistant</option>
          </select>
        </label>
        <label>
          Assistant
          <select value={assistantType} onChange={(event) => setAssistantType(event.target.value)}>
            <option value="all">All</option>
            {assistantTypeOptions.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Failure reason
          <select value={failureReason} onChange={(event) => setFailureReason(event.target.value)}>
            <option value="all">All</option>
            {reasonOptions.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Suggested fix
          <select value={fixType} onChange={(event) => setFixType(event.target.value)}>
            <option value="all">All</option>
            {fixTypeOptions.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Keyword
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Case id or query" />
        </label>
      </div>

      {cases.length === 0 && !loading ? (
        <div className="subtle-note">
          No failed cases are available in the latest evaluation runs. Run retrieval or assistant evaluation first.
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="subtle-note">No failed cases match the current filters.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Case</th>
              <th>Assistant / Category</th>
              <th>Failure reason</th>
              <th>Suggested fix</th>
              <th>Hit@1 / Hit@3</th>
              <th>Keyword / Metadata</th>
              <th>Top documents</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCases.map((item) => (
              <tr key={`${item.source}-${item.id}`}>
                <td>
                  <span className={`status-pill ${statusClass(item.source)}`}>{sourceLabel(item.source)}</span>
                </td>
                <td>
                  <strong>{item.id}</strong>
                  <div className="muted">{item.query}</div>
                  {item.expectedDocument && <div className="muted">Expected: {item.expectedDocument}</div>}
                </td>
                <td>
                  {item.assistantType || "-"}
                  <div className="muted">{item.category}</div>
                </td>
                <td>
                  {item.failureReason}
                  {item.failureDetail && <div className="muted">{item.failureDetail}</div>}
                </td>
                <td>{item.suggestedFixType}</td>
                <td>
                  {boolText(item.hitAt1)} / {boolText(item.hitAt3)}
                  <div className="muted">Hit@5 {boolText(item.hitAt5)}</div>
                </td>
                <td>
                  {percent(item.keywordMatchRate)} / {percent(item.metadataMatchRate)}
                  {item.usedMetadataFilter && Object.keys(item.usedMetadataFilter).length > 0 && (
                    <div className="muted">Filter: {JSON.stringify(item.usedMetadataFilter)}</div>
                  )}
                </td>
                <td>
                  {item.topDocuments.length === 0 ? (
                    <span className="muted">No top documents</span>
                  ) : (
                    <ol className="compact-list">
                      {item.topDocuments.slice(0, 3).map((document, index) => (
                        <li key={`${item.id}-${document}-${index}`}>{document}</li>
                      ))}
                    </ol>
                  )}
                </td>
                <td>
                  <div className="actions">
                    <button type="button" onClick={onOpenEvaluation}>Workbench</button>
                    <button type="button" onClick={() => onOpenAnnotations(annotationSearchFor(item))}>
                      Annotations
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="subtle-note">
        This page is advisory only. It does not create annotations, generate improvement items, rerun evaluation,
        call LLMs, or change production metadata, prompts, chunking, rerank settings, or indexes.
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";
import {
  evaluationApi,
  type CaseAnnotation,
  type EvaluationCaseResultDetail,
  type ImprovementAnnotation,
  type ImprovementItemDetail,
} from "../api/evaluation";

const STATUS_OPTIONS: CaseAnnotation["handling_status"][] = ["open", "investigating", "planned", "resolved", "ignored"];

function truncate(value?: string | null, length = 96) {
  if (!value) return "-";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    : [];
}

function DetailPanel({ detail, onBack }: { detail: EvaluationCaseResultDetail; onBack: () => void }) {
  const retrievedResults = asRecordArray(detail.retrieved_results);
  return (
    <div className="subtle-block">
      <div className="section-heading">
        <h3>Case drill-down: {detail.case_id}</h3>
        <button type="button" onClick={onBack}>Back to improvement item</button>
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
      <p><strong>Answer excerpt:</strong> {detail.answer_excerpt || "-"}</p>
      {detail.annotation && (
        <div className="subtle-block">
          <strong>Human annotation</strong>
          <p>
            {detail.annotation.human_root_cause} / {detail.annotation.human_fix_type} / {detail.annotation.handling_status}
          </p>
          <p>{detail.annotation.handling_notes || "-"}</p>
        </div>
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

interface ImprovementItemDetailPageProps {
  itemId: string | null;
  fromAnnotationSearch?: string;
  onBackToAnnotations?: (search: string) => void;
}

export function ImprovementItemDetailPage({
  itemId,
  fromAnnotationSearch = "",
  onBackToAnnotations,
}: ImprovementItemDetailPageProps) {
  const [detail, setDetail] = useState<ImprovementItemDetail | null>(null);
  const [caseDetail, setCaseDetail] = useState<EvaluationCaseResultDetail | null>(null);
  const [editing, setEditing] = useState<ImprovementAnnotation | null>(null);
  const [editStatus, setEditStatus] = useState<CaseAnnotation["handling_status"]>("open");
  const [editNotes, setEditNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    if (!itemId) return;
    setLoading(true);
    setError("");
    try {
      const response = await evaluationApi.getImprovement(itemId);
      setDetail(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load improvement item");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [itemId]);

  async function openDrillDown(annotation: ImprovementAnnotation) {
    setError("");
    try {
      setCaseDetail(await evaluationApi.getCaseResult(annotation.evaluation_case_result_id));
      window.history.replaceState(
        null,
        "",
        `/evaluation/improvements/${itemId}?from=improvement&case_result_id=${annotation.evaluation_case_result_id}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case drill-down");
    }
  }

  async function updateStatus(annotation: ImprovementAnnotation, status: CaseAnnotation["handling_status"]) {
    setError("");
    try {
      await evaluationApi.updateCaseAnnotation(annotation.evaluation_case_result_id, { handling_status: status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update annotation");
    }
  }

  function beginEdit(annotation: ImprovementAnnotation) {
    setEditing(annotation);
    setEditStatus(annotation.handling_status);
    setEditNotes(annotation.handling_notes ?? "");
  }

  async function saveEdit() {
    if (!editing) return;
    setError("");
    try {
      await evaluationApi.updateCaseAnnotation(editing.evaluation_case_result_id, {
        handling_status: editStatus,
        handling_notes: editNotes,
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save annotation");
    }
  }

  if (caseDetail) {
    return (
      <section className="panel">
        {error && <p className="error">{error}</p>}
        <DetailPanel detail={caseDetail} onBack={() => setCaseDetail(null)} />
      </section>
    );
  }

  if (!itemId) {
    return (
      <section className="panel">
        <p className="muted">No improvement item selected.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Improvement item detail</h2>
        {onBackToAnnotations && (
          <button type="button" onClick={() => onBackToAnnotations(fromAnnotationSearch)}>
            Back to annotations
          </button>
        )}
      </div>
      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">{error}</p>}
      {detail && (
        <>
          <div className="subtle-block">
            <div className="metric-grid">
              <span>ID: {detail.id}</span>
              <span>Fix type: {detail.fix_type}</span>
              <span>Priority: {detail.priority}</span>
              <span>Status: {detail.status}</span>
              <span>Regression: {detail.regression_status}</span>
              <span>Source: {detail.source}</span>
              <span>Failed cases: {detail.failed_case_count}</span>
              <span>Annotations: {detail.annotation_count}</span>
            </div>
            <p><strong>Suggested action:</strong> {detail.suggested_action}</p>
            <p><strong>Main reasons:</strong> {(detail.main_failure_reasons || []).join(", ") || "-"}</p>
          </div>

          <h3>Related annotations</h3>
          {detail.related_annotations.length === 0 ? (
            <p className="muted">No human annotations linked to this improvement item yet.</p>
          ) : (
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
                  <th>Relation</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {detail.related_annotations.map((annotation) => (
                  <tr key={annotation.annotation_id}>
                    <td>
                      <strong>{annotation.case_id}</strong>
                      <div className="muted" title={annotation.query}>{truncate(annotation.query, 72)}</div>
                    </td>
                    <td>{annotation.assistant_type || "-"}</td>
                    <td>
                      <strong>{annotation.evaluation_run_display_label}</strong>
                      <div className="muted">{annotation.evaluation_run_change_type || "unknown"} / {annotation.evaluation_run_mode_summary}</div>
                    </td>
                    <td>
                      {annotation.system_failure_reason || "-"}
                      <div className="muted">{annotation.system_suggested_fix_type || "-"}</div>
                    </td>
                    <td>{annotation.human_root_cause}</td>
                    <td>{annotation.human_fix_type}</td>
                    <td>{annotation.handling_status}</td>
                    <td>{annotation.relation_source}</td>
                    <td>
                      <button type="button" onClick={() => openDrillDown(annotation)}>View drill-down</button>
                      <button type="button" onClick={() => beginEdit(annotation)}>Edit annotation</button>
                      <button type="button" onClick={() => updateStatus(annotation, "investigating")}>Mark investigating</button>
                      <button type="button" onClick={() => updateStatus(annotation, "resolved")}>Mark resolved</button>
                      <button type="button" onClick={() => updateStatus(annotation, "ignored")}>Ignore</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Related case results</h3>
          {detail.related_case_results.length === 0 ? (
            <p className="muted">No case result links found.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Assistant</th>
                  <th>Run</th>
                  <th>System reason</th>
                  <th>Relation</th>
                  <th>Passed</th>
                </tr>
              </thead>
              <tbody>
                {detail.related_case_results.map((item) => (
                  <tr key={item.evaluation_case_result_id}>
                    <td>
                      <strong>{item.case_id}</strong>
                      <div className="muted" title={item.query}>{truncate(item.query, 72)}</div>
                    </td>
                    <td>{item.assistant_type || "-"}</td>
                    <td>{item.evaluation_run_display_label}</td>
                    <td>{item.system_failure_reason || "-"}</td>
                    <td>{item.relation_source}</td>
                    <td>{item.case_passed ? "Pass" : "Fail"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {editing && (
        <div className="subtle-block">
          <div className="section-heading">
            <h3>Edit annotation: {editing.case_id}</h3>
            <button type="button" onClick={() => setEditing(null)}>Close</button>
          </div>
          <label>
            Handling status
            <select value={editStatus} onChange={(event) => setEditStatus(event.target.value as CaseAnnotation["handling_status"])}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label>
            Handling notes
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={3} />
          </label>
          <button type="button" onClick={saveEdit}>Save annotation</button>
        </div>
      )}
    </section>
  );
}

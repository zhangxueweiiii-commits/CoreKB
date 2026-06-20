import { useEffect, useMemo, useState } from "react";
import {
  evaluationApi,
  type AnnotationSummary,
  type AssistantEvaluationResult,
  type AssistantTrendResponse,
  type EvaluationRun,
  type EvaluationRunListItem,
  type ImprovementSummary,
  type RegressionTrendResponse,
} from "../api/evaluation";

interface Props {
  onOpenEvaluation: () => void;
}

function percent(value?: number | null) {
  if (typeof value !== "number") return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function decimal(value?: number | null) {
  if (typeof value !== "number") return "-";
  return value.toFixed(3);
}

function numberMetric(metrics: Record<string, unknown> | undefined, key: string) {
  const value = metrics?.[key];
  return typeof value === "number" ? value : undefined;
}


function statusText(value?: boolean | null) {
  if (value === true) return "Pass";
  if (value === false) return "Fail";
  return "Unknown";
}

function statusClass(value?: boolean | null) {
  if (value === true) return "status-indexed";
  if (value === false) return "status-failed";
  return "status-info";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function openAnnotationCount(summary: AnnotationSummary | null) {
  const statuses = summary?.by_handling_status ?? [];
  return statuses
    .filter((item) => ["open", "investigating", "planned"].includes(item.key))
    .reduce((total, item) => total + item.count, 0);
}

function runMode(run: EvaluationRunListItem) {
  return run.mode_summary || String(run.metrics?.mode || "-");
}

export function EvaluationDashboardPage({ onOpenEvaluation }: Props) {
  const [latestRetrieval, setLatestRetrieval] = useState<EvaluationRun | null>(null);
  const [latestAssistant, setLatestAssistant] = useState<AssistantEvaluationResult | null>(null);
  const [retrievalRuns, setRetrievalRuns] = useState<EvaluationRunListItem[]>([]);
  const [assistantRuns, setAssistantRuns] = useState<EvaluationRunListItem[]>([]);
  const [improvementSummary, setImprovementSummary] = useState<ImprovementSummary | null>(null);
  const [annotationSummary, setAnnotationSummary] = useState<AnnotationSummary | null>(null);
  const [assistantTrends, setAssistantTrends] = useState<AssistantTrendResponse | null>(null);
  const [regressionTrends, setRegressionTrends] = useState<RegressionTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [retrieval, assistant, recentRetrieval, recentAssistant, improvements, annotations, trends, regressions] =
        await Promise.all([
          evaluationApi.latestRetrieval(),
          evaluationApi.latestAssistants(),
          evaluationApi.listRuns({ eval_type: "retrieval", limit: 8 }),
          evaluationApi.listRuns({ eval_type: "assistant", limit: 8 }),
          evaluationApi.improvementSummary(),
          evaluationApi.annotationSummary(),
          evaluationApi.assistantTrends({ limit: 8 }),
          evaluationApi.regressionTrends(8),
        ]);
      setLatestRetrieval(retrieval);
      setLatestAssistant(assistant);
      setRetrievalRuns(recentRetrieval);
      setAssistantRuns(recentAssistant);
      setImprovementSummary(improvements);
      setAnnotationSummary(annotations);
      setAssistantTrends(trends);
      setRegressionTrends(regressions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation dashboard");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const recentRuns = useMemo(
    () =>
      [...retrievalRuns, ...assistantRuns]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 12),
    [retrievalRuns, assistantRuns],
  );

  const retrievalMetrics = latestRetrieval?.metrics;
  const assistantMetrics = latestAssistant?.overall_metrics;
  const qualityGate = latestAssistant?.quality_gate_passed;
  const regressionWarnings = assistantTrends?.regression_warnings ?? [];

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Evaluation Dashboard</h2>
          <p className="muted">Read-only overview of recent retrieval and assistant evaluation results.</p>
        </div>
        <div className="actions">
          <button type="button" onClick={load} disabled={loading}>Refresh</button>
          <button type="button" onClick={onOpenEvaluation}>Open Evaluation Workbench</button>
        </div>
      </div>

      {loading && <p className="muted">Loading evaluation dashboard...</p>}
      {error && <p className="error">{error}</p>}

      <div className="metric-grid dashboard-cards">
        <div className="dashboard-card">
          <span className="muted">Latest retrieval</span>
          <strong>{percent(numberMetric(retrievalMetrics, "hit_at_3"))}</strong>
          <small>Hit@3</small>
          <small>{formatDate(latestRetrieval?.created_at)}</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Retrieval MRR</span>
          <strong>{decimal(numberMetric(retrievalMetrics, "mrr"))}</strong>
          <small>No-answer {percent(numberMetric(retrievalMetrics, "no_answer_accuracy"))}</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Assistant quality</span>
          <strong className={`status-pill ${statusClass(qualityGate)}`}>{statusText(qualityGate)}</strong>
          <small>Citation {percent(assistantMetrics?.citation_rate)}</small>
          <small>{formatDate(latestAssistant?.created_at)}</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Open improvements</span>
          <strong>{improvementSummary?.total_open ?? 0}</strong>
          <small>Prompt {improvementSummary?.by_fix_type.prompt ?? 0}</small>
          <small>Metadata {improvementSummary?.by_fix_type.metadata_filter ?? 0}</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Open annotations</span>
          <strong>{openAnnotationCount(annotationSummary)}</strong>
          <small>Total annotations {annotationSummary?.total_annotations ?? 0}</small>
        </div>
        <div className="dashboard-card">
          <span className="muted">Regression pass rate</span>
          <strong>{percent(regressionTrends?.pass_rate)}</strong>
          <small>{regressionTrends?.passed_count ?? 0} passed / {regressionTrends?.failed_count ?? 0} failed</small>
        </div>
      </div>

      <div className="subtle-block">
        <h3>Recent Evaluation Runs</h3>
        {recentRuns.length === 0 ? (
          <p className="muted">No evaluation runs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Type</th>
                <th>Mode</th>
                <th>Total</th>
                <th>Hit@1</th>
                <th>Hit@3</th>
                <th>MRR</th>
                <th>Gate</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.map((run) => (
                <tr key={run.id}>
                  <td>
                    <strong>{run.display_label}</strong>
                    {run.change_summary && <div className="muted">{run.change_summary}</div>}
                  </td>
                  <td>{run.eval_type}</td>
                  <td>{runMode(run)}</td>
                  <td>{run.total_cases}</td>
                  <td>{percent(run.metrics_summary.hit_at_1 as number | null)}</td>
                  <td>{percent(run.metrics_summary.hit_at_3 as number | null)}</td>
                  <td>{decimal(run.metrics_summary.mrr as number | null)}</td>
                  <td>
                    <span className={`status-pill ${statusClass(run.metrics_summary.quality_gate_passed as boolean | null)}`}>
                      {statusText(run.metrics_summary.quality_gate_passed as boolean | null)}
                    </span>
                  </td>
                  <td>{formatDate(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="subtle-block">
        <h3>Trend Warnings</h3>
        {regressionWarnings.length === 0 ? (
          <p className="muted">No assistant trend warnings in the latest trend window.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Previous</th>
                <th>Current</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {regressionWarnings.map((warning) => (
                <tr key={`${warning.metric}-${String(warning.current)}`}>
                  <td>{warning.metric}</td>
                  <td>{String(warning.previous)}</td>
                  <td>{String(warning.current)}</td>
                  <td>{typeof warning.delta === "number" ? warning.delta.toFixed(3) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="subtle-block">
        <h3>Recent Regressions</h3>
        {!regressionTrends || regressionTrends.recent_items.length === 0 ? (
          <p className="muted">No regression records yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Regression</th>
                <th>Assistant</th>
                <th>Fix type</th>
                <th>Before</th>
                <th>After</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {regressionTrends.recent_items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id.slice(0, 8)}</td>
                  <td>{item.assistant_type}</td>
                  <td>{item.fix_type}</td>
                  <td>{item.before_run_display?.display_label ?? item.before_evaluation_run_id.slice(0, 8)}</td>
                  <td>{item.after_run_display?.display_label ?? item.after_evaluation_run_id.slice(0, 8)}</td>
                  <td>
                    <span className={`status-pill ${statusClass(item.regression_passed)}`}>
                      {statusText(item.regression_passed)}
                    </span>
                  </td>
                  <td>{formatDate(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

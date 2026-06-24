import { FormEvent, useMemo, useState } from "react";
import { api, type AssistantChatResponse } from "../api/client";

const QUICK_QUERIES = [
  { label: "Fault code handling", symptom: "Fault alarm is active. Need meaning, checks, and handling steps." },
  { label: "Safe shutdown", symptom: "Need shutdown and electrical safety checks before repair." },
  { label: "Recurring fault", symptom: "Fault appears repeatedly after reset. Need likely causes and inspection sequence." },
  { label: "Sensor check", symptom: "Suspect sensor or wiring issue. Need inspection steps and safety notes." },
];

function citationLabel(item: AssistantChatResponse["citations"][number]) {
  if (item.sheet_name) {
    const rows = item.row_start && item.row_end ? ` / Rows ${item.row_start}-${item.row_end}` : "";
    return `${item.filename} / Sheet: ${item.sheet_name}${rows}`;
  }
  const page = item.page_number ? ` / p.${item.page_number}` : "";
  const section = item.section_title ? ` / ${item.section_title}` : "";
  return `${item.filename}${page}${section}`;
}

function scoreText(value?: number | null) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function resultTitle(result: NonNullable<AssistantChatResponse["retrieved_results"]>[number], index: number) {
  return result.document_name || result.filename || result.citation?.filename?.toString() || `Evidence #${index + 1}`;
}

export function MaintenanceKnowledgePage() {
  const [equipmentModel, setEquipmentModel] = useState("");
  const [faultCode, setFaultCode] = useState("");
  const [symptom, setSymptom] = useState("");
  const [notes, setNotes] = useState("");
  const [response, setResponse] = useState<AssistantChatResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const metadataFilter = useMemo(() => {
    const filter: Record<string, string> = { category: "maintenance" };
    if (equipmentModel.trim()) filter.equipment_model = equipmentModel.trim();
    if (faultCode.trim()) filter.fault_code = faultCode.trim();
    return filter;
  }, [equipmentModel, faultCode]);

  const generatedQuery = useMemo(() => {
    const parts = [
      equipmentModel.trim() ? `Equipment model: ${equipmentModel.trim()}` : "",
      faultCode.trim() ? `Fault code: ${faultCode.trim()}` : "",
      symptom.trim() ? `Symptom: ${symptom.trim()}` : "",
      notes.trim() ? `Notes: ${notes.trim()}` : "",
    ].filter(Boolean);
    return parts.join("\n");
  }, [equipmentModel, faultCode, notes, symptom]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setError("");
    setResponse(null);
    try {
      const data = await api.assistantChat("maintenance", {
        query: generatedQuery,
        metadata_filter: metadataFilter,
        auto_metadata_filter: true,
        use_rerank: true,
        rerank_top_n: 20,
        top_k: 5,
      });
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Maintenance lookup failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="panel wide maintenance-workspace">
      <div className="section-heading">
        <h2>Maintenance Knowledge</h2>
      </div>

      <form className="maintenance-grid" onSubmit={submit}>
        <div className="maintenance-query-panel">
          <label>
            Equipment model
            <input value={equipmentModel} onChange={(event) => setEquipmentModel(event.target.value)} placeholder="A200" />
          </label>
          <label>
            Fault code
            <input value={faultCode} onChange={(event) => setFaultCode(event.target.value)} placeholder="E12" />
          </label>
          <label>
            Symptom
            <textarea
              value={symptom}
              onChange={(event) => setSymptom(event.target.value)}
              placeholder="Describe the alarm, abnormal behavior, or inspection context"
            />
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Optional safety context, repair history, or site observation"
            />
          </label>
          <button type="submit" disabled={running || !generatedQuery.trim()}>
            {running ? "Checking..." : "Ask maintenance assistant"}
          </button>
        </div>

        <aside className="maintenance-side-panel">
          <h3>Quick queries</h3>
          <div className="quick-query-list">
            {QUICK_QUERIES.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => setSymptom(item.symptom)}
                className={symptom === item.symptom ? "active" : ""}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="effective-filter-preview">
            <span>Metadata filter</span>
            <pre>{JSON.stringify(metadataFilter, null, 2)}</pre>
          </div>
        </aside>
      </form>

      {error && <p className="error">{error}</p>}

      {response && (
        <div className="answer maintenance-answer">
          <div className="section-heading">
            <h3>Answer</h3>
            <span className={response.no_answer_detected ? "status-pill status-warning" : "status-pill status-indexed"}>
              {response.no_answer_detected ? "No reliable basis" : "Answered with sources"}
            </span>
          </div>
          <p>{response.answer}</p>
          <dl className="detail-list">
            <dt>Used filter</dt>
            <dd>{JSON.stringify(response.used_metadata_filter)}</dd>
            <dt>Rerank</dt>
            <dd>{response.rerank_applied ? "Applied" : response.rerank_error || "Not applied"}</dd>
          </dl>

          {response.citations.length > 0 && (
            <div className="subtle-block">
              <h3>Citations</h3>
              {response.citations.map((item, index) => (
                <blockquote key={`${item.filename}-${item.chunk_id}-${index}`}>
                  <strong>{citationLabel(item)}</strong>
                  <p>{item.quote}</p>
                </blockquote>
              ))}
            </div>
          )}

          {response.retrieved_results && response.retrieved_results.length > 0 && (
            <div className="subtle-block">
              <h3>Top evidence</h3>
              <div className="search-result-list">
                {response.retrieved_results.slice(0, 5).map((result, index) => (
                  <article key={`${result.chunk_id || index}`} className="search-result-card">
                    <div className="search-result-header">
                      <span className="status-pill status-info">#{result.rank || index + 1}</span>
                      <div className="score-strip">
                        <span>final {scoreText(result.final_score ?? result.score)}</span>
                        <span>vector {scoreText(result.vector_score)}</span>
                        <span>rerank {scoreText(result.rerank_score)}</span>
                      </div>
                    </div>
                    <h4>{resultTitle(result, index)}</h4>
                    <pre className="search-result-snippet">{result.chunk_excerpt || result.chunk_text || ""}</pre>
                  </article>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

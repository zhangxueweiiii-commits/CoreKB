import { FormEvent, useEffect, useMemo, useState } from "react";
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

type EvidenceResult = NonNullable<AssistantChatResponse["retrieved_results"]>[number];
type Citation = AssistantChatResponse["citations"][number];

const METADATA_LABELS: Record<string, string> = {
  category: "Category",
  doc_type: "Doc type",
  equipment_model: "Equipment",
  fault_code: "Fault code",
  process_name: "Process",
  sop_code: "SOP",
  version: "Version",
  sheet_name: "Sheet",
  row_start: "Row start",
  row_end: "Row end",
};

function scoreText(value?: number | null) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function resultKey(result: EvidenceResult, index: number) {
  return result.chunk_id || `${result.document_id || "document"}-${result.rank || index + 1}`;
}

function resultTitle(result: EvidenceResult, index: number) {
  return result.document_name || result.filename || result.citation?.filename?.toString() || `Evidence #${index + 1}`;
}

function resultExcerpt(result: EvidenceResult) {
  return result.chunk_excerpt || result.chunk_text || "";
}

function resultMetadata(result: EvidenceResult) {
  return result.chunk_metadata || result.metadata || {};
}

function evidenceCitation(result: EvidenceResult, citations: Citation[]) {
  if (!result.chunk_id) return null;
  return citations.find((item) => item.chunk_id === result.chunk_id) ?? null;
}

function evidenceCitationLabel(result: EvidenceResult, citation: Citation | null, index: number) {
  if (citation) return citationLabel(citation);
  const rawCitation = result.citation || {};
  const filename = rawCitation.filename?.toString() || resultTitle(result, index);
  const sheet = rawCitation.sheet_name?.toString();
  const page = rawCitation.page_number ? ` / p.${rawCitation.page_number}` : "";
  const rows = rawCitation.row_start && rawCitation.row_end ? ` / Rows ${rawCitation.row_start}-${rawCitation.row_end}` : "";
  return sheet ? `${filename} / Sheet: ${sheet}${rows}` : `${filename}${page}`;
}

function visibleMetadataEntries(metadata: Record<string, unknown>) {
  return Object.entries(metadata)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== "")
    .slice(0, 12);
}

function buildMaintenanceRecordDraft(params: {
  equipmentModel: string;
  faultCode: string;
  symptom: string;
  notes: string;
  response: AssistantChatResponse;
  evidenceResults: EvidenceResult[];
}) {
  const { equipmentModel, faultCode, symptom, notes, response, evidenceResults } = params;
  const citations = response.citations
    .slice(0, 5)
    .map((item, index) => `${index + 1}. ${citationLabel(item)}\n   Quote: ${item.quote}`)
    .join("\n");
  const evidence = evidenceResults
    .slice(0, 5)
    .map((item, index) => {
      const metadata = resultMetadata(item);
      const metadataText = visibleMetadataEntries(metadata)
        .map(([key, value]) => `${key}=${String(value)}`)
        .join(", ");
      return [
        `${index + 1}. ${resultTitle(item, index)}`,
        `   Rank: ${item.rank || index + 1}; final=${scoreText(item.final_score ?? item.score)}; vector=${scoreText(item.vector_score)}; rerank=${scoreText(item.rerank_score)}`,
        metadataText ? `   Metadata: ${metadataText}` : "",
        `   Excerpt: ${resultExcerpt(item).slice(0, 500)}`,
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n");

  return [
    "Maintenance Record Draft",
    "",
    "Review status: human review required before use",
    "",
    "Equipment",
    `- Model: ${equipmentModel.trim() || "Not provided"}`,
    `- Fault code: ${faultCode.trim() || "Not provided"}`,
    "",
    "Reported symptom",
    symptom.trim() || "Not provided",
    "",
    "Site notes",
    notes.trim() || "Not provided",
    "",
    "Assistant guidance",
    response.answer,
    "",
    "No-answer state",
    response.no_answer_detected ? "No reliable basis found in the current knowledge base." : "Answered with retrieved sources.",
    "",
    "Used metadata filter",
    JSON.stringify(response.used_metadata_filter, null, 2),
    "",
    "Rerank",
    response.rerank_applied ? "Applied" : response.rerank_error || "Not applied",
    "",
    "Citations",
    citations || "No citations returned.",
    "",
    "Retrieved evidence",
    evidence || "No retrieved evidence returned.",
    "",
    "Operator confirmation checklist",
    "- Confirm source citations match the actual equipment and fault.",
    "- Confirm safety conditions before shutdown, lockout, wiring, or disassembly.",
    "- Confirm the final action with site procedure and responsible engineer.",
  ].join("\n");
}

function buildMaintenanceExperienceCandidate(params: {
  equipmentModel: string;
  faultCode: string;
  symptom: string;
  response: AssistantChatResponse;
  evidenceResults: EvidenceResult[];
}) {
  const { equipmentModel, faultCode, symptom, response, evidenceResults } = params;
  const titleParts = [
    equipmentModel.trim() || "Unknown equipment",
    faultCode.trim() ? `fault ${faultCode.trim()}` : "maintenance case",
  ];
  const evidence = evidenceResults
    .slice(0, 3)
    .map((item, index) => {
      const citation = response.citations.find((source) => source.chunk_id === item.chunk_id) ?? null;
      return [
        `${index + 1}. ${resultTitle(item, index)}`,
        `   Source: ${evidenceCitationLabel(item, citation, index)}`,
        `   Score: final=${scoreText(item.final_score ?? item.score)}, rerank=${scoreText(item.rerank_score)}`,
        `   Excerpt: ${resultExcerpt(item).slice(0, 360)}`,
      ].join("\n");
    })
    .join("\n");

  return [
    "Maintenance Experience Candidate",
    "",
    "Candidate status: unreviewed, not approved knowledge",
    "",
    `Title: ${titleParts.join(" - ")}`,
    `Category: maintenance`,
    `Equipment model: ${equipmentModel.trim() || "Not provided"}`,
    `Fault code: ${faultCode.trim() || "Not provided"}`,
    "",
    "Observed trigger or symptom",
    symptom.trim() || "Not provided",
    "",
    "Candidate experience summary",
    response.answer,
    "",
    "Applicability guardrails",
    "- Use only for the equipment model, fault code, and conditions confirmed by cited sources.",
    "- Do not generalize to similar equipment without additional evidence.",
    "- Require maintenance owner review before adding to a formal knowledge base.",
    "",
    "Source citations",
    response.citations.map((item, index) => `${index + 1}. ${citationLabel(item)}`).join("\n") || "No citations returned.",
    "",
    "Supporting evidence",
    evidence || "No retrieved evidence returned.",
    "",
    "Suggested curation checks",
    "- Confirm the answer is grounded in the cited documents.",
    "- Confirm safety notes are complete for shutdown, lockout, wiring, or disassembly.",
    "- Decide whether this is reusable experience or a one-off incident.",
  ].join("\n");
}

export function MaintenanceKnowledgePage() {
  const [equipmentModel, setEquipmentModel] = useState("");
  const [faultCode, setFaultCode] = useState("");
  const [symptom, setSymptom] = useState("");
  const [notes, setNotes] = useState("");
  const [response, setResponse] = useState<AssistantChatResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [citedOnly, setCitedOnly] = useState(false);
  const [selectedEvidenceKey, setSelectedEvidenceKey] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState("");
  const [candidateCopyStatus, setCandidateCopyStatus] = useState("");

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

  const evidenceResults = useMemo(() => response?.retrieved_results ?? [], [response]);
  const citedChunkIds = useMemo(() => new Set(response?.citations.map((item) => item.chunk_id) ?? []), [response]);
  const visibleEvidence = useMemo(
    () => evidenceResults.filter((result) => !citedOnly || (result.chunk_id && citedChunkIds.has(result.chunk_id))),
    [citedChunkIds, citedOnly, evidenceResults],
  );
  const selectedEvidence = visibleEvidence.find((result, index) => resultKey(result, index) === selectedEvidenceKey) ?? visibleEvidence[0];
  const maintenanceRecordDraft = useMemo(
    () =>
      response
        ? buildMaintenanceRecordDraft({
            equipmentModel,
            faultCode,
            symptom,
            notes,
            response,
            evidenceResults,
          })
        : "",
    [equipmentModel, evidenceResults, faultCode, notes, response, symptom],
  );
  const maintenanceExperienceCandidate = useMemo(
    () =>
      response
        ? buildMaintenanceExperienceCandidate({
            equipmentModel,
            faultCode,
            symptom,
            response,
            evidenceResults,
          })
        : "",
    [equipmentModel, evidenceResults, faultCode, response, symptom],
  );

  useEffect(() => {
    setCitedOnly(false);
    setSelectedEvidenceKey(evidenceResults[0] ? resultKey(evidenceResults[0], 0) : null);
    setCopyStatus("");
    setCandidateCopyStatus("");
  }, [evidenceResults]);

  async function copyRecordDraft() {
    if (!maintenanceRecordDraft) return;
    try {
      await navigator.clipboard.writeText(maintenanceRecordDraft);
      setCopyStatus("Draft copied");
    } catch {
      setCopyStatus("Copy failed");
    }
  }

  async function copyExperienceCandidate() {
    if (!maintenanceExperienceCandidate) return;
    try {
      await navigator.clipboard.writeText(maintenanceExperienceCandidate);
      setCandidateCopyStatus("Candidate copied");
    } catch {
      setCandidateCopyStatus("Copy failed");
    }
  }

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

          {evidenceResults.length > 0 && (
            <div className="subtle-block maintenance-evidence-panel">
              <div className="section-heading">
                <div>
                  <h3>Evidence panel</h3>
                  <p className="muted">
                    Inspect retrieved chunks, citations, scores, and metadata used by this maintenance answer.
                  </p>
                </div>
                <label className="inline-toggle">
                  <input type="checkbox" checked={citedOnly} onChange={(event) => setCitedOnly(event.target.checked)} />
                  Cited only
                </label>
              </div>

              {visibleEvidence.length === 0 ? (
                <p className="empty-state">No retrieved evidence is cited in this answer.</p>
              ) : (
                <div className="evidence-layout">
                  <div className="evidence-list" aria-label="Retrieved evidence">
                    {visibleEvidence.map((result, index) => {
                      const key = resultKey(result, index);
                      const citation = evidenceCitation(result, response.citations);
                      const isSelected = selectedEvidence === result;
                      return (
                        <button
                          key={key}
                          type="button"
                          className={`evidence-list-item${isSelected ? " active" : ""}`}
                          onClick={() => setSelectedEvidenceKey(key)}
                        >
                          <span className="status-pill status-info">#{result.rank || index + 1}</span>
                          <span className="evidence-list-main">
                            <strong>{resultTitle(result, index)}</strong>
                            <small>{evidenceCitationLabel(result, citation, index)}</small>
                          </span>
                          <span className={citation ? "status-pill status-indexed" : "status-pill status-warning"}>
                            {citation ? "Cited" : "Not cited"}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {selectedEvidence && (
                    <article className="evidence-detail">
                      {(() => {
                        const selectedIndex = visibleEvidence.indexOf(selectedEvidence);
                        const citation = evidenceCitation(selectedEvidence, response.citations);
                        const metadata = resultMetadata(selectedEvidence);
                        const metadataEntries = visibleMetadataEntries(metadata);
                        return (
                          <>
                            <div className="search-result-header">
                              <span className="status-pill status-info">Rank #{selectedEvidence.rank || selectedIndex + 1}</span>
                              <span className={citation ? "status-pill status-indexed" : "status-pill status-warning"}>
                                {citation ? "Cited in answer" : "Retrieved, not cited"}
                              </span>
                            </div>
                            <h4>{resultTitle(selectedEvidence, selectedIndex)}</h4>
                            <p className="muted">{evidenceCitationLabel(selectedEvidence, citation, selectedIndex)}</p>

                            <div className="score-grid">
                              <span>
                                <strong>{scoreText(selectedEvidence.final_score ?? selectedEvidence.score)}</strong>
                                Final
                              </span>
                              <span>
                                <strong>{scoreText(selectedEvidence.vector_score)}</strong>
                                Vector
                              </span>
                              <span>
                                <strong>{scoreText(selectedEvidence.rerank_score)}</strong>
                                Rerank
                              </span>
                            </div>

                            {metadataEntries.length > 0 && (
                              <div className="metadata-chip-list">
                                {metadataEntries.map(([key, value]) => (
                                  <span key={key} className="metadata-chip">
                                    {METADATA_LABELS[key] || key}: {String(value)}
                                  </span>
                                ))}
                              </div>
                            )}

                            {citation?.quote && (
                              <blockquote className="evidence-quote">
                                <strong>Answer citation</strong>
                                <p>{citation.quote}</p>
                              </blockquote>
                            )}

                            <pre className="search-result-snippet evidence-snippet">{resultExcerpt(selectedEvidence)}</pre>
                          </>
                        );
                      })()}
                    </article>
                  )}
                </div>
              )}
            </div>
          )}

          {maintenanceRecordDraft && (
            <div className="subtle-block maintenance-record-draft">
              <div className="section-heading">
                <div>
                  <h3>Maintenance record draft</h3>
                  <p className="muted">Local draft only. Review citations and site conditions before using it in any repair record.</p>
                </div>
                <button type="button" onClick={copyRecordDraft}>
                  Copy draft
                </button>
              </div>
              {copyStatus && <p className={copyStatus === "Draft copied" ? "success" : "error"}>{copyStatus}</p>}
              <pre className="record-draft-preview">{maintenanceRecordDraft}</pre>
            </div>
          )}

          {maintenanceExperienceCandidate && (
            <div className="subtle-block maintenance-experience-candidate">
              <div className="section-heading">
                <div>
                  <h3>Maintenance experience candidate</h3>
                  <p className="muted">
                    Unreviewed candidate for future knowledge curation. It is not saved or approved by CoreKB.
                  </p>
                </div>
                <button type="button" onClick={copyExperienceCandidate}>
                  Copy candidate
                </button>
              </div>
              {candidateCopyStatus && (
                <p className={candidateCopyStatus === "Candidate copied" ? "success" : "error"}>{candidateCopyStatus}</p>
              )}
              <div className="experience-candidate-summary">
                <span className="status-pill status-warning">Unreviewed</span>
                <span>Requires maintenance owner review before becoming formal knowledge.</span>
              </div>
              <pre className="record-draft-preview">{maintenanceExperienceCandidate}</pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

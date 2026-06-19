import { useEffect, useMemo, useRef, useState } from "react";
import { api, type DocumentItem, type DocumentMetadataSuggestion, type KnowledgeBase } from "../api/client";
import { indexJobsApi, type IndexJobSummary } from "../api/indexJobs";
import { KbPermissionManager } from "../components/KbPermissionManager";
import type { MetadataReviewFocus } from "../utils/metadataPrecheckNavigation";

interface Props {
  knowledgeBase: KnowledgeBase | null;
  metadataReviewFocus?: MetadataReviewFocus | null;
  onMetadataReviewHandled?: () => void;
  onBackToMetadataPrecheck?: (search?: string | null) => void;
  onOpenJob?: (jobId: string) => void;
}

const statusLabels: Record<string, string> = {
  uploaded: "Uploaded",
  parsing: "Parsing",
  chunking: "Chunking",
  embedding: "Embedding",
  indexed: "Indexed",
  failed: "Failed",
};

const processingStatuses = new Set(["uploaded", "parsing", "chunking", "embedding"]);

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function KnowledgeBaseDetail({
  knowledgeBase,
  metadataReviewFocus,
  onMetadataReviewHandled,
  onBackToMetadataPrecheck,
  onOpenJob,
}: Props) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null);
  const [metadataSuggestions, setMetadataSuggestions] = useState<DocumentMetadataSuggestion[]>([]);
  const [pendingSuggestionCounts, setPendingSuggestionCounts] = useState<Record<string, number>>({});
  const [metadataFilter, setMetadataFilter] = useState("all");
  const [jobs, setJobs] = useState<IndexJobSummary[]>([]);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const metadataSectionRef = useRef<HTMLDivElement | null>(null);
  const suggestionRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  const canEdit = knowledgeBase?.access_role === "owner" || knowledgeBase?.access_role === "editor";
  const focusField = metadataReviewFocus?.focusField || "";
  const isPrecheckFocus =
    Boolean(metadataReviewFocus) &&
    metadataReviewFocus?.documentId === selectedDocument?.id &&
    metadataReviewFocus?.from === "metadata_precheck";
  const hasFocusedPendingSuggestion =
    Boolean(focusField) &&
    metadataSuggestions.some((suggestion) => suggestion.field === focusField && suggestion.status === "pending");
  const isPolling = useMemo(
    () => documents.some((document) => processingStatuses.has(document.status)),
    [documents],
  );
  const filteredDocuments = useMemo(
    () =>
      documents.filter((document) => {
        const completeness = document.metadata_completeness?.completeness_status || "missing";
        const hasPending = (pendingSuggestionCounts[document.id] || 0) > 0;
        if (metadataFilter === "pending") return hasPending;
        if (metadataFilter === "complete") return completeness === "complete";
        if (metadataFilter === "missing") return completeness !== "complete";
        return true;
      }),
    [documents, metadataFilter, pendingSuggestionCounts],
  );

  function formatMetadataValue(value: unknown) {
    if (value === undefined || value === null || value === "") return "-";
    if (typeof value === "string") return value;
    return JSON.stringify(value);
  }

  async function loadPendingSuggestionCounts() {
    if (!knowledgeBase) return;
    try {
      const response = await api.listMetadataSuggestions({ knowledge_base_id: knowledgeBase.id, status: "pending" });
      const counts: Record<string, number> = {};
      response.items.forEach((suggestion) => {
        counts[suggestion.document_id] = (counts[suggestion.document_id] || 0) + 1;
      });
      setPendingSuggestionCounts(counts);
    } catch {
      setPendingSuggestionCounts({});
    }
  }

  async function loadDocuments(showLoading = false) {
    if (!knowledgeBase) return;
    if (showLoading) setLoading(true);
    try {
      const data = await api.documents(knowledgeBase.id);
      setDocuments(data);
      const focusDocument = metadataReviewFocus?.documentId
        ? data.find((document) => document.id === metadataReviewFocus.documentId)
        : null;
      if (focusDocument) {
        setSelectedDocument(focusDocument);
        loadMetadataSuggestions(focusDocument.id).catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to load metadata suggestions"),
        );
      } else {
        setSelectedDocument((current) =>
          current ? data.find((document) => document.id === current.id) ?? null : null,
        );
      }
      await loadPendingSuggestionCounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      if (showLoading) setLoading(false);
    }
  }

  async function loadJobs() {
    if (!knowledgeBase) return;
    setJobs(await indexJobsApi.list({ knowledge_base_id: knowledgeBase.id, limit: 8 }));
  }

  async function loadMetadataSuggestions(documentId: string) {
    const response = await api.metadataSuggestions(documentId);
    setMetadataSuggestions(response.items);
  }

  useEffect(() => {
    setDocuments([]);
    setSelectedDocument(null);
    setMetadataSuggestions([]);
    setPendingSuggestionCounts({});
    setError("");
    loadDocuments(true);
    loadJobs().catch(() => undefined);
  }, [knowledgeBase?.id, metadataReviewFocus?.documentId]);

  useEffect(() => {
    if (!metadataReviewFocus?.documentId || !documents.length) return;
    const document = documents.find((item) => item.id === metadataReviewFocus.documentId);
    if (!document || selectedDocument?.id === document.id) return;
    openDocument(document);
  }, [metadataReviewFocus?.documentId, documents, selectedDocument?.id]);

  useEffect(() => {
    if (!isPrecheckFocus || metadataReviewFocus?.tab !== "metadata") return;
    const scrollTarget = focusField ? suggestionRefs.current[focusField] : null;
    const target = scrollTarget ?? metadataSectionRef.current;
    window.setTimeout(() => target?.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
  }, [isPrecheckFocus, metadataReviewFocus?.tab, focusField, metadataSuggestions.length]);

  useEffect(() => {
    if (!knowledgeBase || !isPolling) return;
    const handle = window.setInterval(() => {
      loadDocuments(false);
      loadJobs().catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(handle);
  }, [knowledgeBase?.id, isPolling]);

  async function upload(file?: File) {
    if (!knowledgeBase || !file) return;
    setError("");
    try {
      const document = await api.uploadDocument(knowledgeBase.id, file);
      setDocuments([document, ...documents]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function remove(documentId: string) {
    setError("");
    try {
      await api.deleteDocument(documentId);
      setDocuments(documents.filter((document) => document.id !== documentId));
      if (selectedDocument?.id === documentId) setSelectedDocument(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function retry(documentId: string) {
    setError("");
    try {
      const job = await api.retryDocument(documentId);
      setLastJobId(job.id);
      await Promise.all([loadDocuments(false), loadJobs()]);
      onOpenJob?.(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry indexing failed");
    }
  }

  async function generateSuggestions(documentId: string) {
    setError("");
    try {
      const response = await api.generateMetadataSuggestions(documentId);
      setMetadataSuggestions(response.items);
      await loadPendingSuggestionCounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate metadata suggestions");
    }
  }

  async function acceptSuggestion(suggestion: DocumentMetadataSuggestion, customValue = false) {
    if (!selectedDocument) return;
    const value = customValue
      ? window.prompt("Custom metadata value. This will not be added to the dictionary:", suggestion.raw_value)
      : window.prompt("Confirm standard metadata value:", suggestion.normalized_value || suggestion.suggested_value);
    if (value === null) return;
    setError("");
    try {
      await api.acceptMetadataSuggestion(selectedDocument.id, suggestion.id, value, customValue);
      await Promise.all([
        loadMetadataSuggestions(selectedDocument.id),
        loadDocuments(false),
        loadJobs(),
        loadPendingSuggestionCounts(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept metadata suggestion");
    }
  }

  async function rejectSuggestion(suggestion: DocumentMetadataSuggestion) {
    if (!selectedDocument) return;
    setError("");
    try {
      await api.rejectMetadataSuggestion(selectedDocument.id, suggestion.id);
      await Promise.all([loadMetadataSuggestions(selectedDocument.id), loadPendingSuggestionCounts()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject metadata suggestion");
    }
  }

  function openDocument(document: DocumentItem) {
    setSelectedDocument(document);
    loadMetadataSuggestions(document.id).catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load metadata suggestions"),
    );
  }

  async function reindexAll() {
    if (!knowledgeBase) return;
    const confirmed = window.confirm("Rebuild the index for this knowledge base?");
    if (!confirmed) return;
    setError("");
    try {
      const job = await indexJobsApi.reindexKb(knowledgeBase.id, { force: true });
      setLastJobId(job.id);
      await loadJobs();
      onOpenJob?.(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reindex failed");
    }
  }

  if (!knowledgeBase) {
    return (
      <div className="panel wide">
        <h2>Select a knowledge base</h2>
      </div>
    );
  }

  return (
    <div className="panel wide">
      <h2>{knowledgeBase.name}</h2>
      <p className="muted">{knowledgeBase.description || "No description"}</p>
      {canEdit && (
        <div className="toolbar">
          <label className="upload">
            Upload PDF / DOCX / MD / TXT / XLSX / XLS / CSV
            <input
              type="file"
              accept=".pdf,.docx,.md,.markdown,.txt,.xlsx,.xls,.csv"
              onChange={(event) => upload(event.target.files?.[0])}
            />
          </label>
          <button type="button" onClick={reindexAll} disabled={documents.length === 0}>
            Rebuild index
          </button>
        </div>
      )}
      {lastJobId && (
        <p className="muted">
          Index job submitted: {lastJobId}. You can view progress on the index jobs page.
        </p>
      )}
      {loading && <p className="muted">Loading documents...</p>}
      {isPolling && <p className="muted">Documents are processing. Auto-refresh is active.</p>}
      {error && <p className="error">{error}</p>}
      <div className="toolbar">
        <label>
          Metadata status
          <select value={metadataFilter} onChange={(event) => setMetadataFilter(event.target.value)}>
            <option value="all">All documents</option>
            <option value="pending">Has pending metadata suggestions</option>
            <option value="complete">Metadata complete</option>
            <option value="missing">Missing key fields / pending review</option>
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Type</th>
            <th>Size</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Metadata</th>
            <th>Error</th>
            <th>Indexed at</th>
            <th>Uploaded at</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredDocuments.length === 0 ? (
            <tr><td colSpan={10}>No documents match the current filter.</td></tr>
          ) : (
            filteredDocuments.map((document) => (
              <tr key={document.id}>
                <td>{document.filename}</td>
                <td>{document.file_type}</td>
                <td>{formatBytes(document.file_size)}</td>
                <td>
                  <span className={`status-pill status-${document.status}`}>
                    {statusLabels[document.status] || document.status}
                  </span>
                </td>
                <td>{document.chunk_count}</td>
                <td>
                  <span className={`status-pill status-${document.metadata_completeness?.completeness_status || "missing"}`}>
                    {document.metadata_completeness?.completeness_status || "missing"}
                  </span>
                  {(pendingSuggestionCounts[document.id] || 0) > 0 && (
                    <div className="muted">{pendingSuggestionCounts[document.id]} pending suggestion(s)</div>
                  )}
                </td>
                <td>{document.error_message || ""}</td>
                <td>{document.indexed_at ? new Date(document.indexed_at).toLocaleString() : ""}</td>
                <td>{new Date(document.created_at).toLocaleString()}</td>
                <td className="actions">
                  <button type="button" onClick={() => openDocument(document)}>Details</button>
                  {canEdit && ["failed", "uploaded"].includes(document.status) && (
                    <button type="button" onClick={() => retry(document.id)}>Retry indexing</button>
                  )}
                  {canEdit && <button type="button" onClick={() => remove(document.id)}>Delete</button>}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {selectedDocument && (
        <div className="subtle-block detail-grid" ref={metadataSectionRef} id="metadata-review">
          <div className="section-heading">
            <h3>Document detail</h3>
            {metadataReviewFocus?.from === "metadata_precheck" && (
              <button type="button" onClick={() => onBackToMetadataPrecheck?.(metadataReviewFocus.precheckReturn)}>
                Back to Metadata precheck
              </button>
            )}
          </div>
          {isPrecheckFocus && (
            <div className="notice">
              From Metadata precheck: <strong>{focusField}</strong> current value{" "}
              <strong>{metadataReviewFocus?.currentValue || "-"}</strong>, suggested standard value{" "}
              <strong>{metadataReviewFocus?.suggestedValue || "-"}</strong>
              {metadataReviewFocus?.precheckStatus ? <span> ({metadataReviewFocus.precheckStatus})</span> : null}.
            </div>
          )}
          <dl>
            <dt>ID</dt>
            <dd>{selectedDocument.id}</dd>
            <dt>Filename</dt>
            <dd>{selectedDocument.filename}</dd>
            <dt>Status</dt>
            <dd>{statusLabels[selectedDocument.status] || selectedDocument.status}</dd>
            <dt>Chunks</dt>
            <dd>{selectedDocument.chunk_count}</dd>
            <dt>Error</dt>
            <dd>{selectedDocument.error_message || "None"}</dd>
            <dt>Indexed at</dt>
            <dd>{selectedDocument.indexed_at ? new Date(selectedDocument.indexed_at).toLocaleString() : "Not indexed"}</dd>
            <dt>Updated at</dt>
            <dd>{new Date(selectedDocument.updated_at).toLocaleString()}</dd>
            <dt>Metadata completeness</dt>
            <dd>
              {selectedDocument.metadata_completeness?.completeness_status || "missing"}
              {selectedDocument.metadata_completeness?.missing_recommended_fields?.length ? (
                <span> - missing: {selectedDocument.metadata_completeness.missing_recommended_fields.join(", ")}</span>
              ) : null}
            </dd>
            <dt>Formal metadata</dt>
            <dd><pre>{JSON.stringify(selectedDocument.meta || {}, null, 2)}</pre></dd>
          </dl>
          {isPrecheckFocus && focusField && (
            <div className="subtle-note">
              <strong>Focused field:</strong> {focusField}. Current formal value:{" "}
              <strong>{formatMetadataValue(selectedDocument.meta?.[focusField])}</strong>. Precheck suggestion:{" "}
              <strong>{metadataReviewFocus?.suggestedValue || "-"}</strong>.
            </div>
          )}
          {canEdit && (
            <button type="button" onClick={() => generateSuggestions(selectedDocument.id)}>
              Generate metadata suggestions
            </button>
          )}
          <h4>Metadata suggestions</h4>
          {isPrecheckFocus && focusField && !hasFocusedPendingSuggestion && (
            <p className="notice">
              No pending metadata suggestion for <strong>{focusField}</strong> yet. You can generate metadata suggestions
              and then review them manually.
            </p>
          )}
          {metadataSuggestions.length === 0 ? (
            <p className="muted">No metadata suggestions yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Raw value</th>
                  <th>Normalized value</th>
                  <th>Suggested value</th>
                  <th>Current value</th>
                  <th>Matched by</th>
                  <th>Confidence</th>
                  <th>Source</th>
                  <th>Evidence</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {metadataSuggestions.map((suggestion) => (
                  <tr
                    key={suggestion.id}
                    ref={(node) => {
                      if (suggestion.field === focusField) suggestionRefs.current[suggestion.field] = node;
                    }}
                    className={suggestion.field === focusField && isPrecheckFocus ? "highlight-row" : undefined}
                  >
                    <td>
                      {suggestion.field}
                      {suggestion.field === focusField && isPrecheckFocus ? (
                        <div className="muted">Related to precheck item</div>
                      ) : null}
                    </td>
                    <td>{suggestion.raw_value}</td>
                    <td>{suggestion.normalized_value}</td>
                    <td>{suggestion.suggested_value}</td>
                    <td>{suggestion.current_value || "-"}</td>
                    <td>
                      {suggestion.normalization_source}
                      {suggestion.dictionary_entry_id ? <div className="muted">Dictionary: {suggestion.dictionary_entry_id.slice(0, 8)}</div> : null}
                      {suggestion.review_guardrails?.requires_custom_value_flag ? (
                        <div className="muted">Custom flag required for non-standard overrides</div>
                      ) : null}
                    </td>
                    <td>{suggestion.confidence}</td>
                    <td>{suggestion.source}</td>
                    <td>{suggestion.evidence_excerpt}</td>
                    <td>{suggestion.status}</td>
                    <td>
                      {suggestion.review_guardrails?.warnings?.length ? (
                        <div className="notice">
                          {suggestion.review_guardrails.warnings.map((warning) => (
                            <div key={warning}>{warning}</div>
                          ))}
                        </div>
                      ) : null}
                      {suggestion.review_guardrails?.reindex_required_on_accept ? (
                        <div className="muted">Accepting will submit a single-document reindex.</div>
                      ) : null}
                      {canEdit && suggestion.status === "pending" && (
                        <>
                          <button type="button" onClick={() => acceptSuggestion(suggestion)}>Accept standard</button>
                          <button type="button" onClick={() => acceptSuggestion(suggestion, true)}>Keep custom</button>
                          <button type="button" onClick={() => rejectSuggestion(suggestion)}>Reject</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="subtle-block">
        <h3>Recent index jobs</h3>
        {jobs.length === 0 ? (
          <p className="muted">No index jobs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Type</th>
                <th>Status</th>
                <th>Total</th>
                <th>Success</th>
                <th>Failed</th>
                <th>Pending</th>
                <th>Created at</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="clickable-row" onClick={() => onOpenJob?.(job.id)}>
                  <td>{job.id.slice(0, 8)}</td>
                  <td>{job.job_type}</td>
                  <td>{job.status}</td>
                  <td>{job.total_count}</td>
                  <td>{job.success_count}</td>
                  <td>{job.failed_count}</td>
                  <td>{job.pending_count}</td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <KbPermissionManager kbId={knowledgeBase.id} />
    </div>
  );
}

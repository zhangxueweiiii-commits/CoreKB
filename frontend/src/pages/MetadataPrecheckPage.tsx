import { useEffect, useMemo, useState } from "react";
import { api, type KnowledgeBase } from "../api/client";
import { metadataPrecheckApi, type MetadataPrecheckItem, type MetadataPrecheckResponse } from "../api/metadataPrecheck";
import { buildMetadataReviewUrl, parseMetadataReviewFocus, type MetadataReviewFocus } from "../utils/metadataPrecheckNavigation";

const FIELD_OPTIONS = [
  "equipment_model",
  "fault_code",
  "material_code",
  "product_model",
  "sop_code",
  "process_name",
  "doc_type",
  "category",
];

const STATUS_OPTIONS = [
  "canonical",
  "alias_match",
  "rule_normalizable",
  "dictionary_missing",
  "invalid_or_empty",
  "unsupported",
];

const STATUS_LABELS: Record<string, string> = {
  canonical: "已标准化",
  alias_match: "命中字典别名",
  rule_normalizable: "可按规则规范",
  dictionary_missing: "标准字典缺失",
  invalid_or_empty: "无效或空值",
  unsupported: "暂不支持",
};

const ACTION_LABELS: Record<string, string> = {
  no_action: "无需处理",
  review_and_normalize: "建议人工确认后规范化",
  add_dictionary_entry: "建议补充标准字典",
  review_invalid_value: "建议复核字段值",
  ignore: "无需处理",
};

interface Props {
  onOpenKnowledgeBases?: () => void;
  onOpenDictionary?: () => void;
  onReviewDocument?: (focus: MetadataReviewFocus, url: string) => void;
}

function initialQuery() {
  return new URLSearchParams(window.location.search);
}

export function MetadataPrecheckPage({ onOpenKnowledgeBases, onOpenDictionary, onReviewDocument }: Props) {
  const initialParams = initialQuery();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState(initialParams.get("knowledge_base_id") || "");
  const [fieldName, setFieldName] = useState(initialParams.get("field_name") || "");
  const [status, setStatus] = useState(initialParams.get("status") || "");
  const [keyword, setKeyword] = useState(initialParams.get("keyword") || "");
  const [fixableOnly, setFixableOnly] = useState(true);
  const [page, setPage] = useState(Number(initialParams.get("page") || "1"));
  const [result, setResult] = useState<MetadataPrecheckResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const filteredItems = useMemo(() => {
    const items = result?.items ?? [];
    return items.filter((item) => {
      const keywordText = keyword.trim().toLowerCase();
      const matchesKeyword = !keywordText || [
        item.document_name,
        item.field_name,
        item.current_value,
        item.suggested_value ?? "",
        item.reason,
      ].some((value) => value.toLowerCase().includes(keywordText));
      const fixable = ["alias_match", "rule_normalizable", "dictionary_missing", "invalid_or_empty"].includes(item.status);
      return matchesKeyword && (!fixableOnly || fixable);
    });
  }, [result, keyword, fixableOnly]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await metadataPrecheckApi.run({
        knowledge_base_id: knowledgeBaseId,
        field_name: fieldName,
        status,
        page,
        page_size: 50,
        order_by: "document_id",
        order_direction: "asc",
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run metadata precheck");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.kbs().then(setKnowledgeBases).catch(() => undefined);
    load();
  }, []);

  useEffect(() => {
    load();
  }, [page]);

  async function copySuggested(item: MetadataPrecheckItem) {
    if (!item.suggested_value) return;
    await navigator.clipboard?.writeText(item.suggested_value);
  }

  function currentPrecheckSearch() {
    const params = new URLSearchParams();
    if (knowledgeBaseId) params.set("knowledge_base_id", knowledgeBaseId);
    if (fieldName) params.set("field_name", fieldName);
    if (status) params.set("status", status);
    if (keyword) params.set("keyword", keyword);
    params.set("page", String(page));
    return params.toString();
  }

  function reviewInDocument(item: MetadataPrecheckItem) {
    const url = buildMetadataReviewUrl(item, currentPrecheckSearch());
    const focus = parseMetadataReviewFocus(new URL(url, window.location.origin).pathname, new URL(url, window.location.origin).search);
    if (focus && onReviewDocument) {
      onReviewDocument(focus, url);
      return;
    }
    window.location.assign(url);
  }

  const summary = result?.summary;
  const fixableCount = (summary?.alias_match_count ?? 0) + (summary?.rule_normalizable_count ?? 0);

  return (
    <section className="panel wide">
      <div className="section-heading">
        <h2>Metadata 标准化预检</h2>
        <button type="button" onClick={load} disabled={loading}>Run precheck</button>
      </div>
      <p className="muted">
        只读扫描 documents.metadata；不会修改 metadata、不会创建 suggestions、不会触发重建索引。
      </p>
      {error && <p className="error">{error}</p>}

      <div className="metric-grid">
        <span>Scanned docs: {summary?.documents_scanned ?? 0}</span>
        <span>Fixable: {fixableCount}</span>
        <span>Dictionary missing: {summary?.dictionary_missing_count ?? 0}</span>
        <span>Invalid or empty: {summary?.invalid_or_empty_count ?? 0}</span>
      </div>

      <div className="form-grid">
        <label>
          Knowledge base
          <select value={knowledgeBaseId} onChange={(event) => { setKnowledgeBaseId(event.target.value); setPage(1); }}>
            <option value="">All</option>
            {knowledgeBases.map((kb) => (
              <option key={kb.id} value={kb.id}>{kb.name}</option>
            ))}
          </select>
        </label>
        <label>
          Field
          <select value={fieldName} onChange={(event) => { setFieldName(event.target.value); setPage(1); }}>
            <option value="">All</option>
            {FIELD_OPTIONS.map((field) => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">All</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>{STATUS_LABELS[option]}</option>
            ))}
          </select>
        </label>
        <label>
          Keyword
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} />
        </label>
        <label>
          Fixable only
          <input type="checkbox" checked={fixableOnly} onChange={(event) => setFixableOnly(event.target.checked)} />
        </label>
      </div>

      <table>
        <thead>
          <tr>
            <th>Document</th>
            <th>Field</th>
            <th>Current value</th>
            <th>Suggested value</th>
            <th>Status</th>
            <th>Match source</th>
            <th>Recommended action</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr><td colSpan={8}>No matching precheck items.</td></tr>
          ) : (
            filteredItems.map((item) => (
              <tr key={`${item.document_id}-${item.field_name}`}>
                <td>
                  <strong>{item.document_name}</strong>
                  <div className="muted">{item.document_id}</div>
                </td>
                <td>{item.field_name}</td>
                <td>{item.current_value || "-"}</td>
                <td>{item.suggested_value || "-"}</td>
                <td>{STATUS_LABELS[item.status] || item.status}</td>
                <td>
                  {item.matched_by}
                  {item.dictionary_entry_id ? <div className="muted">{item.dictionary_entry_id.slice(0, 8)}</div> : null}
                </td>
                <td>
                  {ACTION_LABELS[item.recommended_action] || item.recommended_action}
                  <div className="muted">{item.reason}</div>
                </td>
                <td>
                  <button type="button" onClick={() => reviewInDocument(item)}>Review in document</button>
                  <button type="button" onClick={onOpenKnowledgeBases}>View document</button>
                  <button type="button" onClick={onOpenDictionary}>Open metadata dictionary</button>
                  <button type="button" disabled={!item.suggested_value} onClick={() => copySuggested(item)}>Copy suggested value</button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {result && (
        <div className="section-heading">
          <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button>
          <span className="muted">Page {result.page} / {result.pages || 1}, total {result.total}</span>
          <button type="button" disabled={page >= result.pages} onClick={() => setPage((current) => current + 1)}>Next</button>
        </div>
      )}
    </section>
  );
}

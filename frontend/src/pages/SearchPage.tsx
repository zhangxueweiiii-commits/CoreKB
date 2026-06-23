import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, type KnowledgeBase, type SearchResult } from "../api/client";

const METADATA_FILTER_FIELDS = [
  { key: "category", label: "Category", placeholder: "maintenance / quality / sop / material" },
  { key: "doc_type", label: "Document type", placeholder: "parameter_table / manual / sop" },
  { key: "equipment_model", label: "Equipment model", placeholder: "A200" },
  { key: "fault_code", label: "Fault code", placeholder: "E12" },
  { key: "material_code", label: "Material code", placeholder: "MAT-001" },
  { key: "product_model", label: "Product model", placeholder: "PX-200" },
  { key: "process_name", label: "Process name", placeholder: "assembly" },
  { key: "sop_code", label: "SOP code", placeholder: "SOP-001" },
  { key: "version", label: "Version", placeholder: "V1.0" },
] as const;

type MetadataFilterField = (typeof METADATA_FILTER_FIELDS)[number]["key"];
type MetadataFilterValues = Record<MetadataFilterField, string>;

const EMPTY_METADATA_FILTER: MetadataFilterValues = {
  category: "",
  doc_type: "",
  equipment_model: "",
  fault_code: "",
  material_code: "",
  product_model: "",
  process_name: "",
  sop_code: "",
  version: "",
};

function resultTitle(result: SearchResult) {
  if (result.sheet_name) {
    const rows = result.row_start && result.row_end ? ` / Rows ${result.row_start}-${result.row_end}` : "";
    return `${result.filename} / Sheet: ${result.sheet_name}${rows}`;
  }
  const page = result.page_number ? ` / p.${result.page_number}` : "";
  const section = result.section_title ? ` / ${result.section_title}` : "";
  return `${result.filename}${page}${section}`;
}

function scoreText(value?: number | null) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function parseMetadataFilter(text: string): Record<string, string> | undefined {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Metadata filter must be a JSON object.");
  }
  return parsed as Record<string, string>;
}

function compactMetadataFilter(values: MetadataFilterValues): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values)
      .map(([key, value]) => [key, value.trim()])
      .filter(([, value]) => value),
  ) as Record<string, string>;
}

function formatMetadataFilterPreview(filter?: Record<string, string>) {
  return filter && Object.keys(filter).length > 0 ? JSON.stringify(filter, null, 2) : "{}";
}

function tableColumns(result: SearchResult) {
  const columns = result.metadata?.column_names;
  return Array.isArray(columns) ? columns.map(String) : [];
}

export function SearchPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [structuredMetadataFilter, setStructuredMetadataFilter] = useState<MetadataFilterValues>(EMPTY_METADATA_FILTER);
  const [advancedMetadataFilter, setAdvancedMetadataFilter] = useState("");
  const [useRerank, setUseRerank] = useState(false);
  const [rerankTopN, setRerankTopN] = useState(20);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [rerankApplied, setRerankApplied] = useState(false);
  const [rerankError, setRerankError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const tableResultCount = useMemo(
    () => results.filter((result) => result.metadata?.source_type === "table" || result.sheet_name).length,
    [results],
  );
  const effectiveMetadataFilterPreview = useMemo(() => {
    try {
      return formatMetadataFilterPreview({
        ...compactMetadataFilter(structuredMetadataFilter),
        ...(parseMetadataFilter(advancedMetadataFilter) ?? {}),
      });
    } catch {
      return "Invalid advanced metadata JSON";
    }
  }, [advancedMetadataFilter, structuredMetadataFilter]);

  useEffect(() => {
    api.kbs()
      .then((data) => {
        setKbs(data);
        if (data[0]) setSelectedKbIds([data[0].id]);
      })
      .catch((err) => setError(err.message));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResults([]);
    setRerankApplied(false);
    setRerankError(null);
    setLoading(true);
    try {
      const data = await api.search({
        query,
        knowledge_base_ids: selectedKbIds,
        top_k: topK,
        metadata_filter: {
          ...compactMetadataFilter(structuredMetadataFilter),
          ...(parseMetadataFilter(advancedMetadataFilter) ?? {}),
        },
        use_rerank: useRerank,
        rerank_top_n: useRerank ? rerankTopN : undefined,
      });
      setResults(data.results);
      setRerankApplied(data.rerank_applied);
      setRerankError(data.rerank_error ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel wide">
      <div className="section-heading">
        <h2>Search</h2>
      </div>
      <p className="muted">
        Search indexed knowledge base chunks. Table results show sheet and row ranges so reviewers can jump from a match
        to the exact row group evidence.
      </p>

      <form className="search-page-form" onSubmit={submit}>
        <label>
          Query
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search table rows, SOP steps, manuals, or parameters" />
        </label>
        <label>
          Top K
          <input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
        </label>
        <div className="metadata-filter-builder">
          <div className="section-heading compact-heading">
            <h3>Metadata filters</h3>
            <button type="button" onClick={() => {
              setStructuredMetadataFilter(EMPTY_METADATA_FILTER);
              setAdvancedMetadataFilter("");
            }}>
              Clear filters
            </button>
          </div>
          <p className="muted">
            Use supported document metadata to narrow table-heavy searches. Sheet names and row ranges are shown in
            results; this first UI keeps filtering to backend-supported metadata fields.
          </p>
          <div className="metadata-filter-grid">
            {METADATA_FILTER_FIELDS.map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  value={structuredMetadataFilter[field.key]}
                  onChange={(event) =>
                    setStructuredMetadataFilter((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  placeholder={field.placeholder}
                />
              </label>
            ))}
          </div>
          <label>
            Advanced metadata filter JSON
            <textarea
              value={advancedMetadataFilter}
              onChange={(event) => setAdvancedMetadataFilter(event.target.value)}
              placeholder='{"material_code":"P-A200-H"}'
            />
          </label>
          <div className="effective-filter-preview">
            <span>Effective filter sent to Search API</span>
            <pre>{effectiveMetadataFilterPreview}</pre>
          </div>
        </div>
        <label className="toggle-row">
          <input type="checkbox" checked={useRerank} onChange={(event) => setUseRerank(event.target.checked)} />
          Use rerank
        </label>
        {useRerank && (
          <label>
            Rerank top N
            <input
              type="number"
              min={1}
              max={100}
              value={rerankTopN}
              onChange={(event) => setRerankTopN(Number(event.target.value))}
            />
          </label>
        )}
        <div className="kb-picker">
          {kbs.map((kb) => (
            <label key={kb.id}>
              <input
                type="checkbox"
                checked={selectedKbIds.includes(kb.id)}
                onChange={(event) =>
                  setSelectedKbIds((current) =>
                    event.target.checked ? [...current, kb.id] : current.filter((id) => id !== kb.id),
                  )
                }
              />
              {kb.name}
            </label>
          ))}
        </div>
        <button type="submit" disabled={loading || !query.trim() || selectedKbIds.length === 0}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {results.length > 0 && (
        <div className="subtle-block">
          <div className="section-heading">
            <h3>Results</h3>
            <span className="muted">
              {results.length} result(s), {tableResultCount} table result(s), rerank {rerankApplied ? "applied" : "not applied"}
              {rerankError ? ` (${rerankError})` : ""}
            </span>
          </div>
          <div className="search-result-list">
            {results.map((result, index) => {
              const columns = tableColumns(result);
              const isTable = result.metadata?.source_type === "table" || Boolean(result.sheet_name);
              return (
                <article key={result.chunk_id} className={isTable ? "search-result-card table-result-card" : "search-result-card"}>
                  <div className="search-result-header">
                    <div>
                      <span className="status-pill status-info">#{index + 1}</span>
                      {isTable && <span className="status-pill table-pill">Table row match</span>}
                    </div>
                    <div className="score-strip">
                      <span>final {scoreText(result.final_score ?? result.score)}</span>
                      <span>vector {scoreText(result.vector_score)}</span>
                      <span>rerank {scoreText(result.rerank_score)}</span>
                    </div>
                  </div>
                  <h4>{resultTitle(result)}</h4>
                  {isTable && (
                    <div className="table-search-meta">
                      <span>Sheet: {result.sheet_name || "-"}</span>
                      <span>Rows: {result.row_start ?? "-"}-{result.row_end ?? "-"}</span>
                      {columns.length > 0 && <span>Columns: {columns.join(", ")}</span>}
                    </div>
                  )}
                  <pre className="search-result-snippet">{result.chunk_text}</pre>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {!loading && !error && query && results.length === 0 && (
        <p className="muted">No results yet, or the last search returned no matches.</p>
      )}
    </section>
  );
}

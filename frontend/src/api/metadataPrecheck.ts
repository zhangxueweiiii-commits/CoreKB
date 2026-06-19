import { request } from "./client";

export interface MetadataPrecheckSummary {
  documents_scanned: number;
  metadata_fields_scanned: number;
  canonical_count: number;
  alias_match_count: number;
  rule_normalizable_count: number;
  dictionary_missing_count: number;
  invalid_or_empty_count: number;
  unsupported_count: number;
}

export interface MetadataPrecheckItem {
  document_id: string;
  document_name: string;
  knowledge_base_id: string;
  field_name: string;
  current_value: string;
  suggested_value?: string | null;
  status: string;
  matched_by: string;
  dictionary_entry_id?: string | null;
  recommended_action: string;
  reason: string;
}

export interface MetadataPrecheckResponse {
  summary: MetadataPrecheckSummary;
  items: MetadataPrecheckItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface MetadataPrecheckSummaryResponse {
  summary: MetadataPrecheckSummary;
  by_field: Record<string, Record<string, number>>;
  by_status: Record<string, number>;
  top_dictionary_missing_values: Array<{ key: string; count: number }>;
  top_alias_match_values: Array<{ key: string; count: number }>;
  fixable_by_knowledge_base: Array<{ knowledge_base_id: string; count: number }>;
}

export const metadataPrecheckApi = {
  run: (params: {
    knowledge_base_id?: string;
    document_id?: string;
    field_name?: string;
    status?: string;
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
    return request<MetadataPrecheckResponse>(`/metadata/precheck${suffix}`);
  },
  summary: (knowledgeBaseId?: string) => {
    const suffix = knowledgeBaseId ? `?knowledge_base_id=${knowledgeBaseId}` : "";
    return request<MetadataPrecheckSummaryResponse>(`/metadata/precheck/summary${suffix}`);
  },
};

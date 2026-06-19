const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export type UserRole = "admin" | "editor" | "viewer";

export interface User {
  id: string;
  username: string;
  email?: string | null;
  full_name?: string | null;
  role: UserRole;
  is_active: boolean;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string | null;
  owner_id: string;
  visibility: "private" | "company";
  access_role?: "owner" | "editor" | "viewer" | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  knowledge_base_id: string;
  filename: string;
  file_path?: string;
  file_type: string;
  file_size: number;
  status: string;
  error_message?: string | null;
  chunk_count: number;
  meta?: Record<string, unknown>;
  metadata_completeness?: {
    completeness_status: "complete" | "partial" | "missing";
    missing_recommended_fields: string[];
  } | null;
  indexed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentMetadataSuggestion {
  id: string;
  document_id: string;
  field: string;
  raw_value: string;
  normalized_value: string;
  normalization_source: "canonical" | "alias" | "rule" | "fallback" | string;
  dictionary_entry_id?: string | null;
  custom_value: boolean;
  suggested_value: string;
  confidence: "high" | "medium" | "low";
  source: "filename" | "title" | "parsed_text";
  evidence_excerpt: string;
  rule_name: string;
  status: "pending" | "accepted" | "rejected";
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  current_value?: string | null;
  review_guardrails?: {
    requires_evidence_review: boolean;
    requires_current_value_review: boolean;
    requires_custom_value_flag: boolean;
    reindex_required_on_accept: boolean;
    warnings: string[];
    checklist: string[];
  };
}

export interface DocumentMetadataSuggestionList {
  items: DocumentMetadataSuggestion[];
  total: number;
}

export interface SearchResult {
  chunk_text: string;
  filename: string;
  page_number?: number | null;
  section_title?: string | null;
  sheet_name?: string | null;
  row_start?: number | null;
  row_end?: number | null;
  score: number;
  vector_score?: number | null;
  rerank_score?: number | null;
  final_score?: number | null;
  document_id: string;
  chunk_id: string;
  metadata?: Record<string, unknown>;
}

export interface AssistantPreset {
  assistant_type: "maintenance" | "quality" | "sop" | "material";
  display_name: string;
  description: string;
  system_prompt: string;
  default_top_k: number;
  default_rerank_top_n: number;
  default_use_rerank: boolean;
  default_auto_metadata_filter: boolean;
  default_metadata_filter: Record<string, string>;
  answer_format: string[];
}

export interface AssistantChatResponse {
  assistant_type: string;
  answer: string;
  citations: Array<{ filename: string; page_number?: number; section_title?: string; sheet_name?: string; row_start?: number; row_end?: number; quote: string; chunk_id: string }>;
  used_metadata_filter: Record<string, string>;
  use_rerank: boolean;
  rerank_applied: boolean;
  rerank_error?: string | null;
  sources: Array<{ filename: string; page_number?: number; section_title?: string; sheet_name?: string; row_start?: number; row_end?: number; quote: string; chunk_id: string }>;
  no_answer_detected: boolean;
  conversation_id: string;
}

export interface RetryIndexingResponse {
  id: string;
  job_type: string;
  status: string;
  knowledge_base_id: string;
  document_id?: string | null;
  total_count: number;
  success_count: number;
  failed_count: number;
  pending_count: number;
  created_at: string;
}

export function getToken(): string | null {
  return localStorage.getItem("corekb_token");
}

export type StreamChatEvent =
  | { event: "retrieval_started"; data: { message: string } }
  | { event: "retrieval_completed"; data: { chunk_count: number; used_metadata_filter?: Record<string, string>; use_rerank?: boolean; rerank_applied?: boolean; rerank_error?: string | null } }
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: Array<{ filename: string; page_number?: number; section_title?: string; sheet_name?: string; row_start?: number; row_end?: number; quote: string; chunk_id: string }> }
  | { event: "done"; data: { conversation_id: string; used_metadata_filter?: Record<string, string>; use_rerank?: boolean; rerank_applied?: boolean; rerank_error?: string | null } }
  | { event: "error"; data: { message: string } };

export function setToken(token: string | null): void {
  if (token) localStorage.setItem("corekb_token", token);
  else localStorage.removeItem("corekb_token");
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail ?? `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>("/auth/me"),
  users: () => request<User[]>("/users"),
  createUser: (payload: { username: string; password: string; role: UserRole; email?: string }) =>
    request<User>("/users", { method: "POST", body: JSON.stringify(payload) }),
  kbs: () => request<KnowledgeBase[]>("/kb"),
  createKb: (payload: { name: string; description?: string; visibility: "private" | "company" }) =>
    request<KnowledgeBase>("/kb", { method: "POST", body: JSON.stringify(payload) }),
  documents: (kbId: string) => request<DocumentItem[]>(`/kb/${kbId}/documents`),
  document: (documentId: string) => request<DocumentItem>(`/documents/${documentId}`),
  uploadDocument: (kbId: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<DocumentItem>(`/kb/${kbId}/documents`, { method: "POST", body: data });
  },
  deleteDocument: (documentId: string) =>
    request<void>(`/documents/${documentId}`, { method: "DELETE" }),
  retryDocument: (documentId: string) =>
    request<RetryIndexingResponse>(`/documents/${documentId}/retry-indexing`, { method: "POST" }),
  generateMetadataSuggestions: (documentId: string) =>
    request<DocumentMetadataSuggestionList>(`/documents/${documentId}/metadata-suggestions/generate`, { method: "POST" }),
  metadataSuggestions: (documentId: string) =>
    request<DocumentMetadataSuggestionList>(`/documents/${documentId}/metadata-suggestions`),
  listMetadataSuggestions: (params: { status?: string; field?: string; confidence?: string; document_id?: string; knowledge_base_id?: string } = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) search.set(key, String(value));
    });
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<DocumentMetadataSuggestionList>(`/documents/metadata-suggestions${suffix}`);
  },
  acceptMetadataSuggestion: (documentId: string, suggestionId: string, value?: string, customValue = false) =>
    request<DocumentMetadataSuggestion>(`/documents/${documentId}/metadata-suggestions/${suggestionId}/accept`, {
      method: "POST",
      body: JSON.stringify({ value, custom_value: customValue }),
    }),
  rejectMetadataSuggestion: (documentId: string, suggestionId: string) =>
    request<DocumentMetadataSuggestion>(`/documents/${documentId}/metadata-suggestions/${suggestionId}/reject`, {
      method: "POST",
    }),
  search: (payload: { query: string; knowledge_base_ids: string[]; top_k: number; metadata_filter?: Record<string, string>; use_rerank?: boolean; rerank_top_n?: number }) =>
    request<{ results: SearchResult[]; use_rerank: boolean; rerank_applied: boolean; rerank_error?: string | null }>("/search", { method: "POST", body: JSON.stringify(payload) }),
  chat: (payload: { message: string; knowledge_base_ids: string[]; conversation_id?: string; metadata_filter?: Record<string, string>; auto_metadata_filter?: boolean; use_rerank?: boolean; rerank_top_n?: number }) =>
    request<{ answer: string; citations: Array<{ filename: string; page_number?: number; section_title?: string; sheet_name?: string; row_start?: number; row_end?: number; quote: string; chunk_id: string }>; conversation_id: string; used_metadata_filter: Record<string, string>; use_rerank: boolean; rerank_applied: boolean; rerank_error?: string | null }>(
      "/chat",
      { method: "POST", body: JSON.stringify(payload) },
    ),
  streamChat: async (
    payload: { message: string; knowledge_base_ids: string[]; conversation_id?: string; metadata_filter?: Record<string, string>; auto_metadata_filter?: boolean; use_rerank?: boolean; rerank_top_n?: number },
    onEvent: (event: StreamChatEvent) => void,
  ) => {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail ?? `HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const eventLine = part.split("\n").find((line) => line.startsWith("event:"));
        const dataLine = part.split("\n").find((line) => line.startsWith("data:"));
        if (!eventLine || !dataLine) continue;
        onEvent({
          event: eventLine.replace("event:", "").trim(),
          data: JSON.parse(dataLine.replace("data:", "").trim()),
        } as StreamChatEvent);
      }
    }
  },
  assistantPresets: () => request<AssistantPreset[]>("/assistants/presets"),
  assistantChat: (
    assistantType: string,
    payload: {
      query: string;
      metadata_filter?: Record<string, string>;
      auto_metadata_filter?: boolean;
      use_rerank?: boolean;
      rerank_top_n?: number;
      top_k?: number;
      conversation_id?: string;
    },
  ) =>
    request<AssistantChatResponse>(`/assistants/${assistantType}/chat`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

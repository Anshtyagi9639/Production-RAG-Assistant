/**
 * Request/response contracts for the backend API (BUILD.md section 8).
 * The backend's Pydantic schemas must serialize to exactly these shapes.
 */

export type WorkspaceRole = "owner" | "member"
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED"
export type AgentRunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED"

export interface ErrorBody {
  error: { code: string; message: string; details?: unknown }
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface User {
  id: string
  email: string
  full_name: string
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  role: WorkspaceRole
  created_at: string
}

export interface Me {
  user: User
  workspaces: Workspace[]
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
  expires_in: number
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

export interface RegisterResponse {
  user: User
  workspace: Workspace
}

export interface Document {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  status: DocumentStatus
  error_message: string | null
  page_count: number | null
  chunk_count: number | null
  uploaded_by_name: string | null
  created_at: string
  updated_at: string
  processed_at: string | null
}

export type DocumentSort = "-created_at" | "created_at" | "filename" | "-filename"

export interface DocumentListParams {
  page: number
  pageSize: number
  sort: DocumentSort
  status?: DocumentStatus
}

/** A retrieved chunk. `index` is the citation number used as [n] in answers. */
export interface Source {
  index: number
  document_id: string
  filename: string
  page: number | null
  chunk_index: number
  score: number
  snippet: string
}

export interface SearchRequest {
  query: string
  top_k?: number
}

export interface SearchResult {
  document_id: string
  filename: string
  page: number | null
  chunk_index: number
  score: number
  snippet: string
}

export interface SearchResponse {
  results: SearchResult[]
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  sources: Source[]
  /** True when no chunk passed the threshold: the fixed answer was returned without the LLM. */
  insufficient_context: boolean
  created_at: string
}

export interface ChatRequest {
  message: string
  conversation_id?: string
}

export interface ChatResponse {
  conversation_id: string
  message: ChatMessage
}

export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[]
}

export interface AgentStep {
  node: string
  status: "completed" | "failed"
  started_at: string
  duration_ms: number
  summary: string
}

export interface AgentRun {
  id: string
  request: string
  status: AgentRunStatus
  classification: "simple" | "complex" | null
  trace: AgentStep[]
  final_answer: string | null
  sources: Source[]
  is_partial: boolean
  error: string | null
  prompt_tokens: number
  completion_tokens: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface ActivityEntry {
  id: string
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
  user_name: string | null
  created_at: string
}

export interface Stats {
  documents: {
    total: number
    by_status: Record<DocumentStatus, number>
  }
  conversations: number
  agent_runs: number
  tokens: {
    prompt: number
    completion: number
    total: number
  }
}

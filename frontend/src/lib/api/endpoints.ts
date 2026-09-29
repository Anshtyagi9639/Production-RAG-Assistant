import { apiRequest } from "@/lib/api/client"
import type {
  ActivityEntry,
  AgentRun,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  Document,
  DocumentListParams,
  Me,
  Page,
  RegisterRequest,
  RegisterResponse,
  SearchRequest,
  SearchResponse,
  Stats,
  TokenResponse,
  Workspace,
} from "@/lib/api/types"

export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<TokenResponse>("/auth/login", { method: "POST", json: { email, password } }),
  register: (request: RegisterRequest) =>
    apiRequest<RegisterResponse>("/auth/register", { method: "POST", json: request }),
  me: () => apiRequest<Me>("/auth/me"),
}

export const workspacesApi = {
  create: (name: string) =>
    apiRequest<Workspace>("/workspaces", { method: "POST", json: { name } }),
}

export const documentsApi = {
  list: (workspaceId: string, params: DocumentListParams) =>
    apiRequest<Page<Document>>("/documents", {
      workspaceId,
      query: {
        page: params.page,
        page_size: params.pageSize,
        sort: params.sort,
        status: params.status,
      },
    }),
  get: (workspaceId: string, id: string) =>
    apiRequest<Document>(`/documents/${encodeURIComponent(id)}`, { workspaceId }),
  upload: (workspaceId: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiRequest<Document>("/documents/upload", { method: "POST", form, workspaceId })
  },
  remove: (workspaceId: string, id: string) =>
    apiRequest<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE", workspaceId }),
}

export const searchApi = {
  search: (workspaceId: string, request: SearchRequest) =>
    apiRequest<SearchResponse>("/search", { method: "POST", json: request, workspaceId }),
}

export const chatApi = {
  send: (workspaceId: string, request: ChatRequest) =>
    apiRequest<ChatResponse>("/chat", { method: "POST", json: request, workspaceId }),
  listConversations: (workspaceId: string, page: number, pageSize: number) =>
    apiRequest<Page<ConversationSummary>>("/conversations", {
      workspaceId,
      query: { page, page_size: pageSize },
    }),
  getConversation: (workspaceId: string, id: string) =>
    apiRequest<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`, { workspaceId }),
}

export const agentApi = {
  run: (workspaceId: string, request: string) =>
    apiRequest<AgentRun>("/agent/run", { method: "POST", json: { request }, workspaceId }),
  getRun: (workspaceId: string, id: string) =>
    apiRequest<AgentRun>(`/agent/runs/${encodeURIComponent(id)}`, { workspaceId }),
}

export const activityApi = {
  list: (workspaceId: string, page: number, pageSize: number) =>
    apiRequest<Page<ActivityEntry>>("/activity", {
      workspaceId,
      query: { page, page_size: pageSize },
    }),
}

export const statsApi = {
  get: (workspaceId: string) => apiRequest<Stats>("/stats", { workspaceId }),
}

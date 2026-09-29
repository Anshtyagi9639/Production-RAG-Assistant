import type { DocumentListParams } from "@/lib/api/types"

/** Everything tenant-scoped starts with ["workspace", id] so it can be invalidated together. */
export const queryKeys = {
  me: ["me"] as const,
  workspace: (workspaceId: string) => ["workspace", workspaceId] as const,
  documents: (workspaceId: string, params: DocumentListParams) =>
    ["workspace", workspaceId, "documents", params] as const,
  document: (workspaceId: string, id: string) =>
    ["workspace", workspaceId, "document", id] as const,
  conversations: (workspaceId: string, page: number) =>
    ["workspace", workspaceId, "conversations", page] as const,
  conversation: (workspaceId: string, id: string) =>
    ["workspace", workspaceId, "conversation", id] as const,
  agentRun: (workspaceId: string, id: string) =>
    ["workspace", workspaceId, "agent-run", id] as const,
  activity: (workspaceId: string, page: number, pageSize: number) =>
    ["workspace", workspaceId, "activity", page, pageSize] as const,
  stats: (workspaceId: string) => ["workspace", workspaceId, "stats"] as const,
}

"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { MessagesSquare, Plus } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { Pagination } from "@/components/pagination"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { chatApi } from "@/lib/api/endpoints"
import { formatDateTime } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 30

export function ConversationList({
  workspaceId,
  activeId,
  onNavigate,
}: {
  workspaceId: string
  activeId: string | null
  onNavigate?: () => void
}) {
  const [page, setPage] = useState(1)
  const conversations = useQuery({
    queryKey: queryKeys.conversations(workspaceId, page),
    queryFn: () => chatApi.listConversations(workspaceId, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="flex h-full flex-col gap-3">
      <Button asChild variant="outline" className="w-full">
        <Link href="/assistant" onClick={onNavigate}>
          <Plus aria-hidden />
          New conversation
        </Link>
      </Button>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversations.isPending && <ListSkeleton rows={6} label="Loading conversations" />}
        {conversations.isError && (
          <ErrorState
            title="Couldn't load conversations"
            error={conversations.error}
            onRetry={() => conversations.refetch()}
          />
        )}
        {conversations.isSuccess && conversations.data.items.length === 0 && (
          <EmptyState icon={MessagesSquare} title="No conversations yet" />
        )}
        {conversations.isSuccess && conversations.data.items.length > 0 && (
          <nav aria-label="Conversations">
            <ul className="space-y-1">
              {conversations.data.items.map((conversation) => (
                <li key={conversation.id}>
                  <Link
                    href={`/assistant?c=${conversation.id}`}
                    onClick={onNavigate}
                    aria-current={conversation.id === activeId ? "page" : undefined}
                    className={cn(
                      "block rounded-md px-2.5 py-2 transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      conversation.id === activeId && "bg-accent hover:bg-accent",
                    )}
                  >
                    <span className="block truncate text-sm font-medium">{conversation.title}</span>
                    <span className="block text-xs text-muted-foreground">
                      {formatDateTime(conversation.updated_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination page={page} pages={conversations.data.pages} onPageChange={setPage} />
          </nav>
        )}
      </div>
    </div>
  )
}

"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { FileText, MessagesSquare, SquarePen } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { ConversationActions } from "@/components/assistant/conversation-actions"
import { Pagination } from "@/components/pagination"
import { EmptyState, ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { chatApi } from "@/lib/api/endpoints"
import { formatDateTime, formatRelative } from "@/lib/format"
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
  const router = useRouter()
  const [page, setPage] = useState(1)
  const conversations = useQuery({
    queryKey: queryKeys.conversations(workspaceId, page),
    queryFn: () => chatApi.listConversations(workspaceId, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="flex h-full flex-col gap-3">
      <Button asChild variant="outline" className="w-full justify-start bg-card">
        <Link href="/assistant" onClick={onNavigate}>
          <SquarePen aria-hidden />
          New conversation
        </Link>
      </Button>
      <p className="px-1 text-[11px] font-medium tracking-wide text-muted-foreground/80 uppercase">
        History
      </p>
      <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
        {conversations.isPending && (
          <div role="status" aria-label="Loading conversations" className="space-y-3 px-2">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className="space-y-1.5">
                <Skeleton className="h-3.5 w-4/5" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            ))}
          </div>
        )}
        {conversations.isError && (
          <ErrorState
            title="Couldn't load conversations"
            error={conversations.error}
            onRetry={() => conversations.refetch()}
          />
        )}
        {conversations.isSuccess && conversations.data.items.length === 0 && (
          <EmptyState
            icon={MessagesSquare}
            title="No conversations yet"
            description="Your questions will be saved here."
            className="border-none py-6"
          />
        )}
        {conversations.isSuccess && conversations.data.items.length > 0 && (
          <nav aria-label="Conversations">
            <ul className="space-y-0.5">
              {conversations.data.items.map((conversation) => {
                const active = conversation.id === activeId
                return (
                  <li
                    key={conversation.id}
                    className="group/conversation relative flex items-center"
                  >
                    <Link
                      href={`/assistant?c=${conversation.id}`}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "block min-w-0 flex-1 rounded-lg py-2 pr-9 pl-2.5 transition-colors outline-none hover:bg-sidebar-accent focus-visible:ring-3 focus-visible:ring-ring/50",
                        active && "bg-card shadow-xs ring-1 ring-border hover:bg-card",
                      )}
                    >
                      <span className="block truncate text-sm font-medium">
                        {conversation.title}
                      </span>
                      <span className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
                        <span className="shrink-0" title={formatDateTime(conversation.updated_at)}>
                          {formatRelative(conversation.updated_at)}
                        </span>
                        {conversation.scope && (
                          <>
                            <span aria-hidden>·</span>
                            <FileText className="size-3 shrink-0" aria-hidden />
                            <span className="truncate">
                              <span className="sr-only">Only </span>
                              {conversation.scope.map((item) => item.filename).join(", ")}
                            </span>
                          </>
                        )}
                      </span>
                    </Link>
                    <div className="absolute right-1.5">
                      <ConversationActions
                        workspaceId={workspaceId}
                        conversation={conversation}
                        onDeleted={() => {
                          if (active) router.push("/assistant")
                        }}
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
            <Pagination page={page} pages={conversations.data.pages} onPageChange={setPage} />
          </nav>
        )}
      </div>
    </div>
  )
}

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessagesSquare, PanelLeft } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { useWorkspace } from "@/components/app/workspace-context"
import { Composer } from "@/components/assistant/composer"
import { ConversationList } from "@/components/assistant/conversation-list"
import { type Citation, MessageThread } from "@/components/assistant/message-thread"
import { SourcesList } from "@/components/citations/sources-list"
import { FormError } from "@/components/auth/form-error"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { chatApi } from "@/lib/api/endpoints"
import type { ChatMessage } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

function SourcesPanel({
  message,
  citation,
}: {
  message: ChatMessage | undefined
  citation: Citation | null
}) {
  if (!message || message.sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sources for an answer appear here. Select a citation like{" "}
        <span className="rounded border px-1 text-xs text-primary">1</span> to jump to it.
      </p>
    )
  }
  return (
    <SourcesList
      sources={message.sources}
      activeIndex={citation?.messageId === message.id ? citation.sourceIndex : null}
    />
  )
}

function Assistant() {
  const { workspace } = useWorkspace()
  const router = useRouter()
  const queryClient = useQueryClient()
  const conversationId = useSearchParams().get("c")
  const [draft, setDraft] = useState("")
  const [citation, setCitation] = useState<Citation | null>(null)
  const [listOpen, setListOpen] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)

  const conversation = useQuery({
    queryKey: queryKeys.conversation(workspace.id, conversationId ?? ""),
    queryFn: () => chatApi.getConversation(workspace.id, conversationId ?? ""),
    enabled: conversationId !== null,
  })

  const send = useMutation({
    mutationFn: (message: string) =>
      chatApi.send(workspace.id, { message, conversation_id: conversationId ?? undefined }),
    onMutate: () => setDraft(""),
    onError: (_error, message) => setDraft(message),
    onSuccess: async (response) => {
      // Load the updated thread before the pending bubble disappears, to avoid a flash.
      await queryClient.fetchQuery({
        queryKey: queryKeys.conversation(workspace.id, response.conversation_id),
        queryFn: () => chatApi.getConversation(workspace.id, response.conversation_id),
      })
      await queryClient.invalidateQueries({
        queryKey: ["workspace", workspace.id, "conversations"],
      })
      if (response.conversation_id !== conversationId) {
        router.replace(`/assistant?c=${response.conversation_id}`)
      }
      setCitation({ messageId: response.message.id, sourceIndex: null })
    },
  })

  const messages = conversationId ? (conversation.data?.messages ?? []) : []
  const lastWithSources = messages.findLast((m) => m.role === "assistant" && m.sources.length > 0)
  const selectedMessage = messages.find((m) => m.id === citation?.messageId) ?? lastWithSources

  const cite = (next: Citation) => {
    setCitation(next)
    // Below xl the sources panel isn't on screen, so open it as a sheet.
    if (!window.matchMedia("(min-width: 80rem)").matches) setSourcesOpen(true)
  }

  return (
    <div className="-mx-4 -my-6 grid h-[calc(100svh-3.3rem)] sm:-mx-6 lg:-mx-8 lg:h-svh lg:grid-cols-[16rem_1fr] xl:grid-cols-[16rem_1fr_22rem]">
      <title>Assistant · Knowledge Copilot</title>

      <aside aria-label="Conversation history" className="hidden border-r bg-card p-3 lg:block">
        <ConversationList workspaceId={workspace.id} activeId={conversationId} />
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col">
        <header className="flex items-center gap-2 border-b bg-card px-4 py-3">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => setListOpen(true)}
            aria-label="Show conversations"
          >
            <PanelLeft aria-hidden />
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold">
              {conversation.data?.title ?? "Assistant"}
            </h1>
            <p className="text-xs text-muted-foreground">
              Answers use only this workspace&apos;s documents and cite their sources.
            </p>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
          {conversationId && conversation.isPending && (
            <ListSkeleton rows={3} label="Loading conversation" />
          )}
          {conversationId && conversation.isError && (
            <ErrorState
              title="Couldn't load this conversation"
              error={conversation.error}
              onRetry={() => conversation.refetch()}
            />
          )}
          {!conversationId && !send.isPending && (
            <EmptyState
              icon={MessagesSquare}
              title="Ask about your documents"
              description="For example: “What is our refund window for annual plans?” Every answer links to the passages it used."
            />
          )}
          {(messages.length > 0 || send.isPending) && (
            <MessageThread
              messages={messages}
              pendingQuestion={send.isPending ? send.variables : null}
              citation={citation}
              onCite={cite}
            />
          )}
        </div>

        <div className="space-y-2 border-t bg-background px-4 py-3">
          <FormError error={send.error} />
          <Composer
            value={draft}
            onChange={setDraft}
            pending={send.isPending}
            onSubmit={() => send.mutate(draft.trim())}
          />
        </div>
      </section>

      <aside
        aria-labelledby="sources-heading"
        className="hidden overflow-y-auto border-l bg-card p-4 xl:block"
      >
        <h2 id="sources-heading" className="mb-3 text-sm font-semibold">
          Sources
        </h2>
        <SourcesPanel message={selectedMessage} citation={citation} />
      </aside>

      <Sheet open={listOpen} onOpenChange={setListOpen}>
        <SheetContent side="left" className="w-80 p-4">
          <SheetHeader className="p-0">
            <SheetTitle>Conversations</SheetTitle>
            <SheetDescription className="sr-only">
              Your conversations in this workspace
            </SheetDescription>
          </SheetHeader>
          <ConversationList
            workspaceId={workspace.id}
            activeId={conversationId}
            onNavigate={() => setListOpen(false)}
          />
        </SheetContent>
      </Sheet>
      <Sheet open={sourcesOpen} onOpenChange={setSourcesOpen}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Sources</SheetTitle>
            <SheetDescription>Passages this answer was grounded on.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-4">
            <SourcesPanel message={selectedMessage} citation={citation} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export default function AssistantPage() {
  return (
    <Suspense>
      <Assistant />
    </Suspense>
  )
}

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BookMarked, PanelLeft, Quote, Sparkles } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { useWorkspace } from "@/components/app/workspace-context"
import { Composer } from "@/components/assistant/composer"
import { ConversationList } from "@/components/assistant/conversation-list"
import { type Citation, MessageThread } from "@/components/assistant/message-thread"
import { FormError } from "@/components/auth/form-error"
import { SourcesList } from "@/components/citations/sources-list"
import { ErrorState } from "@/components/states"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { chatApi } from "@/lib/api/endpoints"
import type { ChatMessage } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"

// Prompts that work against any knowledge base; selecting one only fills the composer.
const STARTERS = [
  "Summarize the main rules in our documents",
  "What deadlines are mentioned in our documents?",
  "Which documents mention approvals, and what do they require?",
]

function SourcesPanel({
  message,
  citation,
}: {
  message: ChatMessage | undefined
  citation: Citation | null
}) {
  if (!message || message.sources.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center">
        <Quote className="size-5 text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Passages an answer cites appear here. Select a citation such as{" "}
          <span className="rounded-md border border-primary/20 bg-accent px-1 text-[11px] font-semibold text-accent-foreground">
            1
          </span>{" "}
          to jump to it.
        </p>
      </div>
    )
  }
  return (
    <SourcesList
      sources={message.sources}
      activeIndex={citation?.messageId === message.id ? citation.sourceIndex : null}
    />
  )
}

function Welcome({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-col items-center px-2 pt-10 text-center sm:pt-16">
      <span className="mb-4 flex size-12 items-center justify-center rounded-2xl border border-primary/15 bg-accent text-accent-foreground shadow-xs">
        <Sparkles className="size-5" aria-hidden />
      </span>
      <h2 className="text-xl font-semibold tracking-tight">Ask about your documents</h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Answers are written only from this workspace&apos;s documents, and every claim links to the
        passage it came from.
      </p>
      <ul className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-3">
        {STARTERS.map((prompt) => (
          <li key={prompt}>
            <button
              type="button"
              onClick={() => onPick(prompt)}
              className="h-full w-full rounded-xl border bg-card p-3 text-left text-sm text-muted-foreground shadow-xs transition-colors outline-none hover:border-primary/40 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {prompt}
            </button>
          </li>
        ))}
      </ul>
    </div>
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
  // How many messages the thread had when the question was sent: once the refreshed thread
  // holds more, the answer is on screen and the pending bubble must not show it twice.
  const [sentAtCount, setSentAtCount] = useState(0)

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
      // staleTime 0: the cached thread is out of date now, however recently it was fetched.
      await queryClient.fetchQuery({
        queryKey: queryKeys.conversation(workspace.id, response.conversation_id),
        queryFn: () => chatApi.getConversation(workspace.id, response.conversation_id),
        staleTime: 0,
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
  const pendingQuestion = send.isPending && messages.length <= sentAtCount ? send.variables : null
  const lastWithSources = messages.findLast((m) => m.role === "assistant" && m.sources.length > 0)
  const selectedMessage = messages.find((m) => m.id === citation?.messageId) ?? lastWithSources
  const sourceCount = selectedMessage?.sources.length ?? 0

  const cite = (next: Citation) => {
    setCitation(next)
    // Below xl the sources panel isn't on screen, so open it as a sheet.
    if (!window.matchMedia("(min-width: 80rem)").matches) setSourcesOpen(true)
  }

  return (
    <div className="grid h-[calc(100svh-3.5rem)] grid-cols-1 lg:grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)_22rem]">
      <title>Assistant · Knowledge Copilot</title>

      <aside aria-label="Conversation history" className="hidden border-r bg-sidebar p-3 lg:block">
        <ConversationList workspaceId={workspace.id} activeId={conversationId} />
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col">
        <header className="flex items-center gap-2 border-b px-4 py-2.5">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => setListOpen(true)}
            aria-label="Show conversations"
          >
            <PanelLeft aria-hidden />
          </Button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold">
              {conversationId ? (conversation.data?.title ?? "Conversation") : "New conversation"}
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              Answers use only {workspace.name}&apos;s documents and cite their sources.
            </p>
          </div>
          {sourceCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="xl:hidden"
              onClick={() => setSourcesOpen(true)}
            >
              <BookMarked aria-hidden />
              Sources
              <span className="text-muted-foreground tabular-nums">{sourceCount}</span>
            </Button>
          )}
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {conversationId && conversation.isPending && (
              <div role="status" aria-label="Loading conversation" className="space-y-8">
                <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl" />
                <div className="space-y-2">
                  <Skeleton className="h-3.5 w-11/12" />
                  <Skeleton className="h-3.5 w-4/5" />
                  <Skeleton className="h-3.5 w-2/3" />
                </div>
              </div>
            )}
            {conversationId && conversation.isError && (
              <ErrorState
                title="Couldn't load this conversation"
                error={conversation.error}
                onRetry={() => conversation.refetch()}
              />
            )}
            {!conversationId && !send.isPending && <Welcome onPick={setDraft} />}
            {(messages.length > 0 || send.isPending) && (
              <MessageThread
                messages={messages}
                pendingQuestion={pendingQuestion}
                citation={citation}
                onCite={cite}
                canUpload={workspace.role === "owner"}
              />
            )}
          </div>
        </div>

        <div className="border-t bg-background/80 px-4 pt-3 pb-4 backdrop-blur sm:px-6">
          <div className="mx-auto w-full max-w-3xl space-y-2">
            <FormError error={send.error} />
            <Composer
              value={draft}
              onChange={setDraft}
              pending={send.isPending}
              onSubmit={() => {
                setSentAtCount(messages.length)
                send.mutate(draft.trim())
              }}
            />
          </div>
        </div>
      </section>

      <aside
        aria-labelledby="sources-heading"
        className="hidden overflow-y-auto border-l bg-sidebar p-4 xl:block"
      >
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="sources-heading" className="text-sm font-semibold">
            Sources
          </h2>
          {sourceCount > 0 && (
            <span className="text-xs text-muted-foreground">
              {sourceCount} {sourceCount === 1 ? "passage" : "passages"}
            </span>
          )}
        </div>
        <SourcesPanel message={selectedMessage} citation={citation} />
      </aside>

      <Sheet open={listOpen} onOpenChange={setListOpen}>
        <SheetContent side="left" className="w-80 bg-sidebar p-4">
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
        <SheetContent side="right" className="w-full overflow-y-auto bg-sidebar sm:max-w-md">
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

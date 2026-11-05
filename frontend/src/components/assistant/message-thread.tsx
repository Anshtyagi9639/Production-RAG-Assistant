"use client"

import { BookOpenText, Check, Copy, Info, Sparkles } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { CitationText } from "@/components/citations/citation-text"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ChatMessage, Source } from "@/lib/api/types"
import { formatLocation } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface Citation {
  messageId: string
  sourceIndex: number | null
}

/** The assistant's mark next to its answers. */
export function AssistantAvatar({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-lg border border-primary/15 bg-accent text-accent-foreground",
        className,
      )}
    >
      <Sparkles className="size-3.5" />
    </span>
  )
}

export function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden>
      {[0, 1, 2].map((dot) => (
        <span
          key={dot}
          className="size-1.5 animate-[thinking_1.2s_ease-in-out_infinite] rounded-full bg-current"
          style={{ animationDelay: `${dot * 0.15}s` }}
        />
      ))}
    </span>
  )
}

function InsufficientContext({
  canUpload,
  scopeLabel,
}: {
  canUpload: boolean
  scopeLabel?: string
}) {
  return (
    <div className="rounded-xl border border-info/20 bg-info/[0.04] p-4">
      <div className="flex items-start gap-3">
        <Info className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
        <div className="space-y-2">
          <p className="text-sm font-medium">
            {scopeLabel
              ? `Not enough information in ${scopeLabel}`
              : "Not enough information in your knowledge base"}
          </p>
          <p className="text-sm text-muted-foreground">
            {scopeLabel
              ? `This conversation only searches ${scopeLabel}, and no passage in it was relevant enough to answer, so no answer was generated. Nothing was made up. Start a new conversation to search all documents.`
              : "No passage in this workspace was relevant enough to answer, so no answer was generated. Nothing was made up. Try rephrasing the question, or add a document that covers this topic."}
          </p>
          <Button asChild variant="outline" size="sm">
            <Link href="/knowledge">
              <BookOpenText aria-hidden />
              {canUpload ? "Add documents" : "Browse Knowledge Base"}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

function SourceChips({
  sources,
  activeIndex,
  onSelect,
}: {
  sources: Source[]
  activeIndex: number | null
  onSelect: (index: number | null) => void
}) {
  // One chip per document, pointing at its first cited passage.
  const documents = new Map<string, Source>()
  for (const source of sources) {
    if (!documents.has(source.document_id)) documents.set(source.document_id, source)
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-0.5 text-xs text-muted-foreground">
        {sources.length} {sources.length === 1 ? "source" : "sources"}
      </span>
      {[...documents.values()].map((source) => (
        <button
          key={source.document_id}
          type="button"
          onClick={() => onSelect(source.index)}
          className={cn(
            "inline-flex h-6 max-w-56 items-center gap-1.5 rounded-md border bg-card px-2 text-xs text-muted-foreground transition-colors outline-none hover:border-primary/40 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
            activeIndex === source.index && "border-primary/50 text-foreground",
          )}
        >
          <span className="font-semibold text-accent-foreground tabular-nums">{source.index}</span>
          <span className="truncate">{source.filename}</span>
        </button>
      ))}
    </div>
  )
}

/** The answer as plain text, with its numbered sources listed after it. */
function answerWithSources(message: ChatMessage): string {
  if (message.sources.length === 0) return message.content
  const sources = message.sources.map(
    (source) =>
      `[${source.index}] ${source.filename}, ${formatLocation(source.page, source.chunk_index)}`,
  )
  return [message.content, "", "Sources:", ...sources].join("\n")
}

function CopyAnswer({ message }: { message: ChatMessage }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])
  return (
    <Button
      variant="ghost"
      size="xs"
      className="text-muted-foreground"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(answerWithSources(message))
          setCopied(true)
        } catch {
          toast.error("Couldn't copy the answer", {
            description: "Your browser blocked clipboard access.",
          })
        }
      }}
    >
      {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
    </Button>
  )
}

function AssistantMessage({
  message,
  citation,
  onCite,
  canUpload,
  scopeLabel,
}: {
  message: ChatMessage
  citation: Citation | null
  onCite: (citation: Citation) => void
  canUpload: boolean
  scopeLabel?: string
}) {
  const selected = citation?.messageId === message.id
  return (
    <div className="flex gap-3">
      <AssistantAvatar className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-3">
        {message.insufficient_context ? (
          <InsufficientContext canUpload={canUpload} scopeLabel={scopeLabel} />
        ) : (
          <>
            <CitationText
              text={message.content}
              sources={message.sources}
              activeIndex={selected ? citation.sourceIndex : null}
              onCite={(sourceIndex) => onCite({ messageId: message.id, sourceIndex })}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              {message.sources.length > 0 ? (
                <SourceChips
                  sources={message.sources}
                  activeIndex={selected ? citation.sourceIndex : null}
                  onSelect={(sourceIndex) => onCite({ messageId: message.id, sourceIndex })}
                />
              ) : (
                <span />
              )}
              <CopyAnswer message={message} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-muted px-4 py-2.5 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    </div>
  )
}

function PendingAnswer() {
  return (
    <div className="flex gap-3" role="status">
      <AssistantAvatar className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-3">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          Searching your documents and writing an answer
          <ThinkingDots />
        </p>
        <div className="space-y-2" aria-hidden>
          <Skeleton className="h-3.5 w-11/12" />
          <Skeleton className="h-3.5 w-4/5" />
          <Skeleton className="h-3.5 w-2/3" />
        </div>
      </div>
    </div>
  )
}

export function MessageThread({
  messages,
  pendingQuestion,
  citation,
  onCite,
  canUpload,
  scopeLabel,
}: {
  messages: ChatMessage[]
  pendingQuestion: string | null
  citation: Citation | null
  onCite: (citation: Citation) => void
  canUpload: boolean
  /** The documents a scoped conversation searches, for messages that mention its scope. */
  scopeLabel?: string
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [messages.length, pendingQuestion])

  return (
    <div role="log" aria-label="Conversation" aria-live="polite" className="space-y-8">
      {messages.map((message) =>
        message.role === "user" ? (
          <UserMessage key={message.id} content={message.content} />
        ) : (
          <AssistantMessage
            key={message.id}
            message={message}
            citation={citation}
            onCite={onCite}
            canUpload={canUpload}
            scopeLabel={scopeLabel}
          />
        ),
      )}
      {pendingQuestion !== null && (
        <>
          <UserMessage content={pendingQuestion} />
          <PendingAnswer />
        </>
      )}
      <div ref={endRef} />
    </div>
  )
}

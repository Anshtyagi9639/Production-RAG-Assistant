"use client"

import { BookX, FileText, Loader2 } from "lucide-react"
import { useEffect, useRef } from "react"

import { CitationText } from "@/components/citations/citation-text"
import { Button } from "@/components/ui/button"
import type { ChatMessage } from "@/lib/api/types"
import { cn } from "@/lib/utils"

export interface Citation {
  messageId: string
  sourceIndex: number | null
}

function InsufficientContext() {
  return (
    <div className="max-w-2xl rounded-lg border border-dashed bg-muted/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <BookX className="size-4 text-muted-foreground" aria-hidden />
        Not enough information in the knowledge base
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        No passage was relevant enough, so no answer was generated. Try rephrasing, or upload a
        document that covers this topic.
      </p>
    </div>
  )
}

function AssistantMessage({
  message,
  citation,
  onCite,
}: {
  message: ChatMessage
  citation: Citation | null
  onCite: (citation: Citation) => void
}) {
  if (message.insufficient_context) return <InsufficientContext />
  const selected = citation?.messageId === message.id
  return (
    <div
      className={cn(
        "max-w-2xl space-y-2 rounded-lg border bg-card p-4",
        selected && "border-primary/40",
      )}
    >
      <CitationText
        text={message.content}
        sources={message.sources}
        activeIndex={selected ? citation.sourceIndex : null}
        onCite={(sourceIndex) => onCite({ messageId: message.id, sourceIndex })}
      />
      {message.sources.length > 0 && (
        <Button
          variant="ghost"
          size="xs"
          className="-ml-2 text-muted-foreground"
          onClick={() => onCite({ messageId: message.id, sourceIndex: null })}
        >
          <FileText aria-hidden />
          {message.sources.length} {message.sources.length === 1 ? "source" : "sources"}
        </Button>
      )}
    </div>
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="ml-auto max-w-xl rounded-lg bg-accent px-4 py-2.5 text-sm whitespace-pre-wrap text-accent-foreground">
      {content}
    </div>
  )
}

export function MessageThread({
  messages,
  pendingQuestion,
  citation,
  onCite,
}: {
  messages: ChatMessage[]
  pendingQuestion: string | null
  citation: Citation | null
  onCite: (citation: Citation) => void
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [messages.length, pendingQuestion])

  return (
    <div role="log" aria-label="Conversation" aria-live="polite" className="space-y-4">
      {messages.map((message) =>
        message.role === "user" ? (
          <UserMessage key={message.id} content={message.content} />
        ) : (
          <AssistantMessage
            key={message.id}
            message={message}
            citation={citation}
            onCite={onCite}
          />
        ),
      )}
      {pendingQuestion !== null && (
        <>
          <UserMessage content={pendingQuestion} />
          <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Searching your documents and writing an answer…
          </div>
        </>
      )}
      <div ref={endRef} />
    </div>
  )
}

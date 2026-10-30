"use client"

import { ArrowUp, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const MAX_LENGTH = 4000
const COUNTER_FROM = 3500

export function Composer({
  value,
  onChange,
  onSubmit,
  pending,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  pending: boolean
}) {
  const canSend = !pending && value.trim().length > 0

  return (
    <form
      className="rounded-2xl border bg-card p-2 shadow-sm transition-shadow focus-within:border-ring/60 focus-within:ring-3 focus-within:ring-ring/20"
      onSubmit={(event) => {
        event.preventDefault()
        if (canSend) onSubmit()
      }}
    >
      <Textarea
        aria-label="Ask a question about your documents"
        placeholder="Ask a question about your documents…"
        rows={2}
        maxLength={MAX_LENGTH}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          // Enter sends; Shift+Enter adds a new line.
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            if (canSend) onSubmit()
          }
        }}
        className="max-h-48 min-h-0 resize-none border-0 bg-transparent px-2 text-[0.9375rem] shadow-none focus-visible:ring-0"
      />
      <div className="flex items-center justify-between gap-2 px-2 pt-1">
        <p className="text-xs text-muted-foreground">
          <span className="hidden sm:inline">
            <kbd className="font-sans font-medium">Enter</kbd> to send ·{" "}
            <kbd className="font-sans font-medium">Shift + Enter</kbd> for a new line
          </span>
          {value.length >= COUNTER_FROM && (
            <span
              className={cn(
                "tabular-nums sm:ml-2",
                value.length >= MAX_LENGTH && "text-destructive",
              )}
            >
              {value.length} / {MAX_LENGTH}
            </span>
          )}
        </p>
        <Button
          type="submit"
          size="icon"
          className="rounded-full"
          disabled={!canSend}
          aria-label="Send"
        >
          {pending ? <Loader2 className="animate-spin" aria-hidden /> : <ArrowUp aria-hidden />}
        </Button>
      </div>
    </form>
  )
}

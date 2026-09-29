"use client"

import { Loader2, SendHorizonal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const MAX_LENGTH = 4000

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
      className="flex items-end gap-2 rounded-lg border bg-card p-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30"
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
        className="max-h-40 min-h-0 resize-none border-0 shadow-none focus-visible:ring-0"
      />
      <Button type="submit" size="icon" disabled={!canSend} aria-label="Send">
        {pending ? <Loader2 className="animate-spin" aria-hidden /> : <SendHorizonal aria-hidden />}
      </Button>
    </form>
  )
}

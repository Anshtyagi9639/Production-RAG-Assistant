import { Check, CircleAlert } from "lucide-react"

import { ThinkingDots } from "@/components/assistant/message-thread"
import type { AgentStep } from "@/lib/api/types"
import { formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"

// Node names from the LangGraph workflow (BUILD.md section 7), with what each step is for.
export const NODES: Record<string, { label: string; purpose: string }> = {
  classify: {
    label: "Understand the request",
    purpose: "Decides whether one lookup is enough or the task needs a plan.",
  },
  plan: {
    label: "Plan sub-questions",
    purpose: "Breaks the task into focused questions to search for.",
  },
  retrieve: {
    label: "Search the knowledge base",
    purpose: "Finds relevant passages in this workspace's documents.",
  },
  analyze: {
    label: "Analyze the evidence",
    purpose: "Drafts an answer from the passages and spots what is missing.",
  },
  need_more: {
    label: "Check for gaps",
    purpose: "Decides whether another search round is needed.",
  },
  validate: {
    label: "Verify citations",
    purpose: "Checks that every claim is backed by a cited passage.",
  },
  revise: { label: "Revise the answer", purpose: "Removes or fixes unsupported claims." },
  answer: { label: "Write the answer", purpose: "Answers directly from the passages found." },
  final_answer: { label: "Final answer", purpose: "Returns the verified answer with its sources." },
  error: { label: "Stopped", purpose: "The run ended because of an error." },
}

export function StepTimeline({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  return (
    <ol className="space-y-0" aria-label="Agent steps">
      {steps.map((step, position) => {
        const node = NODES[step.node] ?? { label: step.node, purpose: "" }
        const failed = step.status === "failed"
        const isLast = position === steps.length - 1 && !running
        return (
          <li key={`${step.node}-${position}`} className="relative flex gap-3 pb-5 last:pb-0">
            {!isLast && (
              <span className="absolute top-7 bottom-0 left-[13px] w-px bg-border" aria-hidden />
            )}
            <span
              className={cn(
                "relative flex size-7 shrink-0 items-center justify-center rounded-full border",
                failed
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-success/30 bg-success/10 text-success",
              )}
            >
              {failed ? (
                <CircleAlert className="size-3.5" aria-label="Failed" />
              ) : (
                <Check className="size-3.5" aria-label="Completed" />
              )}
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-sm font-medium">{node.label}</p>
                <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {formatDuration(step.duration_ms)}
                </span>
              </div>
              {step.summary && (
                <p className="mt-0.5 text-sm text-muted-foreground">{step.summary}</p>
              )}
            </div>
          </li>
        )
      })}
      {running && (
        <li className="relative flex gap-3" role="status">
          <span className="relative flex size-7 shrink-0 items-center justify-center rounded-full border border-info/30 bg-info/10 text-info">
            <span className="absolute inset-0 animate-ping rounded-full bg-info/20" aria-hidden />
            <span className="size-2 rounded-full bg-info" aria-hidden />
          </span>
          <div className="flex items-center gap-2 pt-1 text-sm text-muted-foreground">
            {steps.length === 0
              ? "Waiting for a worker to start the run"
              : "Working on the next step"}
            <ThinkingDots />
          </div>
        </li>
      )}
    </ol>
  )
}

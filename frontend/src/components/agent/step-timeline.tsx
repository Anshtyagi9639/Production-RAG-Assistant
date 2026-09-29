import { CheckCircle2, CircleAlert, Loader2 } from "lucide-react"

import type { AgentStep } from "@/lib/api/types"
import { formatDuration } from "@/lib/format"

// Node names from the LangGraph workflow (BUILD.md section 7).
const NODE_LABELS: Record<string, string> = {
  classify: "Classify request",
  plan: "Plan sub-questions",
  retrieve: "Retrieve evidence",
  analyze: "Analyze findings",
  need_more: "Check for gaps",
  validate: "Validate citations",
  revise: "Revise answer",
  answer: "Write answer",
  final_answer: "Finalize answer",
  error: "Error",
}

export function StepTimeline({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  return (
    <ol className="relative space-y-4 border-l pl-6" aria-label="Agent steps">
      {steps.map((step, position) => (
        <li key={`${step.node}-${position}`} className="relative">
          <span className="absolute top-0.5 -left-[2.05rem] flex size-5 items-center justify-center rounded-full bg-background">
            {step.status === "completed" ? (
              <CheckCircle2 className="size-4 text-primary" aria-label="Completed" />
            ) : (
              <CircleAlert className="size-4 text-destructive" aria-label="Failed" />
            )}
          </span>
          <div className="flex flex-wrap items-baseline gap-x-2">
            <p className="text-sm font-medium">{NODE_LABELS[step.node] ?? step.node}</p>
            <p className="text-xs text-muted-foreground tabular-nums">
              {formatDuration(step.duration_ms)}
            </p>
          </div>
          {step.summary && <p className="mt-0.5 text-sm text-muted-foreground">{step.summary}</p>}
        </li>
      ))}
      {running && (
        <li className="relative" role="status">
          <span className="absolute top-0.5 -left-[2.05rem] flex size-5 items-center justify-center rounded-full bg-background">
            <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
          </span>
          <p className="text-sm text-muted-foreground">
            {steps.length === 0 ? "Waiting to start…" : "Working…"}
          </p>
        </li>
      )}
    </ol>
  )
}

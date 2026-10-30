"use client"

import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  FileUp,
  Library,
  type LucideIcon,
  MessageSquareText,
  PartyPopper,
  X,
} from "lucide-react"
import Link from "next/link"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import type { Stats } from "@/lib/api/types"
import { plural } from "@/lib/format"
import { persistedValue, usePersistedValue } from "@/lib/session"
import { cn } from "@/lib/utils"

interface Step {
  title: string
  description: string
  icon: LucideIcon
  done: boolean
  /** Shown while this is the current step and it is waiting on something (e.g. processing). */
  status?: string
  action?: { label: string; href: string }
}

/** The product's workflow, with completion read from the workspace's real numbers. */
export function onboardingSteps(stats: Stats, canUpload: boolean): Step[] {
  const { total, by_status: byStatus } = stats.documents
  const inProgress = (byStatus.UPLOADED ?? 0) + (byStatus.PROCESSING ?? 0)
  const ready = byStatus.COMPLETED ?? 0
  const failed = byStatus.FAILED ?? 0
  return [
    {
      title: "Add documents",
      description: canUpload
        ? "Upload PDFs, Word files or text. They become your team's searchable knowledge."
        : "Only workspace owners can upload. Ask an owner to add your team's documents.",
      icon: FileUp,
      done: total > 0,
      action: canUpload ? { label: "Upload documents", href: "/knowledge" } : undefined,
    },
    {
      title: "Let them be indexed",
      description:
        "Each file is read and split into passages so answers can cite it. This takes under a minute.",
      icon: Library,
      done: ready > 0,
      status:
        inProgress > 0
          ? `${plural(inProgress, "document")} queued or processing now`
          : failed > 0
            ? `${plural(failed, "document")} failed. Open it to see why`
            : undefined,
      action: { label: "View Knowledge Base", href: "/knowledge" },
    },
    {
      title: "Ask the Assistant",
      description:
        "Ask in plain language. Every answer cites the passages it used, so you can check it.",
      icon: MessageSquareText,
      done: stats.conversations > 0,
      action: { label: "Ask a question", href: "/assistant" },
    },
    {
      title: "Run the Agent",
      description:
        "For bigger questions: it plans several searches, compares documents and verifies each claim.",
      icon: Bot,
      done: stats.agent_runs > 0,
      action: { label: "Run an analysis", href: "/agent" },
    },
  ]
}

/** Whether the guide is hidden in this workspace (remembered per browser). */
export function useOnboardingHidden(workspaceId: string) {
  const value = useMemo(
    () => persistedValue(`copilot.onboardingHidden.${workspaceId}`),
    [workspaceId],
  )
  const hidden = usePersistedValue(value) === "true"
  return [hidden, (next: boolean) => value.set(next ? "true" : null)] as const
}

function StepMarker({ index, state }: { index: number; state: "done" | "current" | "upcoming" }) {
  return (
    <span
      className={cn(
        "relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
        state === "done" && "border-success/30 bg-success text-white",
        state === "current" &&
          "border-primary bg-primary text-primary-foreground ring-4 ring-primary/15",
        state === "upcoming" && "bg-card text-muted-foreground",
      )}
    >
      {state === "done" ? <Check className="size-3.5" aria-hidden /> : index + 1}
    </span>
  )
}

const STATE_LABELS = { done: "Done", current: "Next step", upcoming: "Not started" }

/**
 * The getting-started guide: the four steps of the real workflow, each marked done, current or
 * upcoming from the workspace's data, with a link to where it happens. It can be collapsed, or
 * hidden and brought back from the dashboard header.
 */
export function GettingStarted({
  stats,
  canUpload,
  onHide,
}: {
  stats: Stats
  canUpload: boolean
  onHide: () => void
}) {
  const steps = onboardingSteps(stats, canUpload)
  const completed = steps.filter((step) => step.done).length
  const allDone = completed === steps.length
  const current = steps.findIndex((step) => !step.done)
  const [expanded, setExpanded] = useState(!allDone)

  return (
    <section
      aria-labelledby="getting-started-title"
      className="overflow-hidden rounded-xl border bg-card shadow-xs"
    >
      <header className="flex items-start gap-3 p-4 sm:px-5">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 id="getting-started-title" className="text-sm font-semibold">
              {allDone ? "You're all set" : "Get started in four steps"}
            </h2>
            <span className="text-xs text-muted-foreground tabular-nums">
              {completed} of {steps.length} complete
            </span>
          </div>
          <div
            className="h-1.5 max-w-xs overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Getting started progress"
            aria-valuemin={0}
            aria-valuemax={steps.length}
            aria-valuenow={completed}
          >
            <div
              className={cn(
                "h-full rounded-full transition-[width]",
                allDone ? "bg-success" : "bg-primary",
              )}
              style={{ width: `${(completed / steps.length) * 100}%` }}
            />
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls="getting-started-steps"
          >
            {expanded ? "Collapse" : "Show steps"}
            <ChevronDown
              className={cn("transition-transform", expanded && "rotate-180")}
              aria-hidden
            />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            className="text-muted-foreground"
            onClick={onHide}
            aria-label="Hide the getting started guide"
            title="Hide (you can bring it back from the dashboard header)"
          >
            <X aria-hidden />
          </Button>
        </div>
      </header>

      {allDone && !expanded && (
        // Its own full-width row, so it never wraps into a narrow column beside the buttons.
        <p className="-mt-1 flex items-start gap-1.5 px-4 pb-4 text-sm text-muted-foreground sm:px-5">
          <PartyPopper className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
          Your workspace is set up. Everything below is live data from it.
        </p>
      )}
      {expanded && (
        <ol
          id="getting-started-steps"
          // A 1px gap over a border-coloured background draws the dividers at every breakpoint.
          className="grid grid-cols-1 gap-px border-t bg-border sm:grid-cols-2 lg:grid-cols-4"
        >
          {steps.map((step, index) => {
            const state = step.done ? "done" : index === current ? "current" : "upcoming"
            const Icon = step.icon
            return (
              <li
                key={step.title}
                aria-current={state === "current" ? "step" : undefined}
                className={cn(
                  "flex flex-col gap-3 bg-card p-4 sm:px-5",
                  state === "current" && "bg-[color-mix(in_oklch,var(--accent)_55%,var(--card))]",
                )}
              >
                <div className="flex items-center gap-2.5">
                  <StepMarker index={index} state={state} />
                  <span
                    className={cn(
                      "text-xs font-medium",
                      state === "done" && "text-success",
                      state === "current" && "text-primary",
                      state === "upcoming" && "text-muted-foreground",
                    )}
                  >
                    {STATE_LABELS[state]}
                  </span>
                  <Icon className="ml-auto size-4 text-muted-foreground" aria-hidden />
                </div>
                <div className="flex-1 space-y-1">
                  <h3
                    className={cn(
                      "text-sm font-semibold",
                      state === "done" && "text-muted-foreground",
                    )}
                  >
                    {step.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {step.description}
                  </p>
                  {state === "current" && step.status && (
                    <p className="text-xs font-medium text-foreground">{step.status}</p>
                  )}
                </div>
                {step.action && state !== "done" && (
                  <Button
                    asChild
                    size="sm"
                    variant={state === "current" ? "default" : "outline"}
                    className="self-start"
                  >
                    <Link href={step.action.href}>
                      {step.action.label}
                      <ArrowRight aria-hidden />
                    </Link>
                  </Button>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

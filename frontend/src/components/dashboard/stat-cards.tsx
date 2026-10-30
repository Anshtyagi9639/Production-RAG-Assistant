"use client"

import {
  ArrowUpRight,
  Bot,
  CheckCircle2,
  CircleAlert,
  Coins,
  Info,
  Library,
  Loader2,
  type LucideIcon,
  MessagesSquare,
} from "lucide-react"
import Link from "next/link"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { Stats } from "@/lib/api/types"
import { formatNumber, plural } from "@/lib/format"
import { cn } from "@/lib/utils"

function InfoHint({ label, text }: { label: string; text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          // Inside a card link: a click must explain, not navigate.
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
          }}
          className="relative z-10 -m-1 rounded-full p-1 text-muted-foreground/70 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
          aria-label={`About ${label}: ${text}`}
        >
          <Info className="size-3.5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-60 text-pretty">
        {text}
      </TooltipContent>
    </Tooltip>
  )
}

function StatCard({
  icon: Icon,
  label,
  hint,
  value,
  children,
  href,
}: {
  icon: LucideIcon
  label: string
  hint: string
  value: string
  children: React.ReactNode
  href?: string
}) {
  return (
    <div
      className={cn(
        "group/card relative flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs transition-colors sm:p-5",
        href && "focus-within:ring-3 focus-within:ring-ring/40 hover:border-primary/30",
      )}
    >
      <div className="flex items-center gap-2">
        <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Icon className="size-3.5" aria-hidden />
        </span>
        {href ? (
          // The link covers the card; the hint button sits above it.
          <Link
            href={href}
            className="text-sm font-medium text-muted-foreground outline-none group-hover/card:text-foreground after:absolute after:inset-0 after:rounded-xl"
          >
            {label}
          </Link>
        ) : (
          <h3 className="text-sm font-medium text-muted-foreground">{label}</h3>
        )}
        <InfoHint label={label} text={hint} />
        {href && (
          <ArrowUpRight
            className="ml-auto size-4 text-muted-foreground/60 transition-colors group-hover/card:text-primary"
            aria-hidden
          />
        )}
      </div>
      <p className="text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      <div className="text-xs text-muted-foreground">{children}</div>
    </div>
  )
}

/** The workspace's headline numbers, from GET /api/stats. */
export function StatCards({
  stats,
  agentOutcomes,
}: {
  stats: Stats
  /** Completed / failed agent runs in the last 30 days, from the activity log (null while loading). */
  agentOutcomes: { completed: number; failed: number } | null
}) {
  const { total, by_status: byStatus } = stats.documents
  const ready = byStatus.COMPLETED ?? 0
  const inProgress = (byStatus.UPLOADED ?? 0) + (byStatus.PROCESSING ?? 0)
  const failed = byStatus.FAILED ?? 0
  const readyShare = total > 0 ? Math.round((ready / total) * 100) : 0

  return (
    <section
      aria-label="Workspace summary"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
    >
      <StatCard
        icon={Library}
        label="Documents"
        hint="Documents in the knowledge base that the Assistant and Agent can search. A document is ready once it has been read and indexed."
        value={formatNumber(total)}
        href="/knowledge"
      >
        {total === 0 ? (
          "No documents yet"
        ) : (
          <div className="space-y-2">
            <p>
              <span className="font-medium text-foreground tabular-nums">
                {formatNumber(ready)}
              </span>{" "}
              of {plural(total, "document")} ready to search
            </p>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
              <div className="h-full rounded-full bg-success" style={{ width: `${readyShare}%` }} />
            </div>
            {(inProgress > 0 || failed > 0) && (
              <p className="flex flex-wrap gap-x-3 gap-y-1">
                {inProgress > 0 && (
                  <span className="inline-flex items-center gap-1 text-info">
                    <Loader2 className="size-3 animate-spin" aria-hidden />
                    {formatNumber(inProgress)} in progress
                  </span>
                )}
                {failed > 0 && (
                  <span className="inline-flex items-center gap-1 text-destructive">
                    <CircleAlert className="size-3" aria-hidden />
                    {formatNumber(failed)} failed
                  </span>
                )}
              </p>
            )}
          </div>
        )}
      </StatCard>
      <StatCard
        icon={MessagesSquare}
        label="Conversations"
        hint="Your chats with the Assistant in this workspace. Each answer links to the passages it was based on."
        value={formatNumber(stats.conversations)}
        href="/assistant"
      >
        {stats.conversations === 0 ? "Ask your first question" : "Grounded answers with citations"}
      </StatCard>
      <StatCard
        icon={Bot}
        label="Agent runs"
        hint="Multi-step analyses. The Agent plans searches, compares documents and checks every claim against a source."
        value={formatNumber(stats.agent_runs)}
        href="/agent"
      >
        {agentOutcomes && agentOutcomes.completed + agentOutcomes.failed > 0 ? (
          <p className="flex flex-wrap gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1 text-success">
              <CheckCircle2 className="size-3" aria-hidden />
              {formatNumber(agentOutcomes.completed)} completed
            </span>
            {agentOutcomes.failed > 0 && (
              <span className="inline-flex items-center gap-1 text-destructive">
                <CircleAlert className="size-3" aria-hidden />
                {formatNumber(agentOutcomes.failed)} failed
              </span>
            )}
            <span>in 30 days</span>
          </p>
        ) : stats.agent_runs === 0 ? (
          "Try it on a question that spans documents"
        ) : (
          "No runs finished in the last 30 days"
        )}
      </StatCard>
      <StatCard
        icon={Coins}
        label="Tokens used"
        hint="Language-model usage for answers and agent runs in this workspace, all time. Tokens are what the AI provider bills for."
        value={formatNumber(stats.tokens.total)}
      >
        {formatNumber(stats.tokens.prompt)} in · {formatNumber(stats.tokens.completion)} out
      </StatCard>
    </section>
  )
}

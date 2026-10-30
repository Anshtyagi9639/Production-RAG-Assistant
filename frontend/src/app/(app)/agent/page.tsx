"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import {
  Bot,
  CircleAlert,
  Clock,
  Coins,
  ListChecks,
  Loader2,
  Play,
  TriangleAlert,
  Workflow,
} from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { NODES, StepTimeline } from "@/components/agent/step-timeline"
import { useWorkspace } from "@/components/app/workspace-context"
import { FormError } from "@/components/auth/form-error"
import { CitationText } from "@/components/citations/citation-text"
import { SourcesList } from "@/components/citations/sources-list"
import { PageHeader } from "@/components/page-header"
import { ErrorState } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { agentApi } from "@/lib/api/endpoints"
import type { AgentRun, AgentRunStatus } from "@/lib/api/types"
import { formatDuration, formatNumber, formatRelative } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const POLL_INTERVAL_MS = 1500
const MAX_LENGTH = 4000

const EXAMPLES = [
  "Compare the approval rules across our policies and list any conflicts by document.",
  "Summarize every deadline mentioned in our documents, grouped by document.",
]

// The steps of a complex run, in order (the graph in app/agents/knowledge_agent.py).
const WORKFLOW = ["classify", "plan", "retrieve", "analyze", "validate", "final_answer"]

const STATUS: Record<AgentRunStatus, { label: string; tone: string }> = {
  QUEUED: { label: "Queued", tone: "border-border bg-muted text-muted-foreground" },
  RUNNING: { label: "Running", tone: "border-info/20 bg-info/8 text-info" },
  COMPLETED: { label: "Completed", tone: "border-success/20 bg-success/8 text-success" },
  FAILED: { label: "Failed", tone: "border-destructive/20 bg-destructive/8 text-destructive" },
}

function isActive(run: AgentRun | undefined): boolean {
  return run?.status === "QUEUED" || run?.status === "RUNNING"
}

function RunStatus({ status }: { status: AgentRunStatus }) {
  const { label, tone } = STATUS[status]
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium",
        tone,
      )}
    >
      {status === "RUNNING" || status === "QUEUED" ? (
        <Loader2 className="size-3 animate-spin" aria-hidden />
      ) : status === "FAILED" ? (
        <CircleAlert className="size-3" aria-hidden />
      ) : (
        <ListChecks className="size-3" aria-hidden />
      )}
      {label}
    </span>
  )
}

function Card({
  title,
  icon: Icon,
  action,
  children,
  className,
}: {
  title: string
  icon?: typeof Bot
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={cn("rounded-xl border bg-card shadow-xs", className)} aria-label={title}>
      <header className="flex items-center gap-2 border-b px-5 py-3">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden />}
        <h2 className="flex-1 text-sm font-semibold">{title}</h2>
        {action}
      </header>
      <div className="p-5">{children}</div>
    </section>
  )
}

function RunMeta({ run }: { run: AgentRun }) {
  const duration =
    run.started_at && run.finished_at
      ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
      : null
  const items = [
    {
      icon: Workflow,
      label: run.classification
        ? `${run.classification === "complex" ? "Complex" : "Simple"} request`
        : "Classifying…",
    },
    { icon: ListChecks, label: `${run.trace.length} ${run.trace.length === 1 ? "step" : "steps"}` },
    {
      icon: Clock,
      label:
        duration !== null ? formatDuration(duration) : `Started ${formatRelative(run.created_at)}`,
    },
    { icon: Coins, label: `${formatNumber(run.prompt_tokens + run.completion_tokens)} tokens` },
  ]
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1.5">
      {items.map(({ icon: Icon, label }) => (
        <li key={label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Icon className="size-3.5" aria-hidden />
          {label}
        </li>
      ))}
    </ul>
  )
}

function RunResult({ run }: { run: AgentRun }) {
  const [activeSource, setActiveSource] = useState<number | null>(null)
  return (
    <div className="space-y-6">
      <section aria-label="Run" className="rounded-xl border bg-card p-5 shadow-xs">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <RunStatus status={run.status} />
          <h2 className="sr-only">Run</h2>
        </div>
        <p className="mb-3 text-[0.9375rem] font-medium whitespace-pre-wrap">{run.request}</p>
        <RunMeta run={run} />
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          {run.status === "FAILED" && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertTitle>The agent run failed</AlertTitle>
              <AlertDescription>{run.error ?? "No reason was recorded."}</AlertDescription>
            </Alert>
          )}

          {run.final_answer !== null && (
            <Card title="Answer" icon={Bot}>
              <div className="space-y-4">
                {run.is_partial && (
                  <Alert className="border-warning/30 bg-warning/5">
                    <TriangleAlert className="text-warning" aria-hidden />
                    <AlertTitle>Partial answer</AlertTitle>
                    <AlertDescription>
                      Some claims could not be matched to a cited passage after one revision. Treat
                      uncited statements with care.
                    </AlertDescription>
                  </Alert>
                )}
                <CitationText
                  text={run.final_answer}
                  sources={run.sources}
                  activeIndex={activeSource}
                  onCite={setActiveSource}
                />
              </div>
            </Card>
          )}

          <Card title="Execution" icon={Workflow}>
            <StepTimeline steps={run.trace} running={isActive(run)} />
          </Card>
        </div>

        <section aria-labelledby="agent-sources-heading" className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 id="agent-sources-heading" className="text-sm font-semibold">
              Evidence
            </h2>
            {run.sources.length > 0 && (
              <span className="text-xs text-muted-foreground">
                {run.sources.length} cited {run.sources.length === 1 ? "passage" : "passages"}
              </span>
            )}
          </div>
          {run.sources.length > 0 ? (
            <SourcesList sources={run.sources} activeIndex={activeSource} />
          ) : (
            <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
              {isActive(run)
                ? "Cited passages appear when the answer is ready."
                : "This answer cites no passages."}
            </p>
          )}
        </section>
      </div>
    </div>
  )
}

function HowItWorks() {
  return (
    <section aria-label="How the agent works" className="rounded-xl border bg-card p-5 shadow-xs">
      <h2 className="text-sm font-semibold">How a run works</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Each step is shown live while the agent works. Only this workspace&apos;s documents are
        searched.
      </p>
      <ol className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {WORKFLOW.map((node, index) => (
          <li key={node} className="flex gap-3 rounded-lg border p-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-semibold text-accent-foreground tabular-nums">
              {index + 1}
            </span>
            <div>
              <p className="text-sm font-medium">{NODES[node].label}</p>
              <p className="text-xs text-muted-foreground">{NODES[node].purpose}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Agent() {
  const { workspace } = useWorkspace()
  const router = useRouter()
  const runId = useSearchParams().get("run")
  const [request, setRequest] = useState("")

  const run = useQuery({
    queryKey: queryKeys.agentRun(workspace.id, runId ?? ""),
    queryFn: () => agentApi.getRun(workspace.id, runId ?? ""),
    enabled: runId !== null,
    refetchInterval: (query) => (isActive(query.state.data) ? POLL_INTERVAL_MS : false),
  })

  const start = useMutation({
    mutationFn: (text: string) => agentApi.run(workspace.id, text),
    onSuccess: (created) => {
      setRequest("")
      router.push(`/agent?run=${created.id}`)
    },
  })
  const busy = start.isPending || isActive(run.data)

  return (
    <>
      <PageHeader
        title="Agent"
        badge={
          <span className="inline-flex h-6 items-center gap-1 rounded-full border border-primary/20 bg-accent px-2.5 text-xs font-medium text-accent-foreground">
            <Workflow className="size-3" aria-hidden />
            Multi-step analysis
          </span>
        }
        description="For tasks that span several documents. The agent plans sub-questions, searches in rounds, verifies that every claim is backed by a cited passage, and shows each step. It takes longer than the Assistant."
      />

      <section aria-label="New run" className="mb-6 rounded-xl border bg-card p-4 shadow-xs sm:p-5">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            if (request.trim()) start.mutate(request.trim())
          }}
        >
          <Label htmlFor="agent-request">Task</Label>
          <Textarea
            id="agent-request"
            rows={3}
            maxLength={MAX_LENGTH}
            placeholder="Describe a task that needs several documents…"
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            className="resize-y text-[0.9375rem]"
          />
          <FormError error={start.error} />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setRequest(example)}
                  className="max-w-full truncate rounded-full border px-3 py-1 text-xs text-muted-foreground transition-colors outline-none hover:border-primary/40 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 sm:max-w-72"
                  title={example}
                >
                  {example}
                </button>
              ))}
            </div>
            <Button type="submit" className="shrink-0" disabled={busy || !request.trim()}>
              {start.isPending ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Play aria-hidden />
              )}
              Run agent
            </Button>
          </div>
        </form>
      </section>

      {!runId && <HowItWorks />}
      {runId && run.isPending && (
        <div role="status" aria-label="Loading agent run" className="space-y-6">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      )}
      {runId && run.isError && (
        <ErrorState
          title="Couldn't load this run"
          error={run.error}
          onRetry={() => run.refetch()}
        />
      )}
      {run.isSuccess && <RunResult key={run.data.id} run={run.data} />}
    </>
  )
}

export default function AgentPage() {
  return (
    <Suspense>
      <Agent />
    </Suspense>
  )
}

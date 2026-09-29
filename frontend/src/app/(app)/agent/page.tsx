"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import { Bot, CircleAlert, Loader2, Play, TriangleAlert } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { StepTimeline } from "@/components/agent/step-timeline"
import { useWorkspace } from "@/components/app/workspace-context"
import { FormError } from "@/components/auth/form-error"
import { CitationText } from "@/components/citations/citation-text"
import { SourcesList } from "@/components/citations/sources-list"
import { PageHeader } from "@/components/page-header"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { agentApi } from "@/lib/api/endpoints"
import type { AgentRun, AgentRunStatus } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"

const POLL_INTERVAL_MS = 1500
const MAX_LENGTH = 4000

const STATUS_TEXT: Record<AgentRunStatus, string> = {
  QUEUED: "Queued",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
}

function isActive(run: AgentRun | undefined): boolean {
  return run?.status === "QUEUED" || run?.status === "RUNNING"
}

function RunResult({ run }: { run: AgentRun }) {
  const [activeSource, setActiveSource] = useState<number | null>(null)
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2">
              <h2>Run</h2>
              <Badge variant={run.status === "FAILED" ? "destructive" : "outline"}>
                {STATUS_TEXT[run.status]}
              </Badge>
              {run.classification && (
                <Badge variant="secondary">
                  {run.classification === "complex" ? "Complex request" : "Simple request"}
                </Badge>
              )}
            </CardTitle>
            <p className="text-sm whitespace-pre-wrap text-muted-foreground">{run.request}</p>
          </CardHeader>
          <CardContent>
            <StepTimeline steps={run.trace} running={isActive(run)} />
          </CardContent>
        </Card>

        {run.status === "FAILED" && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>The agent run failed</AlertTitle>
            <AlertDescription>{run.error ?? "No reason was recorded."}</AlertDescription>
          </Alert>
        )}

        {run.final_answer !== null && (
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>Answer</h2>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {run.is_partial && (
                <Alert>
                  <TriangleAlert aria-hidden />
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
              <p className="text-xs text-muted-foreground tabular-nums">
                {formatNumber(run.prompt_tokens + run.completion_tokens)} tokens used
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {run.sources.length > 0 && (
        <section aria-labelledby="agent-sources-heading" className="space-y-3">
          <h2 id="agent-sources-heading" className="text-sm font-semibold">
            Sources
          </h2>
          <SourcesList sources={run.sources} activeIndex={activeSource} />
        </section>
      )}
    </div>
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

  return (
    <>
      <PageHeader
        title="Agent"
        badge={<Badge variant="outline">Multi-step analysis</Badge>}
        description="For questions that span several documents. The agent breaks the task into sub-questions, retrieves evidence in rounds, checks that every claim is backed by a cited passage, and shows each step. It is slower than the Assistant."
      />

      <Card className="mb-6">
        <CardContent>
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
              placeholder="e.g. Compare the data retention rules across our policies and list any conflicts by document."
              value={request}
              onChange={(event) => setRequest(event.target.value)}
            />
            <FormError error={start.error} />
            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={start.isPending || !request.trim() || isActive(run.data)}
              >
                {start.isPending ? (
                  <Loader2 className="animate-spin" aria-hidden />
                ) : (
                  <Play aria-hidden />
                )}
                Run agent
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {!runId && (
        <EmptyState
          icon={Bot}
          title="No run selected"
          description="Describe a task above. Each step appears here as the agent works."
        />
      )}
      {runId && run.isPending && <ListSkeleton rows={4} label="Loading agent run" />}
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

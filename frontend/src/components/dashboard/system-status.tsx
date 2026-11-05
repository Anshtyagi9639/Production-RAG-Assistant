"use client"

import { useQuery } from "@tanstack/react-query"
import { CircleAlert, CircleCheck, CircleDashed } from "lucide-react"

import { healthApi } from "@/lib/api/endpoints"
import type { HealthReport } from "@/lib/api/types"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const HEALTH_POLL_MS = 30_000

/** The live /api/health report, shared by every component that shows it. */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: healthApi.get,
    refetchInterval: HEALTH_POLL_MS,
    staleTime: HEALTH_POLL_MS / 2,
  })
}

/** True or false once the report has loaded; undefined while unknown. */
export function useWorkerRunning(): boolean | undefined {
  const health = useHealth()
  const worker = health.data?.checks.worker
  return worker === undefined ? undefined : worker.status === "ok"
}

const COMPONENTS: { key: string; label: string; role: string }[] = [
  { key: "mongodb", label: "Database", role: "Documents, conversations and accounts" },
  { key: "redis", label: "Queue and cache", role: "Background jobs and rate limits" },
  { key: "qdrant", label: "Vector index", role: "Semantic search over passages" },
  { key: "worker", label: "Processing worker", role: "Extracts and indexes uploads" },
]

const PROBLEM: Record<string, string> = {
  timeout: "Not responding",
  unreachable: "Unreachable",
  authentication_failed: "Sign-in rejected",
  not_running: "Not running",
}

function Row({ label, role, check }: { label: string; role: string; check?: Check }) {
  const ok = check?.status === "ok"
  const Icon = check === undefined ? CircleDashed : ok ? CircleCheck : CircleAlert
  return (
    <li className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
      <Icon
        className={cn(
          "size-4 shrink-0",
          check === undefined && "text-muted-foreground",
          ok && "text-success",
          check !== undefined && !ok && "text-destructive",
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{label}</p>
        <p className="truncate text-xs text-muted-foreground">{role}</p>
      </div>
      <span
        className={cn(
          "shrink-0 text-xs tabular-nums",
          ok ? "text-muted-foreground" : "font-medium text-destructive",
          check === undefined && "font-normal text-muted-foreground",
        )}
      >
        {check === undefined
          ? "Not reported"
          : ok
            ? `${Math.round(check.latency_ms)} ms`
            : (PROBLEM[check.error ?? ""] ?? "Unavailable")}
      </span>
    </li>
  )
}

type Check = HealthReport["checks"][string]

/** Each backend dependency's live status from /api/health, refreshed every 30 s. */
export function SystemStatus() {
  const health = useHealth()
  return (
    <section
      className="flex flex-col rounded-xl border bg-card shadow-xs"
      aria-labelledby="panel-system-status"
    >
      <header className="flex items-start justify-between gap-3 border-b px-4 py-3 sm:px-5">
        <div className="space-y-0.5">
          <h2 id="panel-system-status" className="text-sm font-semibold">
            System status
          </h2>
          <p className="text-xs text-muted-foreground">Live checks, refreshed every 30 seconds.</p>
        </div>
        {health.data && (
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-medium",
              health.data.status === "ok" && health.data.checks.worker?.status !== "unavailable"
                ? "border-success/30 bg-success/10 text-success"
                : "border-destructive/30 bg-destructive/10 text-destructive",
            )}
          >
            {health.data.status === "ok" && health.data.checks.worker?.status !== "unavailable"
              ? "All systems working"
              : "Needs attention"}
          </span>
        )}
      </header>
      <div className="p-4 sm:p-5">
        {health.isError ? (
          <p className="text-sm text-muted-foreground">
            The status check couldn&apos;t reach the server.
          </p>
        ) : (
          <ul className="divide-y divide-border/60" aria-busy={health.isPending}>
            {COMPONENTS.map(({ key, label, role }) => (
              <Row
                key={key}
                label={label}
                role={role}
                check={health.isPending ? undefined : health.data?.checks[key]}
              />
            ))}
          </ul>
        )}
        {health.data?.checks.worker?.status === "unavailable" && (
          <p className="mt-3 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-muted-foreground">
            New uploads wait in the queue until the worker is started. Locally, run it with{" "}
            <code className="font-mono text-foreground">
              python -m arq app.workers.settings.WorkerSettings
            </code>
            .
          </p>
        )}
      </div>
    </section>
  )
}

"use client"

import { useQuery } from "@tanstack/react-query"
import { FileUp, History } from "lucide-react"
import Link from "next/link"

import { ActivityList } from "@/components/activity/activity-list"
import { useWorkspace } from "@/components/app/workspace-context"
import { STATUS_LABELS, StatusBadge } from "@/components/documents/status-badge"
import { PageHeader } from "@/components/page-header"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { activityApi, statsApi } from "@/lib/api/endpoints"
import type { DocumentStatus, Stats } from "@/lib/api/types"
import { formatNumber } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"

const RECENT_ACTIVITY = 8
const STATUSES: DocumentStatus[] = ["COMPLETED", "PROCESSING", "UPLOADED", "FAILED"]

function StatCard({
  label,
  value,
  children,
}: {
  label: string
  value: number
  children?: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-3xl font-semibold tabular-nums">{formatNumber(value)}</p>
        {children}
      </CardContent>
    </Card>
  )
}

function StatCards({ stats }: { stats: Stats }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Documents" value={stats.documents.total}>
        <ul className="flex flex-wrap gap-1.5" aria-label="Documents by status">
          {STATUSES.map((status) => (
            <li key={status} className="flex items-center gap-1 text-xs">
              <StatusBadge status={status} />
              <span className="tabular-nums" aria-label={`${STATUS_LABELS[status]} count`}>
                {formatNumber(stats.documents.by_status[status] ?? 0)}
              </span>
            </li>
          ))}
        </ul>
      </StatCard>
      <StatCard label="Conversations" value={stats.conversations} />
      <StatCard label="Agent runs" value={stats.agent_runs} />
      <StatCard label="Tokens used" value={stats.tokens.total}>
        <p className="text-xs text-muted-foreground">
          {formatNumber(stats.tokens.prompt)} prompt · {formatNumber(stats.tokens.completion)}{" "}
          completion
        </p>
      </StatCard>
    </div>
  )
}

function StatCardsSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading stats"
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
    >
      {Array.from({ length: 4 }, (_, index) => (
        <Skeleton key={index} className="h-36" />
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { workspace } = useWorkspace()
  const stats = useQuery({
    queryKey: queryKeys.stats(workspace.id),
    queryFn: () => statsApi.get(workspace.id),
  })
  const activity = useQuery({
    queryKey: queryKeys.activity(workspace.id, 1, RECENT_ACTIVITY),
    queryFn: () => activityApi.list(workspace.id, 1, RECENT_ACTIVITY),
  })

  return (
    <>
      <PageHeader title="Dashboard" description={`Usage in ${workspace.name}.`} />

      <section aria-labelledby="stats-heading" className="space-y-4">
        <h2 id="stats-heading" className="sr-only">
          Usage
        </h2>
        {stats.isPending && <StatCardsSkeleton />}
        {stats.isError && (
          <ErrorState
            title="Couldn't load stats"
            error={stats.error}
            onRetry={() => stats.refetch()}
          />
        )}
        {stats.isSuccess && <StatCards stats={stats.data} />}
        {stats.isSuccess && stats.data.documents.total === 0 && (
          <EmptyState
            icon={FileUp}
            title="No documents yet"
            description="Upload internal documents to start searching and asking questions."
            action={
              <Button asChild>
                <Link href="/knowledge">Go to Knowledge Base</Link>
              </Button>
            }
          />
        )}
      </section>

      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>
            <h2>Recent activity</h2>
          </CardTitle>
          <Button asChild variant="ghost" size="sm">
            <Link href="/activity">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {activity.isPending && <ListSkeleton rows={4} label="Loading activity" />}
          {activity.isError && (
            <ErrorState
              title="Couldn't load activity"
              error={activity.error}
              onRetry={() => activity.refetch()}
            />
          )}
          {activity.isSuccess && activity.data.items.length === 0 && (
            <EmptyState
              icon={History}
              title="No activity yet"
              description="Uploads, questions and agent runs will show up here."
            />
          )}
          {activity.isSuccess && activity.data.items.length > 0 && (
            <ActivityList entries={activity.data.items} />
          )}
        </CardContent>
      </Card>
    </>
  )
}

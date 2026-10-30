"use client"

import { useQuery } from "@tanstack/react-query"
import {
  ArrowRight,
  Bot,
  ChevronRight,
  FileUp,
  History,
  Library,
  type LucideIcon,
  MessageSquarePlus,
  MessagesSquare,
  Sparkles,
} from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { ActivityList } from "@/components/activity/activity-list"
import { useWorkspace } from "@/components/app/workspace-context"
import { ActivityChart } from "@/components/dashboard/activity-chart"
import { GettingStarted, useOnboardingHidden } from "@/components/dashboard/getting-started"
import { StatCards } from "@/components/dashboard/stat-cards"
import {
  MAX_RANGE_DAYS,
  rangeStart,
  useDashboardActivity,
} from "@/components/dashboard/use-dashboard-activity"
import { FileTypeIcon } from "@/components/documents/file-type-icon"
import {
  isInProgress,
  STATUS_LABELS,
  STATUS_TONES,
  StatusBadge,
} from "@/components/documents/status-badge"
import { PageHeader } from "@/components/page-header"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { chatApi, documentsApi, statsApi } from "@/lib/api/endpoints"
import type { DocumentStatus, Stats } from "@/lib/api/types"
import { formatBytes, formatNumber, formatRelative } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const RECENT = 5
const RECENT_ACTIVITY = 8
const RANGES = [7, 14, MAX_RANGE_DAYS] as const
const STATUSES: DocumentStatus[] = ["COMPLETED", "PROCESSING", "UPLOADED", "FAILED"]
/** While documents are being processed, keep the numbers current without a manual refresh. */
const PROCESSING_POLL_MS = 5000

function Panel({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const id = `panel-${title.toLowerCase().replaceAll(/\W+/g, "-")}`
  return (
    <section
      className={cn("flex flex-col rounded-xl border bg-card shadow-xs", className)}
      aria-labelledby={id}
    >
      <header className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2 border-b px-4 py-3 sm:px-5">
        <div className="min-w-0 space-y-0.5">
          <h2 id={id} className="text-sm font-semibold">
            {title}
          </h2>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {action}
      </header>
      <div className="flex-1 p-4 sm:p-5">{children}</div>
    </section>
  )
}

function ViewAll({ href, label = "View all" }: { href: string; label?: string }) {
  return (
    <Button asChild variant="ghost" size="sm" className="-mr-2 text-muted-foreground">
      <Link href={href}>
        {label}
        <ArrowRight aria-hidden />
      </Link>
    </Button>
  )
}

function RangePicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div role="group" aria-label="Date range" className="flex rounded-lg border bg-muted/50 p-0.5">
      {RANGES.map((days) => (
        <button
          key={days}
          type="button"
          onClick={() => onChange(days)}
          aria-pressed={value === days}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60",
            value === days && "bg-card text-foreground shadow-xs",
          )}
        >
          {days} days
        </button>
      ))}
    </div>
  )
}

function UsagePanel({ workspaceId, className }: { workspaceId: string; className?: string }) {
  const [days, setDays] = useState<number>(14)
  const activity = useDashboardActivity(workspaceId)
  const since = rangeStart(days).getTime()
  const inRange = activity.data?.entries.filter(
    (entry) => new Date(entry.created_at).getTime() >= since,
  )

  return (
    <Panel
      title="Usage over time"
      description="What your team did each day in this workspace."
      action={<RangePicker value={days} onChange={setDays} />}
      className={className}
    >
      {activity.isPending && (
        <div role="status" aria-label="Loading usage chart" className="space-y-4">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-44 w-full" />
        </div>
      )}
      {activity.isError && (
        <ErrorState
          title="Couldn't load usage"
          error={activity.error}
          onRetry={() => activity.refetch()}
        />
      )}
      {inRange && (
        // Refetching keeps the current chart on screen, dimmed, instead of a skeleton.
        <div className={cn("transition-opacity", activity.isFetching && "opacity-60")}>
          <ActivityChart entries={inRange} days={days} />
          {activity.data?.truncated && (
            <p className="mt-3 text-xs text-muted-foreground">
              Showing the most recent {formatNumber(activity.data.entries.length)} events; older
              days in this range may be incomplete.
            </p>
          )}
        </div>
      )}
    </Panel>
  )
}

function StatusBreakdown({ stats }: { stats: Stats }) {
  const total = stats.documents.total
  return (
    <div className="space-y-3">
      <div
        className="flex h-2 gap-[2px] overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`Document status: ${STATUSES.map(
          (status) => `${STATUS_LABELS[status]} ${stats.documents.by_status[status] ?? 0}`,
        ).join(", ")}`}
      >
        {total > 0 &&
          STATUSES.map((status) => {
            const count = stats.documents.by_status[status] ?? 0
            return count > 0 ? (
              <span
                key={status}
                className={cn("h-full", STATUS_TONES[status].dot)}
                style={{ flexGrow: count }}
              />
            ) : null
          })}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {STATUSES.map((status) => (
          <li key={status} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("size-2 rounded-full", STATUS_TONES[status].dot)} aria-hidden />
            {STATUS_LABELS[status]}
            <span className="ml-auto font-medium text-foreground tabular-nums">
              {formatNumber(stats.documents.by_status[status] ?? 0)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RecentDocuments({ workspaceId }: { workspaceId: string }) {
  const params = { page: 1, pageSize: RECENT, sort: "-created_at" as const }
  const documents = useQuery({
    queryKey: queryKeys.documents(workspaceId, params),
    queryFn: () => documentsApi.list(workspaceId, params),
    refetchInterval: (query) =>
      query.state.data?.items.some((document) => isInProgress(document.status))
        ? PROCESSING_POLL_MS
        : false,
  })
  if (documents.isPending) return <ListSkeleton rows={3} label="Loading documents" />
  if (documents.isError) {
    return (
      <ErrorState
        title="Couldn't load documents"
        error={documents.error}
        onRetry={() => documents.refetch()}
      />
    )
  }
  return (
    <ul className="-mx-2 space-y-0.5">
      {documents.data.items.map((document) => (
        <li key={document.id}>
          <Link
            href={`/knowledge/${document.id}`}
            className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <FileTypeIcon filename={document.filename} contentType={document.content_type} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{document.filename}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {formatBytes(document.size_bytes)} · {formatRelative(document.created_at)}
              </span>
            </span>
            <StatusBadge status={document.status} />
          </Link>
        </li>
      ))}
    </ul>
  )
}

function KnowledgePanel({
  stats,
  workspaceId,
  isOwner,
  className,
}: {
  stats: Stats
  workspaceId: string
  isOwner: boolean
  className?: string
}) {
  return (
    <Panel
      title="Knowledge base"
      description="Documents your AI tools answer from."
      action={stats.documents.total > 0 && <ViewAll href="/knowledge" />}
      className={className}
    >
      {stats.documents.total === 0 ? (
        <EmptyState
          icon={Library}
          title="Your knowledge base is empty"
          description={
            isOwner
              ? "Upload PDFs, Word or text files. Once they're indexed, the Assistant and Agent can answer questions about them."
              : "Only workspace owners can upload documents. Ask an owner to add some; they'll appear here."
          }
          action={
            isOwner && (
              <Button asChild size="sm">
                <Link href="/knowledge">
                  <FileUp aria-hidden />
                  Upload documents
                </Link>
              </Button>
            )
          }
          className="py-8"
        />
      ) : (
        <div className="space-y-5">
          <StatusBreakdown stats={stats} />
          <RecentDocuments workspaceId={workspaceId} />
        </div>
      )}
    </Panel>
  )
}

function RecentActivity({ workspaceId, className }: { workspaceId: string; className?: string }) {
  // Same request as the usage chart: the newest entries of the 30-day window.
  const activity = useDashboardActivity(workspaceId)
  return (
    <Panel
      title="Recent activity"
      description="Uploads, questions and agent runs, newest first."
      action={<ViewAll href="/activity" />}
      className={className}
    >
      {activity.isPending && <ListSkeleton rows={4} label="Loading activity" />}
      {activity.isError && (
        <ErrorState
          title="Couldn't load activity"
          error={activity.error}
          onRetry={() => activity.refetch()}
        />
      )}
      {activity.isSuccess && activity.data.entries.length === 0 && (
        <EmptyState
          icon={History}
          title="No activity in the last 30 days"
          description="Every upload, question and agent run is recorded here, so your team can see what changed and when."
          className="py-8"
        />
      )}
      {activity.isSuccess && activity.data.entries.length > 0 && (
        <ActivityList entries={activity.data.entries.slice(0, RECENT_ACTIVITY)} linkDocuments />
      )}
    </Panel>
  )
}

interface QuickAction {
  href: string
  icon: LucideIcon
  title: string
  description: string
}

function QuickActions({ isOwner }: { isOwner: boolean }) {
  const actions: QuickAction[] = [
    isOwner
      ? {
          href: "/knowledge",
          icon: FileUp,
          title: "Upload documents",
          description: "Add PDF, Word, text or Markdown files to the knowledge base.",
        }
      : {
          href: "/knowledge",
          icon: Library,
          title: "Search documents",
          description: "Find passages across everything in the knowledge base.",
        },
    {
      href: "/assistant",
      icon: MessageSquarePlus,
      title: "Ask the Assistant",
      description: "Get a quick answer that cites its sources.",
    },
    {
      href: "/agent",
      icon: Bot,
      title: "Run the Agent",
      description: "Compare documents or answer a multi-part question, with every claim checked.",
    },
  ]
  return (
    <Panel title="Quick actions">
      <ul className="-mx-2 -my-1 space-y-0.5">
        {actions.map(({ href, icon: Icon, title, description }) => (
          <li key={title}>
            <Link
              href={href}
              className="group/action flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-card text-primary shadow-xs">
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{title}</span>
                <span className="block text-xs text-muted-foreground">{description}</span>
              </span>
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover/action:translate-x-0.5"
                aria-hidden
              />
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function RecentConversations({ workspaceId }: { workspaceId: string }) {
  const conversations = useQuery({
    // Own key (not the Assistant's paginated list), under the same prefix so sends refresh it.
    queryKey: [...queryKeys.workspace(workspaceId), "conversations", "recent", RECENT],
    queryFn: () => chatApi.listConversations(workspaceId, 1, RECENT),
  })
  return (
    <Panel
      title="Your recent conversations"
      action={
        conversations.data &&
        conversations.data.items.length > 0 && <ViewAll href="/assistant" label="Open" />
      }
    >
      {conversations.isPending && <ListSkeleton rows={3} label="Loading conversations" />}
      {conversations.isError && (
        <ErrorState
          title="Couldn't load conversations"
          error={conversations.error}
          onRetry={() => conversations.refetch()}
        />
      )}
      {conversations.isSuccess && conversations.data.items.length === 0 && (
        <EmptyState
          icon={MessagesSquare}
          title="No conversations yet"
          description="Questions you ask the Assistant are saved here so you can pick them up later."
          action={
            <Button asChild size="sm" variant="outline">
              <Link href="/assistant">Ask a question</Link>
            </Button>
          }
          className="py-8"
        />
      )}
      {conversations.isSuccess && conversations.data.items.length > 0 && (
        <ul className="-mx-2 -my-1 space-y-0.5">
          {conversations.data.items.map((conversation) => (
            <li key={conversation.id}>
              <Link
                href={`/assistant?c=${conversation.id}`}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <MessagesSquare className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {conversation.title}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatRelative(conversation.updated_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function DashboardSkeleton() {
  return (
    <div role="status" aria-label="Loading dashboard" className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-32 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Skeleton className="h-80 rounded-xl lg:col-span-3" />
        <Skeleton className="h-80 rounded-xl lg:col-span-2" />
      </div>
    </div>
  )
}

/** Agent runs finished in the dashboard's 30-day window, from the activity log. */
function useAgentOutcomes(workspaceId: string) {
  const activity = useDashboardActivity(workspaceId)
  if (!activity.data) return null
  let completed = 0
  let failed = 0
  for (const entry of activity.data.entries) {
    if (entry.action === "agent.run_completed") completed++
    else if (entry.action === "agent.run_failed") failed++
  }
  return { completed, failed }
}

export default function DashboardPage() {
  const { me, workspace } = useWorkspace()
  const isOwner = workspace.role === "owner"
  const [guideHidden, setGuideHidden] = useOnboardingHidden(workspace.id)
  const stats = useQuery({
    queryKey: queryKeys.stats(workspace.id),
    queryFn: () => statsApi.get(workspace.id),
    refetchInterval: (query) => {
      const byStatus = query.state.data?.documents.by_status
      const processing = (byStatus?.UPLOADED ?? 0) + (byStatus?.PROCESSING ?? 0)
      return processing > 0 ? PROCESSING_POLL_MS : false
    },
  })
  const agentOutcomes = useAgentOutcomes(workspace.id)
  const firstName = me.user.full_name.trim().split(/\s+/)[0]

  return (
    <>
      <PageHeader
        title={`Welcome, ${firstName}`}
        documentTitle="Dashboard"
        description={`Your team's knowledge and AI activity in ${workspace.name}, at a glance.`}
        actions={
          <>
            {guideHidden && (
              <Button variant="ghost" onClick={() => setGuideHidden(false)}>
                <Sparkles aria-hidden />
                Getting started guide
              </Button>
            )}
            {isOwner && (
              <Button asChild variant="outline">
                <Link href="/knowledge">
                  <FileUp aria-hidden />
                  Upload documents
                </Link>
              </Button>
            )}
            <Button asChild>
              <Link href="/assistant">
                <MessageSquarePlus aria-hidden />
                Ask the Assistant
              </Link>
            </Button>
          </>
        }
      />

      {stats.isPending && <DashboardSkeleton />}
      {stats.isError && (
        <ErrorState
          title="Couldn't load the dashboard"
          error={stats.error}
          onRetry={() => stats.refetch()}
        />
      )}
      {stats.isSuccess && (
        <div className="space-y-6">
          {!guideHidden && (
            <GettingStarted
              stats={stats.data}
              canUpload={isOwner}
              onHide={() => setGuideHidden(true)}
            />
          )}
          <StatCards stats={stats.data} agentOutcomes={agentOutcomes} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <UsagePanel workspaceId={workspace.id} className="lg:col-span-3" />
            <KnowledgePanel
              stats={stats.data}
              workspaceId={workspace.id}
              isOwner={isOwner}
              className="lg:col-span-2"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <RecentActivity workspaceId={workspace.id} className="lg:col-span-3" />
            <div className="space-y-6 lg:col-span-2">
              <QuickActions isOwner={isOwner} />
              <RecentConversations workspaceId={workspace.id} />
            </div>
          </div>
        </div>
      )}
    </>
  )
}

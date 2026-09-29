import type { ActivityEntry } from "@/lib/api/types"
import { formatDateTime } from "@/lib/format"

const ACTION_LABELS: Record<string, string> = {
  "workspace.created": "created the workspace",
  "member.added": "added a member",
  "document.uploaded": "uploaded",
  "document.processed": "finished processing",
  "document.failed": "failed to process",
  "document.deleted": "deleted",
  "conversation.created": "started a conversation",
  "agent.run_started": "started an agent run",
  "agent.run_completed": "completed an agent run",
  "agent.run_failed": "had an agent run fail",
}

function describe(entry: ActivityEntry): string {
  const label = ACTION_LABELS[entry.action] ?? entry.action.replaceAll(/[._]/g, " ")
  const subject = entry.details?.filename ?? entry.details?.name ?? entry.details?.email
  return typeof subject === "string" ? `${label} ${subject}` : label
}

export function ActivityList({ entries }: { entries: ActivityEntry[] }) {
  return (
    <ul className="divide-y">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="flex flex-col gap-0.5 py-3 sm:flex-row sm:items-baseline sm:gap-4"
        >
          <p className="min-w-0 flex-1 text-sm">
            {/* Worker-side events (e.g. processing finished) have no user. */}
            <span className="font-medium">{entry.user_name ?? "System"}</span> {describe(entry)}
          </p>
          <time dateTime={entry.created_at} className="shrink-0 text-xs text-muted-foreground">
            {formatDateTime(entry.created_at)}
          </time>
        </li>
      ))}
    </ul>
  )
}

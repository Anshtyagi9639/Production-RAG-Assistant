import {
  Bot,
  Building2,
  CheckCircle2,
  CircleAlert,
  FileUp,
  type LucideIcon,
  MessageSquarePlus,
  MessageSquareText,
  Trash2,
  UserPlus,
} from "lucide-react"
import Link from "next/link"

import type { ActivityEntry } from "@/lib/api/types"
import { formatDateTime, formatDayGroup, formatRelative, formatTime } from "@/lib/format"
import { cn } from "@/lib/utils"

type Tone = "neutral" | "accent" | "success" | "danger"

const ACTIONS: Record<string, { label: string; icon: LucideIcon; tone: Tone }> = {
  "workspace.created": { label: "created the workspace", icon: Building2, tone: "accent" },
  "member.added": { label: "added a member", icon: UserPlus, tone: "accent" },
  "document.uploaded": { label: "uploaded", icon: FileUp, tone: "neutral" },
  "document.processed": { label: "finished processing", icon: CheckCircle2, tone: "success" },
  "document.failed": { label: "failed to process", icon: CircleAlert, tone: "danger" },
  "document.deleted": { label: "deleted", icon: Trash2, tone: "neutral" },
  "conversation.created": {
    label: "started a conversation",
    icon: MessageSquarePlus,
    tone: "accent",
  },
  "chat.answered": {
    label: "asked the assistant a question",
    icon: MessageSquareText,
    tone: "neutral",
  },
  "agent.run_started": { label: "started an agent run", icon: Bot, tone: "accent" },
  "agent.run_completed": { label: "completed an agent run", icon: Bot, tone: "success" },
  "agent.run_failed": { label: "had an agent run fail", icon: Bot, tone: "danger" },
}

const TONES: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground",
  accent: "bg-accent text-accent-foreground",
  success: "bg-success/10 text-success",
  danger: "bg-destructive/10 text-destructive",
}

function subjectOf(entry: ActivityEntry): string | null {
  const subject = entry.details?.filename ?? entry.details?.name ?? entry.details?.email
  return typeof subject === "string" ? subject : null
}

/** The document page for a document event, unless the event is the deletion itself. */
function documentHref(entry: ActivityEntry): string | null {
  if (entry.entity_type !== "document" || !entry.entity_id) return null
  return entry.action === "document.deleted" ? null : `/knowledge/${entry.entity_id}`
}

function ActivityRow({
  entry,
  timeStyle,
  linkDocuments,
}: {
  entry: ActivityEntry
  timeStyle: "relative" | "time"
  linkDocuments: boolean
}) {
  const action = ACTIONS[entry.action] ?? {
    label: entry.action.replaceAll(/[._]/g, " "),
    icon: MessageSquareText,
    tone: "neutral" as const,
  }
  const subject = subjectOf(entry)
  const href = linkDocuments ? documentHref(entry) : null
  const Icon = action.icon
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full",
          TONES[action.tone],
        )}
      >
        <Icon className="size-3.5" aria-hidden />
      </span>
      <p className="min-w-0 flex-1 text-sm leading-6">
        {/* Worker-side events (e.g. processing finished) have no user. */}
        <span className="font-medium">{entry.user_name ?? "System"}</span>{" "}
        <span className="text-muted-foreground">{action.label}</span>
        {subject && !href && <span className="font-medium break-all"> {subject}</span>}
        {subject && href && (
          <>
            {" "}
            <Link
              href={href}
              className="font-medium break-all underline-offset-2 hover:text-primary hover:underline focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:outline-none"
            >
              {subject}
            </Link>
          </>
        )}
      </p>
      <time
        dateTime={entry.created_at}
        title={formatDateTime(entry.created_at)}
        className="mt-0.5 shrink-0 text-xs leading-6 text-muted-foreground tabular-nums"
      >
        {timeStyle === "relative" ? formatRelative(entry.created_at) : formatTime(entry.created_at)}
      </time>
    </li>
  )
}

/** Workspace events. `grouped` adds a heading per day and shows clock times;
 * `linkDocuments` links document names to their page. */
export function ActivityList({
  entries,
  grouped = false,
  linkDocuments = false,
}: {
  entries: ActivityEntry[]
  grouped?: boolean
  linkDocuments?: boolean
}) {
  if (!grouped) {
    return (
      <ul className="divide-y divide-border/60">
        {entries.map((entry) => (
          <ActivityRow
            key={entry.id}
            entry={entry}
            timeStyle="relative"
            linkDocuments={linkDocuments}
          />
        ))}
      </ul>
    )
  }
  const groups: { day: string; entries: ActivityEntry[] }[] = []
  for (const entry of entries) {
    const day = formatDayGroup(entry.created_at)
    const last = groups.at(-1)
    if (last?.day === day) last.entries.push(entry)
    else groups.push({ day, entries: [entry] })
  }
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.day} aria-label={group.day}>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground">{group.day}</h3>
          <ul className="divide-y divide-border/60">
            {group.entries.map((entry) => (
              <ActivityRow
                key={entry.id}
                entry={entry}
                timeStyle="time"
                linkDocuments={linkDocuments}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

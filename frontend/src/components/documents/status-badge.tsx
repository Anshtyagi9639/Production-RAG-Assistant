import { CheckCircle2, CircleAlert, Clock, Loader2 } from "lucide-react"

import type { DocumentStatus } from "@/lib/api/types"
import { cn } from "@/lib/utils"

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Queued",
  PROCESSING: "Processing",
  COMPLETED: "Ready",
  FAILED: "Failed",
}

export function isInProgress(status: DocumentStatus): boolean {
  return status === "UPLOADED" || status === "PROCESSING"
}

/** Tone per status: a subtle tint plus an icon, so status never relies on colour alone. */
export const STATUS_TONES: Record<DocumentStatus, { badge: string; dot: string }> = {
  UPLOADED: {
    badge: "border-border bg-muted text-muted-foreground",
    dot: "bg-muted-foreground/40",
  },
  PROCESSING: { badge: "border-info/20 bg-info/8 text-info", dot: "bg-info" },
  COMPLETED: { badge: "border-success/20 bg-success/8 text-success", dot: "bg-success" },
  FAILED: {
    badge: "border-destructive/20 bg-destructive/8 text-destructive",
    dot: "bg-destructive",
  },
}

const ICONS = {
  UPLOADED: Clock,
  PROCESSING: Loader2,
  COMPLETED: CheckCircle2,
  FAILED: CircleAlert,
}

export function StatusBadge({ status, className }: { status: DocumentStatus; className?: string }) {
  const Icon = ICONS[status]
  return (
    <span
      className={cn(
        "inline-flex h-5.5 items-center gap-1 rounded-full border px-2 text-xs font-medium whitespace-nowrap",
        STATUS_TONES[status].badge,
        className,
      )}
    >
      <Icon className={cn("size-3", status === "PROCESSING" && "animate-spin")} aria-hidden />
      {STATUS_LABELS[status]}
    </span>
  )
}

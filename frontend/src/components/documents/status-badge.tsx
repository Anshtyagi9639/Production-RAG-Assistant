import { CheckCircle2, CircleAlert, Clock, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { DocumentStatus } from "@/lib/api/types"

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Queued",
  PROCESSING: "Processing",
  COMPLETED: "Ready",
  FAILED: "Failed",
}

export function isInProgress(status: DocumentStatus): boolean {
  return status === "UPLOADED" || status === "PROCESSING"
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  switch (status) {
    case "UPLOADED":
      return (
        <Badge variant="outline">
          <Clock aria-hidden />
          {STATUS_LABELS.UPLOADED}
        </Badge>
      )
    case "PROCESSING":
      return (
        <Badge variant="secondary" className="bg-accent text-accent-foreground">
          <Loader2 className="animate-spin" aria-hidden />
          {STATUS_LABELS.PROCESSING}
        </Badge>
      )
    case "COMPLETED":
      return (
        <Badge variant="secondary">
          <CheckCircle2 aria-hidden />
          {STATUS_LABELS.COMPLETED}
        </Badge>
      )
    case "FAILED":
      return (
        <Badge variant="destructive">
          <CircleAlert aria-hidden />
          {STATUS_LABELS.FAILED}
        </Badge>
      )
  }
}

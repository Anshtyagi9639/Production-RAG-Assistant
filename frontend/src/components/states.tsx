import { AlertCircle, type LucideIcon, RotateCw } from "lucide-react"

import { BrandMark } from "@/components/brand"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api/client"
import { cn } from "@/lib/utils"

const STATUS_MESSAGES: Record<number, string> = {
  403: "You don't have permission to do that in this workspace.",
  404: "This item no longer exists, or you don't have access to it.",
  409: "That conflicts with something that already exists.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Something went wrong on our side. Please try again.",
  503: "The service is temporarily unavailable. Please try again in a few minutes.",
}

/** A user-facing sentence for any error. API messages are written for users; others aren't. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500 && error.status !== 503) return STATUS_MESSAGES[500]
    return error.message || STATUS_MESSAGES[error.status] || STATUS_MESSAGES[500]
  }
  return "Something went wrong. Please try again."
}

/** The backend request ID, shown so a failure can be found in the server log. */
export function errorReference(error: unknown): string | undefined {
  return error instanceof ApiError ? error.requestId?.slice(0, 12) : undefined
}

function StateIcon({ icon: Icon, tone }: { icon: LucideIcon; tone: "muted" | "error" }) {
  return (
    <span
      className={cn(
        "flex size-10 items-center justify-center rounded-xl border bg-card shadow-xs",
        tone === "error" && "border-destructive/20 bg-destructive/5",
      )}
    >
      <Icon
        className={cn("size-5", tone === "error" ? "text-destructive" : "text-muted-foreground")}
        aria-hidden
      />
    </span>
  )
}

export function ErrorState({
  error,
  onRetry,
  title = "Couldn't load this",
  className,
}: {
  error: unknown
  onRetry?: () => void
  title?: string
  className?: string
}) {
  const reference = errorReference(error)
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center",
        className,
      )}
    >
      <StateIcon icon={AlertCircle} tone="error" />
      <div className="max-w-sm space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
        {reference && (
          <p className="font-mono text-[11px] text-muted-foreground/80">Reference {reference}</p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden />
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center",
        className,
      )}
    >
      <StateIcon icon={icon} tone="muted" />
      <div className="max-w-sm space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  )
}

export function ListSkeleton({ rows = 5, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-2">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-3 rounded-lg border bg-card px-3 py-3">
          <Skeleton className="size-8 rounded-md" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-3 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function FullPageSpinner({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex min-h-svh flex-col items-center justify-center gap-3 text-muted-foreground"
    >
      <BrandMark className="size-9 animate-pulse" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

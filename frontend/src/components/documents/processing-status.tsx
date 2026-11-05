"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, CircleAlert, Clock, Loader2 } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef } from "react"

import { useWorkerRunning } from "@/components/dashboard/system-status"
import { isInProgress } from "@/components/documents/status-badge"
import { documentsApi } from "@/lib/api/endpoints"
import type { DocumentStatus } from "@/lib/api/types"
import { formatElapsed, plural } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const POLL_MS = 2000
const STEPS: { status: DocumentStatus; label: string }[] = [
  { status: "UPLOADED", label: "Queued" },
  { status: "PROCESSING", label: "Extracting and indexing" },
  { status: "COMPLETED", label: "Ready" },
]

/**
 * Follows a just-uploaded document until it is Ready or Failed: a three-step track plus a
 * plain status line. Shares its cache entry with the document page.
 */
export function ProcessingStatus({
  workspaceId,
  documentId,
}: {
  workspaceId: string
  documentId: string
}) {
  const queryClient = useQueryClient()
  const workerRunning = useWorkerRunning()
  const document = useQuery({
    queryKey: queryKeys.document(workspaceId, documentId),
    queryFn: () => documentsApi.get(workspaceId, documentId),
    refetchInterval: (query) =>
      !query.state.data || isInProgress(query.state.data.status) ? POLL_MS : false,
  })
  const status = document.data?.status

  // When it settles, refresh the list, counts and dashboard that show this document.
  const settled = useRef(false)
  useEffect(() => {
    if (!status || isInProgress(status) || settled.current) return
    settled.current = true
    void queryClient.invalidateQueries({ queryKey: queryKeys.workspace(workspaceId) })
  }, [status, queryClient, workspaceId])

  if (!document.data) {
    return <p className="text-xs text-muted-foreground">Uploaded. Checking status…</p>
  }
  const data = document.data
  const current = data.status === "FAILED" ? -1 : STEPS.findIndex((s) => s.status === data.status)

  return (
    <div className="space-y-1.5" aria-live="polite">
      {data.status !== "FAILED" && (
        <ol className="flex items-center gap-1" aria-label="Processing progress">
          {STEPS.map((step, index) => (
            <li
              key={step.status}
              className={cn(
                "h-1.5 flex-1 overflow-hidden rounded-full bg-muted",
                index < current && "bg-success/70",
                index === current && data.status === "COMPLETED" && "bg-success/70",
              )}
              aria-label={`${step.label}: ${index < current || data.status === "COMPLETED" ? "done" : index === current ? "in progress" : "waiting"}`}
            >
              {index === current && data.status !== "COMPLETED" && (
                <span className="block h-full w-1/2 animate-[upload_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
              )}
            </li>
          ))}
        </ol>
      )}
      <p
        className={cn(
          "flex items-center gap-1 text-xs",
          data.status === "COMPLETED" && "text-success",
          data.status === "FAILED" && "text-destructive",
          isInProgress(data.status) && "text-muted-foreground",
        )}
      >
        {data.status === "COMPLETED" && <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />}
        {data.status === "FAILED" && <CircleAlert className="size-3.5 shrink-0" aria-hidden />}
        {data.status === "PROCESSING" && (
          <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
        )}
        {data.status === "UPLOADED" && <Clock className="size-3.5 shrink-0" aria-hidden />}
        <span className="min-w-0">
          {data.status === "COMPLETED" &&
            `Ready in ${data.processed_at ? formatElapsed(data.created_at, data.processed_at) : "—"} · ${plural(data.chunk_count ?? 0, "passage")} indexed`}
          {data.status === "FAILED" && (data.error_message ?? "Processing failed.")}
          {data.status === "PROCESSING" && "Extracting text and indexing passages…"}
          {data.status === "UPLOADED" &&
            (workerRunning === false
              ? "Queued. The processing worker isn't running, so this will wait until it starts."
              : "Queued. Processing starts in a moment…")}
        </span>
        <Link
          href={`/knowledge/${documentId}`}
          className="ml-1 shrink-0 font-medium text-primary underline-offset-2 hover:underline"
        >
          {data.status === "FAILED" ? "Details" : "View"}
        </Link>
      </p>
    </div>
  )
}

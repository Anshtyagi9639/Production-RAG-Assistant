"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, CircleAlert } from "lucide-react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { useWorkspace } from "@/components/app/workspace-context"
import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog"
import { isInProgress, StatusBadge } from "@/components/documents/status-badge"
import { PageHeader } from "@/components/page-header"
import { ErrorState, ListSkeleton } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { documentsApi } from "@/lib/api/endpoints"
import type { Document } from "@/lib/api/types"
import { formatBytes, formatDateTime } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"

const POLL_INTERVAL_MS = 3000

function Details({ document }: { document: Document }) {
  const rows: [string, string][] = [
    ["Type", document.content_type],
    ["Size", formatBytes(document.size_bytes)],
    ["Pages", document.page_count?.toString() ?? "—"],
    ["Indexed passages", document.chunk_count?.toString() ?? "—"],
    ["Uploaded by", document.uploaded_by_name ?? "Former member"],
    ["Uploaded", formatDateTime(document.created_at)],
    ["Processed", document.processed_at ? formatDateTime(document.processed_at) : "—"],
  ]
  return (
    <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="space-y-0.5">
          <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
          <dd className="text-sm break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { workspace } = useWorkspace()
  const document = useQuery({
    queryKey: queryKeys.document(workspace.id, id),
    queryFn: () => documentsApi.get(workspace.id, id),
    refetchInterval: (query) =>
      query.state.data && isInProgress(query.state.data.status) ? POLL_INTERVAL_MS : false,
  })

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2">
        <Link href="/knowledge">
          <ArrowLeft aria-hidden />
          Knowledge Base
        </Link>
      </Button>

      {document.isPending && <ListSkeleton rows={3} label="Loading document" />}
      {document.isError && (
        <ErrorState
          title="Couldn't load this document"
          error={document.error}
          onRetry={() => document.refetch()}
        />
      )}
      {document.isSuccess && (
        <>
          <PageHeader
            title={document.data.filename}
            badge={<StatusBadge status={document.data.status} />}
            actions={
              workspace.role === "owner" && (
                <DeleteDocumentDialog
                  workspaceId={workspace.id}
                  document={document.data}
                  showLabel
                  onDeleted={() => router.push("/knowledge")}
                />
              )
            }
          />
          {document.data.status === "FAILED" && (
            <Alert variant="destructive" className="mb-4">
              <CircleAlert aria-hidden />
              <AlertTitle>Processing failed</AlertTitle>
              <AlertDescription>
                {document.data.error_message ?? "No reason was recorded."}
              </AlertDescription>
            </Alert>
          )}
          {isInProgress(document.data.status) && (
            <p className="mb-4 text-sm text-muted-foreground" aria-live="polite">
              This document is being processed. The status updates automatically.
            </p>
          )}
          <Card>
            <CardContent>
              <Details document={document.data} />
            </CardContent>
          </Card>
        </>
      )}
    </>
  )
}

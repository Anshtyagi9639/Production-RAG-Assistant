"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { FileText } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog"
import { FileTypeIcon } from "@/components/documents/file-type-icon"
import { isInProgress, STATUS_LABELS, StatusBadge } from "@/components/documents/status-badge"
import { Pagination } from "@/components/pagination"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { documentsApi, statsApi } from "@/lib/api/endpoints"
import type { DocumentSort, DocumentStatus } from "@/lib/api/types"
import {
  FILE_KIND_LABELS,
  fileKind,
  formatBytes,
  formatDateTime,
  formatNumber,
  formatRelative,
  plural,
} from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 20
const POLL_INTERVAL_MS = 3000
const SORT_OPTIONS: { value: DocumentSort; label: string }[] = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "filename", label: "Name A–Z" },
  { value: "-filename", label: "Name Z–A" },
]
const STATUS_FILTERS: (DocumentStatus | undefined)[] = [
  undefined,
  "COMPLETED",
  "PROCESSING",
  "UPLOADED",
  "FAILED",
]

function StatusFilter({
  workspaceId,
  value,
  onChange,
}: {
  workspaceId: string
  value: DocumentStatus | undefined
  onChange: (status: DocumentStatus | undefined) => void
}) {
  // Counts come from the stats endpoint (already cached by the dashboard).
  const stats = useQuery({
    queryKey: queryKeys.stats(workspaceId),
    queryFn: () => statsApi.get(workspaceId),
  })
  const count = (status: DocumentStatus | undefined) =>
    stats.data
      ? status
        ? (stats.data.documents.by_status[status] ?? 0)
        : stats.data.documents.total
      : undefined

  return (
    <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
      {STATUS_FILTERS.map((status) => {
        const selected = value === status
        const n = count(status)
        return (
          <button
            key={status ?? "all"}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(status)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-sm font-medium text-muted-foreground transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
              selected &&
                "border-foreground/15 bg-foreground text-background hover:bg-foreground/90 hover:text-background",
            )}
          >
            {status ? STATUS_LABELS[status] : "All"}
            {n !== undefined && (
              <span
                className={cn(
                  "text-xs tabular-nums",
                  selected ? "text-background/70" : "text-muted-foreground/80",
                )}
              >
                {formatNumber(n)}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function DocumentsTable({
  workspaceId,
  canDelete,
}: {
  workspaceId: string
  canDelete: boolean
}) {
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<DocumentSort>("-created_at")
  const [status, setStatus] = useState<DocumentStatus | undefined>()
  const params = { page, pageSize: PAGE_SIZE, sort, status }

  const documents = useQuery({
    queryKey: queryKeys.documents(workspaceId, params),
    queryFn: () => documentsApi.list(workspaceId, params),
    placeholderData: keepPreviousData,
    // Poll while anything on screen is still being processed.
    refetchInterval: (query) =>
      query.state.data?.items.some((document) => isInProgress(document.status))
        ? POLL_INTERVAL_MS
        : false,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <StatusFilter
          workspaceId={workspaceId}
          value={status}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Select
          value={sort}
          onValueChange={(value) => {
            setSort(value as DocumentSort)
            setPage(1)
          }}
        >
          <SelectTrigger aria-label="Sort documents" className="w-full sm:w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {documents.isPending && <ListSkeleton label="Loading documents" />}
      {documents.isError && (
        <ErrorState
          title="Couldn't load documents"
          error={documents.error}
          onRetry={() => documents.refetch()}
        />
      )}
      {documents.isSuccess && documents.data.items.length === 0 && (
        <EmptyState
          icon={FileText}
          title={
            status ? `No ${STATUS_LABELS[status].toLowerCase()} documents` : "No documents yet"
          }
          description={
            status
              ? "Try a different status filter."
              : canDelete
                ? "Upload files above to build this workspace's knowledge base."
                : "A workspace owner can upload documents."
          }
        />
      )}
      {documents.isSuccess && documents.data.items.length > 0 && (
        <>
          <div className="overflow-hidden rounded-xl border bg-card shadow-xs">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="pl-4">Name</TableHead>
                  <TableHead className="hidden sm:table-cell">Status</TableHead>
                  <TableHead className="hidden md:table-cell">Passages</TableHead>
                  <TableHead className="hidden lg:table-cell">Uploaded</TableHead>
                  {canDelete && (
                    <TableHead className="w-12 pr-4">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.data.items.map((document) => (
                  <TableRow key={document.id} className="group/row">
                    <TableCell className="max-w-0 py-3 pl-4 sm:max-w-80">
                      <div className="flex items-center gap-3">
                        <FileTypeIcon
                          filename={document.filename}
                          contentType={document.content_type}
                        />
                        <div className="min-w-0 flex-1">
                          <Link
                            href={`/knowledge/${document.id}`}
                            className="block truncate font-medium outline-none hover:underline focus-visible:underline"
                          >
                            {document.filename}
                          </Link>
                          {document.status === "FAILED" && document.error_message ? (
                            <p
                              className="truncate text-xs text-destructive"
                              title={document.error_message}
                            >
                              {document.error_message}
                            </p>
                          ) : (
                            <p className="truncate text-xs text-muted-foreground">
                              {FILE_KIND_LABELS[fileKind(document.filename, document.content_type)]}{" "}
                              · {formatBytes(document.size_bytes)}
                              {document.page_count
                                ? ` · ${plural(document.page_count, "page")}`
                                : ""}
                            </p>
                          )}
                          <StatusBadge status={document.status} className="mt-1.5 sm:hidden" />
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <StatusBadge status={document.status} />
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                      {document.chunk_count ?? "—"}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <span className="block text-sm" title={formatDateTime(document.created_at)}>
                        {formatRelative(document.created_at)}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {document.uploaded_by_name ?? "Former member"}
                      </span>
                    </TableCell>
                    {canDelete && (
                      <TableCell className="pr-4 text-right">
                        <DeleteDocumentDialog workspaceId={workspaceId} document={document} />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} pages={documents.data.pages} onPageChange={setPage} />
        </>
      )}
    </div>
  )
}

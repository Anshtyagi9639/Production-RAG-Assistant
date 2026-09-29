"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { FileText } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog"
import { isInProgress, STATUS_LABELS, StatusBadge } from "@/components/documents/status-badge"
import { Pagination } from "@/components/pagination"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Label } from "@/components/ui/label"
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
import { documentsApi } from "@/lib/api/endpoints"
import type { DocumentSort, DocumentStatus } from "@/lib/api/types"
import { formatBytes, formatDateTime } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"

const PAGE_SIZE = 20
const POLL_INTERVAL_MS = 3000
const SORT_OPTIONS: { value: DocumentSort; label: string }[] = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "filename", label: "Name A–Z" },
  { value: "-filename", label: "Name Z–A" },
]
const STATUS_OPTIONS: DocumentStatus[] = ["UPLOADED", "PROCESSING", "COMPLETED", "FAILED"]

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
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="status-filter">Status</Label>
          <Select
            value={status ?? "all"}
            onValueChange={(value) => {
              setStatus(value === "all" ? undefined : (value as DocumentStatus))
              setPage(1)
            }}
          >
            <SelectTrigger id="status-filter" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {STATUS_LABELS[option]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sort">Sort</Label>
          <Select
            value={sort}
            onValueChange={(value) => {
              setSort(value as DocumentSort)
              setPage(1)
            }}
          >
            <SelectTrigger id="sort" className="w-40">
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
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">Size</TableHead>
                  <TableHead className="hidden md:table-cell">Pages</TableHead>
                  <TableHead className="hidden lg:table-cell">Uploaded</TableHead>
                  {canDelete && (
                    <TableHead>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.data.items.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell className="max-w-72">
                      <Link
                        href={`/knowledge/${document.id}`}
                        className="block truncate font-medium hover:underline"
                      >
                        {document.filename}
                      </Link>
                      {document.status === "FAILED" && document.error_message && (
                        <p
                          className="truncate text-xs text-destructive"
                          title={document.error_message}
                        >
                          {document.error_message}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={document.status} />
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                      {formatBytes(document.size_bytes)}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                      {document.page_count ?? "—"}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground lg:table-cell">
                      {formatDateTime(document.created_at)}
                    </TableCell>
                    {canDelete && (
                      <TableCell className="text-right">
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

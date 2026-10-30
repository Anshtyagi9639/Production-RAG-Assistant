"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import { ArrowLeft, Check, CircleAlert, Loader2, Search, SearchX } from "lucide-react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useState } from "react"

import { useBreadcrumb } from "@/components/app/breadcrumb"
import { useWorkspace } from "@/components/app/workspace-context"
import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog"
import { FileTypeIcon } from "@/components/documents/file-type-icon"
import { isInProgress, StatusBadge } from "@/components/documents/status-badge"
import { PageHeader } from "@/components/page-header"
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { documentsApi, searchApi } from "@/lib/api/endpoints"
import type { Document } from "@/lib/api/types"
import {
  cleanSnippet,
  FILE_KIND_LABELS,
  fileKind,
  formatBytes,
  formatDateTime,
  formatLocation,
  formatRelative,
  plural,
} from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const POLL_INTERVAL_MS = 3000

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border bg-card shadow-xs" aria-label={title}>
      <h2 className="border-b px-5 py-3 text-sm font-semibold">{title}</h2>
      <div className="p-5">{children}</div>
    </section>
  )
}

function Details({ document }: { document: Document }) {
  const rows: [string, string][] = [
    ["Type", FILE_KIND_LABELS[fileKind(document.filename, document.content_type)]],
    ["Size", formatBytes(document.size_bytes)],
    ["Pages", document.page_count?.toString() ?? "—"],
    ["Indexed passages", document.chunk_count?.toString() ?? "—"],
    ["Uploaded by", document.uploaded_by_name ?? "Former member"],
    ["Uploaded", formatDateTime(document.created_at)],
    ["Processed", document.processed_at ? formatDateTime(document.processed_at) : "—"],
  ]
  return (
    <dl className="divide-y divide-border/60">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="flex items-baseline justify-between gap-4 py-2 first:pt-0 last:pb-0"
        >
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="text-right text-sm font-medium break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

type StepState = "done" | "active" | "failed" | "waiting"

/** What the worker did with the file, from the document's status and timestamps. */
function Pipeline({ document }: { document: Document }) {
  const { status } = document
  const indexed: StepState =
    status === "COMPLETED"
      ? "done"
      : status === "FAILED"
        ? "failed"
        : status === "PROCESSING"
          ? "active"
          : "waiting"
  const steps: { title: string; detail: string; state: StepState }[] = [
    { title: "Uploaded", detail: formatDateTime(document.created_at), state: "done" },
    {
      title: "Extracted and split into passages",
      detail:
        status === "COMPLETED"
          ? `${plural(document.chunk_count ?? 0, "passage")}${document.page_count ? ` from ${plural(document.page_count, "page")}` : ""}`
          : status === "FAILED"
            ? "Stopped"
            : "In progress",
      state: indexed,
    },
    {
      title: "Indexed for search and answers",
      detail: document.processed_at
        ? formatDateTime(document.processed_at)
        : status === "FAILED"
          ? "Not indexed"
          : "Waiting",
      state: indexed,
    },
  ]
  return (
    <ol className="space-y-0">
      {steps.map((step, position) => (
        <li key={step.title} className="relative flex gap-3 pb-5 last:pb-0">
          {position < steps.length - 1 && (
            <span className="absolute top-6 bottom-0 left-[11px] w-px bg-border" aria-hidden />
          )}
          <span
            className={cn(
              "relative flex size-6 shrink-0 items-center justify-center rounded-full border bg-card",
              step.state === "done" && "border-success/30 bg-success/10 text-success",
              step.state === "active" && "border-info/30 bg-info/10 text-info",
              step.state === "failed" && "border-destructive/30 bg-destructive/10 text-destructive",
            )}
          >
            {step.state === "done" && <Check className="size-3.5" aria-label="Done" />}
            {step.state === "active" && (
              <Loader2 className="size-3.5 animate-spin" aria-label="In progress" />
            )}
            {step.state === "failed" && <CircleAlert className="size-3.5" aria-label="Failed" />}
            {step.state === "waiting" && (
              <span className="size-1.5 rounded-full bg-muted-foreground/40" aria-label="Waiting" />
            )}
          </span>
          <div className="min-w-0 pt-0.5">
            <p className="text-sm font-medium">{step.title}</p>
            <p className="text-xs text-muted-foreground">{step.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

/** Semantic search restricted to this document (the search API's document filter). */
function SearchInDocument({ workspaceId, document }: { workspaceId: string; document: Document }) {
  const [query, setQuery] = useState("")
  const search = useMutation({
    mutationFn: (text: string) =>
      searchApi.search(workspaceId, { query: text, document_ids: [document.id], top_k: 5 }),
  })
  if (document.status !== "COMPLETED") {
    return (
      <p className="text-sm text-muted-foreground">
        Passages become searchable once processing finishes.
      </p>
    )
  }
  return (
    <div className="space-y-4">
      <form
        role="search"
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim()) search.mutate(query.trim())
        }}
      >
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            aria-label={`Search in ${document.filename}`}
            placeholder="Find passages in this document…"
            value={query}
            maxLength={1000}
            className="pl-9"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button type="submit" variant="outline" disabled={search.isPending || !query.trim()}>
          {search.isPending && <Loader2 className="animate-spin" aria-hidden />}
          Search
        </Button>
      </form>
      <div aria-live="polite">
        {search.isPending && <ListSkeleton rows={2} label="Searching" />}
        {search.isError && (
          <ErrorState
            title="Search failed"
            error={search.error}
            onRetry={() => search.mutate(search.variables)}
          />
        )}
        {search.isSuccess && search.data.results.length === 0 && (
          <EmptyState
            icon={SearchX}
            title="No relevant passages"
            description="Nothing in this document matched closely enough. Try other wording."
            className="py-6"
          />
        )}
        {search.isSuccess && search.data.results.length > 0 && (
          <ol className="space-y-2.5">
            {search.data.results.map((result) => (
              <li key={result.chunk_index} className="rounded-lg border bg-muted/30 p-3.5">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  {formatLocation(result.page, result.chunk_index)}
                </p>
                <p className="text-sm leading-relaxed">{cleanSnippet(result.snippet)}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
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
  useBreadcrumb(document.data?.filename)

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-2 text-muted-foreground">
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
          <div className="mb-6 flex items-start gap-4 sm:mb-8">
            <FileTypeIcon
              filename={document.data.filename}
              contentType={document.data.content_type}
              className="size-12 rounded-xl [&_svg]:size-6"
            />
            <div className="min-w-0 flex-1">
              <PageHeader
                className="mb-0 sm:mb-0"
                title={document.data.filename}
                badge={<StatusBadge status={document.data.status} />}
                description={`${FILE_KIND_LABELS[fileKind(document.data.filename, document.data.content_type)]} · ${formatBytes(document.data.size_bytes)} · uploaded ${formatRelative(document.data.created_at)} by ${document.data.uploaded_by_name ?? "a former member"}`}
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
            </div>
          </div>

          {document.data.status === "FAILED" && (
            <Alert variant="destructive" className="mb-6">
              <CircleAlert aria-hidden />
              <AlertTitle>Processing failed</AlertTitle>
              <AlertDescription>
                {document.data.error_message ?? "No reason was recorded."}
              </AlertDescription>
            </Alert>
          )}
          {isInProgress(document.data.status) && (
            <Alert className="mb-6 border-info/30 bg-info/5">
              <Loader2 className="animate-spin text-info" aria-hidden />
              <AlertTitle>Processing</AlertTitle>
              <AlertDescription aria-live="polite">
                The document is being extracted and indexed. This page updates automatically.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Section title="Search this document">
                <SearchInDocument workspaceId={workspace.id} document={document.data} />
              </Section>
              <Section title="Processing">
                <Pipeline document={document.data} />
              </Section>
            </div>
            <Section title="Details">
              <Details document={document.data} />
            </Section>
          </div>
        </>
      )}
    </>
  )
}

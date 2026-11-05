"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"

import { Pagination } from "@/components/pagination"
import { ErrorState, ListSkeleton } from "@/components/states"
import { documentsApi } from "@/lib/api/endpoints"
import { formatLocation, formatNumber, plural } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 8

/**
 * The document's indexed passages: the exact text search and the Assistant cite. Opened from
 * a citation (`?passage=n`), it starts on the page holding passage n and highlights it.
 */
export function Passages({
  workspaceId,
  documentId,
  focus,
}: {
  workspaceId: string
  documentId: string
  /** chunk_index to highlight and scroll to, from the URL. */
  focus: number | null
}) {
  const [page, setPage] = useState(focus === null ? 1 : Math.floor(focus / PAGE_SIZE) + 1)
  const passages = useQuery({
    queryKey: queryKeys.passages(workspaceId, documentId, page),
    queryFn: () => documentsApi.passages(workspaceId, documentId, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })
  const focusRef = useRef<HTMLLIElement>(null)
  const focusShown = passages.data?.items.some((item) => item.chunk_index === focus) ?? false
  useEffect(() => {
    if (focusShown) focusRef.current?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [focusShown])

  if (passages.isPending) return <ListSkeleton rows={3} label="Loading passages" />
  if (passages.isError) {
    return (
      <ErrorState
        title="Couldn't load the passages"
        error={passages.error}
        onRetry={() => passages.refetch()}
      />
    )
  }
  return (
    <div>
      <p className="mb-3 text-xs text-muted-foreground">
        {plural(passages.data.total, "passage")}, in reading order. This is the text search and the
        Assistant use.
      </p>
      <ol className="space-y-2.5" aria-busy={passages.isFetching}>
        {passages.data.items.map((passage) => {
          const focused = passage.chunk_index === focus
          return (
            <li
              key={passage.chunk_index}
              id={`passage-${passage.chunk_index}`}
              ref={focused ? focusRef : undefined}
              aria-current={focused ? "true" : undefined}
              className={cn(
                "scroll-mt-20 rounded-lg border p-3.5 transition-colors",
                focused ? "border-primary/50 bg-accent/60 ring-3 ring-ring/15" : "bg-muted/30",
              )}
            >
              <p className="mb-1.5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className={cn("font-medium", focused && "text-accent-foreground")}>
                  {formatLocation(passage.page, passage.chunk_index)}
                  {focused && " · cited"}
                </span>
                <span className="tabular-nums">{formatNumber(passage.token_count)} tokens</span>
              </p>
              <p className="text-sm leading-relaxed whitespace-pre-line">{passage.text}</p>
            </li>
          )
        })}
      </ol>
      <Pagination page={page} pages={passages.data.pages} onPageChange={setPage} />
    </div>
  )
}
